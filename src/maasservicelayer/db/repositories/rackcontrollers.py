# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import RackControllerTable
from maasservicelayer.models.rackcontrollers import RackController


class RackControllersClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(RackControllerTable.c.id, id))

    @classmethod
    def with_rack_id(cls, rack_id: int) -> Clause:
        return Clause(condition=eq(RackControllerTable.c.rack_id, rack_id))

    @classmethod
    def with_rack_id_in(cls, rack_id_list: list[int]) -> Clause:
        return Clause(
            condition=RackControllerTable.c.rack_id.in_(rack_id_list)
        )

    @classmethod
    def with_uuid(cls, uuid: str) -> Clause:
        return Clause(condition=eq(RackControllerTable.c.uuid, uuid))


class RackControllersRepository(BaseRepository[RackController]):
    def get_repository_table(self) -> Table:
        return RackControllerTable

    def get_model_factory(self) -> type[RackController]:
        return RackController
