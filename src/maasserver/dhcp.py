# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DHCP management module."""

__all__ = [
    'configure_dhcp',
    ]

from collections import defaultdict
from operator import itemgetter

from django.conf import settings
from django.db.models import Q
from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
)
from maasserver.exceptions import UnresolvableHost
from maasserver.models import (
    Config,
    Domain,
    StaticIPAddress,
)
from maasserver.rpc import getClientFor
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.dhcp.omshell import generate_omapi_key
from provisioningserver.rpc.cluster import (
    ConfigureDHCPv4,
    ConfigureDHCPv6,
)
from provisioningserver.utils.twisted import (
    asynchronous,
    synchronous,
)
from twisted.internet.defer import inlineCallbacks


def get_omapi_key():
    """Return the OMAPI key for all DHCP servers that are ran by MAAS."""
    key = Config.objects.get_config("omapi_key")
    if key is None or key == '':
        key = generate_omapi_key()
        Config.objects.set_config("omapi_key", key)
    return key


def split_ipv4_ipv6_subnets(subnets):
    """Divide `subnets` into IPv4 ones and IPv6 ones.

    :param subnets: A sequence of subnets.
    :return: A tuple of two separate sequences: IPv4 subnets and IPv6 subnets.
    """
    split = defaultdict(list)
    for subnet in subnets:
        split[subnet.get_ipnetwork().version].append(subnet)
    assert len(split) <= 2, (
        "Unexpected IP version(s): %s" % ', '.join(list(split.keys())))
    return split[4], split[6]


def ip_is_sticky_or_auto(ip_address):
    """Return True if the `ip_address` alloc_type is STICKY or AUTO."""
    return ip_address.alloc_type in [
        IPADDRESS_TYPE.STICKY, IPADDRESS_TYPE.AUTO]


def get_best_interface(interfaces):
    """Return `Interface` from `interfaces` that is the best.

    This is used by `get_subnet_to_interface_mapping` to select the very best
    interface on a `Subnet`. Bond interfaces are selected over physical/vlan
    interfaces.
    """
    best_interface = None
    for interface in interfaces:
        if best_interface is None:
            best_interface = interface
        elif (best_interface.type == INTERFACE_TYPE.PHYSICAL and
                interface.type == INTERFACE_TYPE.BOND):
            best_interface = interface
        elif (best_interface.type == INTERFACE_TYPE.VLAN and
                interface.type == INTERFACE_TYPE.PHYSICAL):
            best_interface = interface
    return best_interface


def get_best_interface_for_subnet(rack_controller, subnet):
    """Return best `Interface` for `rack_controller` that has access to
    `subnet`."""
    return get_best_interface(
        rack_controller.interface_set.filter(
            vlan__subnet=subnet).order_by('id'))


def get_managed_subnets_for(rack_controller):
    """Return list of `Subnet` for the `rack_controller`."""
    # Get all subnets that are managed by this rack controller.
    interfaces = rack_controller.interface_set.filter(
        Q(vlan__dhcp_on=True) & (
            Q(vlan__primary_rack=rack_controller) |
            Q(vlan__secondary_rack=rack_controller)))
    interfaces = interfaces.prefetch_related("vlan__subnet_set")
    return {
        subnet
        for interface in interfaces
        for subnet in interface.vlan.subnet_set.all()
    }


def ip_is_on_vlan(ip_address, vlan):
    """Return True if `ip_address` is on `vlan`."""
    return (
        ip_is_sticky_or_auto(ip_address) and
        ip_address.subnet.vlan_id == vlan.id and
        ip_address.ip is not None and
        ip_address.ip != "")


def get_ip_address_for_interface(interface, vlan):
    """Return the IP address for `interface` on `vlan`."""
    for ip_address in interface.ip_addresses.all():
        if ip_is_on_vlan(ip_address, vlan):
            return ip_address
    return None


def get_ip_address_for_rack_controller(rack_controller, vlan):
    """Return the IP address for `rack_controller` on `vlan`."""
    # First we build a list of all interfaces that have an IP address
    # on that vlan. Then we pick the best interface for that vlan
    # based on the `get_best_interface` function.
    interfaces = rack_controller.interface_set.all().prefetch_related(
        "ip_addresses__subnet")
    matching_interfaces = set()
    for interface in interfaces:
        for ip_address in interface.ip_addresses.all():
            if ip_is_on_vlan(ip_address, vlan):
                matching_interfaces.add(interface)
    interface = get_best_interface(matching_interfaces)
    return get_ip_address_for_interface(interface, vlan)


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


def make_pools_for_subnet(subnet, failover_peer=None):
    """Return list of pools to create in the DHCP config for `subnet`."""
    pools = []
    for ip_range in subnet.get_dynamic_ranges().order_by('id'):
        pool = {
            "ip_range_low": ip_range.start_ip,
            "ip_range_high": ip_range.end_ip,
        }
        if failover_peer is not None:
            pool["failover_peer"] = failover_peer
        pools.append(pool)
    return pools


