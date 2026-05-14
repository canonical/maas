# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from typing import Iterable, List

from sqlalchemy import Table, insert

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import PowerDriverTable
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.power_drivers import PowerDriver
from maasservicelayer.utils.date import utcnow


class PowerDriverClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(PowerDriverTable.c.id, id))

    @classmethod
    def with_rack_system_id(cls, rack_system_id: str) -> Clause:
        return Clause(
            condition=eq(
                PowerDriverTable.c.rack_system_id, rack_system_id
            )
        )

    @classmethod
    def with_driver_name(cls, driver_name: str) -> Clause:
        return Clause(
            condition=eq(PowerDriverTable.c.driver_name, driver_name)
        )

    @classmethod
    def with_driver_version(cls, driver_version: str) -> Clause:
        return Clause(
            condition=eq(PowerDriverTable.c.driver_version, driver_version)
        )


class PowerDriversRepository(BaseRepository[PowerDriver]):
    def get_repository_table(self) -> Table:
        return PowerDriverTable

    def get_model_factory(self) -> type[PowerDriver]:
        return PowerDriver

    async def upsert_many(
        self, builders: Iterable[ResourceBuilder]
    ) -> List[PowerDriver]:
        """Insert or update power drivers.

        Uses PostgreSQL ON CONFLICT to upsert based on the unique constraint
        (rack_system_id, driver_name, driver_version).
        """
        now = utcnow()
        resources = []
        for builder in builders:
            resource = self.mapper.build_resource(builder)
            # Populate timestamped fields only if the caller did not set them
            resource["created"] = resource.get("created", now)
            resource["updated"] = resource.get("updated", now)
            resources.append(resource.get_values())

        stmt = (
            insert(PowerDriverTable)
            .returning(PowerDriverTable)
            .values(resources)
            .on_conflict_do_update(
                constraint="uk_rack_power_drivers_rack_driver_version",
                set_={
                    "schema": insert(PowerDriverTable).excluded.schema,
                    "updated": now,
                },
            )
        )

        result = (await self.execute_stmt(stmt)).all()
        return [PowerDriver(**row._asdict()) for row in result]
