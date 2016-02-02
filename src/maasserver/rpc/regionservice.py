# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC implementation for regions."""

__all__ = [
    "RegionService",
    "RegionAdvertisingService",
]

from collections import defaultdict
from datetime import (
    datetime,
    timedelta,
)
from functools import partial
import os
from os import urandom
import random
from socket import (
    AF_INET,
    gethostname,
)
import threading

from django.db import IntegrityError
from maasserver import (
    eventloop,
    locks,
)
from maasserver.bootresources import get_simplestream_endpoint
from maasserver.enum import NODE_TYPE
from maasserver.models.node import (
    Node,
    RegionController,
)
from maasserver.models.regioncontrollerprocess import RegionControllerProcess
from maasserver.models.regioncontrollerprocessendpoint import (
    RegionControllerProcessEndpoint,
)
from maasserver.models.timestampedmodel import now
from maasserver.rpc import (
    configuration,
    events,
    leases,
    nodes,
    rackcontrollers,
)
from maasserver.rpc.nodes import (
    commission_node,
    create_node,
    request_node_info_by_mac_address,
)
from maasserver.security import get_shared_secret
from maasserver.utils import synchronised
from maasserver.utils.orm import (
    get_one,
    transactional,
    with_connection,
)
from maasserver.utils.threads import deferToDatabase
from netaddr import IPAddress
from provisioningserver.network import get_mac_addresses
from provisioningserver.path import get_path
from provisioningserver.rpc import (
    cluster,
    common,
    exceptions,
    region,
)
from provisioningserver.rpc.common import RPCProtocol
from provisioningserver.rpc.exceptions import NoSuchCluster
from provisioningserver.rpc.interfaces import IConnection
from provisioningserver.security import calculate_digest
from provisioningserver.twisted.protocols import amp
from provisioningserver.utils.events import EventGroup
from provisioningserver.utils.fs import atomic_write
from provisioningserver.utils.network import get_all_interface_addresses
from provisioningserver.utils.twisted import (
    asynchronous,
    callOut,
    deferWithTimeout,
    FOREVER,
    pause,
    synchronous,
)
from twisted.application import service
from twisted.application.internet import TimerService
from twisted.internet import (
    defer,
    reactor,
)
from twisted.internet.defer import (
    CancelledError,
    inlineCallbacks,
    maybeDeferred,
    returnValue,
    succeed,
)
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.error import ConnectionClosed
from twisted.internet.protocol import Factory
from twisted.internet.threads import deferToThread
from twisted.python import log
from zope.interface import implementer


