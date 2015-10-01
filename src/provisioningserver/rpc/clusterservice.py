# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC implementation for clusters."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "ClusterClientService",
]

from functools import partial
import json
from os import urandom
import random
import re
from urlparse import urlparse

from apiclient.creds import convert_string_to_tuple
from apiclient.utils import ascii_url
from provisioningserver import concurrency
from provisioningserver.config import ClusterConfiguration
from provisioningserver.drivers import (
    ArchitectureRegistry,
    gen_power_types,
)
from provisioningserver.drivers.hardware.mscm import probe_and_enlist_mscm
from provisioningserver.drivers.hardware.msftocs import (
    probe_and_enlist_msftocs,
)
from provisioningserver.drivers.hardware.seamicro import (
    probe_seamicro15k_and_enlist,
)
from provisioningserver.drivers.hardware.ucsm import probe_and_enlist_ucsm
from provisioningserver.drivers.hardware.virsh import probe_virsh_and_enlist
from provisioningserver.drivers.hardware.vmware import probe_vmware_and_enlist
from provisioningserver.logger.log import get_maas_logger
from provisioningserver.network import discover_networks
from provisioningserver.power.change import maybe_change_power_state
from provisioningserver.power.query import get_power_state
from provisioningserver.rpc import (
    cluster,
    common,
    dhcp,
    exceptions,
    region,
)
from provisioningserver.rpc.boot_images import (
    import_boot_images,
    is_import_boot_images_running,
    list_boot_images,
)
from provisioningserver.rpc.common import RPCProtocol
from provisioningserver.rpc.dhcp import (
    create_host_maps,
    remove_host_maps,
)
from provisioningserver.rpc.interfaces import IConnection
from provisioningserver.rpc.monitors import (
    cancel_monitor,
    start_monitors,
)
from provisioningserver.rpc.osystems import (
    gen_operating_systems,
    get_os_release_title,
    get_preseed_data,
    validate_license_key,
)
from provisioningserver.rpc.tags import evaluate_tag
from provisioningserver.security import (
    calculate_digest,
    get_shared_secret_from_filesystem,
)
from provisioningserver.utils.network import find_ip_via_arp
from provisioningserver.utils.twisted import DeferredValue
from twisted import web
from twisted.application.internet import TimerService
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
)
from twisted.internet.endpoints import (
    connectProtocol,
    TCP4ClientEndpoint,
)
from twisted.internet.error import (
    ConnectError,
    ConnectionClosed,
)
from twisted.internet.threads import deferToThread
from twisted.protocols import amp
from twisted.python import log
from twisted.python.reflect import fullyQualifiedName
from twisted.web import http
import twisted.web.client
from twisted.web.client import getPage
from zope.interface import implementer

# From python-twisted 15+ changes the name of _URI to URI.
try:
    from twisted.web.client import _URI as URI
except ImportError:
    from twisted.web.client import URI


maaslog = get_maas_logger("rpc.cluster")


def catch_probe_and_enlist_error(name, failure):
    """Logs any errors when trying to probe and enlist a chassis."""
    maaslog.error(
        "Failed to probe and enlist %s nodes: %s",
        name, failure.getErrorMessage())
    return None


