# Copyright 2014-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC implementation for regions."""
from collections import defaultdict
import copy
from datetime import datetime
import json
from os import urandom
import random
from socket import AF_INET, AF_INET6
import uuid

from netaddr import AddrConversionError, IPAddress
from twisted.application import service
from twisted.internet import defer, reactor
from twisted.internet.address import IPv4Address, IPv6Address
from twisted.internet.defer import (
    CancelledError,
    inlineCallbacks,
    maybeDeferred,
    returnValue,
    succeed,
)
from twisted.internet.endpoints import TCP6ServerEndpoint
from twisted.internet.error import ConnectionClosed
from twisted.internet.protocol import Factory
from twisted.internet.threads import deferToThread
from zope.interface import implementer

from maasserver import eventloop
from maasserver.dns.config import get_trusted_networks
from maasserver.models.config import Config
from maasserver.models.node import RackController
from maasserver.models.subnet import Subnet
from maasserver.rpc import (
    boot,
    configuration,
    events,
    leases,
    nodes,
    packagerepository,
    rackcontrollers,
)
from maasserver.rpc.nodes import (
    commission_node,
    create_node,
    request_node_info_by_mac_address,
)
from maasserver.rpc.services import update_services
from maasserver.secrets import SecretManager, SecretNotFound
from maasserver.security import get_shared_secret
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import LegacyLogger
from provisioningserver.prometheus.metrics import (
    GLOBAL_LABELS,
    PROMETHEUS_METRICS,
)
from provisioningserver.rpc import cluster, common, exceptions, region
from provisioningserver.rpc.common import (
    ConnectionAuthStatus,
    SecuredRPCProtocol,
)
from provisioningserver.rpc.interfaces import IConnection
from provisioningserver.security import calculate_digest, fernet_encrypt_psk
from provisioningserver.utils.events import EventGroup
from provisioningserver.utils.network import resolves_to_loopback_address
from provisioningserver.utils.twisted import (
    asynchronous,
    callOut,
    deferWithTimeout,
    FOREVER,
)
from provisioningserver.utils.version import get_running_version

log = LegacyLogger()


