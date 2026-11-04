# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.mappers.machines_v2 import MachinesV2DomainDataMapper
from maasservicelayer.db.repositories.base import Repository
from maasservicelayer.db.tables import NodeTable
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.models.machine_details import MachineRecord
from maasservicelayer.models.nodes import Node


class MachinesV2Repository(Repository[MachineRecord]):
    def __init__(self, context: Context):
        super().__init__(context)
        self.mapper = MachinesV2DomainDataMapper(
            MachineRecord, NodeTable, query_model=Node
        )

    async def get_many(self, query: QuerySpec) -> list[MachineRecord]:
        translated = self._translate(query)
        stmt = translated.enrich_stmt(self.mapper.select_statement())
        result = await self.execute_stmt(stmt)
        return [self.mapper.to_domain(row._mapping) for row in result.all()]
