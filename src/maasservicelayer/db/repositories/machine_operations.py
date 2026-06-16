# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import select

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.base import Repository
from maasservicelayer.db.tables import MachineOperationTable


class MachineOperationsRepository(Repository):
    def __init__(self, context: Context):
        super().__init__(context)

    async def get_node_id(self, operation_uuid: str) -> int | None:
        stmt = select(MachineOperationTable.c.node_id).where(
            MachineOperationTable.c.operation_uuid == operation_uuid
        )
        result = (await self.execute_stmt(stmt)).scalar_one_or_none()
        return result
