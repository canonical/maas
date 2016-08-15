# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helper to obtain the MAAS server's address."""

__all__ = [
    'get_maas_facing_server_address',
    'get_maas_facing_server_host',
    ]


from urllib.parse import urlparse

from maasserver.config import RegionConfiguration
from maasserver.exceptions import UnresolvableHost
from provisioningserver.utils.network import resolve_hostname


def get_maas_facing_server_host(rack_controller=None):
    """Return configured MAAS server hostname, for use by nodes or workers.

    :param rack_controller: The `RackController` from the point of view of
        which the server host should be computed.
    :return: Hostname or IP address, as configured in the MAAS URL config
        setting or as configured on rack_controller.url.
    """
    if rack_controller is None or not rack_controller.url:
        with RegionConfiguration.open() as config:
            maas_url = config.maas_url
    else:
        maas_url = rack_controller.url
    return urlparse(maas_url).hostname


def get_maas_facing_server_address(rack_controller=None, ipv4=True, ipv6=True):
    """Return address where nodes and workers can reach the MAAS server.

    The address is taken from the configured MAAS URL or `controller.url`.
    Consult the 'maas-region local_config_set' command for details on
    how to set the MAAS URL.

    If there is more than one IP address for the host, the addresses
    will be sorted and the first IP address in the sorted set will be
    returned.  IPv4 addresses will be sorted before IPv6 addresses, so
    this prefers IPv4 addresses over IPv6 addresses.  It also prefers global
    IPv6 addresses over link-local IPv6 addresses.  Note, this is sorted:
        105.181.232.64
        ::ffff:101.1.1.1
        2001:db8::1
        fdd7:30::3
        fe80::1

    :param rack_controller: The rack controller from the point of view of
        which the server address should be computed.
    :param ipv4: Include IPv4 addresses?  Defaults to `True`.
    :param ipv6: Include IPv6 addresses?  Defaults to `True`.
    :return: An IP address as a unicode string.  If the configured URL
        uses a hostname, this function will resolve that hostname.
    :raise UnresolvableHost: if no IP addresses could be found for
        the hostname.

    """
    hostname = get_maas_facing_server_host(rack_controller)
    if ipv6 or ipv4:
        addresses = resolve_hostname(
            hostname, 0 if (ipv6 and ipv4) else 4 if ipv4 else 6)
    else:
        addresses = set()
    if len(addresses) == 0:
        raise UnresolvableHost("No address found for host %s." % hostname)
    return min(addresses).format()
