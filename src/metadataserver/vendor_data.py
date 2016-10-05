# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""vendor-data for cloud-init's use."""

__all__ = [
    'get_vendor_data',
    ]

from itertools import chain

from maasserver import ntp
from netaddr import IPAddress
from provisioningserver.ntp.config import normalise_address
from provisioningserver.utils.text import make_gecos_field


def get_vendor_data(node):
    return dict(chain(
        generate_system_info(node),
        generate_ntp_configuration(node),
    ))


def generate_system_info(node):
    """Generate cloud-init system information for the given node."""
    if node.owner is not None and node.default_user:
        username = node.default_user
        fullname = node.owner.get_full_name()
        gecos = make_gecos_field(fullname)
        yield "system_info", {
            'default_user': {
                'name': username,
                'gecos': gecos,
            },
        }


def generate_ntp_configuration(node):
    """Generate cloud-init configuration for NTP servers.

    cloud-init supports::

      ntp:
        pools:
          - 0.mypool.pool.ntp.org
          - 1.myotherpool.pool.ntp.org
        servers:
          - 102.10.10.10
          - ntp.ubuntu.com

    MAAS assumes that IP addresses are "servers" and hostnames/FQDNs "pools".
    """
    ntp_servers = ntp.get_servers_for(node)
    if len(ntp_servers) >= 1:
        # Separate out IP addresses from the rest.
        addrs, other = set(), set()
        for ntp_server in map(normalise_address, ntp_servers):
            bucket = addrs if isinstance(ntp_server, IPAddress) else other
            bucket.add(ntp_server)
        servers = [addr.format() for addr in sorted(addrs)]
        pools = sorted(other)  # Hostnames and FQDNs only.
        yield "ntp", {"servers": servers, "pools": pools}