class Cluster(RPCProtocol):
    """The RPC protocol supported by a cluster controller.

    This can be used on the client or server end of a connection; once a
    connection is established, AMP is symmetric.
    """

    @cluster.Identify.responder
    def identify(self):
        """identify()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.Identify`.
        """
        with ClusterConfiguration.open() as config:
            return {b"ident": config.cluster_uuid}

    @cluster.Authenticate.responder
    def authenticate(self, message):
        secret = get_shared_secret_from_filesystem()
        salt = urandom(16)  # 16 bytes of high grade noise.
        digest = calculate_digest(secret, message, salt)
        return {"digest": digest, "salt": salt}

    @cluster.ListBootImages.responder
    def list_boot_images(self):
        """list_boot_images()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.ListBootImages`.
        """
        return {"images": list_boot_images()}

    @cluster.ListBootImagesV2.responder
    def list_boot_images_v2(self):
        """list_boot_images_v2()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.ListBootImagesV2`.
        """
        return {"images": list_boot_images()}

    @cluster.ImportBootImages.responder
    def import_boot_images(self, sources, http_proxy=None, https_proxy=None):
        """import_boot_images()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.ImportBootImages`.
        """
        get_proxy_url = lambda url: None if url is None else url.geturl()
        import_boot_images(
            sources, http_proxy=get_proxy_url(http_proxy),
            https_proxy=get_proxy_url(https_proxy))
        return {}

    @cluster.IsImportBootImagesRunning.responder
    def is_import_boot_images_running(self):
        """is_import_boot_images_running()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.IsImportBootImagesRunning`.
        """
        return {"running": is_import_boot_images_running()}

    @cluster.DescribePowerTypes.responder
    def describe_power_types(self):
        """describe_power_types()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.DescribePowerTypes`.
        """
        return {
            'power_types': list(gen_power_types()),
        }

    @cluster.ListSupportedArchitectures.responder
    def list_supported_architectures(self):
        return {
            'architectures': [
                {'name': arch.name, 'description': arch.description}
                for _, arch in ArchitectureRegistry
                ],
            }

    @cluster.ListOperatingSystems.responder
    def list_operating_systems(self):
        """list_operating_systems()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.ListOperatingSystems`.
        """
        return {"osystems": gen_operating_systems()}

    @cluster.GetOSReleaseTitle.responder
    def get_os_release_title(self, osystem, release):
        """get_os_release_title()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.GetOSReleaseTitle`.
        """
        return {"title": get_os_release_title(osystem, release)}

    @cluster.ValidateLicenseKey.responder
    def validate_license_key(self, osystem, release, key):
        """validate_license_key()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.ValidateLicenseKey`.
        """
        return {"is_valid": validate_license_key(osystem, release, key)}

    @cluster.GetPreseedData.responder
    def get_preseed_data(
            self, osystem, preseed_type, node_system_id, node_hostname,
            consumer_key, token_key, token_secret, metadata_url):
        """get_preseed_data()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.GetPreseedData`.
        """
        return {
            "data": get_preseed_data(
                osystem, preseed_type, node_system_id, node_hostname,
                consumer_key, token_key, token_secret, metadata_url),
        }

    @cluster.PowerOn.responder
    def power_on(self, system_id, hostname, power_type, context):
        """Turn a node on."""
        d = maybe_change_power_state(
            system_id, hostname, power_type, power_change='on',
            context=context)
        d.addCallback(lambda _: {})
        return d

    @cluster.PowerOff.responder
    def power_off(self, system_id, hostname, power_type, context):
        """Turn a node off."""
        d = maybe_change_power_state(
            system_id, hostname, power_type, power_change='off',
            context=context)
        d.addCallback(lambda _: {})
        return d

    @cluster.PowerQuery.responder
    def power_query(self, system_id, hostname, power_type, context):
        d = get_power_state(
            system_id, hostname, power_type, context=context)
        d.addCallback(lambda x: {'state': x})
        return d

    @cluster.ConfigureDHCPv4.responder
    def configure_dhcpv4(self, omapi_key, subnet_configs):
        server = dhcp.DHCPv4Server(omapi_key)
        d = concurrency.dhcp.run(
            deferToThread, dhcp.configure, server, subnet_configs)
        d.addCallback(lambda _: {})
        return d

    @cluster.ConfigureDHCPv6.responder
    def configure_dhcpv6(self, omapi_key, subnet_configs):
        server = dhcp.DHCPv6Server(omapi_key)
        d = concurrency.dhcp.run(
            deferToThread, dhcp.configure, server, subnet_configs)
        d.addCallback(lambda _: {})
        return d

    @cluster.CreateHostMaps.responder
    def create_host_maps(self, mappings, shared_key):
        d = concurrency.dhcp.run(
            deferToThread, create_host_maps, mappings, shared_key)
        d.addCallback(lambda _: {})
        return d

    @cluster.RemoveHostMaps.responder
    def remove_host_maps(self, ip_addresses, shared_key):
        # Note that the `ip_addresses` parameter is now a list of
        # IPs *and* MAC addresses. Prior to MAAS 1.9 it was a list of
        # IP addresses because that's what was used as the key for the host
        # mappings but we now use the MAC as the key in order to be able
        # to assign the same IP to two NICs. As a result, this code (the host
        # map removal code) has to deal with legacy host maps using the IP
        # as the key and host maps with the MAC as the key.
        d = concurrency.dhcp.run(
            deferToThread, remove_host_maps, ip_addresses, shared_key)
        d.addCallback(lambda _: {})
        return d

    @cluster.StartMonitors.responder
    def start_monitors(self, monitors):
        start_monitors(monitors)
        return {}

    @cluster.CancelMonitor.responder
    def cancel_timer(self, id):
        cancel_monitor(id)
        return {}

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
            return tls.get_tls_parameters_for_cluster()

    @cluster.EvaluateTag.responder
    def evaluate_tag(self, tag_name, tag_definition, tag_nsmap, credentials):
        """evaluate_tag()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.EvaluateTag`.
        """
        # It's got to run in a thread because it does blocking IO.
        d = deferToThread(
            evaluate_tag, tag_name, tag_definition,
            # Transform tag_nsmap into a format that LXML likes.
            {entry["prefix"]: entry["uri"] for entry in tag_nsmap},
            # Parse the credential string into a 3-tuple.
            convert_string_to_tuple(credentials))
        return d.addCallback(lambda _: {})

    @cluster.AddVirsh.responder
    def add_virsh(self, user, poweraddr, password, prefix_filter, accept_all):
        """add_virsh()

        Implementation of :py:class:`~provisioningserver.rpc.cluster.AddVirsh`.
        """
        d = deferToThread(
            probe_virsh_and_enlist,
            user, poweraddr, password, prefix_filter, accept_all)
        d.addErrback(partial(catch_probe_and_enlist_error, "virsh"))
        return {}

    @cluster.AddSeaMicro15k.responder
    def add_seamicro15k(self, user, mac, username,
                        password, power_control, accept_all):
        """add_virsh()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.AddSeaMicro15k`.
        """
        ip = find_ip_via_arp(mac)
        if ip is not None:
            d = deferToThread(
                probe_seamicro15k_and_enlist,
                user, ip, username, password,
                power_control=power_control, accept_all=accept_all)
            d.addErrback(
                partial(catch_probe_and_enlist_error, "SeaMicro 15000"))
        else:
            message = "Couldn't find IP address for MAC %s" % mac
            maaslog.warning(message)
            raise exceptions.NoIPFoundForMACAddress(message)
        return {}

    @cluster.AddVMware.responder
    def add_vmware(self, user, host, username, password, port, protocol,
                   prefix_filter, accept_all):
        """add_vmware()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.AddVMware`.
        """
        d = deferToThread(
            probe_vmware_and_enlist,
            user, host, username, password,
            port=port, protocol=protocol, prefix_filter=prefix_filter,
            accept_all=accept_all)
        d.addErrback(
            partial(catch_probe_and_enlist_error, "VMware"))
        return {}

    @cluster.EnlistNodesFromMSCM.responder
    def enlist_nodes_from_mscm(self, user, host, username,
                               password, accept_all):
        """enlist_nodes_from_mscm()

        Implemention of
        :py:class:`~provisioningserver.rpc.cluster.EnlistNodesFromMSCM`.
        """
        d = deferToThread(
            probe_and_enlist_mscm,
            user, host, username, password, accept_all)
        d.addErrback(partial(catch_probe_and_enlist_error, "Moonshot"))
        return {}

    @cluster.EnlistNodesFromUCSM.responder
    def enlist_nodes_from_ucsm(self, user, url, username,
                               password, accept_all):
        """enlist_nodes_from_ucsm()

        Implemention of
        :py:class:`~provisioningserver.rpc.cluster.EnlistNodesFromUCSM`.
        """
        d = deferToThread(
            probe_and_enlist_ucsm,
            user, url, username, password, accept_all)
        d.addErrback(partial(catch_probe_and_enlist_error, "UCS"))
        return {}

    @cluster.EnlistNodesFromMicrosoftOCS.responder
    def enlist_nodes_from_msftocs(self, user, ip, port, username,
                                  password, accept_all):
        """enlist_nodes_from_msftocs()

        Implemention of
        :py:class:
          `~provisioningserver.rpc.cluster.EnlistNodesFromMicrosoftOCS`.
        """
        d = deferToThread(
            probe_and_enlist_msftocs,
            user, ip, port, username, password, accept_all)
        d.addErrback(partial(catch_probe_and_enlist_error, "MicrosoftOCS"))
        return {}


