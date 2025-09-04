# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import AgentCertificateTable
from maasservicelayer.models.agentcertificates import AgentCertificate


class AgentCertificatesClauseFactory(ClauseFactory):
    @classmethod
    def with_agent_id(cls, agent_id: int) -> Clause:
        return Clause(condition=eq(AgentCertificateTable.c.agent_id, agent_id))

    @classmethod
    def with_agent_id_in(cls, agent_id_list: list[int]) -> Clause:
        return Clause(
            condition=AgentCertificateTable.c.agent_id.in_(agent_id_list)
        )


class AgentCertificatesRepository(BaseRepository[AgentCertificate]):
    def get_repository_table(self) -> Table:
        return AgentCertificateTable

    def get_model_factory(self) -> type[AgentCertificate]:
        return AgentCertificate
