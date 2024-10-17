# Copyright 2012-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DHCP management module."""

import base64
from collections import defaultdict, namedtuple
from itertools import groupby
from operator import itemgetter
from typing import Iterable, Optional, Union

from django.conf import settings
from django.db.models import Q
from netaddr import IPAddress, IPNetwork
from twisted.internet.defer import inlineCallbacks

from maasserver.dns.zonegenerator import (
    get_dns_search_paths,
    get_dns_server_addresses,
)
from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    IPRANGE_TYPE,
    SERVICE_STATUS,
)
from maasserver.exceptions import UnresolvableHost
from maasserver.models import (
    Config,
    DHCPSnippet,
    Domain,
    RackController,
    ReservedIP,
    Service,
    StaticIPAddress,
    Subnet,
    VLAN,
)
from maasserver.models.subnet import get_boot_rackcontroller_ips
from maasserver.rpc import getClientFor
from maasserver.secrets import SecretManager, SecretNotFound
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maasserver.workflow import start_workflow
from maastemporalworker.workflow.dhcp import ConfigureDHCPParam
from provisioningserver.dhcp.config import get_config_v4, get_config_v6
from provisioningserver.dhcp.omapi import generate_omapi_key
from provisioningserver.logger import LegacyLogger
from provisioningserver.rpc.cluster import ConfigureDHCPv4, ConfigureDHCPv6
from provisioningserver.rpc.clusterservice import DHCP_TIMEOUT
from provisioningserver.utils.network import get_source_address
from provisioningserver.utils.text import split_string_list
from provisioningserver.utils.twisted import asynchronous, synchronous

log = LegacyLogger()


def get_omapi_key():
    """Return the OMAPI key for all DHCP servers that are ran by MAAS."""
    manager = SecretManager()
    try:
        key = manager.get_simple_secret("omapi-key")
    except SecretNotFound:
        key = generate_omapi_key()
        manager.set_simple_secret("omapi-key", key)
    return key


def split_managed_ipv4_ipv6_subnets(subnets: Iterable[Subnet]):
    """Divide `subnets` into IPv4 ones and IPv6 ones.

    :param subnets: A sequence of subnets.
    :return: A tuple of two separate sequences: IPv4 subnets and IPv6 subnets.
    """
    split = defaultdict(list)
    for subnet in (s for s in subnets if s.managed is True):
        split[subnet.get_ipnetwork().version].append(subnet)
    assert len(split) <= 2, "Unexpected IP version(s): %s" % ", ".join(
        list(split.keys())
    )
    return split[4], split[6]


def ip_is_sticky_or_auto(ip_address):
    """Return True if the `ip_address` alloc_type is STICKY or AUTO."""
    return ip_address.alloc_type in [
        IPADDRESS_TYPE.STICKY,
        IPADDRESS_TYPE.AUTO,
    ]


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
        elif (
            best_interface.type == INTERFACE_TYPE.PHYSICAL
            and interface.type == INTERFACE_TYPE.BOND
        ):
            best_interface = interface
        elif (
            best_interface.type == INTERFACE_TYPE.VLAN
            and interface.type == INTERFACE_TYPE.PHYSICAL
        ):
            best_interface = interface
    return best_interface


def ip_is_version(ip_address, ip_version):
    """Return True if `ip_address` is the same IP version as `ip_version`."""
    return (
        ip_address.ip is not None
        and ip_address.ip != ""
        and IPAddress(ip_address.ip).version == ip_version
    )


def _key_interface_subnet_dynamic_range_count(interface):
    """Return the number of dynamic ranges for the subnet on the interface."""
    count = 0
    for ip_address in interface.ip_addresses.all():
        for ip_range in ip_address.subnet.iprange_set.all():
            if ip_range.type == IPRANGE_TYPE.DYNAMIC:
                count += 1
    return count


