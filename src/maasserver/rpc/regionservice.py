# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC implementation for regions."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "RegionService",
    "RegionAdvertisingService",
]

from collections import defaultdict
from contextlib import closing
import random
from socket import AF_INET
from textwrap import dedent
import threading

from crochet import reactor
from django.db import connection
from maasserver import (
    eventloop,
    locks,
    )
from maasserver.bootresources import get_simplestream_endpoint
from maasserver.rpc import (
    configuration,
    events,
    leases,
    nodes,
    )
from maasserver.rpc.monitors import handle_monitor_expired
from maasserver.rpc.nodegroupinterface import (
    get_cluster_interfaces_as_dicts,
    update_foreign_dhcp_ip,
    )
from maasserver.rpc.nodes import (
    create_node,
    request_node_info_by_mac_address,
    )
from maasserver.utils import synchronised
from maasserver.utils.async import transactional
from netaddr import IPAddress
from provisioningserver.rpc import (
    cluster,
    common,
    exceptions,
    region,
    )
from provisioningserver.rpc.common import RPCProtocol
from provisioningserver.rpc.interfaces import IConnection
from provisioningserver.utils.network import get_all_interface_addresses
from provisioningserver.utils.twisted import (
    asynchronous,
    callOut,
    deferWithTimeout,
    synchronous,
    )
from twisted.application import service
from twisted.application.internet import TimerService
from twisted.internet import defer
from twisted.internet.defer import (
    CancelledError,
    inlineCallbacks,
    )
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.protocol import Factory
from twisted.internet.threads import deferToThread
from twisted.protocols import amp
from twisted.python import log
from zope.interface import implementer


