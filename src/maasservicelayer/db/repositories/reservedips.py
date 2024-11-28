# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import ReservedIPTable
from maasservicelayer.models.reservedips import ReservedIP


class ReservedIPsClauseFactory(ClauseFactory):
    @classmethod
    def with_subnet_id(cls, subnet_id: int) -> Clause:
        return Clause(condition=eq(ReservedIPTable.c.subnet_id, subnet_id))


class ReservedIPsRepository(BaseRepository[ReservedIP]):
    def get_repository_table(self) -> Table:
        return ReservedIPTable

    def get_model_factory(self) -> Type[ReservedIP]:
        return ReservedIP
