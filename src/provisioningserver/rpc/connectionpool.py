# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC Connection Pooling and Lifecycle"""

import random

from twisted.internet.defer import inlineCallbacks
from twisted.internet.endpoints import connectProtocol, TCP6ClientEndpoint

from provisioningserver.prometheus.metrics import PROMETHEUS_METRICS
from provisioningserver.rpc import exceptions


class ConnectionPool:
    def __init__(
        self, reactor, service, max_idle_conns=1, max_conns=1, keepalive=1000
    ):
        # The maximum number of connections to allways allocate per eventloop
        self._max_idle_connections = max_idle_conns
        # The maximum number of connections to allocate while under load per eventloop
        self._max_connections = max_conns
        # The duration in milliseconds to keep scaled up connections alive
        self._keepalive = keepalive

        self.connections = {}
        self.try_connections = {}
        self.clock = reactor
        self._service = service

    def __setitem__(self, key, item):
        self.connections[key] = item

    def __getitem__(self, key):
        return self.connections.get(key)

    def __repr__(self):
        return repr(self.connections)

    def __len__(self):
        return len(self.get_all_connections())

    def __delitem__(self, key):
        del self.connections[key]

    def __contains__(self, item):
        return item in self.connections

    def __cmp__(self, value):
        return self.connections.__cmp__(value)

    def __eq__(self, value):
        return self.connections.__eq__(value)

    def keys(self):
        return self.connections.keys()

    def values(self):
        return self.connections.values()

    def items(self):
        return self.connections.items()

    def _reap_extra_connection(self, eventloop, conn):
        if not conn.in_use:
            self.disconnect(conn)
            return self.remove_connection(eventloop, conn)
        return self.clock.callLater(
            self._keepalive, self._reap_extra_connection, eventloop, conn
        )

    def is_staged(self, eventloop):
        return eventloop in self.try_connections

    def get_staged_connection(self, eventloop):
        return self.try_connections.get(eventloop)

    def get_staged_connections(self):
        return self.try_connections

    def stage_connection(self, eventloop, connection):
        self.try_connections[eventloop] = connection

    @PROMETHEUS_METRICS.failure_counter("maas_rpc_pool_exhaustion_count")
    @inlineCallbacks
    def scale_up_connections(self):
        for ev, ev_conns in self.connections.items():
            # pick first group with room for additional conns
            if len(ev_conns) < self._max_connections:
                # spawn an extra connection
                conn_to_clone = random.choice(list(ev_conns))
                conn = yield self.connect(ev, conn_to_clone.address)
                self.clock.callLater(
                    self._keepalive, self._reap_extra_connection, ev, conn
                )
                return
        raise exceptions.MaxConnectionsOpen()

    def get_connection(self, eventloop):
        return random.choice(self.connections[eventloop])

    def get_random_connection(self):
        return random.choice(self.get_all_connections())

    def get_random_free_connection(self):
        free_conns = self.get_all_free_connections()
        if len(free_conns) == 0:
            # caller should create a new connection
            raise exceptions.AllConnectionsBusy()
        return random.choice(free_conns)

    def get_all_connections(self):
        return [
            conn
            for conn_list in self.connections.values()
            for conn in conn_list
        ]

    def get_all_free_connections(self):
        return [
            conn
            for conn_list in self.connections.values()
            for conn in conn_list
            if not conn.in_use
        ]

    @inlineCallbacks
    def connect(self, eventloop, address):
        from provisioningserver.rpc.clusterservice import ClusterClient

        # Force everything to use AF_INET6 sockets.
        endpoint = TCP6ClientEndpoint(self.clock, *address)
        protocol = ClusterClient(address, eventloop, self._service)
        conn = yield connectProtocol(endpoint, protocol)
        return conn

    def disconnect(self, connection):
        if connection.transport:
            return connection.transport.loseConnection()

    @inlineCallbacks
    def add_connection(self, eventloop, connection):
        if self.is_staged(eventloop):
            del self.try_connections[eventloop]
        if eventloop not in self.connections:
            self.connections[eventloop] = []

        self.connections[eventloop].append(connection)
        # clone connection to equal num idle connections
        idle_limit = self._max_idle_connections - len(
            self.connections[eventloop]
        )
        # if there's room for more and first conn, create more idle conns
        if idle_limit > 0 and len(self.connections[eventloop]) == 1:
            for _ in range(idle_limit):
                # calls to service to add self when handshake is finished
                yield self.connect(connection.eventloop, connection.address)

    def remove_connection(self, eventloop, connection):
        if self.is_staged(eventloop):
            if self.try_connections[eventloop] is connection:
                del self.try_connections[eventloop]
        if connection in self.connections.get(eventloop, []):
            self.connections[eventloop].remove(connection)
            if len(self.connections[eventloop]) == 0:
                del self.connections[eventloop]