class Region(RPCProtocol):
    """The RPC protocol supported by a region controller.

    This can be used on the client or server end of a connection; once a
    connection is established, AMP is symmetric.
    """

    @region.Identify.responder
    def identify(self):
        """identify()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.Identify`.
        """
        return {b"ident": eventloop.loop.name}

    @region.ReportBootImages.responder
    def report_boot_images(self, uuid, images):
        """report_boot_images(uuid, images)

        Implementation of
        :py:class:`~provisioningserver.rpc.region.ReportBootImages`.
        """
        return {}

    @region.UpdateLeases.responder
    def update_leases(self, uuid, mappings):
        """update_leases(uuid, mappings)

        Implementation of
        :py:class`~provisioningserver.rpc.region.UpdateLeases`.
        """
        return deferToThread(leases.update_leases, uuid, mappings)

    @amp.StartTLS.responder
    def get_tls_parameters(self):
        """get_tls_parameters()

        Implementation of :py:class:`~twisted.protocols.amp.StartTLS`.
        """
        try:
            from provisioningserver.rpc.testing import tls
        except ImportError:
            # This is not a development/test environment.
            # XXX: Return production TLS parameters.
            return {}
        else:
            return tls.get_tls_parameters_for_region()

    @region.GetBootSources.responder
    def get_boot_sources(self, uuid):
        """get_boot_sources()

        Deprecated: get_boot_sources_v2() should be used instead.

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetBootSources`.
        """
        return {b"sources": [get_simplestream_endpoint()]}

    @region.GetBootSourcesV2.responder
    def get_boot_sources_v2(self, uuid):
        """get_boot_sources_v2()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetBootSources`.
        """
        return {b"sources": [get_simplestream_endpoint()]}

    @region.GetArchiveMirrors.responder
    def get_archive_mirrors(self):
        """get_archive_mirrors()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetArchiveMirrors`.
        """
        d = deferToThread(configuration.get_archive_mirrors)
        return d

    @region.GetProxies.responder
    def get_proxies(self):
        """get_proxies()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetProxies`.
        """
        d = deferToThread(configuration.get_proxies)
        return d

    @region.MarkNodeFailed.responder
    def mark_node_failed(self, system_id, error_description):
        """mark_node_failed()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.MarkNodeFailed`.
        """
        d = deferToThread(
            nodes.mark_node_failed, system_id, error_description)
        d.addCallback(lambda args: {})
        return d

    @region.ListNodePowerParameters.responder
    def list_node_power_parameters(self, uuid):
        """list_node_power_parameters()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.ListNodePowerParameters`.
        """
        d = deferToThread(
            nodes.list_cluster_nodes_power_parameters, uuid)
        d.addCallback(lambda nodes: {b"nodes": nodes})
        return d

    @region.UpdateNodePowerState.responder
    def update_node_power_state(self, system_id, power_state):
        """update_node_power_state()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.UpdateNodePowerState`.
        """
        d = deferToThread(
            nodes.update_node_power_state, system_id, power_state)
        d.addCallback(lambda args: {})
        return d

    @region.RegisterEventType.responder
    def register_event_type(self, name, description, level):
        """register_event_type()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.RegisterEventType`.
        """
        d = deferToThread(
            events.register_event_type, name, description, level)
        d.addCallback(lambda args: {})
        return d

    @region.SendEvent.responder
    def send_event(self, system_id, type_name, description):
        """send_event()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.SendEvent`.
        """
        d = deferToThread(
            events.send_event, system_id, type_name, description)
        d.addCallback(lambda args: {})
        return d

    @region.SendEventMACAddress.responder
    def send_event_mac_address(self, mac_address, type_name, description):
        """send_event_mac_address()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.SendEventMACAddress`.
        """
        d = deferToThread(
            events.send_event_mac_address, mac_address, type_name, description)
        d.addCallback(lambda args: {})
        return d

    @region.ReportForeignDHCPServer.responder
    def report_foreign_dhcp_server(self, cluster_uuid, interface_name,
                                   foreign_dhcp_ip):
        """report_foreign_dhcp_server()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.SendEvent`.
        """
        d = deferToThread(
            update_foreign_dhcp_ip, cluster_uuid, interface_name,
            foreign_dhcp_ip)
        d.addCallback(lambda _: {})
        return d

    @region.GetClusterInterfaces.responder
    def get_cluster_interfaces(self, cluster_uuid):
        """get_cluster_interfaces()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetClusterInterfaces`.
        """
        d = deferToThread(
            get_cluster_interfaces_as_dicts, cluster_uuid)
        d.addCallback(lambda interfaces: {b'interfaces': interfaces})
        return d

    @region.MonitorExpired.responder
    def timer_expired(self, id, context):
        """timer_expired()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.MonitorExpired`.
        """
        d = deferToThread(
            handle_monitor_expired, id, context)
        d.addCallback(lambda _: {})
        return d

    @region.CreateNode.responder
    def create_node(self, cluster_uuid, architecture, power_type,
                    power_parameters, mac_addresses):
        """create_node()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.CreateNode`.
        """
        d = deferToThread(
            create_node, cluster_uuid, architecture, power_type,
            power_parameters, mac_addresses)
        d.addCallback(lambda node: {'system_id': node.system_id})
        return d

    @region.RequestNodeInfoByMACAddress.responder
    def request_node_info_by_mac_address(self, mac_address):
        """request_node_info_by_mac_address()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.RequestNodeInfoByMACAddress`.
        """
        d = deferToThread(
            request_node_info_by_mac_address, mac_address)

        def get_node_info(data):
            node, purpose = data
            return {
                'system_id': node.system_id,
                'hostname': node.hostname,
                'status': node.status,
                'boot_type': node.boot_type,
                'osystem': node.osystem,
                'distro_series': node.distro_series,
                'architecture': node.architecture,
                'purpose': purpose,
            }
        d.addCallback(get_node_info)
        return d


@implementer(IConnection)
class RegionServer(Region):
    """The RPC protocol supported by a region controller, server version.

    This works hand-in-hand with ``RegionService``, maintaining the
    latter's ``connections`` set.

    :ivar factory: Reference to the factory that made this, set by the
        factory. The factory must also have a reference back to the
        service that created it.

    :ivar ident: The identity (e.g. UUID) of the remote cluster.
    """

    factory = None
    ident = None

    def connectionMade(self):
        super(RegionServer, self).connectionMade()
        if self.factory.service.running:
            d = self.callRemote(cluster.Identify)

            def cb_identify(response):
                self.ident = response.get("ident")
                self.factory.service._addConnectionFor(self.ident, self)

            def eb_identify(failure):
                log.err(failure)
                return self.transport.loseConnection()

            d.addCallbacks(cb_identify, eb_identify)
        else:
            self.transport.loseConnection()

    def connectionLost(self, reason):
        self.factory.service._removeConnectionFor(self.ident, self)
        super(RegionServer, self).connectionLost(reason)