class Region(SecuredRPCProtocol):
    """The RPC protocol supported by a region controller.

    This can be used on the client or server end of a connection; once a
    connection is established, AMP is symmetric.
    """

    def __init__(
        self, auth_status: ConnectionAuthStatus = ConnectionAuthStatus(False)
    ):
        super().__init__(
            unauthenticated_commands=[region.Authenticate.commandName],
            auth_status=auth_status,
        )

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

    @region.UpdateLease.responder
    def update_lease(
        self,
        action,
        mac,
        ip_family,
        ip,
        timestamp,
        lease_time=None,
        hostname=None,
    ):
        """update_lease(
            action, mac, ip_family, ip, timestamp,
            lease_time, hostname)

        Implementation of
        :py:class`~provisioningserver.rpc.region.UpdateLease`.
        """
        dbtasks = eventloop.services.getServiceNamed("database-tasks")
        d = dbtasks.deferTask(
            leases.update_lease,
            action,
            mac,
            ip_family,
            ip,
            timestamp,
            lease_time,
            hostname,
        )

        def log_error(failure):
            log.err(failure, "Unhandled failure in updating lease.")
            return {}

        d.addErrback(log_error)

        # Wait for the record to be handled. This will cause the cluster to
        # send one at a time. So they are processed in order no matter which
        # region receives the message.
        return d

    @region.UpdateLeases.responder
    def update_leases(self, updates):
        """update_leases(updates)

        Implementation of
        :py:class`~provisioningserver.rpc.region.UpdateLeases`.
        """

        def log_error(failure):
            log.err(failure, "Unhandled failure in updating lease.")
            return {}

        dbtasks = eventloop.services.getServiceNamed("database-tasks")
        tasks = []
        for upd in updates:
            t = dbtasks.deferTask(
                leases.update_lease,
                upd["action"],
                upd["mac"],
                upd["ip_family"],
                upd["ip"],
                upd["timestamp"],
                upd["lease_time"],
                upd["hostname"],
            )
            t.addErrback(log_error)
            tasks.append(t)

        d = defer.gatherResults(tasks)
        return d

    @region.GetBootConfig.responder
    def get_boot_config(
        self,
        system_id,
        local_ip,
        remote_ip,
        arch=None,
        subarch=None,
        mac=None,
        hardware_uuid=None,
        bios_boot_method=None,
    ):
        """get_boot_config()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetBootConfig`.
        """
        return deferToDatabase(
            boot.get_config,
            system_id,
            local_ip,
            remote_ip,
            arch=arch,
            subarch=subarch,
            mac=mac,
            hardware_uuid=hardware_uuid,
            bios_boot_method=bios_boot_method,
        )

    @region.GetArchiveMirrors.responder
    def get_archive_mirrors(self):
        """get_archive_mirrors()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetArchiveMirrors`.
        """
        d = deferToDatabase(packagerepository.get_archive_mirrors)
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
            nodes.mark_node_failed, system_id, error_description
        )
        d.addCallback(lambda args: {})
        return d

    @region.ListNodePowerParameters.responder
    def list_node_power_parameters(self, uuid):
        """list_node_power_parameters()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.ListNodePowerParameters`.
        """
        d = deferToDatabase(nodes.list_cluster_nodes_power_parameters, uuid)
        d.addCallback(lambda nodes: {"nodes": nodes})
        return d

    @region.UpdateNodePowerState.responder
    def update_node_power_state(self, system_id, power_state):
        """update_node_power_state()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.UpdateNodePowerState`.
        """
        d = deferToDatabase(
            nodes.update_node_power_state, system_id, power_state
        )
        d.addCallback(lambda args: {})
        return d

    @region.RegisterEventType.responder
    def register_event_type(self, name, description, level):
        """register_event_type()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.RegisterEventType`.
        """
        d = deferToDatabase(
            events.register_event_type, name, description, level
        )
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
            events.send_event, system_id, type_name, description, timestamp
        )
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
            events.send_event_mac_address,
            mac_address,
            type_name,
            description,
            timestamp,
        )
        # Don't wait for the record to be written.
        return succeed({})

    @region.SendEventIPAddress.responder
    def send_event_ip_address(self, ip_address, type_name, description):
        """send_event_ip_address()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.SendEventIPAddress`.
        """
        timestamp = datetime.now()
        dbtasks = eventloop.services.getServiceNamed("database-tasks")
        dbtasks.addTask(
            events.send_event_ip_address,
            ip_address,
            type_name,
            description,
            timestamp,
        )
        # Don't wait for the record to be written.
        return succeed({})

    @region.ReportForeignDHCPServer.responder
    def report_foreign_dhcp_server(
        self, system_id, interface_name, dhcp_ip=None
    ):
        """report_foreign_dhcp_server()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.ReportForeignDHCPServer`.
        """
        d = deferToDatabase(
            rackcontrollers.update_foreign_dhcp,
            system_id,
            interface_name,
            dhcp_ip,
        )
        d.addCallback(lambda _: {})
        return d

    @region.CreateNode.responder
    def create_node(
        self,
        architecture,
        power_type,
        power_parameters,
        mac_addresses,
        domain=None,
        hostname=None,
    ):
        """create_node()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.CreateNode`.
        """
        d = deferToDatabase(
            create_node,
            architecture,
            power_type,
            power_parameters,
            mac_addresses,
            domain=domain,
            hostname=hostname,
        )
        d.addCallback(lambda node: {"system_id": node.system_id})
        return d

    @region.CommissionNode.responder
    def commission_node(self, system_id, user):
        """commission_node()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.CommissionNode`.
        """
        d = deferToDatabase(commission_node, system_id, user)
        d.addCallback(lambda args: {})
        return d

    @region.GetDiscoveryState.responder
    def get_discovery_state(self, system_id):
        """get_interface_monitoring_state()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetDiscoveryState`.
        """
        d = deferToDatabase(rackcontrollers.get_discovery_state, system_id)
        d.addCallback(lambda args: {"interfaces": args})
        return d

    @region.ReportMDNSEntries.responder
    def report_mdns_entries(self, system_id, mdns):
        """report_neighbours()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.ReportNeighbours`.
        """
        d = deferToDatabase(
            rackcontrollers.report_mdns_entries, system_id, mdns
        )
        d.addCallback(lambda args: {})
        return d

    @region.ReportNeighbours.responder
    def report_neighbours(self, system_id, neighbours):
        """report_neighbours()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.ReportNeighbours`.
        """
        d = deferToDatabase(
            rackcontrollers.report_neighbours, system_id, neighbours
        )
        d.addCallback(lambda args: {})
        return d

    @region.RequestNodeInfoByMACAddress.responder
    def request_node_info_by_mac_address(self, mac_address):
        """request_node_info_by_mac_address()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.RequestNodeInfoByMACAddress`.
        """
        d = deferToDatabase(request_node_info_by_mac_address, mac_address)

        def get_node_info(data):
            node, purpose = data
            return {
                "system_id": node.system_id,
                "hostname": node.hostname,
                "status": node.status,
                "boot_type": "fastpath",
                "osystem": node.osystem,
                "distro_series": node.distro_series,
                "architecture": node.architecture,
                "purpose": purpose,
            }

        d.addCallback(get_node_info)
        return d

    @region.UpdateServices.responder
    def update_services(self, system_id, services):
        """update_services(system_id, services)

        Implementation of
        :py:class:`~provisioningserver.rpc.region.UpdateServices`.
        """
        return deferToDatabase(update_services, system_id, services)

    @region.RequestRackRefresh.responder
    def request_rack_refresh(self, system_id):
        """Request a refresh of the rack

        Implementation of
        :py:class:`~provisioningserver.rpc.region.RequestRackRefresh`.
        """
        d = deferToDatabase(RackController.objects.get, system_id=system_id)
        d.addCallback(lambda rack: rack.start_refresh())
        return d

    @region.GetControllerType.responder
    def get_controller_type(self, system_id):
        """Get the type of the node specified by its system identifier.

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetControllerType`.
        """
        return deferToDatabase(nodes.get_controller_type, system_id)

    @region.GetTimeConfiguration.responder
    def get_time_configuration(self, system_id):
        """Get settings to use for configuring NTP for the given node.

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetTimeConfiguration`.
        """
        return deferToDatabase(nodes.get_time_configuration, system_id)

    @region.GetDNSConfiguration.responder
    def get_dns_configuration(self, system_id):
        """Get settings to use for configuring DNS.

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetDNSConfiguration`.
        """
        # For consistency `system_id` is passed, but at the moment it is not
        # used to customise the DNS configuration.
        d = deferToDatabase(get_trusted_networks)
        d.addCallback(lambda networks: {"trusted_networks": networks})
        return d

    @region.GetProxyConfiguration.responder
    def get_proxy_configuration(self, system_id):
        """Get settings to use for configuring proxy.

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetProxyConfiguration`.
        """
        # For consistency `system_id` is passed, but at the moment it is not
        # used to customise the proxy configuration.

        @transactional
        def get_from_db():
            allowed_subnets = Subnet.objects.filter(allow_proxy=True)
            cidrs = [subnet.cidr for subnet in allowed_subnets]
            configs = Config.objects.get_configs(
                ["maas_proxy_port", "prefer_v4_proxy", "enable_http_proxy"]
            )
            return {
                "enabled": configs["enable_http_proxy"],
                "port": configs["maas_proxy_port"],
                "allowed_cidrs": cidrs,
                "prefer_v4_proxy": configs["prefer_v4_proxy"],
            }

        return deferToDatabase(get_from_db)

    @region.GetSyslogConfiguration.responder
    def get_syslog_configuration(self, system_id):
        """Get settings to use for configuring syslog.

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetSyslogConfiguration`.
        """
        # For consistency `system_id` is passed, but at the moment it is not
        # used to customise the syslog configuration.

        @transactional
        def get_from_db():
            port = Config.objects.get_config("maas_syslog_port")

            promtail_enabled = Config.objects.get_config("promtail_enabled")
            promtail_port = (
                Config.objects.get_config("promtail_port")
                if promtail_enabled
                else None
            )

            return {
                "port": port,
                "promtail_port": promtail_port,
            }

        return deferToDatabase(get_from_db)

    @region.UpdateControllerState.responder
    def update_controller_state(self, system_id, scope, state):
        """Update state of the controller.

        The scope specificies which part of the state needs to be updated.
        """
        d = deferToDatabase(
            rackcontrollers.update_state, system_id, scope, state
        )
        return d.addCallback(lambda _: {})


