# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import Table

from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import AgentTable
from maasservicelayer.models.agents import Agent


class AgentsRepository(BaseRepository[Agent]):
    def get_repository_table(self) -> Table:
        return AgentTable

    def get_model_factory(self) -> type[Agent]:
        return Agent