def _ip_version_on_vlan(ip_address, ip_version, vlan):
    """Return True when the `ip_address` is the same `ip_version` and is on
    the same `vlan` or relay VLAN's for the `vlan."""
    return (
        ip_is_version(ip_address, ip_version)
        and ip_address.subnet is not None
        and ip_address.subnet.vlan is not None
        and (
            ip_address.subnet.vlan == vlan
            or vlan in list(ip_address.subnet.vlan.relay_vlans.all())
        )
    )


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
    for (
        interface
    ) in rack_controller.current_config.interface_set.all().prefetch_related(
        "ip_addresses__subnet__vlan__relay_vlans",
        "ip_addresses__subnet__iprange_set",
    ):
        for ip_address in interface.ip_addresses.all():
            if ip_address.alloc_type in [
                IPADDRESS_TYPE.AUTO,
                IPADDRESS_TYPE.STICKY,
            ]:
                if _ip_version_on_vlan(ip_address, ip_version, vlan):
                    interfaces_with_static.append(interface)
                    break
            elif ip_address.alloc_type == IPADDRESS_TYPE.DISCOVERED:
                if _ip_version_on_vlan(ip_address, ip_version, vlan):
                    interfaces_with_discovered.append(interface)
                    break
    if len(interfaces_with_static) == 1:
        return interfaces_with_static
    elif len(interfaces_with_static) > 1:
        return sorted(
            interfaces_with_static,
            key=_key_interface_subnet_dynamic_range_count,
            reverse=True,
        )
    elif len(interfaces_with_discovered) == 1:
        return interfaces_with_discovered
    elif len(interfaces_with_discovered) > 1:
        return sorted(
            interfaces_with_discovered,
            key=_key_interface_subnet_dynamic_range_count,
            reverse=True,
        )
    else:
        return []


def gen_managed_vlans_for(rack_controller):
    """Yeilds each `VLAN` for the `rack_controller` when DHCP is enabled and
    `rack_controller` is either the `primary_rack` or the `secondary_rack`.
    """
    interfaces = rack_controller.current_config.interface_set.filter(
        Q(vlan__dhcp_on=True)
        & (
            Q(vlan__primary_rack=rack_controller)
            | Q(vlan__secondary_rack=rack_controller)
        )
    )
    interfaces = interfaces.prefetch_related("vlan__relay_vlans")
    for interface in interfaces:
        yield interface.vlan
        yield from interface.vlan.relay_vlans.all()


def ip_is_on_vlan(ip_address, vlan):
    """Return True if `ip_address` is on `vlan`."""
    return (
        ip_is_sticky_or_auto(ip_address)
        and ip_address.subnet is not None
        and ip_address.subnet.vlan_id == vlan.id
        and ip_address.ip is not None
        and ip_address.ip != ""
    )


def get_ip_address_for_interface(interface, vlan, ip_version: int):
    """Return the IP address for `interface` on `vlan`."""
    for ip_address in interface.ip_addresses.all():
        if ip_is_version(ip_address, ip_version) and ip_is_on_vlan(
            ip_address, vlan
        ):
            return ip_address
    return None


def get_ip_address_for_rack_controller(rack_controller, vlan, ip_version: int):
    """Return the IP address for `rack_controller` on `vlan`."""
    # First we build a list of all interfaces that have an IP address
    # on that vlan. Then we pick the best interface for that vlan
    # based on the `get_best_interface` function.
    interfaces = (
        rack_controller.current_config.interface_set.all().prefetch_related(
            "ip_addresses__subnet"
        )
    )
    matching_interfaces = set()
    for interface in interfaces:
        for ip_address in interface.ip_addresses.all():
            if ip_is_version(ip_address, ip_version) and ip_is_on_vlan(
                ip_address, vlan
            ):
                matching_interfaces.add(interface)
    interface = get_best_interface(matching_interfaces)
    return get_ip_address_for_interface(interface, vlan, ip_version)