class Region(RPCProtocol):
    """The RPC protocol supported by a region controller.

    This can be used on the client or server end of a connection; once a
    connection is established, AMP is symmetric.
    """

    # XXX ltrager 2016-01-09 remove with NodeGroup
    @region.Identify.responder
    def identify(self):
        """identify()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.Identify`.
        """
        return {"ident": eventloop.loop.name}

    @region.Authenticate.responder
    def authenticate(self, message):
        d = maybeDeferred(get_shared_secret)

        def got_secret(secret):
            salt = urandom(16)  # 16 bytes of high grade noise.
            digest = calculate_digest(secret, message, salt)
            return {"digest": digest, "salt": salt}

        return d.addCallback(got_secret)

    @region.RegisterRackController.responder
    def register_rackcontroller(self, system_id, hostname, mac_addresses, url):
        d = deferToDatabase(
            rackcontrollers.register_rackcontroller, system_id=system_id,
            hostname=hostname, mac_addresses=mac_addresses, url=url)

        def cb_registered(rackcontroller):
            self.factory.service._addConnectionFor(
                rackcontroller.system_id, self)
            if rackcontroller.needs_refresh:
                deferToDatabase(rackcontroller.refresh)
            return {'system_id': rackcontroller.system_id}

        def eb_registered(failure):
            failure.trap(IntegrityError)
            raise exceptions.CannotRegisterRackController(
                "Unable to find existing node or create a new one with "
                "hostname '%s'." % hostname)

        return d.addCallbacks(cb_registered, eb_registered)

    @region.ReportBootImages.responder
    def report_boot_images(self, uuid, images):
        """report_boot_images(uuid, images)

        Implementation of
        :py:class:`~provisioningserver.rpc.region.ReportBootImages`.
        """
        return {}

    @region.UpdateLease.responder
    def update_lease(
            self, cluster_uuid, action, mac, ip_family, ip, timestamp,
            lease_time=None, hostname=None):
        """update_lease(
            cluster_uuid, action, mac, ip_family, ip, timestamp,
            lease_time, hostname)

        Implementation of
        :py:class`~provisioningserver.rpc.region.UpdateLease`.
        """
        dbtasks = eventloop.services.getServiceNamed("database-tasks")
        d = dbtasks.deferTask(
            leases.update_lease, action, mac, ip_family, ip,
            timestamp, lease_time, hostname)

        # Catch all errors except the NoSuchCluster failure. We want that to
        # be sent back to the cluster.
        def err_NoSuchCluster_passThrough(failure):
            if failure.check(NoSuchCluster):
                return failure
            else:
                log.err(failure, "Unhandled failure in updating lease.")
                return {}
        d.addErrback(err_NoSuchCluster_passThrough)

        # Wait for the record to be handled. This will cause the cluster to
        # send one at a time. So they are processed in order no matter which
        # region recieves the message.
        return d

    @amp.StartTLS.responder
    def get_tls_parameters(self):
        """get_tls_parameters()

        Implementation of
        :py:class:`~provisioningserver.twisted.protocols.amp.StartTLS`.
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
        return {"sources": [get_simplestream_endpoint()]}

    @region.GetBootSourcesV2.responder
    def get_boot_sources_v2(self, uuid):
        """get_boot_sources_v2()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetBootSources`.
        """
        return {"sources": [get_simplestream_endpoint()]}

    @region.GetArchiveMirrors.responder
    def get_archive_mirrors(self):
        """get_archive_mirrors()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetArchiveMirrors`.
        """
        d = deferToDatabase(configuration.get_archive_mirrors)
        return d

    @region.GetProxies.responder
    def get_proxies(self):
        """get_proxies()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetProxies`.
        """
        d = deferToDatabase(configuration.get_proxies)
        return d

    @region.MarkNodeFailed.responder
    def mark_node_failed(self, system_id, error_description):
        """mark_node_failed()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.MarkNodeFailed`.
        """
        d = deferToDatabase(
            nodes.mark_node_failed, system_id, error_description)
        d.addCallback(lambda args: {})
        return d

    @region.ListNodePowerParameters.responder
    def list_node_power_parameters(self, uuid):
        """list_node_power_parameters()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.ListNodePowerParameters`.
        """
        d = deferToDatabase(
            nodes.list_cluster_nodes_power_parameters, uuid)
        d.addCallback(lambda nodes: {"nodes": nodes})
        return d

    @region.UpdateNodePowerState.responder
    def update_node_power_state(self, system_id, power_state):
        """update_node_power_state()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.UpdateNodePowerState`.
        """
        d = deferToDatabase(
            nodes.update_node_power_state, system_id, power_state)
        d.addCallback(lambda args: {})
        return d

    @region.RegisterEventType.responder
    def register_event_type(self, name, description, level):
        """register_event_type()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.RegisterEventType`.
        """
        d = deferToDatabase(
            events.register_event_type, name, description, level)
        d.addCallback(lambda args: {})
        return d

    @region.SendEvent.responder
    def send_event(self, system_id, type_name, description):
        """send_event()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.SendEvent`.
        """
        timestamp = datetime.now()
        dbtasks = eventloop.services.getServiceNamed("database-tasks")
        dbtasks.addTask(
            events.send_event, system_id, type_name,
            description, timestamp)
        # Don't wait for the record to be written.
        return succeed({})

    @region.SendEventMACAddress.responder
    def send_event_mac_address(self, mac_address, type_name, description):
        """send_event_mac_address()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.SendEventMACAddress`.
        """
        timestamp = datetime.now()
        dbtasks = eventloop.services.getServiceNamed("database-tasks")
        dbtasks.addTask(
            events.send_event_mac_address, mac_address,
            type_name, description, timestamp)
        # Don't wait for the record to be written.
        return succeed({})

    @region.ReportForeignDHCPServer.responder
    def report_foreign_dhcp_server(self, cluster_uuid, interface_name,
                                   foreign_dhcp_ip):
        """report_foreign_dhcp_server()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.SendEvent`.
        """
        d = deferToDatabase(
            rackcontrollers.update_foreign_dhcp_ip,
            cluster_uuid, interface_name, foreign_dhcp_ip)
        d.addCallback(lambda _: {})
        return d

    @region.GetClusterInterfaces.responder
    def get_cluster_interfaces(self, cluster_uuid):
        """get_cluster_interfaces()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetClusterInterfaces`.
        """
        d = deferToDatabase(
            rackcontrollers.get_rack_controllers_interfaces_as_dicts,
            cluster_uuid)
        d.addCallback(lambda interfaces: {'interfaces': interfaces})
        return d

    @region.CreateNode.responder
    def create_node(self, cluster_uuid, architecture, power_type,
                    power_parameters, mac_addresses, hostname=None):
        """create_node()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.CreateNode`.
        """
        d = deferToDatabase(
            create_node, architecture, power_type, power_parameters,
            mac_addresses, hostname=hostname)
        d.addCallback(lambda node: {'system_id': node.system_id})
        return d

    @region.CommissionNode.responder
    def commission_node(self, system_id, user):
        """commission_node()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.CommissionNode`.
        """
        d = deferToDatabase(
            commission_node, system_id, user)
        d.addCallback(lambda args: {})
        return d

    @region.RequestNodeInfoByMACAddress.responder
    def request_node_info_by_mac_address(self, mac_address):
        """request_node_info_by_mac_address()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.RequestNodeInfoByMACAddress`.
        """
        d = deferToDatabase(
            request_node_info_by_mac_address, mac_address)

        def get_node_info(data):
            node, purpose = data
            return {
                'system_id': node.system_id,
                'hostname': node.hostname,
                'status': node.status,
                'boot_type': "fastpath",
                'osystem': node.osystem,
                'distro_series': node.distro_series,
                'architecture': node.architecture,
                'purpose': purpose,
            }
        d.addCallback(get_node_info)
        return d


@transactional
def configureCluster(ident):
    """Configure the cluster.

    Typically this is called once, as soon as a successful handshake is made
    between the region and cluster. After that configuration can be done at
    the moment the change is made. In essence, this is "catches-up" the
    cluster with the region's current idea of how it should be.

    Don't do anything particularly energetic in here because it will be called
    once for each region<-->cluster connection, of which each cluster can have
    many.

    :param ident: The cluster's UUID.
    """
    # NODE_GROUP_REMOVAL - blake_r - Fix.
    #try:
    #    cluster = NodeGroup.objects.get(uuid=ident)
    #except NodeGroup.DoesNotExist:
    #    log.msg("Cluster '%s' is not recognised; cannot configure." % (
    #       ident,))
    #else:
    #    configure_dhcp_now(cluster)
    #    log.msg("Cluster %s (%s) has been configured." % (
    #        cluster.cluster_name, cluster.uuid))


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

    @inlineCallbacks
    def identifyCluster(self):
        response = yield self.callRemote(cluster.Identify)
        self.ident = response.get("ident")

    @inlineCallbacks
    def authenticateCluster(self):
        """Authenticate the cluster."""
        secret = yield get_shared_secret()
        message = urandom(16)  # 16 bytes of the finest.
        response = yield self.callRemote(
            cluster.Authenticate, message=message)
        salt, digest = response["salt"], response["digest"]
        digest_local = calculate_digest(secret, message, salt)
        returnValue(digest == digest_local)

    @inlineCallbacks
    def performHandshake(self):
        yield self.identifyCluster()
        authenticated = yield self.authenticateCluster()
        if authenticated:
            log.msg("Cluster '%s' authenticated." % self.ident)
            self.factory.service._addConnectionFor(self.ident, self)
        else:
            log.msg(
                "Cluster '%s' FAILED authentication; "
                "dropping connection." % self.ident)
            yield self.transport.loseConnection()
        returnValue(authenticated)

    def handshakeSucceeded(self, authenticated):
        """The handshake (identify and authenticate) succeeded.

        :param authenticated: True if the remote cluster has successfully
            authenticated.
        :type authenticated: bool
        """
        if authenticated:
            return deferToDatabase(configureCluster, self.ident).addErrback(
                log.err, "Failed to configure DHCP on %s." % (self.ident,))

    def handshakeFailed(self, failure):
        """The handshake (identify and authenticate) failed."""
        if failure.check(ConnectionClosed):
            # There has been a disconnection, clean or otherwise. There's
            # nothing we can do now, so do nothing. The reason will have been
            # logged elsewhere.
            return
        elif self.ident is None:
            log.err(
                failure, "Cluster could not be identified; "
                "dropping connection.")
            return self.transport.loseConnection()
        else:
            log.err(
                failure, "Cluster '%s' could not be authenticated; "
                "dropping connection." % self.ident)
            return self.transport.loseConnection()

    def connectionMade(self):
        super(RegionServer, self).connectionMade()
        if self.factory.service.running:
            return self.performHandshake().addCallbacks(
                self.handshakeSucceeded, self.handshakeFailed)
        else:
            self.transport.loseConnection()

    def connectionLost(self, reason):
        self.factory.service._removeConnectionFor(self.ident, self)
        super(RegionServer, self).connectionLost(reason)


class RegionService(service.Service, object):
    """A region controller RPC service.

    This is a service - in the Twisted sense - that exposes the
    ``Region`` protocol on a port.

    :ivar endpoints: The endpoints on which to listen, as a list of lists.
        Only one endpoint in each nested list will be bound (they will be
        tried in order until the first success). In this way it is possible to
        specify, say, a range of ports, but only bind one of them.
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
        self.endpoints = [
            [TCP4ServerEndpoint(reactor, port)
             for port in range(5250, 5260)],
        ]
        self.connections = defaultdict(set)
        self.waiters = defaultdict(set)
        self.factory = Factory.forProtocol(RegionServer)
        self.factory.service = self
        self.ports = []
        self.events = EventGroup("connected", "disconnected")

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
            d.addBoth(callOut, waiters.discard, d)
            waiters.add(d)
            return d
        else:
            connection = random.choice(conns)
            return defer.succeed(connection)

    def _getConnectionFromIdentifiers(self, identifiers, timeout):
        """Wait up to `timeout` seconds for at least one connection from
        `identifiers`.

        Returns a `Deferred` which will fire with a list of random connections
        to each client. Only one connection per client will be returned.

        The public interface to this method is `getClientFromIdentifiers`.
        """
        matched_connections = []
        for ident in identifiers:
            conns = list(self.connections[ident])
            if len(conns) > 0:
                matched_connections.append(random.choice(conns))
        if len(matched_connections) > 0:
            return defer.succeed(matched_connections)
        else:
            # No connections for any of the identifiers. Wait for at least one
            # connection to appear during the timeout.

            def discard_all(waiters, identifiers, d):
                """Discard all defers in the waiters for all identifiers."""
                for ident in identifiers:
                    waiters[ident].discard(d)

            def cb_conn_list(conn):
                """Convert connection into a list."""
                return [conn]

            d = deferWithTimeout(timeout)
            d.addBoth(callOut, discard_all, self.waiters, identifiers, d)
            d.addCallback(cb_conn_list)
            for ident in identifiers:
                self.waiters[ident].add(d)
            return d

    def _addConnectionFor(self, ident, connection):
        """Adds `connection` to the set of connections for `ident`.

        Notifies all waiters of this new connection and triggers the connected
        event.
        """
        self.connections[ident].add(connection)
        for waiter in self.waiters[ident].copy():
            waiter.callback(connection)
        self.events.connected.fire(ident)

    def _removeConnectionFor(self, ident, connection):
        """Removes `connection` from the set of connections for `ident`."""
        self.connections[ident].discard(connection)
        self.events.disconnected.fire(ident)

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
                log.err(result, "RegionServer endpoint failed to listen.")

    @inlineCallbacks
    def _bindFirst(self, endpoints, factory):
        """Return the first endpoint to successfully listen.

        :param endpoints: A sized iterable of `IStreamServerEndpoint`.
        :param factory: A protocol factory.

        :return: A `Deferred` yielding a :class:`twisted.internet.tcp.Port` or
            the error encountered when trying to listen on the last of the
            given endpoints.
        """
        assert len(endpoints) > 0, "No endpoint options specified."
        last = len(endpoints) - 1
        for index, endpoint in enumerate(endpoints):
            try:
                port = yield endpoint.listen(factory)
            except:
                if index == last:
                    raise
            else:
                returnValue(port)

    @asynchronous
    def startService(self):
        """Start listening on an ephemeral port."""
        super(RegionService, self).startService()
        self.starting = defer.DeferredList(
            (self._bindFirst(endpoint_options, self.factory)
             for endpoint_options in self.endpoints))

        def log_failure(failure):
            if failure.check(defer.CancelledError):
                log.msg("RegionServer start-up has been cancelled.")
            else:
                log.err(failure, "RegionServer start-up failed.")

        self.starting.addCallback(self._savePorts)
        self.starting.addErrback(log_failure)

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
        for waiters in list(self.waiters.values()):
            for waiter in waiters.copy():
                waiter.cancel()
        for conns in list(self.connections.values()):
            for conn in conns.copy():
                try:
                    yield conn.transport.loseConnection()
                except:
                    log.err()
        yield super(RegionService, self).stopService()

    @asynchronous(timeout=FOREVER)
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

    @asynchronous(timeout=FOREVER)
    def getClientFor(self, system_id, timeout=30):
        """Return a :class:`common.Client` for the specified rack controller.

        If more than one connection exists to that rack controller - implying
        that there are multiple rack controllers for the particular
        cluster, for HA - one of them will be returned at random.

        :param system_id: The system_id - as a string - of the rack controller
            that a connection is wanted for.
        :param timeout: The number of seconds to wait for a connection
            to become available.
        :raises exceptions.NoConnectionsAvailable: When no connection to the
            given rack controller is available.
        """
        d = self._getConnectionFor(system_id, timeout)

        def cancelled(failure):
            failure.trap(CancelledError)
            raise exceptions.NoConnectionsAvailable(
                "Unable to connect to rack controller %s; no connections "
                "available." % system_id, uuid=system_id)

        return d.addCallbacks(common.Client, cancelled)

    @asynchronous(timeout=FOREVER)
    def getClientFromIdentifiers(self, identifiers, timeout=30):
        """Return a :class:`common.Client` for one of the specified
        identifiers.

        If more than one connection exists to that given `identifiers`, then
        one of them will be returned at random.

        :param identifiers: List of system_id's of the rack controller
            that a connection is wanted for.
        :param timeout: The number of seconds to wait for a connection
            to become available.
        :raises exceptions.NoConnectionsAvailable: When no connection to any
            of the rack controllers is available.
        """
        d = self._getConnectionFromIdentifiers(identifiers, timeout)

        def cancelled(failure):
            failure.trap(CancelledError)
            raise exceptions.NoConnectionsAvailable(
                "Unable to connect to any rack controller %s; no connections "
                "available." % ','.join(identifiers))

        def cb_client(conns):
            return common.Client(random.choice(conns))

        return d.addCallbacks(cb_client, cancelled)

    @asynchronous(timeout=FOREVER)
    def getAllClients(self):
        """Return a list of all connected :class:`common.Client`s."""
        return [
            common.Client(conn)
            for conns in self.connections.values()
            for conn in conns
        ]

    @asynchronous(timeout=FOREVER)
    def getRandomClient(self):
        """Return a list of all connected :class:`common.Client`s."""
        clients = list(self.connections.values())
        if len(clients) == 0:
            raise exceptions.NoConnectionsAvailable(
                "Unable to connect to any rack controller; no connections "
                "available.")
        else:
            conns = list(random.choice(clients))
            return common.Client(random.choice(conns))


