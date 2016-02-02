# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DHCP management module."""

__all__ = [
    'configure_dhcp',
    'configure_dhcp_now',
    ]

from collections import defaultdict
import logging
from operator import itemgetter
import threading

from django.conf import settings
from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODEGROUP_STATUS,
)
from maasserver.exceptions import UnresolvableHost
from maasserver.models import (
    Config,
    Domain,
    StaticIPAddress,
)
from maasserver.rpc import getClientFor
from maasserver.utils.orm import (
    post_commit,
    transactional,
)
from maasserver.utils.threads import callOutToDatabase
from netaddr import IPAddress
from provisioningserver.dhcp.omshell import generate_omapi_key
from provisioningserver.rpc.cluster import (
    ConfigureDHCPv4,
    ConfigureDHCPv6,
)
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.utils.twisted import (
    callOut,
    synchronous,
)


logger = logging.getLogger(__name__)


def get_omapi_key():
    """Return the OMAPI key for all DHCP servers that are ran by MAAS."""
    key = Config.objects.get_config("omapi_key")
    if key is None or key == '':
        key = generate_omapi_key()
        Config.objects.set_config("omapi_key", key)
    return key


def split_ipv4_ipv6_interfaces(interfaces):
    """Divide `interfaces` into IPv4 ones and IPv6 ones.

    :param interfaces: An iterable of rack controller interfaces.
    :return: A tuple of two separate iterables: IPv4 cluster interfaces for
        `nodegroup`, and its IPv6 cluster interfaces.
    """
    split = defaultdict(list)
    for interface in interfaces:
        split[interface.subnet.get_ipnetwork().version].append(interface)
    assert len(split) <= 2, (
        "Unexpected IP version(s): %s" % ', '.join(list(split.keys())))
    return split[4], split[6]


def make_interface_hostname(interface):
    """Return the host decleration name for DHCPD for this `interface`."""
    interface_name = interface.name.replace(".", "-")
    if interface.type == INTERFACE_TYPE.UNKNOWN and interface.node is None:
        return "unknown-%d-%s" % (interface.id, interface_name)
    else:
        return "%s-%s" % (interface.node.hostname, interface_name)


def make_hosts_for_subnet(subnet):
    """Return list of host entries to create in the DHCP configuration."""
    sips = StaticIPAddress.objects.filter(
        alloc_type__in=[
            IPADDRESS_TYPE.AUTO,
            IPADDRESS_TYPE.STICKY,
            IPADDRESS_TYPE.USER_RESERVED,
            ],
        subnet=subnet, ip__isnull=False).order_by('id')
    hosts = []
    interface_ids = set()
    for sip in sips:
        # Skip blank IP addresses.
        if sip.ip == '':
            continue

        # Add all interfaces attached to this IP address.
        for interface in sip.interface_set.order_by('id'):
            # Only allow an interface to be in hosts once.
            if interface.id in interface_ids:
                continue
            else:
                interface_ids.add(interface.id)

            # Bond interfaces get all its parent interfaces created as
            # hosts as well.
            if interface.type == INTERFACE_TYPE.BOND:
                for parent in interface.parents.all():
                    # Only add parents that MAC address is different from
                    # from the bond.
                    if parent.mac_address != interface.mac_address:
                        interface_ids.add(parent.id)
                        hosts.append({
                            'host': make_interface_hostname(parent),
                            'mac': str(parent.mac_address),
                            'ip': str(sip.ip),
                        })
                hosts.append({
                    'host': make_interface_hostname(interface),
                    'mac': str(interface.mac_address),
                    'ip': str(sip.ip),
                })
            else:
                hosts.append({
                    'host': make_interface_hostname(interface),
                    'mac': str(interface.mac_address),
                    'ip': str(sip.ip),
                })
    return sorted(hosts, key=itemgetter('host'))


def make_subnet_config(interface, dns_servers, ntp_server, default_domain):
    """Return DHCP subnet configuration dict for a cluster interface."""
    ip_network = interface.subnet.get_ipnetwork()
    return {
        'subnet': str(
            IPAddress(interface.ip_range_low) &
            IPAddress(ip_network.netmask)),
        'subnet_mask': str(ip_network.netmask),
        'subnet_cidr': str(interface.subnet.cidr),
        'broadcast_ip': interface.broadcast_ip,
        'interface': interface.interface,
        'router_ip': (
            '' if not interface.subnet else
            '' if not interface.subnet.gateway_ip
            else str(interface.subnet.gateway_ip)),
        'dns_servers': dns_servers,
        'ntp_server': ntp_server,
        'domain_name': default_domain.name,
        'ip_range_low': interface.ip_range_low,
        'ip_range_high': interface.ip_range_high,
        'hosts': make_hosts_for_subnet(interface.subnet),
        }