def get_ntp_server_addresses_for_rack(rack: RackController) -> dict:
    """Return a map of rack IP addresses suitable for NTP.

    These are keyed by `(subnet-space-id, subnet-ip-address-family)`, e.g.::

      {(73, 4): "192.168.1.1"}

    Only a single routable address for the rack will be returned in each
    space+family group even if there are multiple.
    """
    rack_addresses = StaticIPAddress.objects.filter(
        interface__enabled=True,
        interface__node_config__node=rack,
        alloc_type__in={IPADDRESS_TYPE.STICKY, IPADDRESS_TYPE.USER_RESERVED},
    )
    rack_addresses = rack_addresses.exclude(subnet__isnull=True)
    rack_addresses = rack_addresses.order_by(
        # Prefer subnets with DHCP enabled.
        "-subnet__vlan__dhcp_on",
        "subnet__vlan__space_id",
        "subnet__cidr",
        "ip",
    )
    rack_addresses = rack_addresses.values_list(
        "subnet__vlan__dhcp_on", "subnet__vlan__space_id", "subnet__cidr", "ip"
    )

    def get_space_id_and_family(record):
        dhcp_on, space_id, cidr, ip = record
        return space_id, IPNetwork(cidr).version

    def sort_key__dhcp_on__ip(record):
        dhcp_on, space_id, cidr, ip = record
        return -int(dhcp_on), IPAddress(ip)

    best_ntp_servers = {
        space_id_and_family: min(group, key=sort_key__dhcp_on__ip)
        for space_id_and_family, group in groupby(
            rack_addresses, get_space_id_and_family
        )
    }
    return {key: value[3] for key, value in best_ntp_servers.items()}


def make_interface_hostname(interface):
    """Return the host declaration name for DHCPD for this `interface`."""
    interface_name = interface.name.replace(".", "-")
    if (
        interface.type == INTERFACE_TYPE.UNKNOWN
        and interface.node_config is None
    ):
        return "unknown-%d-%s" % (interface.id, interface_name)
    else:
        return f"{interface.node_config.node.hostname}-{interface_name}"


def make_dhcp_snippet(dhcp_snippet):
    """Return the DHCPSnippet as a dictionary."""
    return {
        "name": dhcp_snippet.name,
        "description": dhcp_snippet.description,
        "value": dhcp_snippet.value.data,
    }


def make_hosts_for_subnets(
    subnets: list[Subnet], nodes_dhcp_snippets: list | None = None
) -> list[dict]:
    """Return list of host entries to create in the DHCP configuration for the
    given `subnets`.
    """
    if nodes_dhcp_snippets is None:
        nodes_dhcp_snippets = []

    def get_dhcp_snippets_for_interface(interface):
        dhcp_snippets = list()
        for dhcp_snippet in nodes_dhcp_snippets:
            iface_node = (
                interface.node_config.node if interface.node_config else None
            )
            if dhcp_snippet.node == iface_node:
                dhcp_snippets.append(make_dhcp_snippet(dhcp_snippet))
        return dhcp_snippets

    sips = StaticIPAddress.objects.filter(
        alloc_type__in=[
            IPADDRESS_TYPE.AUTO,
            IPADDRESS_TYPE.STICKY,
            IPADDRESS_TYPE.USER_RESERVED,
        ],
        subnet__in=subnets,
        ip__isnull=False,
        temp_expires_on__isnull=True,
    ).order_by("id")
    hosts = []
    interface_ids = set()
    for sip in sips:
        # Skip blank IP addresses.
        if sip.ip == "":
            continue
        # Skip temp IP addresses.
        if sip.temp_expires_on:
            continue

        # Add all interfaces attached to this IP address.
        for interface in sip.interface_set.order_by("id"):
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
                        hosts.append(
                            {
                                "host": make_interface_hostname(parent),
                                "mac": str(parent.mac_address),
                                "ip": str(sip.ip),
                                "dhcp_snippets": get_dhcp_snippets_for_interface(
                                    parent
                                ),
                            }
                        )
                hosts.append(
                    {
                        "host": make_interface_hostname(interface),
                        "mac": str(interface.mac_address),
                        "ip": str(sip.ip),
                        "dhcp_snippets": get_dhcp_snippets_for_interface(
                            interface
                        ),
                    }
                )
            else:
                hosts.append(
                    {
                        "host": make_interface_hostname(interface),
                        "mac": str(interface.mac_address),
                        "ip": str(sip.ip),
                        "dhcp_snippets": get_dhcp_snippets_for_interface(
                            interface
                        ),
                    }
                )

    for reserved_ip in ReservedIP.objects.filter(subnet__in=subnets):
        hosts.append(
            {
                "host": "",
                "mac": reserved_ip.mac_address,
                "ip": reserved_ip.ip,
                "dhcp_snippets": [],
            }
        )

    return hosts


