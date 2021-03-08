# Copyright 2014-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC implementation for clusters."""


from functools import partial
import json
from operator import itemgetter
import os
from os import urandom
import random
from socket import AF_INET, AF_INET6, gethostname
import sys
from urllib.parse import urlparse

from netaddr import IPAddress
from twisted import web
from twisted.application.internet import TimerService
from twisted.internet import reactor
from twisted.internet.defer import (
    CancelledError,
    Deferred,
    DeferredList,
    inlineCallbacks,
    maybeDeferred,
    returnValue,
)
from twisted.internet.endpoints import connectProtocol, TCP6ClientEndpoint
from twisted.internet.error import ConnectError, ConnectionClosed, ProcessDone
from twisted.internet.threads import deferToThread
from twisted.protocols import amp
from twisted.python.reflect import fullyQualifiedName
from twisted.web.client import _ReadBodyProtocol, Agent
from twisted.web.http_headers import Headers
from zope.interface import implementer

from apiclient.creds import convert_string_to_tuple
from apiclient.utils import ascii_url
from provisioningserver import concurrency
from provisioningserver.config import ClusterConfiguration, is_dev_environment
from provisioningserver.drivers import ArchitectureRegistry
from provisioningserver.drivers.hardware.seamicro import (
    probe_seamicro15k_and_enlist,
)
from provisioningserver.drivers.hardware.ucsm import probe_and_enlist_ucsm
from provisioningserver.drivers.hardware.virsh import probe_virsh_and_enlist
from provisioningserver.drivers.hardware.vmware import probe_vmware_and_enlist
from provisioningserver.drivers.nos.registry import NOSDriverRegistry
from provisioningserver.drivers.power.mscm import probe_and_enlist_mscm
from provisioningserver.drivers.power.msftocs import probe_and_enlist_msftocs
from provisioningserver.drivers.power.proxmox import probe_proxmox_and_enlist
from provisioningserver.drivers.power.recs import probe_and_enlist_recs
from provisioningserver.drivers.power.registry import PowerDriverRegistry
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.path import get_maas_data_path
from provisioningserver.prometheus.metrics import set_global_labels
from provisioningserver.refresh import refresh
from provisioningserver.rpc import (
    cluster,
    common,
    dhcp,
    exceptions,
    pods,
    region,
)
from provisioningserver.rpc.boot_images import (
    import_boot_images,
    is_import_boot_images_running,
    list_boot_images,
)
from provisioningserver.rpc.common import Ping, RPCProtocol
from provisioningserver.rpc.exceptions import CannotConfigureDHCP
from provisioningserver.rpc.interfaces import IConnectionToRegion
from provisioningserver.rpc.osystems import (
    gen_operating_systems,
    get_os_release_title,
    get_preseed_data,
    validate_license_key,
)
from provisioningserver.rpc.power import (
    get_power_state,
    maybe_change_power_state,
)
from provisioningserver.rpc.tags import evaluate_tag
from provisioningserver.security import (
    calculate_digest,
    get_shared_secret_filesystem_path,
    get_shared_secret_from_filesystem,
)
from provisioningserver.service_monitor import service_monitor
from provisioningserver.utils import sudo
from provisioningserver.utils.env import get_maas_id, set_maas_id
from provisioningserver.utils.fs import get_maas_common_command, NamedLock
from provisioningserver.utils.network import (
    convert_host_to_uri_str,
    find_mac_via_arp,
    get_all_interfaces_definition,
    resolve_host_to_addrinfo,
)
from provisioningserver.utils.shell import (
    call_and_check,
    ExternalProcessError,
    get_env_with_bytes_locale,
)
from provisioningserver.utils.snappy import running_in_snap
from provisioningserver.utils.twisted import (
    call,
    callOut,
    deferred,
    DeferredValue,
    deferWithTimeout,
    makeDeferredWithProcessProtocol,
    suppress,
)
from provisioningserver.utils.url import get_domain
from provisioningserver.utils.version import get_maas_version

maaslog = get_maas_logger("rpc.cluster")
log = LegacyLogger()

# Number of seconds before a DHCP configure command will timeout.
DHCP_TIMEOUT = 30  # 30 seconds.


def catch_probe_and_enlist_error(name, failure):
    """Logs any errors when trying to probe and enlist a chassis."""
    maaslog.error(
        "Failed to probe and enlist %s nodes: %s",
        name,
        failure.getErrorMessage(),
    )
    return None


def get_scan_all_networks_args(
    scan_all=False,
    force_ping=False,
    threads=None,
    cidrs=None,
    slow=False,
    interface=None,
):
    """Return the arguments needed to perform a scan of all networks.

    The output of this function is suitable for passing into a call
    to `subprocess.Popen()`.

    :param cidrs: an iterable of CIDR strings
    """
    args = [get_maas_common_command(), "scan-network"]
    if not is_dev_environment():
        args = sudo(args)
    if threads is not None:
        args.extend(["--threads", str(threads)])
    if force_ping:
        args.append("--ping")
    if slow:
        args.append("--slow")
    # None of these parameters are relevant if we are scanning everything...
    if not scan_all:
        # ... but force the caller to be explicit about scanning all networks.
        # Keep track of the original length of `args` to make sure we add at
        # least one argument.
        original_args_length = len(args)
        if interface is not None:
            args.append(interface)
        if cidrs is not None:
            args.extend(str(cidr) for cidr in cidrs)
        assert original_args_length != len(args), (
            "Invalid scan parameters. Must specify cidrs or interface if not "
            "using scan_all."
        )
    binary_args = [arg.encode(sys.getfilesystemencoding()) for arg in args]
    return binary_args


