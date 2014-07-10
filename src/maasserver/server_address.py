# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helper to obtain the MAAS server's address."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'get_maas_facing_server_address',
    'get_maas_facing_server_host',
    ]


from socket import (
    AF_INET,
    AF_INET6,
    getaddrinfo,
    gaierror,
    )
from urlparse import urlparse

from django.conf import settings
from netaddr import IPAddress
from maasserver.exceptions import (
    NoAddressFoundForHost,
    UnresolvableHost,
    )


# Arbitrary non-privileged port
PORT = 33360


def get_maas_facing_server_host(nodegroup=None):
    """Return configured MAAS server hostname, for use by nodes or workers.

    :param nodegroup: The nodegroup from the point of view of which the
        server host should be computed.
    :return: Hostname or IP address, as configured in the DEFAULT_MAAS_URL
        setting or as configured on nodegroup.maas_url.
    """
    if nodegroup is None or not nodegroup.maas_url:
        maas_url = settings.DEFAULT_MAAS_URL
    else:
        maas_url = nodegroup.maas_url
    return urlparse(maas_url).hostname


def get_maas_facing_server_address(nodegroup=None):
    """Return address where nodes and workers can reach the MAAS server.

    The address is taken from DEFAULT_MAAS_URL or nodegroup.maas_url.
    If there is more than one IP address for the host, the addresses
    will be sorted and the first IP address in the sorted set will be
    returned. IPv4 addresses will be sorted before IPv6 addresses, so
    IPv4 addresses will be preferred if both exist.

    :param nodegroup: The nodegroup from the point of view of which the
        server address should be computed.
    :return: An IP address as a unicode string.  If the configured URL
        uses a hostname, this function will resolve that hostname.
    """
    addresses = set()
    hostname = get_maas_facing_server_host(nodegroup)
    try:
        address_info = getaddrinfo(hostname, PORT)
    except gaierror:
        raise UnresolvableHost("Unable to resolve host %s" % hostname)

    for (family, socktype, proto, canonname, sockaddr) in address_info:
        if family not in (AF_INET, AF_INET6):
            # We're not interested in anything other than IPv4 and v6
            # addresses, so bail out of this loop.
            continue
        # The contents of sockaddr differ for IPv6 and IPv4, but the
        # first elemment is always the address, and that's all we care
        # about.
        addresses.add(IPAddress(sockaddr[0]))
    if len(addresses) == 0:
        raise NoAddressFoundForHost(
            "No address found for host %s." % hostname)
    return min(addresses).format().decode("ascii")
