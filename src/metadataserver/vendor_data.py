# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""vendor-data for cloud-init's use."""

__all__ = [
    'get_vendor_data',
    ]

from itertools import chain

from maasserver.models.config import Config
from provisioningserver.utils.text import (
    make_gecos_field,
    split_string_list,
)


def get_vendor_data(node):
    return dict(chain(
        generate_system_info(node),
        generate_ntp_configuration(),
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


def generate_ntp_configuration():
    """Generate cloud-init configuration for NTP servers.

    cloud-init supports::

      ntp:
        pools:
          - 0.mypool.pool.ntp.org
          - 1.myotherpool.pool.ntp.org
        servers:
          - 102.10.10.10
          - ntp.ubuntu.com

    but MAAS does not yet distinguish between pool and non-pool servers, and
    so this returns a single set of time references.
    """
    ntp_servers = Config.objects.get_config("ntp_servers")
    ntp_servers = set(split_string_list(ntp_servers))
    if len(ntp_servers) >= 1:
        yield "ntp", {"servers": sorted(ntp_servers)}