@implementer(IConnection)
class ClusterClient(Cluster):
    """The RPC protocol supported by a cluster controller, client version.

    This works hand-in-hand with ``ClusterClientService``, maintaining
    the latter's `connections` map.

    :ivar address: The `(host, port)` of the remote endpoint.

    :ivar eventloop: The event-loop this client is related to.

    :ivar service: A reference to the :class:`ClusterClientService` that
        made self.

    :ivar authenticated: A py:class:`DeferredValue` that will be set when the
        region has been authenticated. If the region has been authenticated,
        this will be ``True``, otherwise it will be ``False``. If there was an
        error, it will return a :py:class:`twisted.python.failure.Failure` via
        errback.

    :ivar ready: A py:class:`DeferredValue` that will be set when this
        connection is up and has performed authentication on the region. If
        everything has gone smoothly it will be set to the name of the
        event-loop connected to, otherwise it will be set to: `RuntimeError`
        if the client service is not running; `KeyError` if there's already a
        live connection for this event-loop; or `AuthenticationFailed` if,
        guess, the authentication failed.
    """

    address = None
    eventloop = None
    service = None

    def __init__(self, address, eventloop, service):
        super(ClusterClient, self).__init__()
        self.address = address
        self.eventloop = eventloop
        self.service = service
        # Events for this protocol's life-cycle.
        self.authenticated = DeferredValue()
        self.ready = DeferredValue()

    @property
    def ident(self):
        """The ident of the remote event-loop."""
        return self.eventloop

    @inlineCallbacks
    def authenticateRegion(self):
        """Authenticate the region."""
        secret = get_shared_secret_from_filesystem()
        message = urandom(16)  # 16 bytes of the finest.
        response = yield self.callRemote(
            region.Authenticate, message=message)
        salt, digest = response["salt"], response["digest"]
        digest_local = calculate_digest(secret, message, salt)
        returnValue(digest == digest_local)

    def registerWithRegion(self):
        with ClusterConfiguration.open() as config:
            uuid = config.cluster_uuid
            url = config.maas_url

        networks = discover_networks()

        def cb_register(_):
            log.msg(
                "Cluster '%s' registered (via %s)."
                % (uuid, self.eventloop))
            return True

        def eb_register(failure):
            failure.trap(exceptions.CannotRegisterCluster)
            log.msg(
                "Cluster '%s' REJECTED by the region (via %s)."
                % (uuid, self.eventloop))
            return False

        d = self.callRemote(
            region.Register, uuid=uuid, networks=networks,
            url=urlparse(url))
        return d.addCallbacks(cb_register, eb_register)

    @inlineCallbacks
    def performHandshake(self):
        d_authenticate = self.authenticateRegion()
        self.authenticated.observe(d_authenticate)
        authenticated = yield d_authenticate

        if authenticated:
            log.msg("Event-loop '%s' authenticated." % self.ident)
            registered = yield self.registerWithRegion()
            if registered:
                self.service.connections[self.eventloop] = self
                self.ready.set(self.eventloop)
            else:
                self.transport.loseConnection()
                self.ready.fail(
                    exceptions.RegistrationFailed(
                        "Event-loop '%s' rejected registration."
                        % self.ident))
        else:
            log.msg(
                "Event-loop '%s' FAILED authentication; "
                "dropping connection." % self.ident)
            self.transport.loseConnection()
            self.ready.fail(
                exceptions.AuthenticationFailed(
                    "Event-loop '%s' failed authentication."
                    % self.eventloop))

    def handshakeSucceeded(self, result):
        """The handshake (identify and authenticate) succeeded.

        This does *NOT* mean that the region was successfully authenticated,
        merely that the process of authentication did not encounter an error.
        """

    def handshakeFailed(self, failure):
        """The handshake (identify and authenticate) failed."""
        if failure.check(ConnectionClosed):
            # There has been a disconnection, clean or otherwise. There's
            # nothing we can do now, so do nothing. The reason will have been
            # logged elsewhere.
            self.ready.fail(failure)
        else:
            log.err(
                failure, "Event-loop '%s' handshake failed; "
                "dropping connection." % self.ident)
            self.transport.loseConnection()
            self.ready.fail(failure)

    def connectionMade(self):
        super(ClusterClient, self).connectionMade()

        if not self.service.running:
            log.msg(
                "Event-loop '%s' will be disconnected; the cluster's "
                "client service is not running." % self.ident)
            self.transport.loseConnection()
            self.authenticated.set(None)
            self.ready.fail(RuntimeError("Service not running."))
        elif self.eventloop in self.service.connections:
            log.msg(
                "Event-loop '%s' is already connected; "
                "dropping connection." % self.ident)
            self.transport.loseConnection()
            self.authenticated.set(None)
            self.ready.fail(KeyError(
                "Event-loop '%s' already connected." % self.eventloop))
        else:
            return self.performHandshake().addCallbacks(
                self.handshakeSucceeded, self.handshakeFailed)

    def connectionLost(self, reason):
        if self.eventloop in self.service.connections:
            if self.service.connections[self.eventloop] is self:
                del self.service.connections[self.eventloop]
        super(ClusterClient, self).connectionLost(reason)

    @inlineCallbacks
    def secureConnection(self):
        yield self.callRemote(amp.StartTLS, **self.get_tls_parameters())

        # For some weird reason (it's mentioned in Twisted's source),
        # TLS negotiation does not complete until we do something with
        # the connection. Here we check that the remote event-loop is
        # who we expected it to be.
        response = yield self.callRemote(region.Identify)
        remote_name = response.get("ident")
        if remote_name != self.eventloop:
            log.msg(
                "The remote event-loop identifies itself as %s, but "
                "%s was expected." % (remote_name, self.eventloop))
            self.transport.loseConnection()
            return

        # We should now have a full set of parameters for the transport.
        log.msg("Host certificate: %r" % self.hostCertificate)
        log.msg("Peer certificate: %r" % self.peerCertificate)