def make_pools_for_subnet(subnet, dhcp_snippets, failover_peer=None):
    """Return list of pools to create in the DHCP config for `subnet`."""
    pools = []
    for ip_range in subnet.get_dynamic_ranges().order_by("id"):
        pool = {
            "ip_range_low": ip_range.start_ip,
            "ip_range_high": ip_range.end_ip,
            "dhcp_snippets": dhcp_snippets.get(ip_range.id, []),
        }
        if failover_peer is not None:
            pool["failover_peer"] = failover_peer
        pools.append(pool)
    return pools


def make_subnet_config(
    rack_controller,
    subnet,
    default_dns_servers: Optional[list],
    ntp_servers: Union[list, dict],
    default_domain,
    search_list=None,
    failover_peer=None,
    subnets_dhcp_snippets: list = None,
    peer_rack=None,
):
    """Return DHCP subnet configuration dict for a rack interface.

    :param ntp_servers: Either a list of NTP server addresses or hostnames to
        include in DHCP responses, or a dict; if the latter, it ought to match
        the output from `get_ntp_server_addresses_for_rack`.
    """
    ip_network = subnet.get_ipnetwork()
    dns_servers = []
    ipranges_dhcp_snippets = dict()
    if subnet.allow_dns and default_dns_servers:
        # If the MAAS DNS server is enabled make sure that is used first.
        if subnet.gateway_ip:
            dns_servers += default_dns_servers
        else:
            # if there is no gateway, only provide in-subnet dns servers
            dns_servers += [
                ipaddress
                for ipaddress in default_dns_servers
                if ipaddress in ip_network
            ]
    if subnet.dns_servers:
        # Add DNS user defined DNS servers
        dns_servers += [IPAddress(server) for server in subnet.dns_servers]
    if subnets_dhcp_snippets is None:
        subnets_dhcp_snippets = []
    else:
        subnet_only_dhcp_snippets = []
        for snippet in subnets_dhcp_snippets:
            if snippet.iprange is not None:
                iprange_dhcp_snippets = ipranges_dhcp_snippets.get(
                    snippet.iprange.id, []
                )
                iprange_dhcp_snippets.append(make_dhcp_snippet(snippet))
                ipranges_dhcp_snippets[snippet.iprange.id] = (
                    iprange_dhcp_snippets
                )
            else:
                subnet_only_dhcp_snippets.append(snippet)
        subnets_dhcp_snippets = subnet_only_dhcp_snippets

    subnet_config = {
        "subnet": str(ip_network.network),
        "subnet_mask": str(ip_network.netmask),
        "subnet_cidr": str(ip_network.cidr),
        "broadcast_ip": str(ip_network.broadcast),
        "router_ip": ("" if not subnet.gateway_ip else str(subnet.gateway_ip)),
        "dns_servers": dns_servers,
        "ntp_servers": get_ntp_servers(ntp_servers, subnet, peer_rack),
        "domain_name": default_domain.name,
        "pools": make_pools_for_subnet(
            subnet,
            ipranges_dhcp_snippets,
            failover_peer,
        ),
        "dhcp_snippets": [
            make_dhcp_snippet(dhcp_snippet)
            for dhcp_snippet in subnets_dhcp_snippets
            if dhcp_snippet.subnet == subnet
        ],
        "disabled_boot_architectures": subnet.disabled_boot_architectures,
    }
    if search_list is not None:
        subnet_config["search_list"] = search_list
    return subnet_config


def make_failover_peer_config(vlan, rack_controller, ip_version: int):
    """Return DHCP failover peer configuration dict for a rack controller."""
    is_primary = vlan.primary_rack_id == rack_controller.id
    interface_ip_address = get_ip_address_for_rack_controller(
        rack_controller, vlan, ip_version
    )
    if is_primary:
        peer_rack = vlan.secondary_rack
    else:
        peer_rack = vlan.primary_rack
    peer_address = get_ip_address_for_rack_controller(
        peer_rack, vlan, ip_version
    )
    name = "failover-vlan-%d" % vlan.id
    return (
        name,
        {
            "name": name,
            "mode": "primary" if is_primary else "secondary",
            "address": str(interface_ip_address.ip),
            "peer_address": str(peer_address.ip),
        },
        peer_rack,
    )


