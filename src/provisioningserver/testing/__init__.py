# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

"""Testing tools for `provisioningserver`."""

__metaclass__ = type
__all__ = [
    "network_infos",
    ]


def network_infos(network):
    """Return a dict of info about a network.

    :param network: The network object from which to extract the data.
    :type network: IPNetwork.
    """
    return dict(
        subnet_mask=str(network.netmask),
        broadcast_ip=str(network.broadcast),
        ip_range_low=str(network.first),
        ip_range_high=str(network.last),
    )
