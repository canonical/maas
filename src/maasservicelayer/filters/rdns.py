#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv6Address

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.rdns import RDNS


class RDNSFilters(FilterFactory):
    model = RDNS

    @classmethod
    def with_ip(cls, ip: IPv4Address | IPv6Address) -> FieldFilter:
        return cls._equals("ip", ip)