def get_ntp_servers(ntp_servers, subnet, peer_rack):
    """Return the list of NTP servers, based on the initial input list of
    servers or dictionary, the subnet the servers will be advertised on,
    and the peer rack controller (if present).
    """
    if isinstance(ntp_servers, dict):
        # If ntp_servers is a dict, that means it maps each
        # (space_id, address_family) to the best NTP server for that space.
        # If it's already a list, that means we're just using the external
        # NTP server(s).
        space_address_family = (subnet.vlan.space_id, subnet.get_ip_version())
        ntp_server = ntp_servers.get(space_address_family)
        if ntp_server is None:
            return []
        else:
            if peer_rack is not None:
                alternates = get_ntp_server_addresses_for_rack(peer_rack)
                alternate_ntp_server = alternates.get(space_address_family)
                if alternate_ntp_server is not None:
                    return [ntp_server, alternate_ntp_server]
            return [ntp_server]
    else:
        # Return the original input; it was already a list.
        return ntp_servers


def get_default_dns_servers(rack_controller, subnet, use_rack_proxy=True):
    """Calculates the DNS servers on a per-subnet basis, to make sure we
    choose the best possible IP addresses for each subnet.

    :param rack_controller: The RackController to be used as the DHCP server.
    :param subnet: The DHCP-managed subnet.
    :param use_rack_proxy: Whether to proxy DNS through the rack controller
      or not.
    """
    if not subnet.allow_dns:
        # This subnet isn't allowed to use region or rack addresses for dns
        return []

    ip_version = subnet.get_ip_version()
    default_region_ip = get_source_address(subnet.get_ipnetwork())
    try:
        dns_servers = get_dns_server_addresses(
            rack_controller,
            ipv4=(ip_version == 4),
            ipv6=(ip_version == 6),
            include_alternates=True,
            default_region_ip=default_region_ip,
        )
    except UnresolvableHost:
        dns_servers = []

    if default_region_ip:
        default_region_ip = IPAddress(default_region_ip)
    if use_rack_proxy:
        # Add the IP address for the rack controllers on the subnet before the
        # region DNS servers.
        rack_ips = [
            IPAddress(ip) for ip in get_boot_rackcontroller_ips(subnet)
        ]
        if dns_servers:
            dns_servers = rack_ips + [
                server
                for server in dns_servers
                if server not in rack_ips and server != default_region_ip
            ]
        elif rack_ips:
            dns_servers = rack_ips
    if default_region_ip in dns_servers:
        # Make sure the region DNS server comes last
        dns_servers = [
            server for server in dns_servers if server != default_region_ip
        ] + [default_region_ip]
    # If no DNS servers were found give the region IP. This won't go through
    # the rack but its better than nothing.
    if not dns_servers:
        if default_region_ip:
            log.warn("No DNS servers found, DHCP defaulting to region IP.")
            dns_servers = [default_region_ip]
        else:
            log.warn("No DNS servers found.")

    return dns_servers


def get_dhcp_configure_for(
    ip_version: int,
    rack_controller,
    vlan,
    subnets: list,
    ntp_servers: Union[list, dict],
    domain,
    search_list=None,
    dhcp_snippets: Iterable = None,
    use_rack_proxy=True,
):
    """Get the DHCP configuration for `ip_version`."""
    # Select the best interface for this VLAN. This is an interface that
    # at least has an IP address.
    interfaces = get_interfaces_with_ip_on_vlan(
        rack_controller, vlan, ip_version
    )
    interface = get_best_interface(interfaces)

    has_secondary = vlan.secondary_rack_id is not None

    if has_secondary:
        # Generate the failover peer for this VLAN.
        peer_name, peer_config, peer_rack = make_failover_peer_config(
            vlan, rack_controller, ip_version
        )
    else:
        peer_name, peer_config, peer_rack = None, None, None

    if dhcp_snippets is None:
        dhcp_snippets = []

    subnets_dhcp_snippets = [
        dhcp_snippet
        for dhcp_snippet in dhcp_snippets
        if dhcp_snippet.subnet is not None
    ]
    nodes_dhcp_snippets = [
        dhcp_snippet
        for dhcp_snippet in dhcp_snippets
        if dhcp_snippet.node is not None
    ]

    # Generate the shared network configurations.
    subnet_configs = []
    for subnet in subnets:
        maas_dns_servers = get_default_dns_servers(
            rack_controller, subnet, use_rack_proxy
        )
        subnet_configs.append(
            make_subnet_config(
                rack_controller,
                subnet,
                maas_dns_servers,
                ntp_servers,
                domain,
                search_list,
                peer_name,
                subnets_dhcp_snippets,
                peer_rack,
            )
        )

    # Generate the hosts for all subnets.
    hosts = make_hosts_for_subnets(subnets, nodes_dhcp_snippets)
    return (
        peer_config,
        sorted(subnet_configs, key=itemgetter("subnet")),
        hosts,
        None if interface is None else interface.name,
    )