@synchronous
def do_configure_dhcp(
        ip_version, rack_controller, interfaces, ntp_server, client):
    """Write DHCP configuration and restart the DHCP server.

    Delegates the work to the rack controller, and waits for it
    to complete.

    :param ip_version: The IP version to configure for, either 4 or 6.
    :param client: An RPC client for the given cluster.

    :raise NoConnectionsAvailable: if the region controller could not get
        an RPC connection to the cluster controller.
    :raise CannotConfigureDHCP: if configuration could not be written, or
        restart of the DHCP server fails.
    """
    # XXX jtv 2014-08-26 bug=1361590: UI/API requests to update cluster
    # interfaces will block on this.  We may need an asynchronous error
    # backchannel.

    # Circular imports.
    from maasserver.dns.zonegenerator import get_dns_server_address

    if ip_version == 4:
        command = ConfigureDHCPv4
    elif ip_version == 6:
        command = ConfigureDHCPv6
    else:
        raise AssertionError(
            "Only IPv4 and IPv6 are supported, not IPv%s."
            % (ip_version,))

    try:
        dns_servers = get_dns_server_address(
            rack_controller, ipv4=(ip_version == 4), ipv6=(ip_version == 6))
    except UnresolvableHost:
        # No IPv6 DNS server addresses found.  As a space-separated string,
        # that becomes the empty string.
        dns_servers = ''

    default_domain = Domain.objects.get_default_domain()
    subnets = [
        make_subnet_config(interface, dns_servers, ntp_server, default_domain)
        for interface in interfaces
        ]
    # XXX jtv 2014-08-26 bug=1361673: If this fails remotely, the error
    # needs to be reported gracefully to the caller.
    client(command, omapi_key=get_omapi_key(), subnet_configs=subnets).wait(60)


def configure_dhcpv4(rack_controller, interfaces, ntp_server, client):
    """Call `do_configure_dhcp` for IPv4.

    This serves mainly as a convenience for testing.
    """
    return do_configure_dhcp(
        4, rack_controller, interfaces, ntp_server, client)


def configure_dhcpv6(rack_controller, interfaces, ntp_server, client):
    """Call `do_configure_dhcp` for IPv6.

    This serves mainly as a convenience for testing.
    """
    return do_configure_dhcp(
        6, rack_controller, interfaces, ntp_server, client)


def configure_dhcp_now(rack_controller):
    """Write the DHCP configuration files and restart the DHCP servers.

    :raises: :py:class:`~.exceptions.NoConnectionsAvailable` when there
        are no open connections to the specified cluster controller.
    """
    # Let's get this out of the way first up shall we?
    if not settings.DHCP_CONNECT:
        # For the uninitiated, DHCP_CONNECT is set, by default, to False
        # in all tests and True in non-tests.  This avoids unnecessary
        # calls to async tasks.
        return

    # Get the client early; it's a cheap operation that may raise an
    # exception, meaning we can avoid some work if it fails.
    client = getClientFor(rack_controller.system_id)

    if rack_controller.status == NODEGROUP_STATUS.ENABLED:
        # Cluster is an accepted one.  Control DHCP for its managed interfaces.
        interfaces = rack_controller.get_managed_interfaces()
    else:
        # Cluster isn't accepted.  Effectively, it manages no interfaces.
        interfaces = []

    # Make sure this rack_controller has a key to communicate with the dhcp
    # server.
    rack_controller.ensure_dhcp_key()

    ntp_server = Config.objects.get_config("ntp_server")

    ipv4_interfaces, ipv6_interfaces = split_ipv4_ipv6_interfaces(interfaces)

    configure_dhcpv4(rack_controller, ipv4_interfaces, ntp_server, client)
    configure_dhcpv6(rack_controller, ipv6_interfaces, ntp_server, client)


class Changes:
    """A record of pending DHCP changes, and the means to apply them."""

    # FIXME: This has elements in common with the Changes class in
    # maasserver.dns.config. Consider extracting the common parts into a
    # shared superclass.

    def __init__(self):
        super(Changes, self).__init__()
        self.reset()

    def reset(self):
        self.hook = None
        self.clusters = []

    def activate(self):
        """Arrange for a post-commit hook to be called.

        The hook will apply any pending changes and reset this object to a
        pristine state.

        Can be called multiple times; only one hook will be added.
        """
        if self.hook is None:
            self.hook = post_commit()
            self.hook.addCallback(callOutToDatabase, self.apply)
            self.hook.addBoth(callOut, self.reset)
        return self.hook

    @transactional
    def apply(self):
        """Apply all requested changes."""
        clusters = {cluster.id: cluster for cluster in self.clusters}
        for cluster in clusters.values():
            try:
                configure_dhcp_now(cluster)
            except NoConnectionsAvailable:
                logger.info(
                    "Cluster %s (%s) is not connected at present so cannot "
                    "be configured; it will catch up when it next connects.",
                    cluster.cluster_name, cluster.uuid)


class ChangeConsolidator(threading.local):
    """A singleton used to consolidate DHCP changes.

    Maintains a thread-local `Changes` instance into which changes are
    written. Requesting any change within a transaction automatically arranges
    a post-commit call to apply those changes, after consolidation.
    """

    # FIXME: This has elements in common with the ChangeConsolidator class in
    # maasserver.dns.config. Consider extracting the common parts into a
    # shared superclass.

    def __init__(self):
        super(ChangeConsolidator, self).__init__()
        self.changes = Changes()

    def configure(self, cluster):
        """Request that DHCP be configured for `cluster`.

        This does nothing if `settings.DHCP_CONNECT` is `False`.
        """
        if settings.DHCP_CONNECT:
            self.changes.clusters.append(cluster)
            return self.changes.activate()


# Singleton, for internal use only.
consolidator = ChangeConsolidator()

# The public API.
configure_dhcp = consolidator.configure