def spawnProcessAndNullifyStdout(protocol, args):
    """ "Utility function to spawn a process and redirect stdout to /dev/null.

    Spawns the process with the specified `protocol` in the reactor, with the
    specified list of binary `args`.
    """
    # Using childFDs we arrange for the child's stdout to go to /dev/null
    # and for stderr to be read asynchronously by the reactor.
    with open(os.devnull, "r+b") as devnull:
        # This file descriptor to /dev/null will be closed before the
        # spawned process finishes, but will remain open in the spawned
        # process; that's the Magic Of UNIX™.
        reactor.spawnProcess(
            protocol,
            args[0],
            args,
            childFDs={0: devnull.fileno(), 1: devnull.fileno(), 2: "r"},
            env=get_env_with_bytes_locale(),
        )


def executeScanNetworksSubprocess(
    scan_all=False,
    force_ping=False,
    slow=False,
    threads=None,
    cidrs=None,
    interface=None,
):
    """Runs the network scanning subprocess.

    Redirects stdout and stderr in the subprocess to /dev/null. Leaves
    stderr intact, so that we might pass useful logging through.

    Returns the `reason` (see `ProcessProtocol.processEnded`) from the
    scan process after waiting for it to complete.

    :param cidrs: A list of CIDR strings to run neighbour scans on.
    """
    done, protocol = makeDeferredWithProcessProtocol()
    # Technically this is not guaranteed to be a string containing just
    # one line of text. But reality in this case is both atomic and
    # concise. (And if it isn't, we can fix it, since we're calling our
    # own command.)
    protocol.errReceived = lambda data: (
        log.msg("Scan all networks: " + data.decode("utf-8"))
    )
    args = get_scan_all_networks_args(
        scan_all=scan_all,
        force_ping=force_ping,
        slow=slow,
        threads=threads,
        cidrs=cidrs,
        interface=interface,
    )
    spawnProcessAndNullifyStdout(protocol, args)
    return done


