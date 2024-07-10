# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from sqlalchemy import desc, select, Select
from sqlalchemy.sql.operators import eq, le

from maasapiserver.common.db.tables import SubnetTable
from maasapiserver.v3.api.models.requests.subnets import SubnetRequest
from maasapiserver.v3.db.base import BaseRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.subnets import Subnet


class SubnetsRepository(BaseRepository[Subnet, SubnetRequest]):
    async def create(self, request: SubnetRequest) -> Subnet:
        raise NotImplementedError()

    async def find_by_id(self, id: int) -> Subnet | None:
        stmt = self._select_all_statement().filter(eq(SubnetTable.c.id, id))

        result = await self.connection.execute(stmt)
        subnet = result.first()
        if not subnet:
            return None
        return Subnet(**subnet._asdict())

    async def find_by_name(self, name: str) -> Subnet | None:
        raise NotImplementedError()

    async def list(self, token: str | None, size: int) -> ListResult[Subnet]:
        stmt = (
            self._select_all_statement()
            .order_by(desc(SubnetTable.c.id))
            .limit(size + 1)  # Retrieve one more element to get the next token
        )
        if token is not None:
            stmt = stmt.where(le(SubnetTable.c.id, int(token)))

        result = (await self.connection.execute(stmt)).all()
        next_token = None
        if len(result) > size:  # There is another page
            next_token = result.pop().id
        return ListResult[Subnet](
            items=[Subnet(**row._asdict()) for row in result],
            next_token=next_token,
        )

    async def update(self, resource: Subnet) -> Subnet:
        raise NotImplementedError()

    async def delete(self, id: int) -> None:
        raise NotImplementedError()

    def _select_all_statement(self) -> Select[Any]:
        return select(
            SubnetTable.c.id,
            SubnetTable.c.created,
            SubnetTable.c.updated,
            SubnetTable.c.name,
            SubnetTable.c.cidr,
            SubnetTable.c.gateway_ip,
            SubnetTable.c.dns_servers,
            SubnetTable.c.rdns_mode,
            SubnetTable.c.allow_proxy,
            SubnetTable.c.description,
            SubnetTable.c.active_discovery,
            SubnetTable.c.managed,
            SubnetTable.c.allow_dns,
            SubnetTable.c.disabled_boot_architectures,
        ).select_from(SubnetTable)
