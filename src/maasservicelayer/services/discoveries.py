# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv6Address

import structlog

from maascommon.logging.security import AUTHZ_ADMIN, SECURITY
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.discoveries import DiscoveriesRepository
from maasservicelayer.filters.mdns import MDNSFilters
from maasservicelayer.filters.neighbours import NeighbourFilters
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.filters.rdns import RDNSFilters
from maasservicelayer.models.discoveries import Discovery
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.services.base import ReadOnlyService
from maasservicelayer.services.mdns import MDNSService
from maasservicelayer.services.neighbours import NeighboursService
from maasservicelayer.services.rdns import RDNSService

logger = structlog.getLogger()


class DiscoveriesService(ReadOnlyService[Discovery, DiscoveriesRepository]):
    def __init__(
        self,
        context: Context,
        discoveries_repository: DiscoveriesRepository,
        mdns_service: MDNSService,
        rdns_service: RDNSService,
        neighbours_service: NeighboursService,
    ):
        super().__init__(context, discoveries_repository)
        self.mdns_service = mdns_service
        self.rdns_service = rdns_service
        self.neighbours_service = neighbours_service

    async def clear_by_ip_and_mac(
        self, ip: IPv4Address | IPv6Address, mac: MacAddress
    ) -> None:
        await self.neighbours_service.delete_many(
            query=QuerySpec(
                where=NeighbourFilters.and_filters(
                    [
                        NeighbourFilters.with_ip(ip),
                        NeighbourFilters.with_mac(mac),
                    ]
                )
            )
        )
        await self.mdns_service.delete_many(
            query=QuerySpec(where=MDNSFilters.with_ip(ip))
        )
        await self.rdns_service.delete_many(
            query=QuerySpec(where=RDNSFilters.with_ip(ip))
        )
        logger.info(
            f"{AUTHZ_ADMIN}:discovery ip and mac cleared:{ip}:{mac}",
            type=SECURITY,
        )

    async def clear_neighbours(self) -> None:
        await self.neighbours_service.delete_many(query=QuerySpec())
        logger.info(
            f"{AUTHZ_ADMIN}:discovery neighbors cleared",
            type=SECURITY,
        )

    async def clear_mdns_and_rdns_records(self) -> None:
        await self.mdns_service.delete_many(query=QuerySpec())
        await self.rdns_service.delete_many(query=QuerySpec())
        logger.info(
            f"{AUTHZ_ADMIN}:discovery mdns and rdns records cleared",
            type=SECURITY,
        )

    async def clear_all(self) -> None:
        await self.clear_neighbours()
        await self.clear_mdns_and_rdns_records()