def make_subnet_config(
        rack_controller, subnet, dns_servers, ntp_server, default_domain,
        failover_peer=None):
    """Return DHCP subnet configuration dict for a rack interface."""
    ip_network = subnet.get_ipnetwork()
    interface = get_best_interface_for_subnet(rack_controller, subnet)
    return {
        'subnet': str(ip_network.network),
        'subnet_mask': str(ip_network.netmask),
        'subnet_cidr': str(ip_network.cidr),
        'broadcast_ip': str(ip_network.broadcast),
        'interface': interface.name,
        'router_ip': (
            '' if not subnet.gateway_ip
            else str(subnet.gateway_ip)),
        'dns_servers': dns_servers,
        'ntp_server': ntp_server,
        'domain_name': default_domain.name,
        'pools': make_pools_for_subnet(subnet, failover_peer),
        'hosts': make_hosts_for_subnet(subnet),
        }


def make_failover_peer_config(vlan, rack_controller):
    """Return DHCP failover peer configuration dict for a rack controller."""
    is_primary = vlan.primary_rack_id == rack_controller.id
    interface_ip_address = get_ip_address_for_rack_controller(
        rack_controller, vlan)
    if is_primary:
        peer_address = get_ip_address_for_rack_controller(
            vlan.secondary_rack, vlan)
    else:
        peer_address = get_ip_address_for_rack_controller(
            vlan.primary_rack, vlan)
    name = "failover-vlan-%d" % vlan.id
    return name, {
        "name": name,
        "mode": "primary" if is_primary else "secondary",
        "address": str(interface_ip_address.ip),
        "peer_address": str(peer_address.ip),
    }


def get_dhcp_configure_for(
        ip_version, rack_controller, subnets, ntp_server, domain):
    """Get the DHCP configuration for `ip_version`."""
    # Circular imports.
    from maasserver.dns.zonegenerator import get_dns_server_address

    try:
        dns_servers = get_dns_server_address(
            rack_controller, ipv4=(ip_version == 4), ipv6=(ip_version == 6))
    except UnresolvableHost:
        # No IPv6 DNS server addresses found.  As a space-separated string,
        # that becomes the empty string.
        dns_servers = ''

    # Generate the failover peers and the subnet configuration.
    failover_peers = {}
    subnet_configs = []
    for subnet in subnets:
        peer_name = None
        if subnet.vlan.secondary_rack_id is not None:
            if subnet.vlan not in failover_peers:
                peer_name, peer_config = make_failover_peer_config(
                    subnet.vlan, rack_controller)
                failover_peers[subnet.vlan] = (peer_name, peer_config)
            else:
                (peer_name, peer_config) = failover_peers[subnet.vlan]

        subnet_config = make_subnet_config(
            rack_controller, subnet, dns_servers, ntp_server,
            domain, peer_name)
        subnet_configs.append(subnet_config)
    return [
        config
        for _, config in failover_peers.values()
    ], subnet_configs


@synchronous
@transactional
def get_dhcp_configuration(rack_controller):
    """Return tuple with IPv4 and IPv6 configurations for the
    rack controller."""
    # Get list of all subnets that are being managed by the rack controller.
    subnets = get_managed_subnets_for(rack_controller)

    # Split the subnets into IPv4 and IPv6 subnets.
    subnets_v4, subnets_v6 = split_ipv4_ipv6_subnets(subnets)

    # Configure both DHCPv4 and DHCPv6 on the rack controller.
    ntp_server = Config.objects.get_config("ntp_server")
    default_domain = Domain.objects.get_default_domain()
    failover_peers_v4, subnets_v4 = get_dhcp_configure_for(
        4, rack_controller, subnets_v4, ntp_server, default_domain)
    failover_peers_v6, subnets_v6 = get_dhcp_configure_for(
        6, rack_controller, subnets_v6, ntp_server, default_domain)
    return (
        get_omapi_key(),
        failover_peers_v4, subnets_v4,
        failover_peers_v6, subnets_v6)


@asynchronous
@inlineCallbacks
def configure_dhcp(rack_controller):
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
    client = yield getClientFor(rack_controller.system_id)

    # Get configuration for both IPv4 and IPv6.
    omapi_key, failover_peers_v4, subnets_v4, failover_peers_v6, subnets_v6 = (
        yield deferToDatabase(
            get_dhcp_configuration, rack_controller))

    # Configure both IPv4 and IPv6.
    yield client(
        ConfigureDHCPv4, omapi_key=omapi_key,
        failover_peers=failover_peers_v4, subnet_configs=subnets_v4)
    yield client(
        ConfigureDHCPv6, omapi_key=omapi_key,
        failover_peers=failover_peers_v6, subnet_configs=subnets_v6)
