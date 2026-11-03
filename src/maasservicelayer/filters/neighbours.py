#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv6Address

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.models.neighbours import Neighbour


class NeighbourFilters(FilterFactory):
    model = Neighbour

    @classmethod
    def with_ip(cls, ip: IPv4Address | IPv6Address) -> FieldFilter:
        return cls._equals("ip", ip)

    @classmethod
    def with_mac(cls, mac: MacAddress) -> FieldFilter:
        return cls._equals("mac_address", mac)