class RegionService(service.Service, object):
    """A region controller RPC service.

    This is a service - in the Twisted sense - that exposes the
    ``Region`` protocol on a port.

    :ivar endpoints: The endpoints on which to listen.
    :ivar ports: The opened :py:class:`IListeningPort`s.
    :ivar connections: Maps :class:`Region` connections to clusters.
    :ivar waiters: Maps cluster idents to callers waiting for a connection.
    :ivar starting: Either `None`, or a :class:`Deferred` that fires when
        attempts have been made to open all endpoints. Some or all of them may
        not have been opened successfully.
    """

    connections = None
    starting = None

    def __init__(self):
        super(RegionService, self).__init__()
        self.endpoints = [TCP4ServerEndpoint(reactor, 0)]
        self.connections = defaultdict(set)
        self.waiters = defaultdict(set)
        self.factory = Factory.forProtocol(RegionServer)
        self.factory.service = self
        self.ports = []

    def _getConnectionFor(self, ident, timeout):
        """Wait up to `timeout` seconds for a connection for `ident`.

        Returns a `Deferred` which will fire with the connection, or fail with
        `CancelledError`.

        The public interface to this method is `getClientFor`.
        """
        conns = list(self.connections[ident])
        if len(conns) == 0:
            waiters = self.waiters[ident]
            d = deferWithTimeout(timeout)
            d.addBoth(callOut(waiters.discard, d))
            waiters.add(d)
            return d
        else:
            connection = random.choice(conns)
            return defer.succeed(connection)

    def _addConnectionFor(self, ident, connection):
        """Adds `connection` to the set of connections for `ident`.

        Notifies all waiters of this new connection.
        """
        self.connections[ident].add(connection)
        for waiter in self.waiters[ident].copy():
            waiter.callback(connection)

    def _removeConnectionFor(self, ident, connection):
        """Removes `connection` from the set of connections for `ident`."""
        self.connections[ident].discard(connection)

    def _savePorts(self, results):
        """Save the opened ports to ``self.ports``.

        Expects `results` to be an iterable of ``(success, result)`` tuples,
        just as is passed into a :py:class:`~defer.DeferredList` callback.
        """
        for success, result in results:
            if success:
                self.ports.append(result)
            elif result.check(defer.CancelledError):
                pass  # Ignore.
            else:
                log.err(result)

    @asynchronous
    def startService(self):
        """Start listening on an ephemeral port."""
        super(RegionService, self).startService()
        self.starting = defer.DeferredList(
            endpoint.listen(self.factory)
            for endpoint in self.endpoints)
        self.starting.addCallback(self._savePorts)
        self.starting.addErrback(log.err)
        # Twisted's service framework does not track start-up progress, i.e.
        # it does not check for Deferreds returned by startService(). Here we
        # return a Deferred anyway so that direct callers (esp. those from
        # tests) can easily wait for start-up.
        return self.starting

    @asynchronous
    @inlineCallbacks
    def stopService(self):
        """Stop listening."""
        self.starting.cancel()
        for port in list(self.ports):
            self.ports.remove(port)
            yield port.stopListening()
        for waiters in list(self.waiters.viewvalues()):
            for waiter in waiters.copy():
                waiter.cancel()
        for conns in list(self.connections.viewvalues()):
            for conn in conns.copy():
                try:
                    yield conn.transport.loseConnection()
                except:
                    log.err()
        yield super(RegionService, self).stopService()

    @asynchronous
    def getPort(self):
        """Return the TCP port number on which this service is listening.

        This currently only considers ports (in the Twisted sense) for
        ``AF_INET`` sockets, i.e. IPv4 sockets.

        Returns `None` if the port has not yet been opened.
        """
        try:
            # Look for the first AF_INET port.
            port = next(
                port for port in self.ports
                if port.addressFamily == AF_INET)
        except StopIteration:
            # There's no AF_INET (IPv4) port. As far as this method goes, this
            # means there's no connection.
            return None

        try:
            socket = port.socket
        except AttributeError:
            # When self._port.socket is not set it means there's no
            # connection.
            return None

        host, port = socket.getsockname()
        return port

    @asynchronous
    def getClientFor(self, uuid, timeout=30):
        """Return a :class:`common.Client` for the specified cluster.

        If more than one connection exists to that cluster - implying
        that there are multiple cluster controllers for the particular
        cluster, for HA - one of them will be returned at random.

        :param uuid: The UUID - as a string - of the cluster that a
            connection is wanted for.
        :param timeout: The number of seconds to wait for a connection
            to become available.
        :raises exceptions.NoConnectionsAvailable: When no connection to the
            given cluster is available.
        """
        d = self._getConnectionFor(uuid, timeout)

        def cancelled(failure):
            failure.trap(CancelledError)
            raise exceptions.NoConnectionsAvailable(
                "Unable to connect to cluster %s; no connections available." %
                uuid)

        return d.addCallbacks(common.Client, cancelled)

    @asynchronous
    def getAllClients(self):
        """Return a list of all connected :class:`common.Client`s."""
        return [
            common.Client(conn)
            for conns in self.connections.itervalues()
            for conn in conns
        ]


