# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""vendor-data for cloud-init's use."""

__all__ = [
    'get_vendor_data',
    ]

from collections import defaultdict
from itertools import chain
import random

from maasserver.models.config import Config
from maasserver.routablepairs import find_addresses_between_nodes
from provisioningserver.utils.text import (
    make_gecos_field,
    split_string_list,
)


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

    but MAAS does not yet distinguish between pool and non-pool servers, and
    so this returns a single set of time references.
    """
    ntp_external_only = Config.objects.get_config("ntp_external_only")
    if ntp_external_only:
        ntp_servers = Config.objects.get_config("ntp_servers")
        ntp_servers = set(split_string_list(ntp_servers))
    else:
        # Point the node back to its primary and secondary rack controllers as
        # a source of time information.
        rack_controllers = node.get_boot_rack_controllers()
        routable_addrs = find_addresses_between_nodes([node], rack_controllers)
        routable_addrs_by_rack = _group_addresses_by_right_node(routable_addrs)
        # Choose one routable address per rack at random.
        ntp_servers = {
            random.choice(address).format()
            for address in routable_addrs_by_rack.values()
        }

    if len(ntp_servers) >= 1:
        yield "ntp", {"servers": sorted(ntp_servers)}


def _group_addresses_by_right_node(addresses):
    """Group `addresses` by the "right" node.

    Effectively this assumes that there is only one "left" node and thus
    ignores it; it's only concerned with grouping addresses on the "right".

    :param addresses: The output from `find_addresses_between_nodes`.
    :return: A dict mapping "right" nodes to a list of their IP addresses.
    """
    collated = defaultdict(list)
    for _, _, right_node, right_ip in addresses:
        collated[right_node].append(right_ip)
    return collated
