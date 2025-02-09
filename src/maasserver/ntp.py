# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""NTP related functionality."""

from typing import FrozenSet, Iterable

from maasserver.models.config import Config
from maasserver.models.node import Node, RackController, RegionController
from maasserver.routablepairs import (
    get_routable_address_map,
    reduce_routable_address_map,
)
from provisioningserver.utils.text import split_string_list


def get_servers_for(node: Node | None) -> FrozenSet[str]:
    """Return NTP servers to use for the given node."""
    if node is None or node.is_region_controller or _ntp_external_only():
        routable_addrs = _get_external_servers()
    elif node.is_rack_controller:
        # Point the rack back at all the region controllers.
        regions = RegionController.objects.all()
        routable_addrs_map = get_routable_address_map(regions, node)
        routable_addrs = reduce_routable_address_map(routable_addrs_map)
    elif node.is_machine:
        # Point the node back to its primary and secondary rack controllers as
        # a source of time information.
        racks = node.get_boot_rack_controllers()
        if len(racks) == 0:
            # This machine hasn't previously booted, so use all racks. Perhaps
            # we should do this anyway, and disregard boot rack information?
            racks = RackController.objects.all()
        routable_addrs_map = get_routable_address_map(racks, node)
        routable_addrs = reduce_routable_address_map(routable_addrs_map)
    else:
        # Point the node back at *all* rack controllers.
        racks = RackController.objects.all()
        routable_addrs_map = get_routable_address_map(racks, node)
        routable_addrs = reduce_routable_address_map(routable_addrs_map)
    # Return a frozenset of strings, be they IP addresses or hostnames.
    return frozenset(map(str, routable_addrs))


def get_peers_for(node: Node | None) -> FrozenSet[str]:
    """Return NTP peers to use for the given node.

    For all node types other than region or region+rack controllers, this
    returns the empty set.
    """
    if node is None:
        return frozenset()
    elif node.is_region_controller:
        peer_regions = RegionController.objects.exclude(id=node.id)
        peer_addresses_map = get_routable_address_map(peer_regions, node)
        peer_addresses = reduce_routable_address_map(peer_addresses_map)
        return frozenset(map(str, peer_addresses))
    else:
        return frozenset()


def _ntp_external_only() -> bool:
    """Has `ntp_external_only` been set?"""
    return Config.objects.get_config("ntp_external_only")


def _get_external_servers() -> Iterable[str]:
    """Get the configured external NTP servers."""
    ntp_servers = Config.objects.get_config("ntp_servers")
    return split_string_list(ntp_servers)