@synchronous
@transactional
def get_dhcp_configuration(rack_controller, test_dhcp_snippet=None):
    """Return tuple with IPv4 and IPv6 configurations for the
    rack controller."""
    # Get list of all vlans that are being managed by the rack controller.
    vlans = gen_managed_vlans_for(rack_controller)

    # Group the subnets on each VLAN into IPv4 and IPv6 subnets.
    vlan_subnets = {
        vlan: split_managed_ipv4_ipv6_subnets(vlan.subnet_set.all())
        for vlan in vlans
    }

    # Get the list of all DHCP snippets so we only have to query the database
    # 1 + (the number of DHCP snippets used in this VLAN) instead of
    # 1 + (the number of subnets in this VLAN) +
    #     (the number of nodes in this VLAN)
    dhcp_snippets = DHCPSnippet.objects.filter(enabled=True)
    # If we're testing a DHCP Snippet insert it into our list
    if test_dhcp_snippet is not None:
        dhcp_snippets = list(dhcp_snippets)
        replaced_snippet = False
        # If its an existing DHCPSnippet with its contents being modified
        # replace it with the new values and test
        for i, dhcp_snippet in enumerate(dhcp_snippets):
            if dhcp_snippet.id == test_dhcp_snippet.id:
                dhcp_snippets[i] = test_dhcp_snippet
                replaced_snippet = True
                break
        # If the snippet wasn't updated its either new or testing a currently
        # disabled snippet
        if not replaced_snippet:
            dhcp_snippets.append(test_dhcp_snippet)
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

    # DNS can either go through the rack controller or directly to the
    # region controller.
    use_rack_proxy = Config.objects.get_config("use_rack_proxy")

    # NTP configuration can get tricky...
    ntp_external_only = Config.objects.get_config("ntp_external_only")
    if ntp_external_only:
        ntp_servers = Config.objects.get_config("ntp_servers")
        ntp_servers = list(split_string_list(ntp_servers))
    else:
        ntp_servers = get_ntp_server_addresses_for_rack(rack_controller)

    default_domain = Domain.objects.get_default_domain()
    search_list = [default_domain.name] + [
        name
        for name in sorted(get_dns_search_paths())
        if name != default_domain.name
    ]
    for vlan, (subnets_v4, subnets_v6) in vlan_subnets.items():
        # IPv4
        if len(subnets_v4) > 0:
            config = get_dhcp_configure_for(
                4,
                rack_controller,
                vlan,
                subnets_v4,
                ntp_servers,
                default_domain,
                search_list=search_list,
                dhcp_snippets=dhcp_snippets,
                use_rack_proxy=use_rack_proxy,
            )
            failover_peer, subnets, hosts, interface = config
            if failover_peer is not None:
                failover_peers_v4.append(failover_peer)
            shared_network = {
                "name": "vlan-%d" % vlan.id,
                "mtu": vlan.mtu,
                "subnets": subnets,
            }
            shared_networks_v4.append(shared_network)
            hosts_v4.extend(hosts)
            if interface is not None:
                interfaces_v4.add(interface)
                shared_network["interface"] = interface
        # IPv6
        if len(subnets_v6) > 0:
            config = get_dhcp_configure_for(
                6,
                rack_controller,
                vlan,
                subnets_v6,
                ntp_servers,
                default_domain,
                search_list=search_list,
                dhcp_snippets=dhcp_snippets,
                use_rack_proxy=use_rack_proxy,
            )
            failover_peer, subnets, hosts, interface = config
            if failover_peer is not None:
                failover_peers_v6.append(failover_peer)
            shared_network = {
                "name": "vlan-%d" % vlan.id,
                "mtu": vlan.mtu,
                "subnets": subnets,
            }
            shared_networks_v6.append(shared_network)
            hosts_v6.extend(hosts)
            if interface is not None:
                interfaces_v6.add(interface)
                shared_network["interface"] = interface
    # When no interfaces exist for each IP version clear the shared networks
    # as DHCP server cannot be started and needs to be stopped.
    if len(interfaces_v4) == 0:
        shared_networks_v4 = {}
    if len(interfaces_v6) == 0:
        shared_networks_v6 = {}
    return DHCPConfigurationForRack(
        failover_peers_v4,
        shared_networks_v4,
        hosts_v4,
        interfaces_v4,
        failover_peers_v6,
        shared_networks_v6,
        hosts_v6,
        interfaces_v6,
        get_omapi_key(),
        global_dhcp_snippets,
    )


