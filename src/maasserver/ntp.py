# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""NTP related functionality."""

__all__ = [
    "get_servers_for",
]

from collections import defaultdict
import random
from typing import (
    FrozenSet,
    Iterable,
    Mapping,
    Sequence,
)

from maasserver.models.config import Config
from maasserver.models.node import (
    Node,
    RackController,
    RegionController,
)
from maasserver.routablepairs import find_addresses_between_nodes
from netaddr import IPAddress
from provisioningserver.utils import typed
from provisioningserver.utils.text import split_string_list


@typed
def get_servers_for(node: Node) -> FrozenSet[str]:
    """Return NTP servers to use for the given node."""
    if node.is_region_controller or _ntp_external_only():
        routable_addrs = _get_external_servers()
    elif node.is_rack_controller:
        # Point the rack back at all the region controllers.
        regions = RegionController.objects.all()
        routable_addrs_map = _get_routable_address_map(regions, node)
        routable_addrs = _reduce_routable_address_map(routable_addrs_map)
    elif node.is_machine:
        # Point the node back to its primary and secondary rack controllers as
        # a source of time information.
        racks = node.get_boot_rack_controllers()
        if len(racks) == 0:
            # This machine hasn't previously booted, so use all racks. Perhaps
            # we should do this anyway, and disregard boot rack information?
            racks = RackController.objects.all()
        routable_addrs_map = _get_routable_address_map(racks, node)
        routable_addrs = _reduce_routable_address_map(routable_addrs_map)
    else:
        # Point the node back at *all* rack controllers.
        racks = RackController.objects.all()
        routable_addrs_map = _get_routable_address_map(racks, node)
        routable_addrs = _reduce_routable_address_map(routable_addrs_map)
    # Return a frozenset of strings, be they IP addresses or hostnames.
    return frozenset(map(str, routable_addrs))


@typed
def _ntp_external_only() -> bool:
    """Has `ntp_external_only` been set?"""
    return Config.objects.get_config("ntp_external_only")


@typed
def _get_external_servers() -> Iterable[str]:
    """Get the configured external NTP servers."""
    ntp_servers = Config.objects.get_config("ntp_servers")
    return split_string_list(ntp_servers)


AddressMap = Mapping[Node, Sequence[IPAddress]]


@typed
def _get_routable_address_map(
        destinations: Iterable[Node], whence: Node) -> AddressMap:
    """Return addresses of `destinations` routable from `whence`.

    Returns a dict keyed by the nodes in `destinations`, with values that are
    lists of addresses on each destination that `whence` can reach.
    """
    routable_addrs = find_addresses_between_nodes({whence}, destinations)
    return _group_addresses_by_right_node(routable_addrs)


@typed
def _group_addresses_by_right_node(addresses) -> AddressMap:
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


@typed
def _reduce_routable_address_map(
        routable_addrs_map: AddressMap) -> Iterable[IPAddress]:
    """Choose one routable address per destination node at random.

    XXX: This may change to be more stable.
    """
    return map(random.choice, routable_addrs_map.values())