def check_ip_address(request):
    """Perform's the actual IP address checking using `ping`.

    Redirects stdout and stderr in the subprocess to /dev/null. Leaves
    stderr intact, so that we might pass useful logging through.

    Returns the `reason` (see `ProcessProtocol.processEnded`) from the
    scan process after waiting for it to complete.

    :param request: An individual request from the
        :py:class:`~provisioningserver.rpc.cluster.CheckIPs`.
    """
    args = ["ping", "-c", "1"]
    if request.get("interface"):
        args += ["-I", request["interface"]]
    args += [request["ip_address"]]
    done = deferToThread(call_and_check, args)

    # This will only occur if the ping was successful and now the MAC address
    # for that IP address will now be in the ARP cache.
    done.addCallback(
        lambda _: deferToThread(find_mac_via_arp, request["ip_address"])
    )

    return done


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

        def get_proxy_url(url):
            return None if url is None else url.geturl()

        import_boot_images(
            sources,
            self.service.maas_url,
            http_proxy=get_proxy_url(http_proxy),
            https_proxy=get_proxy_url(https_proxy),
        )
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
        # Detection of missing packages is now done reactively instead of
        # proactively. When a power check is performed it will raise an error
        # if their are any missing packages.
        return {
            "power_types": list(
                PowerDriverRegistry.get_schema(detect_missing_packages=False)
            )
        }

    @cluster.DescribeNOSTypes.responder
    def describe_nos_types(self):
        """describe_nos_types()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.DescribeNOSTypes`.
        """
        return {"nos_types": list(NOSDriverRegistry.get_schema())}

    @cluster.ListSupportedArchitectures.responder
    def list_supported_architectures(self):
        return {
            "architectures": [
                {"name": arch.name, "description": arch.description}
                for _, arch in ArchitectureRegistry
            ]
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
        self,
        osystem,
        preseed_type,
        node_system_id,
        node_hostname,
        consumer_key,
        token_key,
        token_secret,
        metadata_url,
    ):
        """get_preseed_data()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.GetPreseedData`.
        """
        return {
            "data": get_preseed_data(
                osystem,
                preseed_type,
                node_system_id,
                node_hostname,
                consumer_key,
                token_key,
                token_secret,
                metadata_url,
            )
        }

    @cluster.PowerOn.responder
    def power_on(self, system_id, hostname, power_type, context):
        """Turn a node on."""
        d = maybe_change_power_state(
            system_id, hostname, power_type, power_change="on", context=context
        )
        d.addCallback(lambda _: {})
        return d

    @cluster.PowerOff.responder
    def power_off(self, system_id, hostname, power_type, context):
        """Turn a node off."""
        d = maybe_change_power_state(
            system_id,
            hostname,
            power_type,
            power_change="off",
            context=context,
        )
        d.addCallback(lambda _: {})
        return d

    @cluster.PowerCycle.responder
    def power_cycle(self, system_id, hostname, power_type, context):
        """Power cycle a node."""
        d = maybe_change_power_state(
            system_id,
            hostname,
            power_type,
            power_change="cycle",
            context=context,
        )
        d.addCallback(lambda _: {})
        return d

    @cluster.PowerQuery.responder
    def power_query(self, system_id, hostname, power_type, context):
        d = get_power_state(system_id, hostname, power_type, context=context)
        d.addCallback(lambda x: {"state": x})
        d.addErrback(
            lambda f: {"state": "error", "error_msg": f.getErrorMessage()}
        )
        return d

    @cluster.PowerDriverCheck.responder
    def power_driver_check(self, power_type):
        """Return a list of missing power driver packages, if any."""
        driver = PowerDriverRegistry.get_item(power_type)
        if driver is None:
            raise exceptions.UnknownPowerType(
                "No driver found for power type '%s'" % power_type
            )
        return {"missing_packages": driver.detect_missing_packages()}

    @cluster.ConfigureDHCPv4.responder
    def configure_dhcpv4(
        self,
        omapi_key,
        failover_peers,
        shared_networks,
        hosts,
        interfaces,
        global_dhcp_snippets=[],
    ):
        dhcp.upgrade_shared_networks(shared_networks)
        return self.configure_dhcpv4_v2(
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )

    @cluster.ConfigureDHCPv4_V2.responder
    def configure_dhcpv4_v2(
        self,
        omapi_key,
        failover_peers,
        shared_networks,
        hosts,
        interfaces,
        global_dhcp_snippets=[],
    ):
        server = dhcp.DHCPv4Server(omapi_key)
        if concurrency.dhcpv4.locked:
            log.debug(
                "DHCPv4 configure triggered; another is already processing, "
                "scheduled next"
            )
        else:
            log.debug("DHCPv4 configure triggered; processing immediately")

        # LP:1785078 - DHCP updating gets stuck and prevents sequential updates
        # from occurring. Being defensive here and only allowing the DHCP
        # configure 30 seconds to perform its work.
        d = concurrency.dhcpv4.run(
            deferWithTimeout,
            DHCP_TIMEOUT,
            dhcp.configure,
            server,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )
        d.addCallback(lambda _: {})

        # Catch the cancelled error, which means the work timed out.
        def _timeoutEb(failure):
            failure.trap(CancelledError)
            log.err(failure, "DHCPv4 configure timed out")
            raise CannotConfigureDHCP("timed out") from failure.value

        d.addErrback(_timeoutEb)

        return d

    @cluster.ValidateDHCPv4Config.responder
    def validate_dhcpv4_config(
        self,
        omapi_key,
        failover_peers,
        shared_networks,
        hosts,
        interfaces,
        global_dhcp_snippets=[],
    ):
        dhcp.upgrade_shared_networks(shared_networks)
        return self.validate_dhcpv4_config_v2(
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )

    @cluster.ValidateDHCPv4Config_V2.responder
    def validate_dhcpv4_config_v2(
        self,
        omapi_key,
        failover_peers,
        shared_networks,
        hosts,
        interfaces,
        global_dhcp_snippets=[],
    ):
        server = dhcp.DHCPv4Server(omapi_key)
        d = deferToThread(
            dhcp.validate,
            server,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )
        d.addCallback(lambda ret: {"errors": ret} if ret is not None else {})
        return d

    @cluster.ConfigureDHCPv6.responder
    def configure_dhcpv6(
        self,
        omapi_key,
        failover_peers,
        shared_networks,
        hosts,
        interfaces,
        global_dhcp_snippets=[],
    ):
        dhcp.upgrade_shared_networks(shared_networks)
        return self.configure_dhcpv6_v2(
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )

    @cluster.ConfigureDHCPv6_V2.responder
    def configure_dhcpv6_v2(
        self,
        omapi_key,
        failover_peers,
        shared_networks,
        hosts,
        interfaces,
        global_dhcp_snippets=[],
    ):
        server = dhcp.DHCPv6Server(omapi_key)
        if concurrency.dhcpv6.locked:
            log.debug(
                "DHCPv6 configure triggered; another is already processing, "
                "scheduled next"
            )
        else:
            log.debug("DHCPv6 configure triggered; processing immediately")

        # LP:1785078 - DHCP updating gets stuck and prevents sequential updates
        # from occurring. Being defensive here and only allowing the DHCP
        # configure 30 seconds to perform its work.
        d = concurrency.dhcpv6.run(
            deferWithTimeout,
            DHCP_TIMEOUT,
            dhcp.configure,
            server,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )
        d.addCallback(lambda _: {})

        # Catch the cancelled error, which means the work timed out.
        def _timeoutEb(failure):
            failure.trap(CancelledError)
            log.err(failure, "DHCPv6 configure timed out")
            raise CannotConfigureDHCP("timed out") from failure.value

        d.addErrback(_timeoutEb)

        return d

    @cluster.ValidateDHCPv6Config.responder
    def validate_dhcpv6_config(
        self,
        omapi_key,
        failover_peers,
        shared_networks,
        hosts,
        interfaces,
        global_dhcp_snippets=[],
    ):
        dhcp.upgrade_shared_networks(shared_networks)
        return self.validate_dhcpv6_config_v2(
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )

    @cluster.ValidateDHCPv6Config_V2.responder
    def validate_dhcpv6_config_v2(
        self,
        omapi_key,
        failover_peers,
        shared_networks,
        hosts,
        interfaces,
        global_dhcp_snippets=[],
    ):
        server = dhcp.DHCPv6Server(omapi_key)
        d = deferToThread(
            dhcp.validate,
            server,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )
        d.addCallback(lambda ret: {"errors": ret} if ret is not None else {})
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
        self,
        system_id,
        tag_name,
        tag_definition,
        tag_nsmap,
        credentials,
        nodes,
    ):
        """evaluate_tag()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.EvaluateTag`.
        """
        # It's got to run in a thread because it does blocking IO.
        d = deferToThread(
            evaluate_tag,
            system_id,
            nodes,
            tag_name,
            tag_definition,
            # Transform tag_nsmap into a format that LXML likes.
            {entry["prefix"]: entry["uri"] for entry in tag_nsmap},
            # Parse the credential string into a 3-tuple.
            convert_string_to_tuple(credentials),
            self.service.maas_url,
        )
        return d.addCallback(lambda _: {})

    @cluster.RefreshRackControllerInfo.responder
    def refresh(self, system_id, consumer_key, token_key, token_secret):
        """RefreshRackControllerInfo()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.RefreshRackControllerInfo`.
        """

        def _refresh():
            return deferToThread(
                refresh,
                system_id,
                consumer_key,
                token_key,
                token_secret,
                self.service.maas_url,
            )

        lock = NamedLock("refresh")
        try:
            lock.acquire()
        except lock.NotAvailable:
            # Refresh is already running, don't do anything
            raise exceptions.RefreshAlreadyInProgress()
        else:
            # Start gathering node results (lshw, lsblk, etc) but don't wait.
            maybeDeferred(_refresh).addBoth(callOut, lock.release).addErrback(
                log.err, "Failed to refresh the rack controller."
            )

        return deferToThread(lambda: {"maas_version": get_maas_version()})

    @cluster.AddChassis.responder
    def add_chassis(
        self,
        user,
        chassis_type,
        hostname,
        username=None,
        password=None,
        accept_all=False,
        domain=None,
        prefix_filter=None,
        power_control=None,
        port=None,
        protocol=None,
        token_name=None,
        token_secret=None,
        verify_ssl=False,
    ):
        """AddChassis()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.AddChassis`.
        """
        if chassis_type in ("virsh", "powerkvm"):
            d = deferToThread(
                probe_virsh_and_enlist,
                user,
                hostname,
                password,
                prefix_filter,
                accept_all,
                domain,
            )
            d.addErrback(partial(catch_probe_and_enlist_error, "virsh"))
        elif chassis_type == "proxmox":
            d = deferToThread(
                probe_proxmox_and_enlist,
                user,
                hostname,
                username,
                password,
                token_name,
                token_secret,
                verify_ssl,
                accept_all,
                domain,
                prefix_filter,
            )
            d.addErrback(partial(catch_probe_and_enlist_error, "proxmox"))
        elif chassis_type == "vmware":
            d = deferToThread(
                probe_vmware_and_enlist,
                user,
                hostname,
                username,
                password,
                port,
                protocol,
                prefix_filter,
                accept_all,
                domain,
            )
            d.addErrback(partial(catch_probe_and_enlist_error, "VMware"))
        elif chassis_type == "recs_box":
            d = deferToThread(
                probe_and_enlist_recs,
                user,
                hostname,
                port,
                username,
                password,
                accept_all,
                domain,
            )
            d.addErrback(partial(catch_probe_and_enlist_error, "RECS|Box"))
        elif chassis_type == "seamicro15k":
            d = deferToThread(
                probe_seamicro15k_and_enlist,
                user,
                hostname,
                username,
                password,
                power_control,
                accept_all,
                domain,
            )
            d.addErrback(
                partial(catch_probe_and_enlist_error, "SeaMicro 15000")
            )
        elif chassis_type == "mscm":
            d = deferToThread(
                probe_and_enlist_mscm,
                user,
                hostname,
                username,
                password,
                accept_all,
                domain,
            )
            d.addErrback(partial(catch_probe_and_enlist_error, "Moonshot"))
        elif chassis_type == "msftocs":
            d = deferToThread(
                probe_and_enlist_msftocs,
                user,
                hostname,
                port,
                username,
                password,
                accept_all,
                domain,
            )
            d.addErrback(partial(catch_probe_and_enlist_error, "MicrosoftOCS"))
        elif chassis_type == "ucsm":
            d = deferToThread(
                probe_and_enlist_ucsm,
                user,
                hostname,
                username,
                password,
                accept_all,
                domain,
            )
            d.addErrback(partial(catch_probe_and_enlist_error, "UCS"))
        else:
            message = "Unknown chassis type %s" % chassis_type
            maaslog.error(message)
        return {}

    @cluster.DiscoverPod.responder
    def discover_pod(self, type, context, pod_id=None, name=None):
        """DiscoverPod()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.DiscoverPod`.
        """
        return pods.discover_pod(type, context, pod_id=pod_id, name=name)

    @cluster.SendPodCommissioningResults.responder
    def send_pod_commissioning_results(
        self,
        pod_id,
        name,
        type,
        system_id,
        context,
        consumer_key,
        token_key,
        token_secret,
        metadata_url,
    ):
        """SendPodCommissioningResults()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.SendPodCommissioningResults`.
        """
        return pods.send_pod_commissioning_results(
            type,
            context,
            pod_id,
            name,
            system_id,
            consumer_key,
            token_key,
            token_secret,
            metadata_url,
        )

    @cluster.ComposeMachine.responder
    def compose_machine(self, type, context, request, pod_id, name):
        """ComposeMachine()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.ComposeMachine`.
        """
        return pods.compose_machine(
            type, context, request, pod_id=pod_id, name=name
        )

    @cluster.DecomposeMachine.responder
    def decompose_machine(self, type, context, pod_id, name):
        """DecomposeMachine()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.DecomposeMachine`.
        """
        return pods.decompose_machine(type, context, pod_id=pod_id, name=name)

    @cluster.ScanNetworks.responder
    def scan_all_networks(
        self,
        scan_all=False,
        force_ping=False,
        slow=False,
        threads=None,
        cidrs=None,
        interface=None,
    ):
        """ScanNetworks()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.ScanNetworks`.
        """
        lock = NamedLock("scan-networks")
        try:
            lock.acquire()
        except lock.NotAvailable:
            # Scan is already running; don't do anything.
            raise exceptions.ScanNetworksAlreadyInProgress(
                "Only one concurrent network scan is allowed."
            )
        else:
            # The lock *must* be released, so put on the paranoid hat here and
            # use maybeDeferred to make sure that errors all trigger the call
            # to lock.release.
            d = maybeDeferred(
                executeScanNetworksSubprocess,
                scan_all=scan_all,
                force_ping=force_ping,
                slow=slow,
                cidrs=cidrs,
                threads=threads,
                interface=interface,
            )
            d.addErrback(suppress, ProcessDone)  # Exited normally.
            d.addErrback(log.err, "Failed to scan all networks.")
            d.addBoth(callOut, lock.release)
        return {}

    @cluster.DisableAndShutoffRackd.responder
    def disable_and_shutoff_rackd(self):
        """DisableAndShutoffRackd()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.DisableAndShutoffRackd`.
        """
        maaslog.info("Attempting to disable the rackd service.")
        secret_path = get_shared_secret_filesystem_path()
        if secret_path.exists():
            secret_path.unlink()
        try:
            if running_in_snap():
                call_and_check(["snapctl", "restart", "maas.supervisor"])
            else:
                call_and_check(["sudo", "systemctl", "restart", "maas-rackd"])
        except ExternalProcessError as e:
            # Since the snap sends a SIGTERM to terminate the process, python
            # returns -15 as a return code. This indicates the termination
            # signal has been performed and the process terminated. However,
            # This is not a failure. As such, work around the non-zero return
            # (-15) and do not raise an error.
            if not (running_in_snap() and e.returncode == -15):
                maaslog.error("Unable to disable and stop the rackd service")
                raise exceptions.CannotDisableAndShutoffRackd(
                    e.output_as_unicode
                )
        return {}

    @cluster.CheckIPs.responder
    def check_ips(self, ip_addresses):
        """CheckIPs()

        Implementation of
        :py:class:`~provisioningserver.rpc.cluster.CheckIPs`.
        """
        d = DeferredList(
            map(check_ip_address, ip_addresses), consumeErrors=True
        )

        def map_results(results):
            for request, (success, mac_address) in zip(ip_addresses, results):
                request["used"] = success
                if success and mac_address:
                    request["mac_address"] = mac_address
            return {"ip_addresses": ip_addresses}

        d.addCallback(map_results)
        d.addErrback(log.err, "Failed to perform IP address checking.")
        return d


