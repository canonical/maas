# Copyright 2012-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Write config output for ISC DHCPD."""

from itertools import chain, repeat
import logging
import socket
from typing import Sequence

from netaddr import IPAddress, IPNetwork, IPRange
import tempita

from provisioningserver.boot import BootMethodRegistry
from provisioningserver.path import get_maas_data_path, get_path
from provisioningserver.utils import load_template, snap
import provisioningserver.utils.network as net_utils
from provisioningserver.utils.text import (
    normalise_to_comma_list,
    normalise_whitespace,
    quote,
)
from provisioningserver.utils.twisted import synchronous

logger = logging.getLogger(__name__)


# Used to generate the conditional bootloader behaviour
CONDITIONAL_BOOTLOADER = tempita.Template(
    """
{{if ipv6}}
{{if user_class}}
{{if user_class=="iPXE"}}
  {{behaviour}} exists dhcp6.user-class and
  option dhcp6.user-class = \"{{user_class}}\" or
  (exists ipxe.http and ( exists ipxe.bzimage or exists ipxe.efi )) {
{{else}}
{{behaviour}} exists dhcp6.user-class and
  option dhcp6.user-class = \"{{user_class}}\" {
{{endif}}
    # {{name}}
    option dhcp6.bootfile-url \"{{url}}\";
    {{if path_prefix_force}}
    if exists dhcp6.oro {
        # Always send the PXELINUX option (path-prefix)
        option dhcp6.oro = concat(option dhcp6.oro,00d2);
    }
    {{endif}}
    {{if http_client}}
    option dhcp6.vendor-class 0 10 "HTTPClient";
    {{endif}}
}
{{else}}
{{behaviour}} exists dhcp6.client-arch-type and
  option dhcp6.client-arch-type = {{arch_octet}} {
    # {{name}}
    option dhcp6.bootfile-url \"{{url}}\";
    {{if path_prefix_force}}
    if exists dhcp6.oro {
        # Always send the PXELINUX option (path-prefix)
        option dhcp6.oro = concat(option dhcp6.oro,00d2);
    }
    {{endif}}
    {{if http_client}}
    option dhcp6.vendor-class 0 10 "HTTPClient";
    {{endif}}
}
{{endif}}
{{else}}
{{if user_class}}
{{if user_class=="iPXE"}}
  {{behaviour}} option user-class = \"{{user_class}}\" or (exists ipxe.http and ( exists ipxe.bzimage or exists ipxe.efi )) {
{{else}}
  {{behaviour}} option user-class = \"{{user_class}}\" {
{{endif}}
    # {{name}}
    filename \"{{bootloader}}\";
    {{if path_prefix}}
    option path-prefix \"{{path_prefix}}\";
    {{endif}}
    {{if path_prefix_force}}
    if exists dhcp-parameter-request-list {
        # Always send the PXELINUX option (path-prefix)
        option dhcp-parameter-request-list = concat(
            option dhcp-parameter-request-list,d2);
    }
    {{endif}}
    {{if http_client}}
    option vendor-class-identifier "HTTPClient";
    {{endif}}
}
{{else}}
{{behaviour}} option arch = {{arch_octet}} {
    # {{name}}
    filename \"{{bootloader}}\";
    {{if path_prefix}}
    option path-prefix \"{{path_prefix}}\";
    {{endif}}
    {{if path_prefix_force}}
    if exists dhcp-parameter-request-list {
        # Always send the PXELINUX option (path-prefix)
        option dhcp-parameter-request-list = concat(
            option dhcp-parameter-request-list,d2);
    }
    {{endif}}
    {{if http_client}}
    option vendor-class-identifier "HTTPClient";
    {{endif}}
}
{{endif}}
{{endif}}
"""
)

# Used to generate the PXEBootLoader special case
DEFAULT_BOOTLOADER = tempita.Template(
    """
{{if ipv6}}
else {
    # {{name}}
    option dhcp6.bootfile-url \"{{url}}\";
    {{if path_prefix_force}}
    if exists dhcp6.oro {
        # Always send the PXELINUX option (path-prefix)
        option dhcp6.oro = concat(option dhcp6.oro,00d2);
    }
    {{endif}}
}
{{else}}
else {
    # {{name}}
    filename \"{{bootloader}}\";
    {{if path_prefix}}
    option path-prefix \"{{path_prefix}}\";
    {{endif}}
    {{if path_prefix_force}}
    if exists dhcp-parameter-request-list {
        # Always send the PXELINUX option (path-prefix)
        option dhcp-parameter-request-list = concat(
            option dhcp-parameter-request-list,d2);
    }
    {{endif}}
}
{{endif}}
"""
)


