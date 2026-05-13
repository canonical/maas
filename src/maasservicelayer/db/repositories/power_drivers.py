# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import PowerDriverTable
from maasservicelayer.models.power_drivers import PowerDriver


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