@implementer(IConnectionToRegion)
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
        super().__init__()
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
        response = yield self.callRemote(region.Authenticate, message=message)
        salt, digest = response["salt"], response["digest"]
        digest_local = calculate_digest(secret, message, salt)
        returnValue(digest == digest_local)

    @inlineCallbacks
    def registerRackWithRegion(self):
        # Grab the cluster UUID. It is possible that the cluster UUID is blank.
        with ClusterConfiguration.open() as config:
            cluster_uuid = config.cluster_uuid

        # Grab the set system_id if already set for this controller.
        system_id = get_maas_id()
        if system_id is None:
            # Cannot send None over RPC when the system_id is not set.
            system_id = ""

        # Gather the required information for registration.
        interfaces = get_all_interfaces_definition()
        hostname = gethostname()
        parsed_url = urlparse(self.service.maas_url)
        version = get_maas_version()

        try:
            # Note: we indicate support for beacons here, and act differently
            # later depending on if the region we're registering with supports
            # them or not.
            data = yield self.callRemote(
                region.RegisterRackController,
                system_id=system_id,
                hostname=hostname,
                interfaces=interfaces,
                url=parsed_url,
                nodegroup_uuid=cluster_uuid,
                beacon_support=True,
                version=version,
            )
            self.localIdent = data["system_id"]
            set_global_labels(maas_uuid=data.get("uuid"), service_type="rack")
            set_maas_id(self.localIdent)
            version = data.get("version", None)
            if version is None:
                version_log = "MAAS version 2.2 or below"
            elif version == "":
                version_log = "unknown MAAS version"
            else:
                version_log = "MAAS version " + version
            log.msg(
                "Rack controller '%s' registered (via %s) with %s."
                % (self.localIdent, self.eventloop, version_log)
            )
            # If the region supports beacons, full registration of rack
            # interfaces will not have occurred yet. The networks monitoring
            # service is responsible for updating the interfaces
            # post-registration.
            return True
        except exceptions.CannotRegisterRackController:
            log.msg(
                "Rack controller REJECTED by the region (via %s)."
                % self.eventloop
            )
            return False

    @inlineCallbacks
    def performHandshake(self):
        d_authenticate = self.authenticateRegion()
        self.authenticated.observe(d_authenticate)
        authenticated = yield d_authenticate

        if authenticated:
            log.msg("Event-loop '%s' authenticated." % self.ident)
            registered = yield self.registerRackWithRegion()
            if registered:
                self.service.add_connection(self.eventloop, self)
                self.ready.set(self.eventloop)
            else:
                self.transport.loseConnection()
                self.ready.fail(
                    exceptions.RegistrationFailed(
                        "Event-loop '%s' rejected registration." % self.ident
                    )
                )
        else:
            log.msg(
                "Event-loop '%s' FAILED authentication; "
                "dropping connection." % self.ident
            )
            self.transport.loseConnection()
            self.ready.fail(
                exceptions.AuthenticationFailed(
                    "Event-loop '%s' failed authentication." % self.eventloop
                )
            )

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
                failure,
                "Event-loop '%s' handshake failed; "
                "dropping connection." % self.ident,
            )
            self.transport.loseConnection()
            self.ready.fail(failure)

    def connectionMade(self):
        super().connectionMade()

        if not self.service.running:
            log.msg(
                "Event-loop '%s' will be disconnected; the cluster's "
                "client service is not running." % self.ident
            )
            self.transport.loseConnection()
            self.authenticated.set(None)
            self.ready.fail(RuntimeError("Service not running."))
        elif self.eventloop in self.service.connections:
            log.msg(
                "Event-loop '%s' is already connected; "
                "dropping connection." % self.ident
            )
            self.transport.loseConnection()
            self.authenticated.set(None)
            self.ready.fail(
                KeyError("Event-loop '%s' already connected." % self.eventloop)
            )
        else:
            return self.performHandshake().addCallbacks(
                self.handshakeSucceeded, self.handshakeFailed
            )

    def connectionLost(self, reason):
        self.service.remove_connection(self.eventloop, self)
        super().connectionLost(reason)

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
                "%s was expected." % (remote_name, self.eventloop)
            )
            self.transport.loseConnection()
            return

        # We should now have a full set of parameters for the transport.
        log.msg("Host certificate: %r" % self.hostCertificate)
        log.msg("Peer certificate: %r" % self.peerCertificate)


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

    INTERVAL_LOW = 1  # seconds.
    INTERVAL_MID = 5  # seconds.
    INTERVAL_HIGH = 30  # seconds.

    time_started = None

    def __init__(self, reactor):
        super().__init__(self._calculate_interval(None, None), self._tryUpdate)
        self.connections = {}
        self.try_connections = {}
        self._previous_work = (None, None)
        self.clock = reactor

        # Stored the URL used to connect to the region controller. This will be
        # the URL that was used to get the eventloops.
        self.maas_url = None

        # Holds the last stored state of the RPC connection information. This
        # state is used to only update the RPC state file when the URL have
        # actually changed.
        self._rpc_info_state = None

        # When _doUpdate is called we capture it into _updateInProgress so
        # that concurrent calls can piggyback rather than initiating extra
        # calls. We start with an already-fired DeferredValue: _tryUpdate
        # checks if it is set to decide whether or not to call _doUpdate.
        self._updateInProgress = DeferredValue()
        self._updateInProgress.set(None)

    def startService(self):
        self.time_started = self.clock.seconds()
        super().startService()

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

    @deferred
    def getClientNow(self):
        """Returns a `Defer` that resolves to a :class:`common.Client`
        connected to a region.

        If a connection already exists to the region then this method
        will just return that current connection. If no connections exists
        this method will try its best to make a connection before returning
        the client.

        :raises: :py:class:`~.exceptions.NoConnectionsAvailable` when
            there no connections can be made to a region controller.
        """
        try:
            return self.getClient()
        except exceptions.NoConnectionsAvailable:
            return self._tryUpdate().addCallback(call, self.getClient)

    def getAllClients(self):
        """Return a list of all connected :class:`common.Client`s."""
        return [common.Client(conn) for conn in self.connections.values()]

    def _tryUpdate(self):
        """Attempt to refresh outgoing connections.

        This ensures that calls to `_doUpdate` are deferred, with errors
        logged but not propagated. It also ensures that `_doUpdate` is never
        called concurrently.
        """
        if self._updateInProgress.isSet:
            d = maybeDeferred(self._doUpdate).addErrback(
                log.err, "Cluster client update failed."
            )
            self._updateInProgress = DeferredValue()
            self._updateInProgress.capture(d)
        return self._updateInProgress.get()

    @inlineCallbacks
    def _doUpdate(self):
        """Refresh outgoing connections.

        This obtains a list of endpoints from the region then connects
        to new ones and drops connections to those no longer used.
        """
        eventloops = None
        urls = self._get_config_rpc_info_urls()
        try:
            eventloops, maas_url = yield self._get_rpc_info(urls)
            if eventloops is None:
                # This means that the region process we've just asked about
                # RPC event-loop endpoints is not running the RPC
                # advertising service. It could be just starting up for
                # example.
                self.maas_url = None
                log.msg(
                    "Region is not advertising RPC endpoints."
                    " (While requesting RPC info at %s)" % ", ".join(urls)
                )
            else:
                self.maas_url = maas_url
                yield self._update_connections(eventloops)
        except ConnectError as error:
            self.maas_url = None
            log.msg(
                "Region not available: %s "
                "(While requesting RPC info at %s)." % (error, ", ".join(urls))
            )
        except Exception:
            self.maas_url = None
            log.err(
                None,
                "Failed to contact region. "
                "(While requesting RPC info at %s)." % (", ".join(urls)),
            )

        self._update_interval(
            None if eventloops is None else len(eventloops),
            len(self.connections),
        )

    @inlineCallbacks
    def _build_rpc_info_urls(self, urls):
        """
        Take a list of `urls` and breakdown them down to try IPv6 before IPv4.
        """
        orig_urls = []
        for orig_url in urls:
            url = urlparse(orig_url)
            url = url._replace(path="%s/rpc/" % url.path.rstrip("/"))
            url = url.geturl()
            url = ascii_url(url)
            orig_urls.append((url, orig_url))

        urls = []
        for url, orig_url in orig_urls:
            urls_group = []
            url_base = urlparse(url).decode()
            url_addresses = yield resolve_host_to_addrinfo(
                url_base.hostname, ip_version=0, port=url_base.port
            )
            # Prefer AF_INET6 addresses
            url_addresses.sort(key=itemgetter(0), reverse=True)
            for family, _, _, _, sockaddr in url_addresses:
                addr, port, *_ = sockaddr
                # We could use compose_URL (from provisioningserver.utils.url),
                # but that just calls url._replace itself, and returns a url
                # literal, rather than a url structure.  So we use _replace()
                # here as well. What we are actually doing here is replacing
                # the given host:port in the URL with the answer we got from
                # socket.getaddrinfo().
                if family == AF_INET6:
                    if port == 0:
                        netloc = "[%s]" % IPAddress(addr).ipv6()
                    else:
                        netloc = "[%s]:%d" % (IPAddress(addr).ipv6(), port)
                    url = url_base._replace(netloc=netloc)
                elif family == AF_INET:
                    url = url_base
                else:
                    continue
                url = ascii_url(url.geturl())
                urls_group.append(url)
            urls.append((urls_group, orig_url))

        return urls

    def _get_config_rpc_info_urls(self):
        """Return the URLs to the RPC endpoint from rackd.conf."""
        # Load the URLs from the rackd configuration.
        with ClusterConfiguration.open() as config:
            return config.maas_url

    def _get_saved_rpc_info_path(self):
        """Return path to the saved RPC state file."""
        return get_maas_data_path("rpc.state")

    def _get_saved_rpc_info_urls(self):
        """Return the URLs to the RPC endpoint from the saved RPC state."""
        path = self._get_saved_rpc_info_path()
        try:
            with open(path, "r") as stream:
                return stream.read().splitlines()
        except OSError:
            return []

    def _update_saved_rpc_info_state(self):
        """Update the saved RPC info state."""
        # Build a list of addresses based on the current connections.
        connected_addr = {
            conn.address[0] for _, conn in self.connections.items()
        }
        if (
            self._rpc_info_state is None
            or self._rpc_info_state != connected_addr
        ):
            path = self._get_saved_rpc_info_path()
            with open(path, "w") as stream:
                for addr in sorted(list(connected_addr)):
                    host = convert_host_to_uri_str(addr)
                    stream.write("http://%s:5240/MAAS\n" % host)
            self._rpc_info_state = connected_addr

    def _fetch_rpc_info(self, url, orig_url):
        def catch_503_error(failure):
            # Catch `twisted.web.error.Error` if has a 503 status code. That
            # means the region is not all the way up. Ignore the error as this
            # service will try again after the calculated interval.
            failure.trap(web.error.Error)
            if failure.value.status != "503":
                failure.raiseException()
            else:
                return ({"eventloops": None}, orig_url)

        def read_body(response):
            # Read the body of the response and convert it to JSON.
            d = Deferred()
            protocol = _ReadBodyProtocol(response.code, response.phrase, d)
            response.deliverBody(protocol)
            d.addCallback(
                lambda data: (json.loads(data.decode("utf-8")), orig_url)
            )
            return d

        # Request the RPC information.
        agent = Agent(reactor)
        d = agent.request(
            b"GET",
            url,
            Headers(
                {
                    b"User-Agent": [fullyQualifiedName(type(self))],
                    b"Host": [get_domain(orig_url)],
                }
            ),
        )
        d.addCallback(read_body)
        d.addErrback(catch_503_error)

        # Timeout making HTTP request after 5 seconds.
        self.clock.callLater(5, d.cancel)

        return d

    @inlineCallbacks
    def _serial_fetch_rpc_info(self, urls, orig_url):
        """Fetch the RPC information serially."""
        last_exc = None
        for url in urls:
            try:
                response = yield self._fetch_rpc_info(url, orig_url)
                return response
            except Exception as exc:
                # The exception is stored so that if trying all URLs fail,
                # the last branch in this method will raise this exception.
                # This allows all URLs to be tried before raising the error.
                last_exc = exc
        if last_exc is not None:
            raise last_exc

    def _parallel_fetch_rpc_info(self, urls):
        """Fetch the RPC information in parallel.

        `urls` is a list of tuples in the form (url_group, orig_url). Each
        tuple is fetched in parallel and the url_group list is fetched
        serially. The url_group inner list is fetched serially because it
        points to the same region controller, just at different IP addresses.
        """

        def handle_responses(results):
            # Gather the list of successful responses.
            successful = []
            errors = []
            for sucess, result in results:
                if sucess:
                    body, orig_url = result
                    eventloops = body.get("eventloops")
                    if eventloops is not None:
                        eventloops_count = len(eventloops)
                        if eventloops_count > 0:
                            successful.append(
                                (eventloops_count, eventloops, orig_url)
                            )
                else:
                    errors.append(result)

            # When successful use the response with the most eventloops. This
            # ensures that the rack controller will connect to as many RPC
            # eventloops as possible.
            if len(successful) > 0:
                successful = sorted(
                    successful, key=itemgetter(0), reverse=True
                )
                return (successful[0][1], successful[0][2])

            # No success so lets raise the first error.
            if len(errors) > 0:
                errors[0].raiseException()

            # All responses had empty eventloops.
            return (None, None)

        defers = []
        for url_group, orig_url in urls:
            defers.append(self._serial_fetch_rpc_info(url_group, orig_url))
        defers = DeferredList(defers, consumeErrors=True)
        defers.addCallback(handle_responses)
        return defers

    @inlineCallbacks
    def _get_rpc_info(self, config_urls):
        """Return the RPC connection information.

        Connect to the region controller(s) to determine all the RPC endpoints
        for connection.
        """
        eventloops, maas_url = None, None

        # First try to get the eventloop information using the URLs
        # defined in rackd.conf.
        config_exc = None
        urls = yield self._build_rpc_info_urls(config_urls)
        try:
            eventloops, maas_url = yield self._parallel_fetch_rpc_info(urls)
            if eventloops is None:
                maas_url = None
        except Exception as exc:
            # Hold the exception raised trying to get endpoints from the region
            # using URLs defined in the rackd.conf. This exception will be
            # re-raised if the stored state URLs fail.
            config_exc = exc

        # Second try to get the eventloop information using the URLs
        # defined in the saved rpc connection information.
        if not eventloops:
            saved_urls = self._get_saved_rpc_info_urls()
            if saved_urls:
                urls = yield self._build_rpc_info_urls(saved_urls)
                try:
                    eventloops, maas_url = yield self._parallel_fetch_rpc_info(
                        urls
                    )
                    if eventloops is None:
                        maas_url = None
                except Exception:
                    # Ignore this exception, the `config_exc` will be raised
                    # instead, because that is the real issue. The rackd.conf
                    # should point to an active region controller.
                    pass

        # Raise the `config_exc` if present and still not eventloops.
        if not eventloops and config_exc is not None:
            raise config_exc

        return eventloops, maas_url

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

    def _update_interval(self, num_eventloops, num_connections, reset=False):
        """Change the update interval."""
        self._loop.interval = self.step = self._calculate_interval(
            num_eventloops, num_connections
        )
        if reset and self._loop.running:
            self._loop.reset()

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

        def map_to_ipv6(address_port_tuple):
            ipaddr, port = address_port_tuple
            ipaddr = IPAddress(ipaddr).ipv6()
            return str(ipaddr), port

        # Ensure that the event-loop addresses are tuples so that
        # they'll work as dictionary keys.
        eventloops = {
            name: [
                map_to_ipv6(address)
                for address in addresses
                if map_to_ipv6(address)
            ]
            for name, addresses in eventloops.items()
        }

        drop, connect = self._calculate_work(eventloops)

        # Log fully connected only once. If that state changes then log
        # it again. This prevents flooding the log with the same message when
        # the state of the connections has not changed.
        prev_work, self._previous_work = self._previous_work, (drop, connect)
        if len(drop) == 0 and len(connect) == 0:
            if prev_work != (drop, connect) and len(eventloops) > 0:
                controllers = {
                    eventloop.split(":")[0]
                    for eventloop, _ in eventloops.items()
                }
                log.msg(
                    "Fully connected to all %d event-loops on all %d "
                    "region controllers (%s)."
                    % (
                        len(eventloops),
                        len(controllers),
                        ", ".join(sorted(controllers)),
                    )
                )

        # Drop all connections at once, as the are no longer required.
        if len(drop) > 0:
            log.msg(
                "Dropping connections to event-loops: %s"
                % (", ".join(drop.keys()))
            )
            yield DeferredList(
                [
                    maybeDeferred(self._drop_connection, connection)
                    for eventloop, connections in drop.items()
                    for connection in connections
                ],
                consumeErrors=True,
            )

        # Make all the new connections to each endpoint at the same time.
        if len(connect) > 0:
            log.msg(
                "Making connections to event-loops: %s"
                % (", ".join(connect.keys()))
            )
            yield DeferredList(
                [
                    self._make_connections(eventloop, addresses)
                    for eventloop, addresses in connect.items()
                ],
                consumeErrors=True,
            )

    def _calculate_work(self, eventloops):
        """Calculate the work that needs to be performed for reconnection."""
        drop, connect = {}, {}

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
                    drop[eventloop] = [connection]
            if eventloop in self.try_connections:
                connection = self.try_connections[eventloop]
                if connection.address not in addresses:
                    drop[eventloop] = [connection]

        # Create new connections to event-loops that the cluster does
        # not yet have a connection to.
        for eventloop, addresses in eventloops.items():
            if (
                eventloop not in self.connections
                and eventloop not in self.try_connections
            ) or eventloop in drop:
                connect[eventloop] = addresses

        # Remove connections to event-loops that are no longer
        # advertised by the RPC info view. Most likely this means that
        # the process in which the event-loop is no longer running, but
        # it could be an indicator of a heavily loaded machine, or a
        # fault. In any case, it seems to make sense to disconnect.
        for eventloop in self.connections:
            if eventloop not in eventloops:
                connection = self.connections[eventloop]
                drop[eventloop] = [connection]
        for eventloop in self.try_connections:
            if eventloop not in eventloops:
                connection = self.try_connections[eventloop]
                drop[eventloop] = [connection]

        return drop, connect

    @inlineCallbacks
    def _make_connections(self, eventloop, addresses):
        """Connect to `eventloop` using all `addresses`."""
        for address in addresses:
            try:
                connection = yield self._make_connection(eventloop, address)
            except ConnectError as error:
                host, port = address
                log.msg(
                    "Event-loop %s (%s:%d): %s"
                    % (eventloop, host, port, error)
                )
            except Exception:
                host, port = address
                log.err(
                    None,
                    (
                        "Failure with event-loop %s (%s:%d)"
                        % (eventloop, host, port)
                    ),
                )
            else:
                self.try_connections[eventloop] = connection
                break

    def _make_connection(self, eventloop, address):
        """Connect to `eventloop` at `address`."""
        # Force everything to use AF_INET6 sockets.
        endpoint = TCP6ClientEndpoint(self.clock, *address)
        protocol = ClusterClient(address, eventloop, self)
        return connectProtocol(endpoint, protocol)

    def _drop_connection(self, connection):
        """Drop the given `connection`."""
        return connection.transport.loseConnection()

    def add_connection(self, eventloop, connection):
        """Add the connection to the tracked connections.

        Update the saved RPC info state information based on the new
        connection.
        """
        if eventloop in self.try_connections:
            del self.try_connections[eventloop]
        self.connections[eventloop] = connection
        self._update_saved_rpc_info_state()

    def remove_connection(self, eventloop, connection):
        """Remove the connection from the tracked connections.

        If this is the last connection that was keeping rackd connected to
        a regiond then dhcpd and dhcpd6 services will be turned off.
        """
        if eventloop in self.try_connections:
            if self.try_connections[eventloop] is connection:
                del self.try_connections[eventloop]
        if eventloop in self.connections:
            if self.connections[eventloop] is connection:
                del self.connections[eventloop]
        # Disable DHCP when no connections to a region controller.
        if len(self.connections) == 0:
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
                log.msg(
                    "Lost all connections to region controllers. "
                    "Stopping service(s) %s." % ",".join(stopping_services)
                )
                service_monitor.ensureServices()
        # Lower and reset the interval so a reconnection happens.
        self._update_interval(0, 0, reset=True)


