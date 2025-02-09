# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Routable addresses."""

from collections import defaultdict
from textwrap import dedent
from typing import Iterable, Mapping, Sequence, TypeVar

from django.db import connection
from netaddr import IPAddress

Node = TypeVar("Node")


# Convert an `int` to a `str`. Using `str(thing)` is probably faster, but this
# ensures that the result is a decimal representation of an integer, and so is
# safer to use when constructing SQL queries for example.
_int2str = "{:d}".format


_find_addresses_sql = dedent(
    """\
    SELECT left_node_id, left_ip,
           right_node_id, right_ip
      FROM maasserver_routable_pairs
     WHERE left_node_id IN (%s)
       AND right_node_id IN (%s)
       AND metric < 4
     ORDER BY metric ASC
"""
)


def find_addresses_between_nodes(nodes_left: Iterable, nodes_right: Iterable):
    """Find routable addresses between `nodes_left` and `nodes_right`.

    Yields ``(node-left, addr-left, node-right, addr-right)`` tuples, where
    ``node-left`` and ``node-right`` are one of the nodes passed in and
    ``addr-left`` and ``addr-right`` are :class:`netaddr.IPAddress` instances
    corresponding to an active address on their respective nodes.

    The results are sorted, lowest metric first, meaning that earlier
    addresses are likely to have a lower overall communications cost, lower
    latency, and so on. The order of preference is:

    - Same node
    - Same subnet
    - Same VLAN
    - Same space

    An explicitly defined space is preferred to the default / null space.
    """
    nodes_left = {node.id: node for node in nodes_left}
    nodes_right = {node.id: node for node in nodes_right}
    if None in nodes_left or None in nodes_right:
        raise AssertionError("One or more nodes are not in the database.")
    if len(nodes_left) > 0 and len(nodes_right) > 0:
        with connection.cursor() as cursor:
            cursor.execute(
                _find_addresses_sql
                % (
                    ",".join(map(_int2str, nodes_left)),
                    ",".join(map(_int2str, nodes_right)),
                )
            )
            for id_left, ip_left, id_right, ip_right in cursor:
                yield (
                    nodes_left[id_left],
                    IPAddress(ip_left),
                    nodes_right[id_right],
                    IPAddress(ip_right),
                )


AddressMap = Mapping[Node, Sequence[IPAddress]]


def get_routable_address_map(
    destinations: Iterable[Node], whence: Node
) -> AddressMap:
    """Return addresses of `destinations` routable from `whence`.

    Returns a dict keyed by the nodes in `destinations`, with values that are
    lists of addresses on each destination that `whence` can reach.
    """
    routable_addrs = find_addresses_between_nodes({whence}, destinations)
    return group_addresses_by_right_node(routable_addrs)


def group_addresses_by_right_node(addresses) -> AddressMap:
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


def reduce_routable_address_map(
    routable_addrs_map: AddressMap,
) -> Iterable[IPAddress]:
    """Choose one routable address per destination node.

    The addresses are in preference order (see `find_addresses_between_nodes`
    for information on how that's derived) so this simply chooses the first.
    """
    for addresses in routable_addrs_map.values():
        if addresses:
            yield addresses[0]