@inlineCallbacks
def isLoopbackURL(url):
    """Checks if the specified URL refers to a loopback address.

    :return: True if the URL refers to the loopback interface, otherwise False.
    """
    if url is not None:
        if url.hostname is not None:
            is_loopback = yield deferToThread(
                resolves_to_loopback_address, url.hostname
            )
        else:
            # Empty URL == localhost.
            is_loopback = True
    else:
        # We need to pass is_loopback in, but it is only checked if url
        # is not None.  None is the "I don't know and you won't ask"
        # state for this boolean.
        is_loopback = None
    return is_loopback


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

    def __init__(self):
        super().__init__(auth_status=ConnectionAuthStatus())

    factory = None
    connid = None
    ident = None
    host = None
    hostIsRemote = False

    @asynchronous
    def initResponder(self, rack_controller):
        """Set up local connection identifiers for this RPC connection.

        Sets up connection identifiers, and adds the connection into the
        service and forwards to connection info to master.

        :param rack_controller: A RackController model object representing the
            remote rack controller.
        """
        self.ident = rack_controller.system_id
        self.factory.service._addConnectionFor(self.ident, self)
        # A local rack is treated differently to one that's remote.
        self.host = self.transport.getHost()
        self.hostIsRemote = isinstance(self.host, (IPv4Address, IPv6Address))
        # Only register the connection with the master when it's a valid
        # IPv4 or IPv6. Only time it is not an IPv4 or IPv6 address is
        # when mocking a connection.
        if self.hostIsRemote:
            return self.registerWithMaster()

    @asynchronous
    def registerWithMaster(self):
        # We need to handle the incoming name being an IPv6-form IPv4 address.
        # Assume that's the case, and ignore the error if it is not.
        try:
            # Convert the hostname to an IPAddress, and then coerce that to
            # dotted quad form, and from thence to a string.  If it works, we
            # had an IPv4 address.  We want the dotted quad form, since that
            # is what the region advertises.
            self.host.host = str(IPAddress(self.host.host).ipv4())
        except AddrConversionError:
            # If we got an AddressConversionError, it's not one we need to
            # convert.
            pass
        return self.factory.service.ipcWorker.rpcRegisterConnection(
            self.connid, self.ident, self.host.host, self.host.port
        )

    @inlineCallbacks
    def authenticateCluster(self):
        """Authenticate the cluster."""
        secret = yield get_shared_secret()
        message = urandom(16)  # 16 bytes of the finest.
        response = yield self.callRemote(cluster.Authenticate, message=message)
        salt, digest = response["salt"], response["digest"]
        digest_local = calculate_digest(secret, message, salt)
        returnValue(digest == digest_local)

    @region.RegisterRackController.responder
    @inlineCallbacks
    def register(
        self,
        system_id,
        hostname,
        interfaces,
        url,
        beacon_support=False,
        version=None,
    ):
        result = yield self._register(
            system_id,
            hostname,
            interfaces,
            url,
            version=version,
        )
        if beacon_support:
            # The remote supports beaconing, so acknowledge that.
            result["beacon_support"] = True
        if version:
            # The remote supports version checking, so reply to that.
            result["version"] = str(get_running_version())
        return result

    @inlineCallbacks
    def _register(
        self,
        system_id,
        hostname,
        interfaces,
        url,
        version=None,
    ):
        try:
            # Register, which includes updating interfaces.
            is_loopback = yield isLoopbackURL(url)
            rack_controller = yield deferToDatabase(
                rackcontrollers.register,
                system_id=system_id,
                hostname=hostname,
                interfaces=interfaces,
                url=url,
                is_loopback=is_loopback,
                version=version,
            )

            yield self.initResponder(rack_controller)
        except Exception:
            # Ensure we're not hanging onto this connection.
            self.factory.service._removeConnectionFor(self.ident, self)
            # Tell the logs about it.
            msg = (
                "Failed to register rack controller '%s' with the "
                "master. Connection will be dropped." % self.ident
            )
            log.err(None, msg)
            # Finally, tell the callers.
            raise exceptions.CannotRegisterRackController(msg)
        else:
            # Done registering the rack controller and connection.
            def get_cluster_certificate() -> bytes | None:
                try:
                    secret_manager = SecretManager()
                    raw_certificate_secret = (
                        secret_manager.get_composite_secret(
                            "cluster-certificate"
                        )
                    )
                    return fernet_encrypt_psk(
                        json.dumps(raw_certificate_secret)
                    )
                # This should happen only in some tests. We don't want to encrypt the certificate in every test that uses RPC:
                # this computation would be very expensive and would be pleonastic outside the dedicated unit tests for
                # this functionality.
                except SecretNotFound:
                    log.warn(
                        "The 'cluster-certificate' secret was not found. This should never happen outside the test suite."
                    )
                    return None

            encrypted_certificate = yield deferToDatabase(
                get_cluster_certificate
            )
            return {
                "encrypted_cluster_certificate": (
                    encrypted_certificate.decode("utf-8")
                    if encrypted_certificate
                    else None
                ),
                "system_id": self.ident,
                "uuid": GLOBAL_LABELS["maas_uuid"],
            }

    @inlineCallbacks
    def performHandshake(self):
        authenticated = yield self.authenticateCluster()
        peer = self.transport.getPeer()
        if isinstance(peer, (IPv4Address, IPv6Address)):
            client = f"{peer.host}:{peer.port}"
        else:
            client = peer.name
        if authenticated:
            log.msg("Rack controller authenticated from '%s'." % client)
        else:
            log.msg(
                "Rack controller FAILED authentication from '%s'; "
                "dropping connection." % client
            )
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
            log.msg(
                "Rack controller '%s' could not be authenticated; dropping "
                "connection. Check that /var/lib/maas/secret on the "
                "controller contains the correct shared key." % self.ident
            )
            if self.transport is not None:
                return self.transport.loseConnection()
            else:
                return

    def connectionMade(self):
        super().connectionMade()
        self.connid = str(uuid.uuid4())

        def trust_connection(authenticated: bool):
            if authenticated:
                log.info(
                    f"Connection {self.connid} is trusted and ready to respond/serve commands."
                )
            else:
                log.info(
                    f"Connection {self.connid} is NOT trusted and will be dropped."
                )
            # If the authentication process is successful, we allow to execute rpc calls from now on
            self.auth_status.set_is_authenticated(authenticated)

        if self.factory.service.running:
            return (
                self.performHandshake()
                .addCallback(trust_connection)
                .addErrback(self.handshakeFailed)
            )
        else:
            self.transport.loseConnection()

    def connectionLost(self, reason):
        if self.hostIsRemote:
            d = self.factory.service.ipcWorker.rpcUnregisterConnection(
                self.connid
            )
            d.addErrback(
                log.err, "Failed to unregister the connection with the master."
            )
        self.factory.service._removeConnectionFor(self.ident, self)
        if self.factory.service.rack_controller_is_disconnected(self.ident):
            log.msg("Rack controller '%s' disconnected." % self.ident)
        super().connectionLost(reason)


