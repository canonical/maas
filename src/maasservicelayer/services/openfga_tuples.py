# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass

from maascommon.openfga.async_client import OpenFGAClient
from maasservicelayer.builders.openfga_tuple import OpenFGATupleBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.openfga_tuples import (
    OpenFGATuplesClauseFactory,
    OpenFGATuplesRepository,
)
from maasservicelayer.models.openfga_tuple import OpenFGATuple
from maasservicelayer.services.base import Service, ServiceCache


@dataclass(slots=True)
class OpenFGAServiceCache(ServiceCache):
    client: OpenFGAClient | None = None

    async def close(self) -> None:
        if self.client:
            await self.client.close()


class OpenFGATupleService(Service):
    def __init__(
        self,
        context: Context,
        openfga_tuple_repository: OpenFGATuplesRepository,
        cache: ServiceCache,
    ):
        super().__init__(context, cache)
        self.openfga_tuple_repository = openfga_tuple_repository

    @staticmethod
    def build_cache_object() -> OpenFGAServiceCache:
        return OpenFGAServiceCache()

    @Service.from_cache_or_execute(attr="client")
    async def get_client(self) -> OpenFGAClient:
        return OpenFGAClient()

    async def create(self, builder: OpenFGATupleBuilder) -> OpenFGATuple:
        return await self.openfga_tuple_repository.create(builder)

    async def delete_many(self, query: QuerySpec) -> None:
        return await self.openfga_tuple_repository.delete_many(query)

    async def delete_pool(self, pool_id: int) -> None:
        query = QuerySpec(
            where=OpenFGATuplesClauseFactory.and_clauses(
                [
                    OpenFGATuplesClauseFactory.with_object_id(str(pool_id)),
                    OpenFGATuplesClauseFactory.with_object_type("pool"),
                    OpenFGATuplesClauseFactory.with_relation("parent"),
                ]
            )
        )
        await self.delete_many(query)

    async def delete_user(self, user_id: int) -> None:
        query = QuerySpec(
            where=OpenFGATuplesClauseFactory.and_clauses(
                [
                    OpenFGATuplesClauseFactory.with_user(f"user:{user_id}"),
                    OpenFGATuplesClauseFactory.with_relation("member"),
                ]
            )
        )
        await self.delete_many(query)