class RegionAdvertisingService(TimerService, object):
    """Advertise the local event-loop to all other event-loops.

    This implementation uses an unlogged table in PostgreSQL.

    :cvar lock: A lock to help coordinate - and prevent - concurrent
        database access from this service across the whole interpreter.

    :ivar starting: Either `None`, or a :class:`Deferred` that fires
        with the service has successfully started. It does *not*
        indicate that the first update has been done.

    """

    # Django defaults to read committed isolation, but this is not
    # enough for `update()`. Writing a decent wrapper to get it to use
    # serializable isolation for a single transaction is difficult; it
    # looks like Django squashes psycopg2's TransactionRollbackError
    # into IntegrityError, which is overly broad. We're concerned only
    # about concurrent access from this process (other processes will
    # not conflict), so a thread-lock is a sufficient workaround.
    lock = threading.Lock()

    starting = None
    stopping = None

    def __init__(self, interval=60):
        super(RegionAdvertisingService, self).__init__(
            interval, deferToThread, self.update)

    @asynchronous
    def startService(self):
        self.starting = deferToThread(self.prepare)
        self.starting.addCallback(lambda ignore: (
            super(RegionAdvertisingService, self).startService()))

        def ignore_cancellation(failure):
            failure.trap(defer.CancelledError)
        self.starting.addErrback(ignore_cancellation)

        self.starting.addErrback(log.err)
        return self.starting

    @asynchronous
    def stopService(self):
        if self.starting.called:
            # Start-up is complete; remove all records then up-call in
            # the usual way.
            self.stopping = deferToThread(self.remove)
            self.stopping.addCallback(lambda ignore: (
                super(RegionAdvertisingService, self).stopService()))
            return self.stopping
        else:
            # Start-up has not yet finished; cancel it.
            self.starting.cancel()
            return self.starting

    @synchronous
    @synchronised(lock)
    @transactional
    @synchronised(locks.eventloop)
    def prepare(self):
        """Ensure that the ``eventloops`` table exists.

        If not, create it. It is not managed by Django's ORM - though
        this borrows Django's database connection code - because using
        database-specific features like unlogged tables is hard work
        with Django (and South).

        The ``eventloops`` table contains an address and port where each
        event-loop in a region is listening. Each record also contains a
        timestamp so that old records can be erased.
        """
        with closing(connection.cursor()) as cursor:
            self._do_create(cursor)

    @synchronous
    @synchronised(lock)
    @transactional
    def update(self):
        """Repopulate the ``eventloops`` with this process's information.

        It updates all the records in ``eventloops`` related to the
        event-loop running in the same process, and deletes - garbage
        collects - old records related to any event-loop.
        """
        with closing(connection.cursor()) as cursor:
            self._do_delete(cursor)
            self._do_insert(cursor)
            self._do_collect(cursor)

    @synchronous
    @synchronised(lock)
    @transactional
    def dump(self):
        """Returns a list of ``(name, addr, port)`` tuples.

        Each tuple corresponds to somewhere an event-loop is listening
        within the whole region. The `name` is the event-loop name.
        """
        with closing(connection.cursor()) as cursor:
            self._do_select(cursor)
            return list(cursor)

    @synchronous
    @synchronised(lock)
    @transactional
    def remove(self):
        """Removes all records related to this event-loop.

        A subsequent call to `update()` will restore these records,
        hence calling this while this service is started won't be
        terribly efficacious.
        """
        with closing(connection.cursor()) as cursor:
            self._do_delete(cursor)

    def _get_addresses(self):
        """Generate the addresses on which to advertise region availablilty.

        This excludes link-local addresses. We may want to revisit this at a
        later time, but right now it causes issues because multiple network
        interfaces may have the same link-local address.

        This also excludes IPv6 addresses because `RegionServer` only supports
        IPv4. However, this will probably change in the near future.
        """
        try:
            service = eventloop.services.getServiceNamed("rpc")
        except KeyError:
            pass  # No RPC service yet.
        else:
            port = service.getPort().wait(5)
            if port is not None:
                for addr in get_all_interface_addresses():
                    ipaddr = IPAddress(addr)
                    if ipaddr.is_link_local():
                        continue  # Don't advertise link-local addresses.
                    if ipaddr.version != 4:
                        continue  # Only advertise IPv4 for now.
                    yield addr, port

    _create_statement = dedent("""\
      CREATE UNLOGGED TABLE IF NOT EXISTS eventloops (
        name          TEXT NOT NULL,
        address       INET NOT NULL,
        port          INTEGER NOT NULL,
        updated       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        CHECK (port > 0 AND port <= 65535),
        UNIQUE (name, address, port),
        UNIQUE (address, port)
      )
    """)

    _create_lock_statement = dedent("""\
      LOCK TABLE eventloops IN EXCLUSIVE MODE
    """)

    _create_index_check_statement = dedent("""\
      SELECT 1 FROM pg_catalog.pg_indexes
       WHERE schemaname = CURRENT_SCHEMA()
         AND tablename = 'eventloops'
         AND indexname = 'eventloops_name_idx'
    """)

    _create_index_statement = dedent("""\
      CREATE INDEX eventloops_name_idx ON eventloops (name)
    """)

    def _do_create(self, cursor):
        cursor.execute(self._create_statement)
        # Lock the table exclusine to prevent a race when checking for
        # the presence of the eventloops_name_idx index.
        cursor.execute(self._create_lock_statement)
        cursor.execute(self._create_index_check_statement)
        if list(cursor) == []:
            cursor.execute(self._create_index_statement)

    _delete_statement = "DELETE FROM eventloops WHERE name = %s"

    def _do_delete(self, cursor):
        cursor.execute(self._delete_statement, [eventloop.loop.name])

    _insert_statement = "INSERT INTO eventloops (name, address, port) VALUES "
    _insert_values_statement = "(%s, %s, %s)"

    def _do_insert(self, cursor):
        name = eventloop.loop.name
        statement, values = [], []
        for addr, port in self._get_addresses():
            statement.append(self._insert_values_statement)
            values.extend([name, addr, port])
        if len(statement) != 0:
            statement = self._insert_statement + ", ".join(statement)
            cursor.execute(statement, values)

    _collect_statement = dedent("""\
      DELETE FROM eventloops WHERE
        updated < (NOW() - INTERVAL '5 minutes')
    """)

    def _do_collect(self, cursor):
        cursor.execute(self._collect_statement)

    _select_statement = "SELECT name, address, port FROM eventloops"

    def _do_select(self, cursor):
        cursor.execute(self._select_statement)