class PatchedURI(URI):

    @classmethod
    def fromBytes(cls, uri, defaultPort=None):
        """Patched replacement for `twisted.web.client._URI.fromBytes`.

        The Twisted version of this function breaks when you give it a URL
        whose netloc is based on an IPv6 address.
        """
        uri = uri.strip()
        scheme, netloc, path, params, query, fragment = http.urlparse(uri)

        if defaultPort is None:
            scheme_ports = {
                'https': 443,
                'http': 80,
                }
            defaultPort = scheme_ports.get(scheme, 80)

        if '[' in netloc:
            # IPv6 address.  This is complicated.
            parsed_netloc = re.match(
                '\\[(?P<host>[0-9A-Fa-f:.]+)\\]([:](?P<port>[0-9]+))?$',
                netloc)
            host, port = parsed_netloc.group('host', 'port')
        elif ':' in netloc:
            # IPv4 address or hostname, with port spec.  This is easy.
            host, port = netloc.split(':')
        else:
            # IPv4 address or hostname, without port spec.  This is trivial.
            host = netloc
            port = None

        if port is None:
            port = defaultPort
        try:
            port = int(port)
        except ValueError:
            port = defaultPort

        return cls(scheme, netloc, host, port, path, params, query, fragment)


class ClusterClientService(TimerService, object):
    """A cluster controller RPC client service.

    This is a service - in the Twisted sense - that connects to a set of
    remote AMP endpoints. The endpoints are obtained from a view in the
    region controller and periodically refreshed; this list is used to
    update the connections maintained in this service.

    :ivar connections: A mapping of eventloop names to protocol
        instances connected to it.
    :ivar time_started: Records the time that `startService` was last called,
        or `None` if it hasn't yet.
    """

    INTERVAL_LOW = 2  # seconds.
    INTERVAL_MID = 10  # seconds.
    INTERVAL_HIGH = 30  # seconds.

    time_started = None

    def __init__(self, reactor):
        super(ClusterClientService, self).__init__(
            self._calculate_interval(None, None), self.update)
        self.connections = {}
        self.clock = reactor

        # XXX jtv 2014-09-23, bug=1372767: Fix
        # twisted.web.client._URI.fromBytes to handle IPv6 addresses.
        # A `getPage` call on Twisted's web client breaks if you give it a
        # URL with an IPv6 address, at the point where `_makeGetterFactory`
        # calls `fromBytes`.  That last function assumes that a colon can only
        # occur in the URL's netloc portion as part of a port specification.
        if hasattr(twisted.web.client, "_URI"):
            twisted.web.client._URI = PatchedURI
        else:
            twisted.web.client.URI = PatchedURI

    def startService(self):
        self.time_started = self.clock.seconds()
        super(ClusterClientService, self).startService()

    def getClient(self):
        """Returns a :class:`common.Client` connected to a region.

        The client is chosen at random.

        :raises: :py:class:`~.exceptions.NoConnectionsAvailable` when
            there are no open connections to a region controller.
        """
        conns = list(self.connections.viewvalues())
        if len(conns) == 0:
            raise exceptions.NoConnectionsAvailable()
        else:
            return common.Client(random.choice(conns))

    @inlineCallbacks
    def update(self):
        """Refresh outgoing connections.

        This obtains a list of endpoints from the region then connects
        to new ones and drops connections to those no longer used.
        """
        try:
            info_url = self._get_rpc_info_url()
            info = yield self._fetch_rpc_info(info_url)
            eventloops = info["eventloops"]
            if eventloops is None:
                # This means that the region process we've just asked about
                # RPC event-loop endpoints is not running the RPC advertising
                # service. It could be just starting up for example.
                log.msg("Region is not advertising RPC endpoints.")
            else:
                yield self._update_connections(eventloops)
        except ConnectError as error:
            self._update_interval(None, len(self.connections))
            log.msg(
                "Region not available: %s (While requesting RPC info at %s)."
                % (error, info_url))
        except:
            self._update_interval(None, len(self.connections))
            log.err()
        else:
            if eventloops is None:
                # The advertising service on the region was not running yet.
                self._update_interval(None, len(self.connections))
            else:
                self._update_interval(len(eventloops), len(self.connections))

    @staticmethod
    def _get_rpc_info_url():
        """Return the URL to the RPC infomation page on the region."""
        with ClusterConfiguration.open() as config:
            url = urlparse(config.maas_url)
            url = url._replace(path="%s/rpc/" % url.path.rstrip("/"))
            url = url.geturl()
        return ascii_url(url)

    @classmethod
    def _fetch_rpc_info(cls, url):

        def catch_503_error(failure):
            # Catch `twisted.web.error.Error` if has a 503 status code. That
            # means the region is not all the way up. Ignore the error as this
            # service will try again after the calculated interval.
            failure.trap(web.error.Error)
            if failure.value.status != "503":
                failure.raiseException()
            else:
                return {"eventloops": None}

        d = getPage(url, agent=fullyQualifiedName(cls))
        d.addCallback(json.loads)
        d.addErrback(catch_503_error)
        return d

    def _calculate_interval(self, num_eventloops, num_connections):
        """Calculate the update interval.

        The interval is `INTERVAL_LOW` seconds when there are no
        connections, so that this can quickly obtain its first
        connection.

        The interval is also `INTERVAL_LOW` for a time after the service
        starts. This helps to get everything connected quickly when the
        cluster is started at a similar time to the region.

        The interval changes to `INTERVAL_MID` seconds when there are
        some connections, but fewer than there are event-loops.

        After that it drops back to `INTERVAL_HIGH` seconds.
        """
        if self.time_started is not None:
            time_running = self.clock.seconds() - self.time_started
            if time_running < self.INTERVAL_HIGH:
                # This service has recently started; keep trying regularly.
                return self.INTERVAL_LOW

        if num_eventloops is None:
            # The region is not available; keep trying regularly.
            return self.INTERVAL_LOW
        elif num_eventloops == 0:
            # The region is coming up; keep trying regularly.
            return self.INTERVAL_LOW
        elif num_connections == 0:
            # No connections to the region; keep trying regularly.
            return self.INTERVAL_LOW
        elif num_connections < num_eventloops:
            # Some connections to the region, but not to all event
            # loops; keep updating reasonably frequently.
            return self.INTERVAL_MID
        else:
            # Fully connected to the region; update every so often.
            return self.INTERVAL_HIGH

    def _update_interval(self, num_eventloops, num_connections):
        """Change the update interval."""
        self._loop.interval = self.step = self._calculate_interval(
            num_eventloops, num_connections)

    @inlineCallbacks
    def _update_connections(self, eventloops):
        """Update the persistent connections to the region.

        For each event-loop, ensure that there is (a) a connection
        established and that (b) that connection corresponds to one of
        the endpoints declared. If not (a), attempt to connect to each
        endpoint in turn. If not (b), immediately drop the connection
        and proceed as if not (a).

        For each established connection to an event-loop, check that
        it's still in the list of event-loops to which this cluster
        should connect. If not, immediately drop the connection.
        """
        # Ensure that the event-loop addresses are tuples so that
        # they'll work as dictionary keys.
        eventloops = {
            name: [tuple(address) for address in addresses]
            for name, addresses in eventloops.iteritems()
        }
        # Drop connections to event-loops that no longer include one of
        # this cluster's established connections among its advertised
        # endpoints. This is most likely to have happened because of
        # network reconfiguration on the machine hosting the event-loop,
        # and so the connection may have dropped already, but there's
        # nothing wrong with a bit of belt-and-braces engineering
        # between consenting adults.
        for eventloop, addresses in eventloops.iteritems():
            if eventloop in self.connections:
                connection = self.connections[eventloop]
                if connection.address not in addresses:
                    yield self._drop_connection(connection)
        # Create new connections to event-loops that the cluster does
        # not yet have a connection to. Try each advertised endpoint
        # (address) in turn until one of them bites.
        for eventloop, addresses in eventloops.iteritems():
            if eventloop not in self.connections:
                for address in addresses:
                    try:
                        yield self._make_connection(eventloop, address)
                    except ConnectError as error:
                        host, port = address
                        log.msg("Event-loop %s (%s:%d): %s" % (
                            eventloop, host, port, error))
                    except:
                        log.err()
                    else:
                        break
        # Remove connections to event-loops that are no longer
        # advertised by the RPC info view. Most likely this means that
        # the process in which the event-loop is no longer running, but
        # it could be an indicator of a heavily loaded machine, or a
        # fault. In any case, it seems to make sense to disconnect.
        for eventloop in self.connections:
            if eventloop not in eventloops:
                connection = self.connections[eventloop]
                yield self._drop_connection(connection)

    def _make_connection(self, eventloop, address):
        """Connect to `eventloop` at `address`."""
        endpoint = TCP4ClientEndpoint(self.clock, *address)
        protocol = ClusterClient(address, eventloop, self)
        return connectProtocol(endpoint, protocol)

    def _drop_connection(self, connection):
        """Drop the given `connection`."""
        return connection.transport.loseConnection()