class DHCPConfigError(Exception):
    """Exception raised for errors processing the DHCP config."""


def compose_conditional_bootloader(
    ipv6, rack_ip=None, disabled_boot_architectures=None
):
    if disabled_boot_architectures is None:
        disabled_boot_architectures = []
    output = ""
    behaviour = chain(["if"], repeat("elsif"))
    for name, method in BootMethodRegistry:
        if (
            method.arch_octet is None
            and method.user_class is None
            or name in disabled_boot_architectures
        ):
            continue

        use_http = method.path_prefix_http or method.http_url
        schema = "http" if use_http else "tftp"
        port = ":5248" if use_http else ""
        url = ("%s://[%s]%s/" if ipv6 else "%s://%s%s/") % (
            schema,
            rack_ip,
            port,
        )
        # Set the URL to pull from '/images/' so nginx handles the request.
        # Requests to '/' are forwarded to the rack's http service to
        # handle which should only be done for configuration files.
        if method.http_url:
            url = f"{url}images/"
        path_prefix = method.path_prefix
        if path_prefix:
            url += path_prefix
        if method.path_prefix_http:
            # Force an absolute URL as the path prefix.
            path_prefix = url
        url += method.bootloader_path
        bootloader = method.bootloader_path
        if method.absolute_url_as_filename:
            bootloader = url
            # path_prefix gets removed with this setting, because a
            # absolute url is provided as the bootloader.
            path_prefix = None
        output += (
            CONDITIONAL_BOOTLOADER.substitute(
                ipv6=ipv6,
                rack_ip=rack_ip,
                url=url,
                behaviour=next(behaviour),
                arch_octet=method.arch_octet,
                user_class=method.user_class,
                bootloader=bootloader,
                path_prefix=path_prefix,
                path_prefix_force=method.path_prefix_force,
                http_client=method.http_url,
                name=method.name,
            ).strip()
            + " "
        )

    # The PXEBootMethod is used in an else statement for the generated
    # dhcpd config. This ensures that a booting node that does not
    # provide an architecture octet, or architectures that emulate
    # uefi_amd64 or pxelinux can still boot.
    method = BootMethodRegistry.get_item("uefi_amd64" if ipv6 else "pxe")
    if method is not None and method.name not in disabled_boot_architectures:
        use_http = method.path_prefix_http or method.http_url
        schema = "http" if use_http else "tftp"
        port = ":5248" if use_http else ""
        url = ("%s://[%s]%s/" if ipv6 else "%s://%s%s/") % (
            schema,
            rack_ip,
            port,
        )
        if method.http_url:
            url = f"{url}images/"
        path_prefix = method.path_prefix
        if path_prefix:
            url += path_prefix
        if method.path_prefix_http:
            # Force an absolute URL as the path prefix.
            path_prefix = url
        url += "/%s" % method.bootloader_path
        output += DEFAULT_BOOTLOADER.substitute(
            ipv6=ipv6,
            rack_ip=rack_ip,
            url=url,
            bootloader=method.bootloader_path,
            path_prefix=path_prefix,
            path_prefix_force=method.path_prefix_force,
            name=method.name,
        ).strip()
    return output.strip()


@synchronous
def _gen_addresses(hostname):
    """Yield IPv4 and IPv6 addresses for `hostname`.

    Yields (ip-version, address) tuples, where ip-version is either 4 or 6.

    Internally this uses `socket.getaddrinfo` and limits resolution to UDP
    datagram sockets.
    """
    for family, _, _, _, addr in socket.getaddrinfo(
        hostname, 0, 0, socket.SOCK_DGRAM, socket.IPPROTO_UDP
    ):
        if family == socket.AF_INET:
            ipaddr, _ = addr
            yield 4, ipaddr
        elif family == socket.AF_INET6:
            ipaddr, _, _, _ = addr
            yield 6, ipaddr


# See `_gen_addresses_where_possible`.
_gen_addresses_where_possible_suppress = frozenset(
    (
        socket.EAI_ADDRFAMILY,
        socket.EAI_AGAIN,
        socket.EAI_FAIL,
        socket.EAI_NODATA,
        socket.EAI_NONAME,
    )
)