class RackClient(common.Client):
    """A `common.Client` for communication from region to rack."""

    # Currently the only calls that can be cached are the ones that take
    # no arguments. More work needs to be done to this class to handle
    # argument matching.
    cache_calls = [cluster.DescribePowerTypes]

    def __init__(self, connection, cache):
        super().__init__(connection)
        self.cache = cache

    def _getCallCache(self):
        """Return the call cache."""
        if "call_cache" not in self.cache:
            call_cache = {}
            self.cache["call_cache"] = call_cache
            return call_cache
        else:
            return self.cache["call_cache"]

    @PROMETHEUS_METRICS.record_call_latency(
        "maas_region_rack_rpc_call_latency",
        get_labels=lambda args, kwargs, retval: {"call": args[1].__name__},
    )
    @asynchronous
    def __call__(self, cmd, *args, **kwargs):
        """Call a remote RPC method.

        This caches calls to the rack controller that do not change value,
        unless the rack controller disconnects and reconnects to the region.
        """
        call_cache = self._getCallCache()
        if cmd not in self.cache_calls:
            return super().__call__(cmd, *args, **kwargs)
        if cmd in call_cache:
            # Call has already been made over this connection, just return
            # the original result.
            return succeed(copy.deepcopy(call_cache[cmd]))
        else:
            # First time this call has been made so cache the result so
            # so the next call over this connection will just be returned
            # from the cache.

            def cb_cache(result):
                call_cache[cmd] = result
                return result

            d = super().__call__(cmd, *args, **kwargs)
            d.addCallback(cb_cache)
            return d


