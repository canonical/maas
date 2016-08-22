# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Write config output for ISC DHCPD."""

__all__ = [
    "DHCPConfigError",
    "get_config",
]

from itertools import (
    chain,
    repeat,
)
from platform import linux_distribution
import socket
from typing import Sequence

from netaddr import (
    IPAddress,
    IPNetwork,
)
from provisioningserver.boot import BootMethodRegistry
from provisioningserver.utils import (
    locate_template,
    typed,
)
import provisioningserver.utils.network as net_utils
from provisioningserver.utils.text import (
    normalise_to_comma_list,
    normalise_whitespace,
    split_string_list,
)
from provisioningserver.utils.twisted import synchronous
import tempita

# Used to generate the conditional bootloader behaviour
CONDITIONAL_BOOTLOADER = ("""
{{if ipv6}}
           {{behaviour}} client-arch-type = {{arch_octet}} {
               option dhcp6.bootfile-url \"{{url}}\";
           }
{{else}}
{{behaviour}} option arch = {{arch_octet}} {
    filename \"{{bootloader}}\";
    {{if path_prefix}}
    option path-prefix \"{{path_prefix}}\";
    {{endif}}
}
{{endif}}
""")

# Used to generate the PXEBootLoader special case
DEFAULT_BOOTLOADER = ("""
{{if ipv6}}
            else {
               option dhcp6.bootfile-url \"{{url}}\";
           }
{{else}}
else {
    filename \"{{bootloader}}\";
    {{if path_prefix}}
    option path-prefix \"{{path_prefix}}\";
    {{endif}}
}
{{endif}}
""")


class DHCPConfigError(Exception):
    """Exception raised for errors processing the DHCP config."""


def compose_conditional_bootloader(ipv6, rack_ip=None):
    default_name = 'uefi' if ipv6 else 'pxe'
    output = ""
    behaviour = chain(["if"], repeat("elsif"))
    for name, method in BootMethodRegistry:
        if name != default_name and method.arch_octet is not None:
            url = ('tftp://[%s]/' if ipv6 else 'tftp://%s/') % rack_ip
            if method.path_prefix:
                url += method.path_prefix
            url += '/%s' % method.bootloader_path
            output += tempita.sub(
                CONDITIONAL_BOOTLOADER,
                ipv6=ipv6, rack_ip=rack_ip, url=url,
                behaviour=next(behaviour),
                arch_octet=method.arch_octet,
                bootloader=method.bootloader_path,
                path_prefix=method.path_prefix,
                ).strip() + ' '

    # The PXEBootMethod is used in an else statement for the generated
    # dhcpd config. This ensures that a booting node that does not
    # provide an architecture octet, or architectures that emulate
    # pxelinux can still boot.
    method = BootMethodRegistry.get_item(default_name)
    if method is not None:
        url = ('tftp://[%s]/' if ipv6 else 'tftp://%s/') % rack_ip
        if method.path_prefix:
            url += method.path_prefix
        url += '/%s' % method.bootloader_path
        output += tempita.sub(
            DEFAULT_BOOTLOADER,
            ipv6=ipv6, rack_ip=rack_ip, url=url,
            bootloader=method.bootloader_path,
            path_prefix=method.path_prefix,
            ).strip()
    return output.strip()


@synchronous
def gen_addresses(hostname):
    """Yield IPv4 and IPv6 addresses for `hostname`.

    Yields (ip-version, address) tuples, where ip-version is either 4 or 6.

    Internally this uses `socket.getaddrinfo` and limits resolution to UDP
    datagram sockets.
    """
    for family, _, _, _, addr in socket.getaddrinfo(
            hostname, 0, 0, socket.SOCK_DGRAM, socket.IPPROTO_UDP):
        if family == socket.AF_INET:
            ipaddr, _ = addr
            yield 4, ipaddr
        elif family == socket.AF_INET6:
            ipaddr, _, _, _ = addr
            yield 6, ipaddr


def get_addresses(*hostnames):
    """Resolve and collate addresses for the given hostnames.

    :return: A tuple of two lists. The first contains all IPv4 addresses
    discovered, the second all IPv6 addresses.
    """
    ipv4, ipv6 = [], []
    for hostname in hostnames:
        for ipver, addr in gen_addresses(hostname):
            if ipver == 4:
                ipv4.append(addr)
            elif ipver == 6:
                ipv6.append(addr)
            else:
                raise AssertionError(
                    "IP version %r for address %r is not recognised."
                    % (ipver, addr))
    return ipv4, ipv6


