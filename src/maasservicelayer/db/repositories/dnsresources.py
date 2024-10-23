from typing import List, Optional

from sqlalchemy import delete, insert, select
from sqlalchemy.sql.operators import eq

from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    CreateOrUpdateResource,
    CreateOrUpdateResourceBuilder,
)
from maasservicelayer.db.tables import (
    DNSResourceIPAddressTable,
    DNSResourceTable,
    StaticIPAddressTable,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.dnsresources import DNSResource
from maasservicelayer.models.domains import Domain
from maasservicelayer.models.staticipaddress import StaticIPAddress


class DNSResourceClauseFactory(ClauseFactory):
    @classmethod
    def with_name(cls, name: str) -> Clause:
        return Clause(condition=eq(DNSResourceTable.c.name, name))

    @classmethod
    def with_domain_id(cls, id: int) -> Clause:
        return Clause(condition=eq(DNSResourceTable.c.domain_id, id))


class DNSResourceResourceBuilder(CreateOrUpdateResourceBuilder):
    def with_name(self, value: str) -> "DNSResourceResourceBuilder":
        self._request.set_value(DNSResourceTable.c.name.name, value)
        return self

    def with_domain_id(self, value: id) -> "DNSResourceResourceBuilder":
        self._request.set_value(DNSResourceTable.c.domain_id.name, value)
        return self


class DNSResourceRepository(BaseRepository):
    async def find_by_id(self, id: int) -> DNSResource | None:
        raise NotImplementedError("Not implemented yet.")

    async def list(
        self, token: str | None, size: int, query: QuerySpec | None = None
    ) -> ListResult[DNSResource]:
        raise NotImplementedError("Not implemented yet.")

    async def update(
        self, id: int, resource: CreateOrUpdateResource
    ) -> DNSResource:
        raise NotImplementedError("Not implemented yet.")

    async def get(self, query: QuerySpec) -> DNSResource | None:
        stmt = (
            select(DNSResourceTable)
            .select_from(DNSResourceTable)
            .where(query.where.condition)
        )

        result = (await self.connection.execute(stmt)).one_or_none()
        if result:
            return DNSResource(**result._asdict())
        return None

    async def create(self, resource: CreateOrUpdateResource) -> DNSResource:
        stmt = (
            insert(DNSResourceTable)
            .returning(DNSResourceTable)
            .values(**resource.get_values())
        )

        result = (await self.connection.execute(stmt)).one()

        return DNSResource(**result._asdict())

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

        result = (await self.connection.execute(stmt)).all()
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

        result = (await self.connection.execute(stmt)).all()

        return [StaticIPAddress(**row._asdict()) for row in result]

    async def remove_ip_relation(
        self, dnsrr: DNSResource, ip: StaticIPAddress
    ) -> None:
        remove_relation_stmt = delete(DNSResourceIPAddressTable).where(
            DNSResourceIPAddressTable.c.staticipaddress_id == ip.id,
            DNSResourceIPAddressTable.c.dnsresource_id == dnsrr.id,
        )
        await self.connection.execute(remove_relation_stmt)

    async def delete(self, id: int) -> None:
        stmt = delete(DNSResourceTable).where(DNSResourceTable.c.id == id)
        await self.connection.execute(stmt)

    async def link_ip(self, dnsrr: DNSResource, ip: StaticIPAddress) -> None:
        stmt = insert(DNSResourceIPAddressTable).values(
            dnsresource_id=dnsrr.id, staticipaddress_id=ip.id
        )

        await self.connection.execute(stmt)