def _gen_addresses_where_possible(hostname):
    """Yield IPv4 and IPv6 addresses for `hostname`.

    A variant of `_gen_addresses` that ignores some resolution failures. The
    addresses returned are only those that are resolvable at the time this
    function is called. Specifically the following errors are ignored:

      +----------------+-----------------------------------------------+
      | EAI_ADDRFAMILY | The specified network host does not have any  |
      |                | network addresses in the requested address    |
      |                | family.                                       |
      +----------------+-----------------------------------------------+
      | EAI_AGAIN      | The name server returned a temporary failure  |
      |                | indication. Try again later.                  |
      +----------------+-----------------------------------------------+
      | EAI_FAIL       | The name server returned a permanent failure  |
      |                | indication.                                   |
      +----------------+-----------------------------------------------+
      | EAI_NODATA     | The specified network host exists, but does   |
      |                | not have any network addresses defined.       |
      +----------------+-----------------------------------------------+
      | EAI_NONAME     | The node or service is not known; or both node|
      |                | and service are NULL; or AI_NUMERICSERV was   |
      |                | specified and service was not a numeric       |
      |                | port-number string.                           |
      +----------------+-----------------------------------------------+

    Descriptions from getaddrinfo(3).
    """
    try:
        yield from _gen_addresses(hostname)
    except socket.gaierror as error:
        if error.errno in _gen_addresses_where_possible_suppress:
            # Log this but otherwise suppress/ignore for now.
            logger.warning("Could not resolve %s: %s", hostname, error)
        else:
            raise


def _get_addresses(*hostnames):
    """Resolve and collate addresses for the given hostnames.

    Uses `_gen_addresses_where_possible` internally so suppresses a few
    different name resolution failures.

    :return: A tuple of two lists. The first contains all IPv4 addresses
        discovered, the second all IPv6 addresses.
    """
    ipv4, ipv6 = [], []
    for hostname in hostnames:
        for ipver, addr in _gen_addresses_where_possible(hostname):
            if ipver == 4:
                ipv4.append(addr)
            elif ipver == 6:
                ipv6.append(addr)
            else:
                raise AssertionError(
                    "IP version %r for address %r is not recognised."
                    % (ipver, addr)
                )
    return ipv4, ipv6


def get_config(
    template_name: str,
    global_dhcp_snippets: Sequence[dict],
    failover_peers: Sequence[dict],
    shared_networks: Sequence[dict],
    hosts: Sequence[dict],
    omapi_key: str,
    ipv6: bool,
) -> str:
    """Return a DHCP config file based on the supplied parameters.

    :param template_name: Template file name: `dhcpd.conf.template` for the
        IPv4 template, `dhcpd6.conf.template` for the IPv6 template.
    :param ipv6: True if ipv6 configuration should be generated.
    :return: A full configuration, as a string.
    """
    if ipv6:
        return get_config_v6(
            template_name,
            global_dhcp_snippets,
            failover_peers,
            shared_networks,
            hosts,
            omapi_key,
        )
    else:
        return get_config_v4(
            template_name,
            global_dhcp_snippets,
            failover_peers,
            shared_networks,
            hosts,
            omapi_key,
        )


def normalise_any_iterable_to_comma_list(iterable):
    """Like `normalise_to_comma_list` but coerces any iterable."""
    if isinstance(iterable, str):
        return normalise_to_comma_list(iterable)
    else:
        return ", ".join(map(str, iterable))


def normalise_any_iterable_to_quoted_comma_list(iterable):
    """Like `normalise_to_comma_list` but coerces any iterable."""
    if isinstance(iterable, str):
        return normalise_to_comma_list(iterable, quoted=True)
    else:
        return ", ".join(map(quote, iterable))


def get_rack_ip_for_subnet(version, cidr, interface):
    """
    Return the IP address on this rack controller.

    First the code will try to find an IP address that is in the cidr, but if
    not it will use the first IP address on the interface (to support
    VLAN relay).
    """
    cidr = IPNetwork(cidr)
    if interface:
        ip_addresses = [
            IPAddress(addr)
            for addr in net_utils.get_all_addresses_for_interface(interface)
        ]
    else:
        ip_addresses = [
            IPAddress(addr) for addr in net_utils.get_all_interface_addresses()
        ]
    for ip_addr in ip_addresses:
        if ip_addr in cidr:
            return ip_addr
    for ip_addr in ip_addresses:
        if ip_addr.version == version:
            return ip_addr
    return None