@typed
def get_config(
        template_name: str, global_dhcp_snippets: Sequence[dict],
        failover_peers: Sequence[dict], shared_networks: Sequence[dict],
        hosts: Sequence[dict], omapi_key: str, ipv6: bool) -> str:
    """Return a DHCP config file based on the supplied parameters.

    :param template_name: Template file name: `dhcpd.conf.template` for the
        IPv4 template, `dhcpd6.conf.template` for the IPv6 template.
    :param ipv6: True if ipv6 configuration should be generated.
    :return: A full configuration, as a string.
    """
    if ipv6:
        return get_config_v6(
            template_name, global_dhcp_snippets, failover_peers,
            shared_networks, hosts, omapi_key)
    else:
        return get_config_v4(
            template_name, global_dhcp_snippets, failover_peers,
            shared_networks, hosts, omapi_key)


@typed
def get_config_v4(
        template_name: str, global_dhcp_snippets: Sequence[dict],
        failover_peers: Sequence[dict], shared_networks: Sequence[dict],
        hosts: Sequence[dict], omapi_key: str) -> str:
    """Return a DHCP config file based on the supplied parameters.

    :param template_name: Template file name: `dhcpd.conf.template` for the
        IPv4 template.
    :return: A full configuration, as a string.
    """
    bootloader = compose_conditional_bootloader(False)
    platform_codename = linux_distribution()[2]
    template_file = locate_template('dhcp', template_name)
    template = tempita.Template.from_filename(template_file, encoding="UTF-8")
    # Helper functions to stuff into the template namespace.
    helpers = {
        "oneline": normalise_whitespace,
        "commalist": normalise_to_comma_list,
    }

    for shared_network in shared_networks:
        for subnet in shared_network["subnets"]:
            ntp_servers = split_string_list(subnet.get("ntp_servers", ""))
            ntp_servers_ipv4, ntp_servers_ipv6 = get_addresses(*ntp_servers)
            subnet["ntp_servers_ipv4"] = ", ".join(ntp_servers_ipv4)
            subnet["ntp_servers_ipv6"] = ", ".join(ntp_servers_ipv6)

    try:
        return template.substitute(
            global_dhcp_snippets=global_dhcp_snippets, hosts=hosts,
            failover_peers=failover_peers, shared_networks=shared_networks,
            bootloader=bootloader, platform_codename=platform_codename,
            omapi_key=omapi_key, **helpers)
    except (KeyError, NameError) as error:
        raise DHCPConfigError(
            "Failed to render DHCP configuration.") from error


@typed
def get_config_v6(
        template_name: str, global_dhcp_snippets: Sequence[dict],
        failover_peers: Sequence[dict], shared_networks: Sequence[dict],
        hosts: Sequence[dict], omapi_key: str) -> str:
    """Return a DHCP config file based on the supplied parameters.

    :param template_name: Template file name: `dhcpd6.conf.template` for the
        IPv6 template.
    :return: A full configuration, as a string.
    """
    platform_codename = linux_distribution()[2]
    template_file = locate_template('dhcp', template_name)
    template = tempita.Template.from_filename(template_file, encoding="UTF-8")
    # Helper functions to stuff into the template namespace.
    helpers = {
        "oneline": normalise_whitespace,
        "commalist": normalise_to_comma_list,
    }

    rack_addrs = [
        IPAddress(addr)
        for addr in net_utils.get_all_interface_addresses()]

    for shared_network in shared_networks:
        for subnet in shared_network["subnets"]:
            cidr = IPNetwork(subnet['subnet_cidr'])
            rack_ip_found = False
            for rack_addr in rack_addrs:
                if rack_addr in cidr:
                    rack_ip = str(rack_addr)
                    rack_ip_found = True
                    break
            if rack_ip_found:
                subnet["bootloader"] = compose_conditional_bootloader(
                    True, rack_ip)
            ntp_servers = split_string_list(subnet.get("ntp_servers", ""))
            ntp_servers_ipv4, ntp_servers_ipv6 = get_addresses(*ntp_servers)
            subnet["ntp_servers_ipv4"] = ", ".join(ntp_servers_ipv4)
            subnet["ntp_servers_ipv6"] = ", ".join(ntp_servers_ipv6)

    try:
        return template.substitute(
            global_dhcp_snippets=global_dhcp_snippets, hosts=hosts,
            failover_peers=failover_peers, shared_networks=shared_networks,
            platform_codename=platform_codename,
            omapi_key=omapi_key, **helpers)
    except (KeyError, NameError) as error:
        raise DHCPConfigError(
            "Failed to render DHCP configuration.") from error
