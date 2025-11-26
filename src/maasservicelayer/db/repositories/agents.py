# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import AgentTable
from maasservicelayer.models.agents import Agent


class AgentsClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(AgentTable.c.id, id))

    @classmethod
    def with_rack_id(cls, rack_id: int) -> Clause:
        return Clause(condition=eq(AgentTable.c.rack_id, rack_id))

    @classmethod
    def with_rack_id_in(cls, rack_id_list: list[int]) -> Clause:
        return Clause(condition=AgentTable.c.rack_id.in_(rack_id_list))

    @classmethod
    def with_uuid(cls, uuid: str) -> Clause:
        return Clause(condition=eq(AgentTable.c.uuid, uuid))


class AgentsRepository(BaseRepository[Agent]):
    def get_repository_table(self) -> Table:
        return AgentTable

    def get_model_factory(self) -> type[Agent]:
        return Agent