class ClusterClientCheckerService(TimerService, object):
    """A cluster controller RPC client checker service.

    This is a service - in the Twisted sense - that cordinates with the
    `ClusterClientService` to ensure that all RPC connections are functional.
    A ping is performed over each current connection to ensure that the
    connection is working properly. If connection is not operational then it
    is dropped allowing the `ClusterClientService` to make a new connection.

    :ivar client_service: The `ClusterClientService` instance.
    """

    def __init__(self, client_service, reactor):
        super().__init__(30, self.tryLoop)
        self.client_service = client_service
        self.clock = reactor

    def tryLoop(self):
        d = self.loop()
        d.addErrback(
            log.err, "Failure while performing ping on RPC connections."
        )
        return d

    def loop(self):
        return DeferredList(
            [
                self._ping(client)
                for client in self.client_service.getAllClients()
            ],
            consumeErrors=True,
        )

    def _ping(self, client):
        """Ping the client to ensure it works."""

        def _onFailure(failure):
            log.msg(
                "Failure on ping dropping connection to event-loop: %s"
                % (client.ident)
            )
            # The protocol will call `remove_connection on the
            # `ClusterClientService` that will perform the reconnection.
            client._conn.transport.loseConnection()

        d = client(Ping, _timeout=10)
        d.addErrback(_onFailure)
        return d