def get_config_v4(
    template_name: str,
    global_dhcp_snippets: Sequence[dict],
    failover_peers: Sequence[dict],
    shared_networks: Sequence[dict],
    hosts: Sequence[dict],
    omapi_key: str,
) -> str:
    """Return a DHCP config file based on the supplied parameters.

    :param template_name: Template file name: `dhcpd.conf.template` for the
        IPv4 template.
    :return: A full configuration, as a string.
    """
    template = load_template("dhcp", template_name)
    dhcp_socket = get_maas_data_path("dhcpd.sock")

    # Helper functions to stuff into the template namespace.
    helpers = {
        "oneline": normalise_whitespace,
        "commalist": normalise_any_iterable_to_comma_list,
        "quoted_commalist": normalise_any_iterable_to_quoted_comma_list,
        "running_in_snap": snap.running_in_snap(),
    }

    for shared_network in shared_networks:
        interface = shared_network.get("interface", None)
        for subnet in shared_network["subnets"]:
            rack_ip = get_rack_ip_for_subnet(
                4, subnet["subnet_cidr"], interface
            )
            if rack_ip is not None:
                subnet["next_server"] = rack_ip
                subnet["bootloader"] = compose_conditional_bootloader(
                    False, rack_ip, subnet.get("disabled_boot_architectures")
                )
            ntp_servers = subnet["ntp_servers"]  # Is a list.
            ntp_servers_ipv4, ntp_servers_ipv6 = _get_addresses(*ntp_servers)
            subnet["ntp_servers_ipv4"] = ", ".join(ntp_servers_ipv4)
            subnet["ntp_servers_ipv6"] = ", ".join(ntp_servers_ipv6)

    try:
        return template.substitute(
            global_dhcp_snippets=global_dhcp_snippets,
            hosts=hosts,
            failover_peers=failover_peers,
            shared_networks=shared_networks,
            omapi_key=omapi_key,
            dhcp_helper=(get_path("/usr/sbin/maas-dhcp-helper")),
            dhcp_socket=dhcp_socket,
            **helpers,
        )
    except (KeyError, NameError) as error:
        raise DHCPConfigError(
            "Failed to render DHCP configuration."
        ) from error


def get_config_v6(
    template_name: str,
    global_dhcp_snippets: Sequence[dict],
    failover_peers: Sequence[dict],
    shared_networks: Sequence[dict],
    hosts: Sequence[dict],
    omapi_key: str,
) -> str:
    """Return a DHCP config file based on the supplied parameters.

    :param template_name: Template file name: `dhcpd6.conf.template` for the
        IPv6 template.
    :return: A full configuration, as a string.
    """
    template = load_template("dhcp", template_name)
    # Helper functions to stuff into the template namespace.
    helpers = {
        "oneline": normalise_whitespace,
        "commalist": normalise_any_iterable_to_comma_list,
        "quoted_commalist": normalise_any_iterable_to_quoted_comma_list,
        "running_in_snap": snap.running_in_snap(),
    }

    shared_networks = _process_network_parameters_v6(
        failover_peers, shared_networks
    )

    try:
        return template.substitute(
            global_dhcp_snippets=global_dhcp_snippets,
            hosts=hosts,
            failover_peers=failover_peers,
            shared_networks=shared_networks,
            omapi_key=omapi_key,
            **helpers,
        )
    except (KeyError, NameError) as error:
        raise DHCPConfigError(
            "Failed to render DHCP configuration."
        ) from error


def _process_network_parameters_v6(failover_peers, shared_networks):
    """Preprocess shared_networks prior to rendering the template.

    This is a separate function, partly for readability, and partly for ease
    of testing.

    :param failover_peers: failover_peers from get_config_v6.
    :param shared_networks: shared_networks from get_config_v6.
    :return: an updated shared_networks, suitable for rendering the template.
    """
    peers = {x["name"]: x for x in failover_peers}

    for shared_network in shared_networks:
        interface = shared_network.get("interface", None)
        for subnet in shared_network["subnets"]:
            rack_ip = get_rack_ip_for_subnet(
                6, subnet["subnet_cidr"], interface
            )
            if rack_ip is not None:
                subnet["bootloader"] = compose_conditional_bootloader(
                    True, rack_ip, subnet.get("disabled_boot_architectures")
                )
            ntp_servers = subnet["ntp_servers"]  # Is a list.
            ntp_servers_ipv4, ntp_servers_ipv6 = _get_addresses(*ntp_servers)
            subnet["ntp_servers_ipv4"] = ", ".join(ntp_servers_ipv4)
            subnet["ntp_servers_ipv6"] = ", ".join(ntp_servers_ipv6)
            for pool in subnet["pools"]:
                peer = pool.get("failover_peer", None)
                if peer is not None:
                    ip_range = IPRange(
                        pool["ip_range_low"], pool["ip_range_high"]
                    )
                    if peers[peer]["mode"] == "primary":
                        pool["ip_range_high"] = str(
                            IPAddress(
                                ip_range.first + int(ip_range.size / 2) - 1
                            )
                        )
                    else:
                        pool["ip_range_low"] = str(
                            IPAddress(ip_range.first + int(ip_range.size / 2))
                        )
    return shared_networks
