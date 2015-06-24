# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
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


from urlparse import urlparse

from maasserver.config import RegionConfiguration
from maasserver.exceptions import UnresolvableHost
from netaddr import (
    valid_ipv4,
    valid_ipv6,
)
from provisioningserver.utils.network import resolve_hostname


def get_maas_facing_server_host(nodegroup=None):
    """Return configured MAAS server hostname, for use by nodes or workers.

    :param nodegroup: The nodegroup from the point of view of which the
        server host should be computed.
    :return: Hostname or IP address, as configured in the MAAS URL config
        setting or as configured on nodegroup.maas_url.
    """
    if nodegroup is None or not nodegroup.maas_url:
        with RegionConfiguration.open() as config:
            maas_url = config.maas_url
    else:
        maas_url = nodegroup.maas_url
    return urlparse(maas_url).hostname


def get_maas_facing_server_address(nodegroup=None, ipv4=True, ipv6=True):
    """Return address where nodes and workers can reach the MAAS server.

    The address is taken from the configured MAAS URL or `nodegroup.maas_url`.
    Consult the 'maas-region-admin local_config_set' command for details on
    how to set the MAAS URL.

    If there is more than one IP address for the host, the addresses
    will be sorted and the first IP address in the sorted set will be
    returned.  IPv4 addresses will be sorted before IPv6 addresses, so
    this prefers IPv4 addresses over IPv6 addresses.  It also prefers global
    IPv6 addresses over link-local IPv6 addresses or IPv6-mapped IPv4
    addresses.

    :param nodegroup: The nodegroup from the point of view of which the
        server address should be computed.
    :param ipv4: Include IPv4 addresses?  Defaults to `True`.
    :param ipv6: Include IPv6 addresses?  Defaults to `True`.
    :return: An IP address as a unicode string.  If the configured URL
        uses a hostname, this function will resolve that hostname.
    :raise UnresolvableHost: if no IP addresses could be found for
        the hostname.

    """
    hostname = get_maas_facing_server_host(nodegroup)
    addresses = set()
    if valid_ipv6(hostname):
        if ipv6:
            addresses.add(hostname)
    elif valid_ipv4(hostname):
        if ipv4:
            addresses.add(hostname)
    else:
        if ipv4:
            addresses = addresses.union(resolve_hostname(hostname, 4))
        if ipv6:
            addresses = addresses.union(resolve_hostname(hostname, 6))
    if len(addresses) == 0:
        raise UnresolvableHost("No address found for host %s." % hostname)
    return min(addresses).format().decode("ascii")
