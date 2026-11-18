# Copyright 2022-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC Connection Pooling and Lifecycle"""

import random

from twisted.internet.defer import inlineCallbacks
from twisted.internet.endpoints import connectProtocol, TCP6ClientEndpoint


class ConnectionPool:
    def __init__(self, reactor, service):
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

    def is_staged(self, eventloop):
        return eventloop in self.try_connections

    def get_staged_connection(self, eventloop):
        return self.try_connections.get(eventloop)

    def get_staged_connections(self):
        return self.try_connections

    def stage_connection(self, eventloop, connection):
        self.try_connections[eventloop] = connection

    def get_connection(self, eventloop):
        return random.choice(self.connections[eventloop])

    def get_random_connection(self):
        return random.choice(self.get_all_connections())

    def get_all_connections(self):
        return [
            conn
            for conn_list in self.connections.values()
            for conn in conn_list
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

    def add_connection(self, eventloop, connection):
        if self.is_staged(eventloop):
            del self.try_connections[eventloop]
        self.connections.setdefault(eventloop, []).append(connection)

    def remove_connection(self, eventloop, connection):
        if self.is_staged(eventloop):
            if self.try_connections[eventloop] is connection:
                del self.try_connections[eventloop]
        if connection in self.connections.get(eventloop, []):
            self.connections[eventloop].remove(connection)
            if len(self.connections[eventloop]) == 0:
                del self.connections[eventloop]
