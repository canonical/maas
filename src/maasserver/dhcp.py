# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
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
    IPRANGE_TYPE,
)
from maasserver.exceptions import (
    DHCPConfigurationError,
    UnresolvableHost,
)
from maasserver.models import (
    Config,
    DHCPSnippet,
    Domain,
    StaticIPAddress,
)
from maasserver.rpc import getClientFor
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from netaddr import IPAddress
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


def ip_is_version(ip_address, ip_version):
    """Return True if `ip_address` is the same IP version as `ip_version`."""
    return (
        ip_address.ip is not None and
        ip_address.ip != "" and
        IPAddress(ip_address.ip).version == ip_version)


def _key_interface_subnet_dynamic_range_count(interface):
    """Return the number of dynamic ranges for the subnet on the interface."""
    count = 0
    for ip_address in interface.ip_addresses.all():
        for ip_range in ip_address.subnet.iprange_set.all():
            if ip_range.type == IPRANGE_TYPE.DYNAMIC:
                count += 1
    return count


def get_interfaces_with_ip_on_vlan(rack_controller, vlan, ip_version):
    """Return a list of interfaces that have an assigned IP address on `vlan`.

    The assigned IP address needs to be of same `ip_version`. Only a list of
    STICKY or AUTO addresses will be returned, unless none exists which will
    fallback to DISCOVERED addresses.

    The interfaces will be ordered so that interfaces with IP address on
    subnets for the VLAN that have dynamic IP ranges defined.
    """
    interfaces_with_static = []
    interfaces_with_discovered = []
    for interface in rack_controller.interface_set.all().prefetch_related(
            "ip_addresses__subnet__vlan",
            "ip_addresses__subnet__iprange_set"):
        for ip_address in interface.ip_addresses.all():
            if ip_address.alloc_type in [
                    IPADDRESS_TYPE.AUTO, IPADDRESS_TYPE.STICKY]:
                if (ip_is_version(ip_address, ip_version) and
                        ip_address.subnet is not None and
                        ip_address.subnet.vlan == vlan):
                    interfaces_with_static.append(interface)
                    break
            elif ip_address.alloc_type == IPADDRESS_TYPE.DISCOVERED:
                if (ip_is_version(ip_address, ip_version) and
                        ip_address.subnet is not None and
                        ip_address.subnet.vlan == vlan):
                    interfaces_with_discovered.append(interface)
                    break
    if len(interfaces_with_static) == 1:
        return interfaces_with_static
    elif len(interfaces_with_static) > 1:
        return sorted(
            interfaces_with_static,
            key=_key_interface_subnet_dynamic_range_count,
            reverse=True)
    elif len(interfaces_with_discovered) == 1:
        return interfaces_with_discovered
    elif len(interfaces_with_discovered) > 1:
        return sorted(
            interfaces_with_discovered,
            key=_key_interface_subnet_dynamic_range_count,
            reverse=True)
    else:
        return []


