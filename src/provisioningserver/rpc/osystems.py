# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to operating systems."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "gen_operating_systems",
    "validate_license_key",
]

from provisioningserver.drivers.osystem import (
    Node,
    OperatingSystemRegistry,
    Token,
)
from provisioningserver.rpc import exceptions


def gen_operating_system_releases(osystem):
    """Yield operating system release dicts.

    Each dict adheres to the response specification of an operating
    system release in the ``ListOperatingSystems`` RPC call.
    """
    releases_for_commissioning = set(
        osystem.get_supported_commissioning_releases())
    for release in osystem.get_supported_releases():
        requires_license_key = osystem.requires_license_key(release)
        can_commission = release in releases_for_commissioning
        yield {
            "name": release,
            "title": osystem.get_release_title(release),
            "requires_license_key": requires_license_key,
            "can_commission": can_commission,
        }


def gen_operating_systems():
    """Yield operating system dicts.

    Each dict adheres to the response specification of an operating
    system in the ``ListOperatingSystems`` RPC call.
    """

    for _, os in sorted(OperatingSystemRegistry):
        default_release = os.get_default_release()
        default_commissioning_release = os.get_default_commissioning_release()
        yield {
            "name": os.name,
            "title": os.title,
            "releases": gen_operating_system_releases(os),
            "default_release": default_release,
            "default_commissioning_release": default_commissioning_release,
        }


def get_os_release_title(osystem, release):
    """Get the title for the operating systems release.

    :raises NoSuchOperatingSystem: If ``osystem`` is not found.
    """
    try:
        osystem = OperatingSystemRegistry[osystem]
    except KeyError:
        raise exceptions.NoSuchOperatingSystem(osystem)
    else:
        title = osystem.get_release_title(release)
        if title is None:
            return ""
        return title


def validate_license_key(osystem, release, key):
    """Validate a license key.

    :raises NoSuchOperatingSystem: If ``osystem`` is not found.
    """
    try:
        osystem = OperatingSystemRegistry[osystem]
    except KeyError:
        raise exceptions.NoSuchOperatingSystem(osystem)
    else:
        return osystem.validate_license_key(release, key)


def get_preseed_data(
        osystem, preseed_type, node_system_id, node_hostname,
        consumer_key, token_key, token_secret, metadata_url):
    """Composes preseed data for the given node.

    :param preseed_type: The preseed type being composed.
    :param node: The node for which a preseed is being composed.
    :param token: OAuth token for the metadata URL.
    :param metadata_url: The metdata URL for the node.
    :type metadata_url: :py:class:`urlparse.ParseResult`
    :return: Preseed data for the given node.
    :raise NotImplementedError: when the specified operating system does
        not require custom preseed data.
    """
    try:
        osystem = OperatingSystemRegistry[osystem]
    except KeyError:
        raise exceptions.NoSuchOperatingSystem(osystem)
    else:
        return osystem.compose_preseed(
            preseed_type, Node(node_system_id, node_hostname),
            Token(consumer_key, token_key, token_secret),
            metadata_url.geturl())


def compose_curtin_network_preseed(os_name, interfaces, auto_interfaces,
                                   ips_mapping, gateways_mapping,
                                   disable_ipv4, nameservers, netmasks):
    """Compose Curtin network preseed for a node.

    :param os_name: Identifying name of the operating system for which a
        preseed should be generated.
    :param interfaces: A list of interface/MAC pairs for the node.
    :param auto_interfaces: A list of MAC addresses whose network interfaces
        should come up automatically on node boot.
    :param ips_mapping: A dict mapping MAC addresses to lists of the
        corresponding network interfaces' IP addresses.
    :param gateways_mapping: A dict mapping MAC addresses to lists of the
        corresponding network interfaces' default gateways.
    :param disable_ipv4: Should this node be installed without IPv4 networking?
    :param nameservers: List of DNS servers.
    :param netmasks: A dict mapping IP dadresses from `ips_mapping` to their
        respective netmasks.
    :return: Preseed data, as JSON.
    """
    try:
        osystem = OperatingSystemRegistry[os_name]
    except KeyError:
        raise exceptions.NoSuchOperatingSystem(os_name)
    else:
        return osystem.compose_curtin_network_preseed(
            interfaces, auto_interfaces, ips_mapping=ips_mapping,
            gateways_mapping=gateways_mapping, disable_ipv4=disable_ipv4,
            nameservers=nameservers, netmasks=netmasks)
