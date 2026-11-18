#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import Table
from sqlalchemy.sql.operators import eq

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BMCTable
from maasservicelayer.models.bmc import Bmc


class BmcClauseFactory(ClauseFactory):
    @classmethod
    def with_ip_address_id(cls, ip_address_id: int) -> Clause:
        return Clause(condition=eq(BMCTable.c.ip_address_id, ip_address_id))


class BmcsRepository(BaseRepository[Bmc]):
    def get_repository_table(self) -> Table:
        return BMCTable

    def get_model_factory(self) -> Type[Bmc]:
        return Bmc
