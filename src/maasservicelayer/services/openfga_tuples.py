# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.openfga_tuple import OpenFGATupleBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.openfga_tuples import (
    OpenFGATuplesRepository,
)
from maasservicelayer.models.openfga_tuple import OpenFGATuple
from maasservicelayer.services.base import Service


class OpenFGATupleService(Service):
    def __init__(
        self,
        context: Context,
        openfga_tuple_repository: OpenFGATuplesRepository,
    ):
        super().__init__(context)
        self.openfga_tuple_repository = openfga_tuple_repository

    async def create(self, builder: OpenFGATupleBuilder) -> OpenFGATuple:
        return await self.openfga_tuple_repository.create(builder)

    async def delete_many(self, query: QuerySpec) -> None:
        return await self.openfga_tuple_repository.delete_many(query)
