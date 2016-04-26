# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC implementation for clusters."""

__all__ = [
    "ClusterClientService",
]

from functools import partial
import json
from os import urandom
import random
import re
from socket import gethostname
from urllib.parse import urlparse

from apiclient.creds import convert_string_to_tuple
from apiclient.utils import ascii_url
from provisioningserver import concurrency
from provisioningserver.config import ClusterConfiguration
from provisioningserver.drivers import (
    ArchitectureRegistry,
    gen_power_types,
)
from provisioningserver.drivers.hardware.seamicro import (
    probe_seamicro15k_and_enlist,
)
from provisioningserver.drivers.hardware.ucsm import probe_and_enlist_ucsm
from provisioningserver.drivers.hardware.virsh import probe_virsh_and_enlist
from provisioningserver.drivers.hardware.vmware import probe_vmware_and_enlist
from provisioningserver.drivers.power import power_drivers_by_name
from provisioningserver.drivers.power.mscm import probe_and_enlist_mscm
from provisioningserver.drivers.power.msftocs import probe_and_enlist_msftocs
from provisioningserver.logger.log import get_maas_logger
from provisioningserver.networks import get_interfaces_definition
from provisioningserver.power.change import maybe_change_power_state
from provisioningserver.power.query import (
    get_power_state,
    report_power_state,
)
from provisioningserver.refresh import (
    get_architecture,
    get_os_release,
    get_swap_size,
    refresh,
)
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
from provisioningserver.rpc.interfaces import IConnection
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
from provisioningserver.service_monitor import service_monitor
from provisioningserver.utils.env import (
    get_maas_id,
    set_maas_id,
)
from provisioningserver.utils.twisted import (
    DeferredValue,
    synchronous,
)
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
        ident = get_maas_id()
        if ident is None:
            ident = ""
        return {"ident": ident}

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
        d = report_power_state(d, system_id, hostname)
        d.addCallback(lambda x: {'state': x})
        return d

    @cluster.PowerDriverCheck.responder
    def power_driver_check(self, power_type):
        """Return a list of missing power driver packages, if any."""
        driver = power_drivers_by_name.get(power_type)
        if driver is None:
            raise exceptions.UnknownPowerType(
                "No driver found for power type '%s'" % power_type)
        return {"missing_packages": driver.detect_missing_packages()}

    @cluster.ConfigureDHCPv4.responder
    def configure_dhcpv4(
            self, omapi_key, failover_peers, shared_networks,
            hosts, interfaces, global_dhcp_snippets=[]):
        server = dhcp.DHCPv4Server(omapi_key)
        d = concurrency.dhcp.run(
            dhcp.configure, server,
            failover_peers, shared_networks, hosts, interfaces,
            global_dhcp_snippets)
        d.addCallback(lambda _: {})
        return d

    @cluster.ValidateDHCPv4Config.responder
    def validate_dhcpv4_config(
            self, omapi_key, failover_peers, shared_networks,
            hosts, interfaces, global_dhcp_snippets=[]):
        server = dhcp.DHCPv4Server(omapi_key)

        d = deferToThread(
            dhcp.validate, server,
            failover_peers, shared_networks, hosts, interfaces,
            global_dhcp_snippets)
        d.addCallback(lambda ret: {'errors': ret} if ret is not None else {})
        return d

    @cluster.ConfigureDHCPv6.responder
    def configure_dhcpv6(
            self, omapi_key, failover_peers, shared_networks,
            hosts, interfaces, global_dhcp_snippets=[]):
        server = dhcp.DHCPv6Server(omapi_key)
        d = concurrency.dhcp.run(
            dhcp.configure, server,
            failover_peers, shared_networks, hosts, interfaces,
            global_dhcp_snippets)
        d.addCallback(lambda _: {})
        return d

    @cluster.ValidateDHCPv6Config.responder
    def validate_dhcpv6_config(
            self, omapi_key, failover_peers, shared_networks,
            hosts, interfaces, global_dhcp_snippets=[]):
        server = dhcp.DHCPv6Server(omapi_key)

        d = deferToThread(
            dhcp.validate, server,
            failover_peers, shared_networks, hosts, interfaces,
            global_dhcp_snippets)
        d.addCallback(lambda ret: {'errors': ret} if ret is not None else {})
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
            return tls.get_tls_parameters_for_cluster()

    @cluster.EvaluateTag.responder
    def evaluate_tag(
            self, tag_name, tag_definition, tag_nsmap, credentials, nodes):
        """evaluate_tag()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.EvaluateTag`.
        """
        # It's got to run in a thread because it does blocking IO.
        d = deferToThread(
            evaluate_tag, nodes, tag_name, tag_definition,
            # Transform tag_nsmap into a format that LXML likes.
            {entry["prefix"]: entry["uri"] for entry in tag_nsmap},
            # Parse the credential string into a 3-tuple.
            convert_string_to_tuple(credentials))
        return d.addCallback(lambda _: {})

    @cluster.RefreshRackControllerInfo.responder
    def refresh(self, system_id, consumer_key, token_key, token_secret):
        """RefreshRackControllerInfo()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.RefreshRackControllerInfo`.
        """
        d = deferToThread(
            refresh, system_id, consumer_key, token_key, token_secret)
        d.addErrback(log.err, "Failed to refresh the rack controller.")

        @synchronous
        def perform_refresh():
            architecture = get_architecture()
            os_release = get_os_release()
            swap_size = get_swap_size()
            interfaces, _ = get_interfaces_definition()
            return architecture, os_release, swap_size, interfaces

        def cb_result(result):
            architecture, os_release, swap_size, interfaces = result
            if 'ID' in os_release:
                osystem = os_release['ID']
            elif 'NAME' in os_release:
                osystem = os_release['NAME']
            else:
                osystem = ''
            if 'UBUNTU_CODENAME' in os_release:
                distro_series = os_release['UBUNTU_CODENAME']
            elif 'VERSION_ID' in os_release:
                distro_series = os_release['VERSION_ID']
            else:
                distro_series = ''
            return {
                'architecture': architecture,
                'osystem': osystem,
                'distro_series': distro_series,
                'swap_size': swap_size,
                'interfaces': interfaces
            }

        d = deferToThread(perform_refresh)
        d.addCallback(cb_result)
        return d

    @cluster.AddChassis.responder
    def add_chassis(
            self, user, chassis_type, hostname, username=None, password=None,
            accept_all=False, domain=None, prefix_filter=None,
            power_control=None, port=None, protocol=None):
        """AddChassis()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.AddChassis`.
        """
        if chassis_type in ('virsh', 'powerkvm'):
            d = deferToThread(
                probe_virsh_and_enlist,
                user, hostname, password, prefix_filter, accept_all,
                domain)
            d.addErrback(partial(catch_probe_and_enlist_error, "virsh"))
        elif chassis_type == 'vmware':
            d = deferToThread(
                probe_vmware_and_enlist,
                user, hostname, username, password, port, protocol,
                prefix_filter, accept_all, domain)
            d.addErrback(partial(catch_probe_and_enlist_error, "VMware"))
        elif chassis_type == 'seamicro15k':
            d = deferToThread(
                probe_seamicro15k_and_enlist,
                user, hostname, username, password, power_control, accept_all,
                domain)
            d.addErrback(
                partial(catch_probe_and_enlist_error, "SeaMicro 15000"))
        elif chassis_type == 'mscm':
            d = deferToThread(
                probe_and_enlist_mscm, user, hostname, username, password,
                accept_all, domain)
            d.addErrback(partial(catch_probe_and_enlist_error, "Moonshot"))
        elif chassis_type == 'msftocs':
            d = deferToThread(
                probe_and_enlist_msftocs, user, hostname, port, username,
                password, accept_all, domain)
            d.addErrback(partial(catch_probe_and_enlist_error, "MicrosoftOCS"))
        elif chassis_type == 'ucsm':
            d = deferToThread(
                probe_and_enlist_ucsm, user, hostname, username, password,
                accept_all, domain)
            d.addErrback(partial(catch_probe_and_enlist_error, "UCS"))
        else:
            message = "Unknown chassis type %s" % chassis_type
            maaslog.error(message)
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
        self.localIdent = None

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

    def registerRackWithRegion(self):
        # Grab the URL the rack uses to communicate to the region API along
        # with the cluster UUID. It is possible that the cluster UUID is blank.
        with ClusterConfiguration.open() as config:
            url = config.maas_url
            cluster_uuid = config.cluster_uuid

        # Grab the set system_id if already set for this controller.
        system_id = get_maas_id()
        if system_id is None:
            # Cannot send None over RPC when the system_id is not set.
            system_id = ''

        # Gather the interface definition and hostname.
        interfaces, _ = get_interfaces_definition()
        hostname = gethostname().split('.')[0]

        def cb_register(data):
            self.localIdent = data["system_id"]
            set_maas_id(self.localIdent)
            log.msg(
                "Rack controller '%s' registered (via %s)."
                % (self.localIdent, self.eventloop))
            return True

        def eb_register(failure):
            failure.trap(exceptions.CannotRegisterRackController)
            log.msg(
                "Rack controller REJECTED by the region (via %s)."
                % self.eventloop)
            return False

        d = self.callRemote(
            region.RegisterRackController, system_id=system_id,
            hostname=hostname, interfaces=interfaces, url=urlparse(url),
            nodegroup_uuid=cluster_uuid)
        return d.addCallbacks(cb_register, eb_register)

    @inlineCallbacks
    def performHandshake(self):
        d_authenticate = self.authenticateRegion()
        self.authenticated.observe(d_authenticate)
        authenticated = yield d_authenticate

        if authenticated:
            log.msg("Event-loop '%s' authenticated." % self.ident)
            registered = yield self.registerRackWithRegion()
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
        self.service.remove_connection(self.eventloop, self)
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
            scheme_ports = {b'https': 443, b'http': 80}
            defaultPort = scheme_ports.get(scheme, 80)

        if b'[' in netloc:
            # IPv6 address.  This is complicated.
            parsed_netloc = re.match(
                b'\\[(?P<host>[0-9A-Fa-f:.]+)\\]([:](?P<port>[0-9]+))?$',
                netloc)
            host, port = parsed_netloc.group('host', 'port')
        elif b':' in netloc:
            # IPv4 address or hostname, with port spec.  This is easy.
            host, port = netloc.split(b':')
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
        conns = list(self.connections.values())
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
        d.addCallback(lambda data: data.decode("ascii"))
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
            for name, addresses in eventloops.items()
        }
        # Drop connections to event-loops that no longer include one of
        # this cluster's established connections among its advertised
        # endpoints. This is most likely to have happened because of
        # network reconfiguration on the machine hosting the event-loop,
        # and so the connection may have dropped already, but there's
        # nothing wrong with a bit of belt-and-braces engineering
        # between consenting adults.
        for eventloop, addresses in eventloops.items():
            if eventloop in self.connections:
                connection = self.connections[eventloop]
                if connection.address not in addresses:
                    yield self._drop_connection(connection)
        # Create new connections to event-loops that the cluster does
        # not yet have a connection to. Try each advertised endpoint
        # (address) in turn until one of them bites.
        for eventloop, addresses in eventloops.items():
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

    def remove_connection(self, eventloop, connection):
        """Remove the connection from the tracked connections.

        If this is the last connection that was keeping rackd connected to
        a regiond then dhcpd and dhcpd6 services will be turned off.
        """
        if eventloop in self.connections:
            if self.connections[eventloop] is connection:
                del self.connections[eventloop]
        if len(self.connections) == 0:
            # No connections to any region. DHCP should be turned off.
            stopping_services = []
            dhcp_v4 = service_monitor.getServiceByName("dhcpd")
            if dhcp_v4.is_on():
                dhcp_v4.off()
                stopping_services.append("dhcpd")
            dhcp_v6 = service_monitor.getServiceByName("dhcpd6")
            if dhcp_v6.is_on():
                dhcp_v6.off()
                stopping_services.append("dhcpd6")
            if len(stopping_services) > 0:
                maaslog.error(
                    "Lost all connections to region controllers. "
                    "Stopping service(s) %s." % ",".join(stopping_services))
                service_monitor.ensureServices()
