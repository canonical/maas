# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
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
import os
from os import urandom
import random
from socket import (
    AF_INET,
    gethostname,
)
import threading

from maasserver import (
    eventloop,
    locks,
)
from maasserver.bootresources import get_simplestream_endpoint
from maasserver.enum import SERVICE_STATUS
from maasserver.models.node import (
    Node,
    RackController,
    RegionController,
)
from maasserver.models.regioncontrollerprocess import RegionControllerProcess
from maasserver.models.regioncontrollerprocessendpoint import (
    RegionControllerProcessEndpoint,
)
from maasserver.models.regionrackrpcconnection import RegionRackRPCConnection
from maasserver.models.service import Service
from maasserver.models.timestampedmodel import now
from maasserver.rpc import (
    boot,
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
from maasserver.rpc.services import update_services
from maasserver.security import get_shared_secret
from maasserver.utils import synchronised
from maasserver.utils.orm import (
    transactional,
    with_connection,
)
from maasserver.utils.threads import deferToDatabase
from netaddr import IPAddress
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
from provisioningserver.utils.events import EventGroup
from provisioningserver.utils.network import get_all_interface_addresses
from provisioningserver.utils.twisted import (
    asynchronous,
    call,
    callOut,
    deferred,
    DeferredValue,
    deferWithTimeout,
    FOREVER,
    pause,
    synchronous,
)
from twisted.application import service
from twisted.internet import (
    defer,
    reactor,
)
from twisted.internet.address import (
    IPv4Address,
    IPv6Address,
)
from twisted.internet.defer import (
    CancelledError,
    fail,
    inlineCallbacks,
    maybeDeferred,
    returnValue,
    succeed,
)
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.error import ConnectionClosed
from twisted.internet.protocol import Factory
from twisted.internet.task import LoopingCall
from twisted.protocols import amp
from twisted.python import log
from zope.interface import implementer

# Number of regiond processes that should be running for a regiond.
# XXX blake_r 2016-03-10 bug=1555901: It would be better to determine this
# value from systemd or other means instead of hard coding the number.
NUMBER_OF_REGIOND_PROCESSES = 4


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
        return {"ident": eventloop.loop.name}

    @region.Authenticate.responder
    def authenticate(self, message):
        d = maybeDeferred(get_shared_secret)

        def got_secret(secret):
            salt = urandom(16)  # 16 bytes of high grade noise.
            digest = calculate_digest(secret, message, salt)
            return {"digest": digest, "salt": salt}

        return d.addCallback(got_secret)

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
        :py:class:`~twisted.protocols.amp.StartTLS`.
        """
        try:
            from provisioningserver.rpc.testing import tls
        except ImportError:
            # This is not a development/test environment.
            # XXX: Return production TLS parameters.
            return {}
        else:
            return tls.get_tls_parameters_for_region()

    @region.GetBootConfig.responder
    def get_boot_config(
            self, system_id, local_ip, remote_ip, arch=None, subarch=None,
            mac=None, bios_boot_method=None):
        """get_boot_config()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetBootConfig`.
        """
        return deferToDatabase(
            boot.get_config, system_id, local_ip, remote_ip,
            arch=arch, subarch=subarch, mac=mac,
            bios_boot_method=bios_boot_method)

    @region.GetBootSources.responder
    def get_boot_sources(self, uuid):
        """get_boot_sources()

        Deprecated: get_boot_sources_v2() should be used instead.

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetBootSources`.
        """
        d = deferToDatabase(get_simplestream_endpoint)
        d.addCallback(lambda source: {"sources": [source]})
        return d

    @region.GetBootSourcesV2.responder
    def get_boot_sources_v2(self, uuid):
        """get_boot_sources_v2()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetBootSources`.
        """
        d = deferToDatabase(get_simplestream_endpoint)
        d.addCallback(lambda source: {"sources": [source]})
        return d

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

    @region.UpdateLastImageSync.responder
    def update_last_image_sync(self, system_id):
        """update_last_image_sync()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.UpdateLastImageSync`.
        """
        d = deferToDatabase(
            rackcontrollers.update_last_image_sync, system_id)
        d.addCallback(lambda args: {})
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
    def report_foreign_dhcp_server(
            self, system_id, interface_name, dhcp_ip=None):
        """report_foreign_dhcp_server()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.ReportForeignDHCPServer`.
        """
        d = deferToDatabase(
            rackcontrollers.update_foreign_dhcp,
            system_id, interface_name, dhcp_ip)
        d.addCallback(lambda _: {})
        return d

    @region.CreateNode.responder
    def create_node(self, architecture, power_type, power_parameters,
                    mac_addresses, domain=None, hostname=None):
        """create_node()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.CreateNode`.
        """
        d = deferToDatabase(
            create_node, architecture, power_type, power_parameters,
            mac_addresses, domain=domain, hostname=hostname)
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

    @region.UpdateInterfaces.responder
    def update_interfaces(self, system_id, interfaces):
        """update_interfaces()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.UpdateInterfaces`.
        """
        d = deferToDatabase(
            rackcontrollers.update_interfaces, system_id, interfaces)
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

    @region.UpdateServices.responder
    def update_services(self, system_id, services):
        """update_services(system_id, services)

        Implementation of
        :py:class:`~provisioningserver.rpc.region.UpdateServices`.
        """
        return deferToDatabase(
            update_services, system_id, services)

    @region.RequestRackRefresh.responder
    def request_rack_refresh(self, system_id):
        """Request a refresh of the rack

        Implementation of
        :py:class:`~provisioningserver.rpc.region.RequestRackRefresh`.
        """
        d = deferToDatabase(RackController.objects.get, system_id=system_id)
        d.addCallback(lambda rack: rack.refresh())
        d.addCallback(lambda _: {})
        return d


@transactional
def registerConnection(region_id, rack_controller, host):
    """Register the connection into the database.

    :param region_id: The region ID (aka MAAS ID, or system ID for the host on
        which regiond is running).
    """
    region = RegionController.objects.get(system_id=region_id)
    process = RegionControllerProcess.objects.get(
        region=region, pid=os.getpid())
    endpoint = RegionControllerProcessEndpoint.objects.get(
        process=process, address=host.host, port=host.port)
    connection, created = RegionRackRPCConnection.objects.get_or_create(
        endpoint=endpoint, rack_controller=rack_controller)
    if not created:
        # Force the save so that signals connected to the
        # RegionRackRPCConnection are performed.
        connection.save()


@transactional
def unregisterConnection(region_id, ident, host):
    """Unregister the connection into the database.

    :param region_id: The region ID (aka MAAS ID, or system ID for the host on
        which regiond is running).
    """
    region = RegionController.objects.get(system_id=region_id)
    process = RegionControllerProcess.objects.get(
        region=region, pid=os.getpid())
    endpoint = RegionControllerProcessEndpoint.objects.get(
        process=process, address=host.host, port=host.port)
    rack_controller = RackController.objects.get(system_id=ident)
    RegionRackRPCConnection.objects.filter(
        endpoint=endpoint, rack_controller=rack_controller).delete()


def getRegionID():
    """Obtain the region ID from the advertising service.

    :return: :class:`Deferred`
    """
    try:
        advertise = eventloop.services.getServiceNamed("rpc-advertise")
    except:
        return fail()
    else:
        return advertise.advertising.get().addCallback(
            lambda advertising: advertising.region_id)


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
    host = None
    hostIsRemote = False

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

    @region.RegisterRackController.responder
    @inlineCallbacks
    def register(
            self, system_id, hostname, interfaces, url, nodegroup_uuid=None):

        try:
            # Register, which includes updating interfaces.
            rack_controller = yield deferToDatabase(
                rackcontrollers.register, system_id=system_id,
                hostname=hostname, interfaces=interfaces, url=url)

            # Check for upgrade.
            if nodegroup_uuid is not None:
                yield deferToDatabase(
                    rackcontrollers.handle_upgrade,
                    rack_controller, nodegroup_uuid)

            # Set the identifier and add the connection into the service
            # and into the database.
            self.ident = rack_controller.system_id
            self.factory.service._addConnectionFor(self.ident, self)
            self.host = self.transport.getHost()
            self.hostIsRemote = isinstance(
                self.host, (IPv4Address, IPv6Address))

            # Get the region ID if we're dealing with a non-local rack; we
            # won't need to bother for local racks.
            if self.hostIsRemote:
                region_id = yield getRegionID()

            # Only register the connection into the database when its a valid
            # IPv4 and IPv6. Only time it is not an IPv4 or IPv6 address is
            # when mocking a connection.
            if self.hostIsRemote:
                yield deferToDatabase(
                    registerConnection, region_id, rack_controller, self.host)

            # Rack controller is now registered. Log this status.
            log.msg(
                "Rack controller '%s' has been registered." % self.ident)

            # Done registering the rack controller and connection.
            return {'system_id': self.ident}
        except Exception as exc:
            # Some error occurred here. Remove the connection in the database,
            # log the error and alert the connected rack controller. The
            # connected rack controller will drop the connection.
            if (self.ident is not None and self.hostIsRemote):
                yield deferToDatabase(
                    unregisterConnection, region_id, self.ident, self.host)
            msg = (
                "Failed to register rack controller '%s' into the "
                "database. Connection has been dropped." % (
                    self.ident))
            log.err(exc, msg)
            raise exceptions.CannotRegisterRackController(msg)

    @inlineCallbacks
    def performHandshake(self):
        authenticated = yield self.authenticateCluster()
        peer = self.transport.getPeer()
        if isinstance(peer, (IPv4Address, IPv6Address)):
            client = "%s:%s" % (peer.host, peer.port)
        else:
            client = peer.name
        if authenticated:
            log.msg(
                "Rack controller authenticated from '%s'." % client)
        else:
            log.msg(
                "Rack controller FAILED authentication from '%s'; "
                "dropping connection." % client)
            yield self.transport.loseConnection()
        returnValue(authenticated)

    def handshakeFailed(self, failure):
        """The authenticate handshake failed."""
        if failure.check(ConnectionClosed):
            # There has been a disconnection, clean or otherwise. There's
            # nothing we can do now, so do nothing. The reason will have been
            # logged elsewhere.
            return
        else:
            log.err(
                failure, "Rack controller '%s' could not be authenticated; "
                "dropping connection." % self.ident)
            return self.transport.loseConnection()

    def connectionMade(self):
        super(RegionServer, self).connectionMade()
        if self.factory.service.running:
            return self.performHandshake().addErrback(self.handshakeFailed)
        else:
            self.transport.loseConnection()

    def connectionLost(self, reason):
        if self.hostIsRemote:
            getRegionID().addCallback(
                lambda region_id: deferToDatabase(
                    unregisterConnection, region_id, self.ident, self.host))
        self.factory.service._removeConnectionFor(self.ident, self)
        log.msg("Rack controller '%s' disconnected." % self.ident)
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


def ignoreCancellation(failure):
    """Suppress `defer.CancelledError`."""
    failure.trap(defer.CancelledError)


class RegionAdvertisingService(service.Service):
    """Advertise the `RegionControllerProcess` and all of its
    `RegionControllerProcessEndpoints` into the database.

    :cvar lock: A lock to help coordinate - and prevent - concurrent
        database access from this service across the whole interpreter.

    :ivar starting: Either `None`, or a :class:`Deferred` that fires
        with the service has successfully started. It does *not*
        indicate that the first update has been done.
    """

    # Interval for this service when the rpc service has not started.
    INTERVAL_NO_ENDPOINTS = 2  # seconds.

    # Interval for this service when the rpc service has started.
    INTERVAL_WITH_ENDPOINTS = 60  # seconds.

    # A LoopingCall that ensures that this region is being advertised, and the
    # Deferred that fires when it has stopped.
    advertiser = advertiserDone = None

    starting = None
    stopping = None

    def __init__(self):
        super(RegionAdvertisingService, self).__init__()
        self.advertiser = LoopingCall(self._tryUpdate)
        self.advertising = DeferredValue()

    @asynchronous
    def startService(self):
        self.starting = maybeDeferred(super().startService)
        # Populate advertising records in the database.
        self.starting.addCallback(call, self._tryPromote)
        self.starting.addCallbacks(self._promotionOkay, self._promotionFailed)
        # Start the advertising loop to keep those records up-to-date.
        self.starting.addCallback(callOut, self._startAdvertising)
        # We may get cancelled; suppress the exception as a penultimate step.
        self.starting.addErrback(ignoreCancellation)
        # It would be better to let failures propagate, but MultiService does
        # not wait for startService to complete. If we don't handle errors
        # here we'll end up with "Unhandled error in Deferred" messages.
        self.starting.addErrback(
            log.err, "Failure starting advertising service.")
        # Let the caller track all of this.
        return self.starting

    @asynchronous
    def stopService(self):
        # Officially begin stopping this service.
        self.stopping = maybeDeferred(super().stopService)
        # Wait for all start-up tasks to finish.
        self.stopping.addCallback(callOut, lambda: self.starting)
        # Stop the advertising loop and wait for it to complete.
        self.stopping.addCallback(callOut, self._stopAdvertising)
        # Remove this regiond from all advertising records.
        self.stopping.addCallback(callOut, self._tryDemote)
        # Let the caller track all of this.
        return self.stopping

    @inlineCallbacks
    def _tryPromote(self):
        """Keep calling `promote` until it works.

        The call to `promote` can sometimes fail, particularly after starting
        the region for the first time on a fresh MAAS installation, but the
        mechanism is not yet understood. We take a pragmatic stance and just
        keep trying until it works.

        Each failure will be logged, and there will be a pause of 5 seconds
        between each attempt.

        :return: An instance of `RegionAdvertising`.
        """
        while self.running:
            try:
                advertising = yield deferToDatabase(RegionAdvertising.promote)
            except RegionController.DoesNotExist:
                # Wait for the region controller object to be created
                yield pause(1)
            except:
                log.err(None, (
                    "Promotion of %s failed; will try again in "
                    "5 seconds." % (eventloop.loop.name,)))
                yield pause(5)
            else:
                returnValue(advertising)
        else:
            # Preparation did not complete before this service was shutdown,
            # so raise CancelledError to prevent callbacks from being called.
            raise defer.CancelledError()

    def _promotionOkay(self, advertising):
        """Store the region advertising object.

        Also ensures that the `maas_id` file is created. This is read by other
        regiond processes on this host so that the `RegionControllerProcess`s
        they create in the database all refer to the same `RegionController`.

        :param advertising: An instance of `RegionAdvertising`.
        """
        self.advertising.set(advertising)

    def _promotionFailed(self, failure):
        """Clear up when service preparation fails."""
        self.advertising.fail(failure)
        return failure

    def _tryUpdate(self):
        d = self.advertising.get()

        def deferUpdate(advertising):
            return deferToDatabase(advertising.update, self._getAddresses())
        d.addCallback(deferUpdate)

        def setInterval(interval):
            self.advertiser.interval = interval
        d.addCallback(setInterval)

        return d.addErrback(ignoreCancellation).addErrback(
            log.err, "Failed to update regiond's process and endpoints; "
            "%s record's may be out of date" % (eventloop.loop.name,))

    def _tryDemote(self):
        d = self.advertising.get(0.0)  # Don't wait around.

        def deferDemote(advertising):
            return deferToDatabase(advertising.demote)
        d.addCallback(deferDemote)

        return d.addErrback(ignoreCancellation).addErrback(
            log.err, "Failed to demote regiond's process and endpoints; "
            "%s record's may be out of date" % (eventloop.loop.name,))

    @deferred
    def _startAdvertising(self):
        """Keep advertising that this regiond is on active duty.

        :return: A `Deferred` that will fire when the loop has started.
        """
        self.advertiserDone = self.advertiser.start(self.INTERVAL_NO_ENDPOINTS)

    @deferred
    def _stopAdvertising(self):
        """Stop advertising that this regiond is on active duty.

        :return: A `Deferred` that will fire when the loop has stopped.
        """
        if self.advertiser.running:
            self.advertiser.stop()
            return self.advertiserDone

    @classmethod
    @asynchronous
    def _getAddresses(cls):
        """Generate the addresses on which to advertise region availablilty.

        This excludes link-local addresses. We may want to revisit this at a
        later time, but right now it causes issues because multiple network
        interfaces may have the same link-local address. Loopback addresses
        are also excluded unless no other addresses are available.

        This also excludes IPv6 addresses because `RegionServer` only supports
        IPv4. However, this will probably change in the near future.

        :rtype: set
        """
        try:
            service = eventloop.services.getServiceNamed("rpc")
        except KeyError:
            return set()  # No RPC service yet.
        else:
            port = service.getPort()
            if port is None:
                return set()  # Not serving yet.
            else:
                addresses = set()
                loopback_addresses = set()
                for addr in get_all_interface_addresses():
                    ipaddr = IPAddress(addr)
                    if ipaddr.is_link_local():
                        continue  # Don't advertise link-local addresses.
                    if ipaddr.version != 4:
                        continue  # Only advertise IPv4 for now.
                    if ipaddr.is_loopback():
                        loopback_addresses.add((addr, port))
                    else:
                        addresses.add((addr, port))
                if len(addresses) > 0:
                    return addresses
                else:
                    # There are no non-loopback addresses, so return loopback
                    # address as a fallback.
                    return loopback_addresses


class RegionAdvertising:
    """Encapsulate all database operations related to advertising a regiond.

    This class has a lifecycle:

    * Set-up with `promote`.
    * Keep up-to-date with calls to `update`.
    * Tear-down with `demote`.

    """

    # Prevent advertising related transactions from overlapping.
    lock = threading.Lock()

    @classmethod
    @synchronous
    @synchronised(lock)
    @transactional
    def dump(cls):
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
                        endpoint.address, endpoint.port))
        return all_endpoints

    @classmethod
    @synchronous
    @synchronised(lock)
    @with_connection  # Needed by the following lock.
    @synchronised(locks.eventloop)
    @transactional
    def promote(cls):
        """Promote this regiond to active duty.

        Ensure that `RegionController` and `RegionControllerProcess` records
        exists for this regiond.

        :return: An instance of `RegionAdvertising`.
        """
        region_obj = RegionController.objects.get_running_controller()
        # Create the process for this region. This process object will be
        # updated by calls to `update`, which is the responsibility of the
        # rpc-advertise service. Calls to `update` also remove old process
        # records from the database.
        process, _ = RegionControllerProcess.objects.get_or_create(
            region=region_obj, pid=os.getpid())

        return cls(region_obj.system_id, process.id)

    def __init__(self, region_id, process_id):
        """Use `promote` to construct new instances."""
        super(RegionAdvertising, self).__init__()
        self.region_id = region_id
        self.process_id = process_id

    @synchronous
    @synchronised(lock)
    @transactional
    def update(self, addresses):
        """Repopulate the `RegionControllerProcess` with this process's
        information.

        It updates all the records in `RegionControllerProcess` related to the
        `RegionController`. Old `RegionControllerProcess` and
        `RegionControllerProcessEndpoints` are garbage collected.

        :param addresses: A set of `(address, port)` tuples.
        """
        # Get the region controller and update its hostname and last
        # updated time.
        region_obj = RegionController.objects.get(system_id=self.region_id)
        update_fields = ["updated"]
        hostname = gethostname()
        if region_obj.hostname != hostname:
            region_obj.hostname = hostname
            update_fields.append("hostname")
        region_obj.save(update_fields=update_fields)

        # Update the updated time for this process. This prevents other
        # region process from removing this process.
        try:
            process = RegionControllerProcess.objects.get(id=self.process_id)
        except RegionControllerProcess.DoesNotExist:
            # Possible that another regiond process deleted this process
            # because the updated field was not updated in time. Re-create the
            # process with the same ID so its the same across the running of
            # this regiond process.
            process = RegionControllerProcess(
                region=region_obj, pid=os.getpid(), created=now())
            process.id = self.process_id
            process.save()
        else:
            process.save(update_fields=["updated"])

        # Remove any old processes that are older than 90 seconds.
        remove_before_time = now() - timedelta(seconds=90)
        RegionControllerProcess.objects.filter(
            updated__lte=remove_before_time).delete()

        # Update all endpoints for this process.
        previous_endpoint_ids = set(
            RegionControllerProcessEndpoint.objects.filter(
                process=process).values_list("id", flat=True))
        if len(addresses) == 0:
            # No endpoints; set the interval so it updates quickly.
            interval = RegionAdvertisingService.INTERVAL_NO_ENDPOINTS
        else:
            # Has endpoints; update less frequently.
            interval = RegionAdvertisingService.INTERVAL_WITH_ENDPOINTS
            for addr, port in addresses:
                endpoint, created = (
                    RegionControllerProcessEndpoint.objects.get_or_create(
                        process=process, address=addr, port=port))
                if not created:
                    previous_endpoint_ids.remove(endpoint.id)

        # Remove any previous endpoints.
        RegionControllerProcessEndpoint.objects.filter(
            id__in=previous_endpoint_ids).delete()

        # Update the status of this regiond service for this region based on
        # the number of running processes.
        Service.objects.create_services_for(region_obj)
        number_of_processes = RegionControllerProcess.objects.filter(
            region=region_obj).count()
        not_running_count = NUMBER_OF_REGIOND_PROCESSES - number_of_processes
        if not_running_count > 0:
            if number_of_processes == 1:
                process_text = "process"
            else:
                process_text = "processes"
            Service.objects.update_service_for(
                region_obj, "regiond", SERVICE_STATUS.DEGRADED,
                "%d %s running but %d were expected." % (
                    number_of_processes, process_text,
                    NUMBER_OF_REGIOND_PROCESSES))
        else:
            Service.objects.update_service_for(
                region_obj, "regiond", SERVICE_STATUS.RUNNING, "")

        # Update the status of all regions that have no processes running.
        for other_region in RegionController.objects.exclude(
                system_id=self.region_id).prefetch_related("processes"):
            # Use len with `all` so the prefetch cache is used.
            if len(other_region.processes.all()) == 0:
                Service.objects.mark_dead(other_region, dead_region=True)

        # The caller is responsible for setting the update interval.
        return interval

    @synchronous
    @synchronised(lock)
    @transactional
    def demote(self):
        """Demote this regiond from active duty.

        Removes all `RegionControllerProcess` records related to this process.

        A subsequent call to `update()` will restore these records, hence
        calling this while this service is running won't ultimately be very
        useful.
        """
        # There should be only one, but this loop copes with zero too.
        for region_obj in Node.objects.filter(system_id=self.region_id):
            RegionControllerProcess.objects.get(
                region=region_obj, pid=os.getpid()).delete()