def get_managed_vlans_for(rack_controller):
    """Return list of `VLAN` for the `rack_controller` when DHCP is enabled and
    `rack_controller` is either the `primary_rack` or the `secondary_rack`.
    """
    interfaces = rack_controller.interface_set.filter(
        Q(vlan__dhcp_on=True) & (
            Q(vlan__primary_rack=rack_controller) |
            Q(vlan__secondary_rack=rack_controller))).select_related("vlan")
    return {
        interface.vlan
        for interface in interfaces
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


def make_dhcp_snippet(dhcp_snippet):
    """Return the DHCPSnippet as a dictionary."""
    return {
        "name": dhcp_snippet.name,
        "description": dhcp_snippet.description,
        "value": dhcp_snippet.value.data,
    }


def make_hosts_for_subnets(subnets, nodes_dhcp_snippets=[]):
    """Return list of host entries to create in the DHCP configuration for the
    given `subnets`.
    """
    def get_dhcp_snippets_for_interface(interface):
        dhcp_snippets = list()
        for dhcp_snippet in nodes_dhcp_snippets:
            if dhcp_snippet.node == interface.node:
                dhcp_snippets.append(make_dhcp_snippet(dhcp_snippet))
        return dhcp_snippets

    sips = StaticIPAddress.objects.filter(
        alloc_type__in=[
            IPADDRESS_TYPE.AUTO,
            IPADDRESS_TYPE.STICKY,
            IPADDRESS_TYPE.USER_RESERVED,
            ],
        subnet__in=subnets, ip__isnull=False).order_by('id')
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
                            'dhcp_snippets': get_dhcp_snippets_for_interface(
                                parent),
                        })
                hosts.append({
                    'host': make_interface_hostname(interface),
                    'mac': str(interface.mac_address),
                    'ip': str(sip.ip),
                    'dhcp_snippets': get_dhcp_snippets_for_interface(
                        interface),
                })
            else:
                hosts.append({
                    'host': make_interface_hostname(interface),
                    'mac': str(interface.mac_address),
                    'ip': str(sip.ip),
                    'dhcp_snippets': get_dhcp_snippets_for_interface(
                        interface),
                })
    return hosts


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
        failover_peer=None, subnets_dhcp_snippets=[]):
    """Return DHCP subnet configuration dict for a rack interface."""
    ip_network = subnet.get_ipnetwork()
    return {
        'subnet': str(ip_network.network),
        'subnet_mask': str(ip_network.netmask),
        'subnet_cidr': str(ip_network.cidr),
        'broadcast_ip': str(ip_network.broadcast),
        'router_ip': (
            '' if not subnet.gateway_ip
            else str(subnet.gateway_ip)),
        'dns_servers': dns_servers,
        'ntp_server': ntp_server,
        'domain_name': default_domain.name,
        'pools': make_pools_for_subnet(subnet, failover_peer),
        'dhcp_snippets': [
            make_dhcp_snippet(dhcp_snippet)
            for dhcp_snippet in subnets_dhcp_snippets
            if dhcp_snippet.subnet == subnet
            ],
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
        ip_version, rack_controller, vlan, subnets, ntp_server, domain,
        dhcp_snippets=[]):
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

    # Select the best interface for this VLAN. This is an interface that
    # at least has an IP address.
    interfaces = get_interfaces_with_ip_on_vlan(
        rack_controller, vlan, ip_version)
    interface = get_best_interface(interfaces)
    if interface is None:
        raise DHCPConfigurationError(
            "No interface on rack controller '%s' has an IP address on any "
            "subnet on VLAN '%s.%d'." % (
                rack_controller.hostname, vlan.fabric.name, vlan.vid))

    # Generate the failover peer for this VLAN.
    if vlan.secondary_rack_id is not None:
        peer_name, peer_config = make_failover_peer_config(
            vlan, rack_controller)
    else:
        peer_name, peer_config = None, None

    subnets_dhcp_snippets = [
        dhcp_snippet for dhcp_snippet in dhcp_snippets
        if dhcp_snippet.subnet is not None]
    nodes_dhcp_snippets = [
        dhcp_snippet for dhcp_snippet in dhcp_snippets
        if dhcp_snippet.node is not None]

    # Generate the shared network configurations.
    subnet_configs = []
    hosts = []
    for subnet in subnets:
        subnet_configs.append(
            make_subnet_config(
                rack_controller, subnet, dns_servers, ntp_server,
                domain, peer_name, subnets_dhcp_snippets))

    # Generate the hosts for all subnets.
    hosts = make_hosts_for_subnets(subnets, nodes_dhcp_snippets)
    return (
        peer_config, sorted(subnet_configs, key=itemgetter("subnet")),
        hosts, interface.name)