DHCPConfigurationForRack = namedtuple(
    "DHCPConfigurationForRack",
    (
        "failover_peers_v4",
        "shared_networks_v4",
        "hosts_v4",
        "interfaces_v4",
        "failover_peers_v6",
        "shared_networks_v6",
        "hosts_v6",
        "interfaces_v6",
        "omapi_key",
        "global_dhcp_snippets",
    ),
)


def generate_dhcp_configuration(rack_controller):
    # Get configuration for both IPv4 and IPv6.
    config = get_dhcp_configuration(rack_controller)

    # Fix interfaces to go over the wire.
    interfaces_v4 = " ".join(sorted(name for name in config.interfaces_v4))
    interfaces_v6 = " ".join(sorted(name for name in config.interfaces_v6))

    result = {}

    result["dhcpd"] = base64.b64encode(
        get_config_v4(
            template_name="dhcpd.conf.template",
            global_dhcp_snippets=config.global_dhcp_snippets,
            failover_peers=config.failover_peers_v4,
            shared_networks=config.shared_networks_v4,
            hosts=config.hosts_v4,
            omapi_key=config.omapi_key,
        ).encode("utf-8")
    ).decode("utf-8")

    result["dhcpd_interfaces"] = base64.b64encode(
        interfaces_v4.encode("utf-8")
    ).decode("utf-8")

    result["dhcpd6"] = base64.b64encode(
        get_config_v6(
            template_name="dhcpd6.conf.template",
            global_dhcp_snippets=config.global_dhcp_snippets,
            failover_peers=config.failover_peers_v6,
            shared_networks=config.shared_networks_v6,
            hosts=config.hosts_v6,
            omapi_key=config.omapi_key,
        ).encode("utf-8")
    ).decode("utf-8")

    result["dhcpd6_interfaces"] = base64.b64encode(
        interfaces_v6.encode("utf-8")
    ).decode("utf-8")

    return result


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
    config = yield deferToDatabase(get_dhcp_configuration, rack_controller)

    # Fix interfaces to go over the wire.
    interfaces_v4 = [{"name": name} for name in config.interfaces_v4]
    interfaces_v6 = [{"name": name} for name in config.interfaces_v6]

    # Configure both IPv4 and IPv6.
    ipv4_exc, ipv6_exc = None, None
    ipv4_status, ipv6_status = SERVICE_STATUS.UNKNOWN, SERVICE_STATUS.UNKNOWN

    try:
        yield client(
            ConfigureDHCPv4,
            _timeout=DHCP_TIMEOUT + 5,
            failover_peers=config.failover_peers_v4,
            interfaces=interfaces_v4,
            shared_networks=config.shared_networks_v4,
            hosts=config.hosts_v4,
            global_dhcp_snippets=config.global_dhcp_snippets,
            omapi_key=config.omapi_key,
        )
    except Exception as exc:
        ipv4_exc = exc
        ipv4_status = SERVICE_STATUS.DEAD
        log.err(
            None,
            "Error configuring DHCPv4 on rack controller '%s (%s)': %s"
            % (rack_controller.hostname, rack_controller.system_id, exc),
        )
    else:
        if len(config.shared_networks_v4) > 0:
            ipv4_status = SERVICE_STATUS.RUNNING
        else:
            ipv4_status = SERVICE_STATUS.OFF
        log.msg(
            "Successfully configured DHCPv4 on rack controller '%s (%s)'."
            % (rack_controller.hostname, rack_controller.system_id)
        )

    try:
        yield client(
            ConfigureDHCPv6,
            _timeout=DHCP_TIMEOUT + 5,
            failover_peers=config.failover_peers_v6,
            interfaces=interfaces_v6,
            shared_networks=config.shared_networks_v6,
            hosts=config.hosts_v6,
            global_dhcp_snippets=config.global_dhcp_snippets,
            omapi_key=config.omapi_key,
        )
    except Exception as exc:
        ipv6_exc = exc
        ipv6_status = SERVICE_STATUS.DEAD
        log.err(
            None,
            "Error configuring DHCPv6 on rack controller '%s (%s)': %s"
            % (rack_controller.hostname, rack_controller.system_id, exc),
        )
    else:
        if len(config.shared_networks_v6) > 0:
            ipv6_status = SERVICE_STATUS.RUNNING
        else:
            ipv6_status = SERVICE_STATUS.OFF
        log.msg(
            "Successfully configured DHCPv6 on rack controller '%s (%s)'."
            % (rack_controller.hostname, rack_controller.system_id)
        )

    # Update the status for both services so the user is always seeing the
    # most up to date status.
    @transactional
    def update_services():
        if ipv4_exc is None:
            ipv4_status_info = ""
        else:
            ipv4_status_info = str(ipv4_exc)
        if ipv6_exc is None:
            ipv6_status_info = ""
        else:
            ipv6_status_info = str(ipv6_exc)
        Service.objects.update_service_for(
            rack_controller, "dhcpd", ipv4_status, ipv4_status_info
        )
        Service.objects.update_service_for(
            rack_controller, "dhcpd6", ipv6_status, ipv6_status_info
        )

    yield deferToDatabase(update_services)

    # Raise the exceptions to the caller, it might want to retry. This raises
    # IPv4 before IPv6 if they both fail. No specific reason for this, if
    # the function is called again both will be performed.
    if ipv4_exc:
        raise ipv4_exc
    elif ipv6_exc:
        raise ipv6_exc


