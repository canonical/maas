# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import StaticRouteTable
from maasservicelayer.models.staticroutes import StaticRoute


class StaticRoutesClauseFactory(ClauseFactory):
    @classmethod
    def with_source_id(cls, subnet_id: int) -> Clause:
        return Clause(condition=eq(StaticRouteTable.c.source_id, subnet_id))

    @classmethod
    def with_destination_id(cls, subnet_id: int) -> Clause:
        return Clause(
            condition=eq(StaticRouteTable.c.destination_id, subnet_id)
        )


class StaticRoutesRepository(BaseRepository[StaticRoute]):
    def get_repository_table(self) -> Table:
        return StaticRouteTable

    def get_model_factory(self) -> Type[StaticRoute]:
        return StaticRoute