class RegionAdvertisingService(TimerService, object):
    """Advertise the `RegionControllerProcess` and all of its
    `RegionControllerProcessEndpoints` into the database.

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
            interval, self.try_update)

    def try_update(self):
        return deferToDatabase(self.update).addErrback(
            log.err, "Failed to update this region's process and endpoints; "
            "%s record's may be out of date" % (eventloop.loop.name,))

    @asynchronous
    def startService(self):
        self.starting = self._prepareService()

        def prepared(_):
            return super(RegionAdvertisingService, self).startService()
        self.starting.addCallback(prepared)

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
            self.stopping = deferToDatabase(self.remove)
            self.stopping.addCallback(lambda ignore: (
                super(RegionAdvertisingService, self).stopService()))
            return self.stopping
        else:
            # Start-up has not yet finished; cancel it.
            self.starting.cancel()
            return self.starting

    @inlineCallbacks
    def _prepareService(self):
        """Keep calling `prepare` until it works.

        The call to `prepare` can sometimes fail, particularly after starting
        the region for the first time on a fresh MAAS installation, but the
        mechanism is not yet understood. We take a pragmatic stance and just
        keep trying until it works.

        Each failure will be logged, and there will be a pause of 5 seconds
        between each attempt.
        """
        while True:
            try:
                d = deferToThread(get_mac_addresses)
                d.addCallback(partial(deferToDatabase, self.prepare))
                yield d
            except defer.CancelledError:
                raise
            except Exception as e:
                log.err(e, (
                    "Preparation of %s failed; will try again in "
                    "5 seconds." % self.__class__.__name__))
                yield pause(5)
            else:
                break

    @synchronous
    @synchronised(lock)
    @with_connection  # Needed by the following lock.
    @synchronised(locks.eventloop)
    @transactional
    def prepare(self, mac_addresses):
        """Ensure that the RegionController` exists.

        If not, create it. On first creation the `system_id` of the
        `RegionController` is written to /var/lib/maas/region_id. That file
        is used by the other `RegionControllerProcess` on this region to use
        the same `RegionController`.
        """
        self.region_id = self._get_region_id()
        if self.region_id is None:
            # See if any other nodes is this node, by checkin interfaces on
            # this node.
            region_obj = get_one(Node.objects.filter(
                interface__mac_address__in=mac_addresses))
            if region_obj is not None:
                # Already a node with a MAC address that matches this machine.
                # Convert that into a region.
                region_obj = self._fix_node_for_region(region_obj)
            else:
                # This is the first time MAAS has ran on this node. Create a
                # new `RegionController` and save the region_id.
                region_obj = RegionController.objects.create(
                    hostname=gethostname())
            self.region_id = region_obj.system_id
            self._write_region_id(self.region_id)
        else:
            # Region already exists load it from the database.
            region_obj = Node.objects.get(system_id=self.region_id)
            self._fix_node_for_region(region_obj)

    @synchronous
    @synchronised(lock)
    @transactional
    def update(self):
        """Repopulate the `RegionControllerProcess` with this process's
        information.

        It updates all the records in `RegionControllerProcess` related to the
        `RegionController`. Old `RegionControllerProcess` and
        `RegionControllerProcessEndpoints` are garbage collected.
        """
        # Get the region controller and update its hostname and last
        # updated time.
        region_obj = Node.objects.get(system_id=self.region_id)
        update_fields = ["updated"]
        hostname = gethostname()
        if region_obj.hostname != hostname:
            region_obj.hostname = hostname
            update_fields.append("hostname")
        region_obj.save(update_fields=update_fields)

        # Get or create the process for this region and update its last updated
        # time.
        process, created = RegionControllerProcess.objects.get_or_create(
            region=region_obj, pid=os.getpid())
        if not created:
            # Update its latest updated time.
            process.save(update_fields=["updated"])

        # Remove any old processes that are older than 90 seconds.
        remove_before_time = now() - timedelta(seconds=90)
        RegionControllerProcess.objects.filter(
            updated__lte=remove_before_time).delete()

        # Update all endpoints for this process.
        previous_endpoint_ids = set(
            RegionControllerProcessEndpoint.objects.filter(
                process=process).values_list("id", flat=True))
        addresses = frozenset(self._get_addresses())
        for addr, port in addresses:
            endpoint, created = (
                RegionControllerProcessEndpoint.objects.get_or_create(
                    process=process, address=addr, port=port))
            if not created:
                previous_endpoint_ids.remove(endpoint.id)
        RegionControllerProcessEndpoint.objects.filter(
            id__in=previous_endpoint_ids).delete()

    @synchronous
    @synchronised(lock)
    @transactional
    def dump(self):
        """Returns a list of ``(name, addr, port)`` tuples.

        Each tuple corresponds to somewhere an event-loop is listening
        within the whole region. The `name` is the event-loop name.
        """
        regions = RegionController.objects.all()
        regions = regions.prefetch_related("processes", "processes__endpoints")
        all_endpoints = []
        for region_obj in regions:
            for process in region_obj.processes.all():
                for endpoint in process.endpoints.all():
                    all_endpoints.append((
                        "%s:pid=%d" % (region_obj.hostname, process.pid),
                        endpoint.address,
                        endpoint.port))
        return all_endpoints

    @synchronous
    @synchronised(lock)
    @transactional
    def remove(self):
        """Removes all records related to this process.

        A subsequent call to `update()` will restore these records,
        hence calling this while this service is started won't be
        terribly efficacious.
        """
        region_obj = Node.objects.get(system_id=self.region_id)
        RegionControllerProcess.objects.get(
            region=region_obj, pid=os.getpid()).delete()

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
            port = service.getPort()
            if port is not None:
                for addr in get_all_interface_addresses():
                    ipaddr = IPAddress(addr)
                    if ipaddr.is_link_local():
                        continue  # Don't advertise link-local addresses.
                    if ipaddr.version != 4:
                        continue  # Only advertise IPv4 for now.
                    yield addr, port

    @classmethod
    def _get_path_to_region_id(cls):
        """Return the path to '/var/lib/maas/region_id'.

        Help's with testing as this method is mocked.
        """
        return get_path('/var/lib/maas/region_id')

    def _get_region_id(self):
        """Return the `RegionController` system_id from
        '/var/lib/maas/region_id'."""
        region_id_path = RegionAdvertisingService._get_path_to_region_id()
        if os.path.exists(region_id_path):
            with open(region_id_path, "r", encoding="ascii") as fp:
                return fp.read().strip()
        else:
            return None

    def _write_region_id(self, system_id):
        """Return the `RegionController` system_id from
        '/var/lib/maas/region_id'."""
        region_id_path = RegionAdvertisingService._get_path_to_region_id()
        atomic_write(system_id.encode("ascii"), region_id_path)

    def _fix_node_for_region(self, region_obj):
        """Fix the `node_type` and `hostname` on `region_obj`.

        This method only updates the database if it has changed.
        """
        update_fields = []
        if region_obj.node_type not in [
                NODE_TYPE.REGION_CONTROLLER,
                NODE_TYPE.REGION_AND_RACK_CONTROLLER]:
            if region_obj.node_type == NODE_TYPE.RACK_CONTROLLER:
                region_obj.node_type = NODE_TYPE.REGION_AND_RACK_CONTROLLER
            else:
                region_obj.node_type = NODE_TYPE.REGION_CONTROLLER
            update_fields.append("node_type")
        hostname = gethostname()
        if region_obj.hostname != hostname:
            region_obj.hostname = hostname
            update_fields.append("hostname")
        if len(update_fields) > 0:
            region_obj.save(update_fields=update_fields)
        return region_obj