def get_racks_by_subnet(subnet):
    """Return the set of racks with at least one interface configured on the
    specified subnet.
    """
    racks = RackController.objects.filter(
        current_config__interface__ip_addresses__subnet__in=[subnet]
    )

    if subnet.vlan.relay_vlan_id:
        relay_vlan = VLAN.objects.get(id=subnet.vlan.relay_vlan_id)
        racks = racks.union(
            RackController.objects.filter(
                id__in=[
                    relay_vlan.primary_rack_id,
                    relay_vlan.secondary_rack_id,
                ]
            )
        )
    return racks


def _get_dhcp_rackcontrollers(dhcp_snippet):
    if dhcp_snippet.subnet is not None:
        return get_racks_by_subnet(dhcp_snippet.subnet)
    elif dhcp_snippet.node is not None:
        return dhcp_snippet.node.get_boot_rack_controllers()


def configure_dhcp_on_agents(
    system_ids: list[str] | None = None,
    vlan_ids: list[int] | None = None,
    subnet_ids: list[int] | None = None,
    static_ip_addr_ids: list[int] | None = None,
    ip_range_ids: list[int] | None = None,
    reserved_ip_ids: list[int] | None = None,
):
    return start_workflow(
        workflow_name="configure-dhcp",
        param=ConfigureDHCPParam(
            system_ids=system_ids,
            vlan_ids=vlan_ids,
            subnet_ids=subnet_ids,
            static_ip_addr_ids=static_ip_addr_ids,
            ip_range_ids=ip_range_ids,
            reserved_ip_ids=reserved_ip_ids,
        ),
        task_queue="region",
    )
