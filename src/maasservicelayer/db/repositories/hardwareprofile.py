# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert as pg_insert

from maasservicelayer.builders.hardwareprofile import HardwareProfileBuilder
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import HardwareProfileTable
from maasservicelayer.models.hardwareprofile import HardwareProfile
from maasservicelayer.utils.date import utcnow


class HardwareProfileRepository(BaseRepository[HardwareProfile]):
    def get_repository_table(self) -> Table:
        return HardwareProfileTable

    def get_model_factory(self) -> type[HardwareProfile]:
        return HardwareProfile

    async def create_or_update(
        self, builder: HardwareProfileBuilder
    ) -> HardwareProfile:
        now = utcnow()
        resource = builder.populated_fields()
        resource.setdefault("created", now)
        resource["updated"] = now
        stmt = (
            pg_insert(HardwareProfileTable)
            .values(**resource)
            .on_conflict_do_update(
                index_elements=[HardwareProfileTable.c.node_id],
                set_={
                    k: resource[k]
                    for k in resource
                    if k not in ("id", "created", "node_id")
                },
            )
            .returning(HardwareProfileTable)
        )
        result = (await self.execute_stmt(stmt)).one()
        return HardwareProfile(**result._asdict())
