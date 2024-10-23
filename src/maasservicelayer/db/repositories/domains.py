#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import select

from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    CreateOrUpdateResource,
)
from maasservicelayer.db.tables import DomainTable, GlobalDefaultTable
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.domains import Domain


class DomainsRepository(BaseRepository):
    async def find_by_id(self, id: int) -> Domain | None:
        raise NotImplementedError("Not implemented yet.")

    async def list(
        self, token: str | None, size: int, query: QuerySpec | None = None
    ) -> ListResult[Domain]:
        raise NotImplementedError("Not implemented yet.")

    async def update(
        self, id: int, resource: CreateOrUpdateResource
    ) -> Domain:
        raise NotImplementedError("Not implemented yet.")

    async def create(self, resource: CreateOrUpdateResource) -> Domain:
        raise NotImplementedError("Not implemented yet.")

    async def delete(self, id: int) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def get_default_domain(self) -> Domain:
        stmt = (
            select(DomainTable)
            .select_from(GlobalDefaultTable)
            .join(
                DomainTable, DomainTable.c.id == GlobalDefaultTable.c.domain_id
            )
            .filter(GlobalDefaultTable.c.id == 0)
        )

        default_domain = (await self.connection.execute(stmt)).one()

        return Domain(**default_domain._asdict())
