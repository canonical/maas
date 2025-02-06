#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List, Optional, Type

from sqlalchemy import delete, insert, select, Table
from sqlalchemy.sql.operators import eq

from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import (
    DNSResourceIPAddressTable,
    DNSResourceTable,
    StaticIPAddressTable,
)
from maasservicelayer.models.dnsresources import DNSResource
from maasservicelayer.models.domains import Domain
from maasservicelayer.models.staticipaddress import StaticIPAddress


class DNSResourceClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(DNSResourceTable.c.id, id))

    @classmethod
    def with_name(cls, name: str) -> Clause:
        return Clause(condition=eq(DNSResourceTable.c.name, name))

    @classmethod
    def with_domain_id(cls, id: int) -> Clause:
        return Clause(condition=eq(DNSResourceTable.c.domain_id, id))


class DNSResourceRepository(BaseRepository[DNSResource]):
    def get_repository_table(self) -> Table:
        return DNSResourceTable

    def get_model_factory(self) -> Type[DNSResource]:
        return DNSResource

    async def get_dnsresources_in_domain_for_ip(
        self,
        domain: Domain,
        ip: StaticIPAddress,
        but_not_for: Optional[DNSResource] = None,
    ) -> List[DNSResource]:
        stmt = (
            select(DNSResourceTable)
            .select_from(DNSResourceTable)
            .join(
                DNSResourceIPAddressTable,
                DNSResourceIPAddressTable.c.dnsresource_id
                == DNSResourceTable.c.id,
            )
            .filter(
                DNSResourceTable.c.domain_id == domain.id,
                DNSResourceIPAddressTable.c.staticipaddress_id == ip.id,
            )
        )

        if but_not_for:
            stmt = stmt.filter(DNSResourceTable.c.id != but_not_for.id)

        result = (await self.execute_stmt(stmt)).all()
        return [DNSResource(**row._asdict()) for row in result]

    async def get_ips_for_dnsresource(
        self,
        dnsrr: DNSResource,
        discovered_only: Optional[bool] = False,
        matching: Optional[StaticIPAddress] = None,
    ) -> List[StaticIPAddress]:
        filters = [
            DNSResourceIPAddressTable.c.dnsresource_id == dnsrr.id,
        ]

        if discovered_only:
            filters.append(
                StaticIPAddressTable.c.alloc_type
                == IpAddressType.DISCOVERED.value
            )

        if matching:
            filters.append(StaticIPAddressTable.c.ip == matching.ip)

        stmt = (
            select(
                StaticIPAddressTable,
            )
            .select_from(StaticIPAddressTable)
            .join(
                DNSResourceIPAddressTable,
                DNSResourceIPAddressTable.c.staticipaddress_id
                == StaticIPAddressTable.c.id,
            )
            .filter(*filters)
        )

        result = (await self.execute_stmt(stmt)).all()

        return [StaticIPAddress(**row._asdict()) for row in result]

    async def remove_ip_relation(
        self, dnsrr: DNSResource, ip: StaticIPAddress
    ) -> None:
        remove_relation_stmt = delete(DNSResourceIPAddressTable).where(
            DNSResourceIPAddressTable.c.staticipaddress_id == ip.id,
            DNSResourceIPAddressTable.c.dnsresource_id == dnsrr.id,
        )
        await self.execute_stmt(remove_relation_stmt)

    async def link_ip(self, dnsrr: DNSResource, ip: StaticIPAddress) -> None:
        stmt = insert(DNSResourceIPAddressTable).values(
            dnsresource_id=dnsrr.id, staticipaddress_id=ip.id
        )

        await self.execute_stmt(stmt)
