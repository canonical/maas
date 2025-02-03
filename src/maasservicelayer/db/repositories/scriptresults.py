#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Type

from sqlalchemy import join, Table

from maascommon.enums.scriptresult import ScriptStatus
from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import ScriptResultTable, ScriptSetTable
from maasservicelayer.models.scriptresult import ScriptResult


class ScriptResultClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(ScriptResultTable.c.id, id))

    @classmethod
    def with_script_id(cls, script_id: int) -> Clause:
        return Clause(condition=eq(ScriptResultTable.c.script_id, script_id))

    @classmethod
    def with_script_id_in(cls, script_ids: list[int]) -> Clause:
        return Clause(
            condition=ScriptResultTable.c.script_id.in_(set(script_ids))
        )

    @classmethod
    def with_script_set_id(cls, script_set_id: int) -> Clause:
        return Clause(
            condition=eq(ScriptResultTable.c.script_set_id, script_set_id)
        )

    @classmethod
    def with_script_set_id_in(cls, set_ids: list[int]) -> Clause:
        return Clause(
            condition=ScriptResultTable.c.script_set_id.in_(set(set_ids))
        )

    @classmethod
    def with_status(cls, status: ScriptStatus) -> Clause:
        return Clause(condition=eq(ScriptResultTable.c.status, status))

    @classmethod
    def with_status_in(cls, statuses: list[ScriptStatus]) -> Clause:
        return Clause(condition=ScriptResultTable.c.status.in_(set(statuses)))

    @classmethod
    def with_node_id(cls, node_id: int) -> Clause:
        return Clause(
            condition=eq(ScriptSetTable.c.node_id, node_id),
            joins=[
                join(
                    ScriptSetTable,
                    ScriptResultTable,
                    eq(ScriptResultTable.c.script_set_id, ScriptSetTable.c.id),
                )
            ],
        )


class ScriptResultsRepository(BaseRepository[ScriptResult]):
    def get_repository_table(self) -> Table:
        return ScriptResultTable

    def get_model_factory(self) -> Type[ScriptResult]:
        return ScriptResult