class RegionService(service.Service):
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

    def __init__(self, ipcWorker):
        super().__init__()
        self.ipcWorker = ipcWorker
        self.endpoints = [
            [TCP6ServerEndpoint(reactor, port) for port in range(5250, 5260)]
        ]
        self.connections = defaultdict(set)
        self.connectionsCache = defaultdict(dict)
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

    def rack_controller_is_disconnected(self, ident):
        return len(self.connections[ident]) == 0

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
        self.connectionsCache.pop(connection, None)
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
            except Exception:
                if index == last:
                    raise
            else:
                returnValue(port)

    @asynchronous
    def startService(self):
        """Start listening on an ephemeral port."""
        super().startService()
        self.starting = defer.DeferredList(
            (
                self._bindFirst(endpoint_options, self.factory)
                for endpoint_options in self.endpoints
            ),
            consumeErrors=True,
        )

        def log_failure(failure):
            if failure.check(defer.CancelledError):
                log.msg("RegionServer start-up has been cancelled.")
            else:
                log.err(failure, "RegionServer start-up failed.")

        def report_to_master(result):
            return self.ipcWorker.rpcPublish(self.getPort())

        self.starting.addCallback(self._savePorts)
        self.starting.addCallback(report_to_master)
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
                except Exception:
                    log.err(None, "Failure when closing RPC connection.")
        yield super().stopService()

    @asynchronous(timeout=FOREVER)
    def getPort(self):
        """Return the TCP port number on which this service is listening.

        This considers ports (in the Twisted sense) for both IPv4 and IPv6.

        Returns `None` if the port has not yet been opened.
        """
        try:
            # Look for the first AF_INET{,6} port.
            port = next(
                port
                for port in self.ports
                if port.addressFamily in [AF_INET, AF_INET6]
            )
        except StopIteration:
            # There's no AF_INET (IPv4) or AF_INET6 (IPv6) port. As far as this
            # method goes, this means there's no connection.
            return None

        try:
            socket = port.socket
        except AttributeError:
            # When self._port.socket is not set it means there's no
            # connection.
            return None

        # IPv6 addreses have 4 elements, IPv4 addresses have 2.  We only care
        # about host and port, which are the first 2 elements either way.
        host, port = socket.getsockname()[:2]
        return port

    @asynchronous(timeout=FOREVER)
    def getClientFor(self, system_id, timeout=30):
        """Return a :class:`RackClient` for the specified rack controller.

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
                "available." % system_id,
                uuid=system_id,
            )

        def cb_client(connection):
            return RackClient(connection, self.connectionsCache[connection])

        return d.addCallbacks(cb_client, cancelled)

    @asynchronous(timeout=FOREVER)
    def getClientFromIdentifiers(self, identifiers, timeout=30):
        """Return a :class:`RackClient` for one of the specified
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
                "available." % ",".join(identifiers)
            )

        def cb_client(conns):
            connection = random.choice(conns)
            return RackClient(connection, self.connectionsCache[connection])

        return d.addCallbacks(cb_client, cancelled)

    @asynchronous(timeout=FOREVER)
    def getAllClients(self):
        """Return a list with one connection per rack controller."""

        def _client(connection):
            return RackClient(connection, self.connectionsCache[connection])

        return [
            _client(random.choice(list(connections)))
            for connections in self.connections.values()
            if len(connections) > 0
        ]

    @asynchronous(timeout=FOREVER)
    def getRandomClient(self):
        """Return a random connected :class:`RackClient`."""
        connections = list(self.connections.values())
        if len(connections) == 0:
            raise exceptions.NoConnectionsAvailable(
                "Unable to connect to any rack controller; no connections "
                "available."
            )
        else:
            connection = random.choice(connections)
            # The connection object is a set of RegionServer objects.
            # Make sure a sane set was returned.
            assert len(connection) > 0, "Connection set empty."
            connection = random.choice(list(connection))
            return RackClient(connection, self.connectionsCache[connection])
