# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BootstrapTokenTable
from maasservicelayer.models.bootstraptokens import BootstrapToken


class BootstrapTokensClauseFactory(ClauseFactory):
    @classmethod
    def with_rack_id(cls, rack_id: int) -> Clause:
        return Clause(condition=eq(BootstrapTokenTable.c.rack_id, rack_id))

    @classmethod
    def with_rack_id_in(cls, rack_id_list: list[int]) -> Clause:
        return Clause(
            condition=BootstrapTokenTable.c.rack_id.in_(rack_id_list)
        )

    @classmethod
    def with_secret(cls, secret):
        return Clause(condition=eq(BootstrapTokenTable.c.secret, secret))


class BootstrapTokensRepository(BaseRepository[BootstrapToken]):
    def get_repository_table(self) -> Table:
        return BootstrapTokenTable

    def get_model_factory(self) -> type[BootstrapToken]:
        return BootstrapToken