@synchronous
@transactional
def get_dhcp_configuration(rack_controller):
    """Return tuple with IPv4 and IPv6 configurations for the
    rack controller."""
    # Get list of all vlans that are being managed by the rack controller.
    vlans = get_managed_vlans_for(rack_controller)

    # Group the subnets on each VLAN into IPv4 and IPv6 subnets.
    vlan_subnets = {
        vlan: split_ipv4_ipv6_subnets(vlan.subnet_set.all())
        for vlan in vlans
    }

    # Get the list of all DHCP snippets so we only have to query the database
    # 1 + (the number of DHCP snippets used in this VLAN) instead of
    # 1 + (the number of subnets in this VLAN) +
    #     (the number of nodes in this VLAN)
    dhcp_snippets = DHCPSnippet.objects.filter(enabled=True)
    global_dhcp_snippets = [
        make_dhcp_snippet(dhcp_snippet)
        for dhcp_snippet in dhcp_snippets
        if dhcp_snippet.node is None and dhcp_snippet.subnet is None
        ]

    # Configure both DHCPv4 and DHCPv6 on the rack controller.
    failover_peers_v4 = []
    shared_networks_v4 = []
    hosts_v4 = []
    interfaces_v4 = set()
    failover_peers_v6 = []
    shared_networks_v6 = []
    hosts_v6 = []
    interfaces_v6 = set()
    ntp_server = Config.objects.get_config("ntp_server")
    default_domain = Domain.objects.get_default_domain()
    for vlan, (subnets_v4, subnets_v6) in vlan_subnets.items():
        # IPv4
        if len(subnets_v4) > 0:
            failover_peer, subnets, hosts, interface = get_dhcp_configure_for(
                4, rack_controller, vlan, subnets_v4,
                ntp_server, default_domain, dhcp_snippets)
            if failover_peer is not None:
                failover_peers_v4.append(failover_peer)
            shared_networks_v4.append({
                "name": "vlan-%d" % vlan.id,
                "subnets": subnets,
            })
            hosts_v4.extend(hosts)
            interfaces_v4.add(interface)

        # IPv6
        if len(subnets_v6) > 0:
            failover_peer, subnets, hosts, interface = get_dhcp_configure_for(
                6, rack_controller, vlan, subnets_v6,
                ntp_server, default_domain, dhcp_snippets)
            if failover_peer is not None:
                failover_peers_v6.append(failover_peer)
            shared_networks_v6.append({
                "name": "vlan-%d" % vlan.id,
                "subnets": subnets,
            })
            hosts_v6.extend(hosts)
            interfaces_v6.add(interface)
    return (
        get_omapi_key(),
        failover_peers_v4, shared_networks_v4, hosts_v4, interfaces_v4,
        failover_peers_v6, shared_networks_v6, hosts_v6, interfaces_v6,
        global_dhcp_snippets)


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
    (omapi_key, failover_peers_v4, shared_networks_v4, hosts_v4, interfaces_v4,
     failover_peers_v6, shared_networks_v6, hosts_v6, interfaces_v6,
     global_dhcp_snippets) = (
        yield deferToDatabase(get_dhcp_configuration, rack_controller))

    # Fix interfaces to go over the wire.
    interfaces_v4 = [
        {"name": name}
        for name in interfaces_v4
    ]
    interfaces_v6 = [
        {"name": name}
        for name in interfaces_v6
    ]

    # Configure both IPv4 and IPv6.
    yield client(
        ConfigureDHCPv4, omapi_key=omapi_key,
        failover_peers=failover_peers_v4, shared_networks=shared_networks_v4,
        hosts=hosts_v4, interfaces=interfaces_v4,
        global_dhcp_snippets=global_dhcp_snippets)
    yield client(
        ConfigureDHCPv6, omapi_key=omapi_key,
        failover_peers=failover_peers_v6, shared_networks=shared_networks_v6,
        hosts=hosts_v6, interfaces=interfaces_v6,
        global_dhcp_snippets=global_dhcp_snippets)
