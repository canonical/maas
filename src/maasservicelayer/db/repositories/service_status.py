#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from operator import eq
from typing import Type

from sqlalchemy import Table

from maascommon.enums.service import ServiceName
from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import ServiceStatusTable
from maasservicelayer.models.service_status import ServiceStatus


class ServiceStatusClauseFactory(ClauseFactory):
    @classmethod
    def with_name(cls, name: ServiceName) -> Clause:
        return Clause(condition=eq(ServiceStatusTable.c.name, name))

    @classmethod
    def with_node_id(cls, id: int) -> Clause:
        return Clause(condition=eq(ServiceStatusTable.c.node_id, id))


class ServiceStatusRepository(BaseRepository[ServiceStatus]):
    def get_repository_table(self) -> Table:
        return ServiceStatusTable

    def get_model_factory(self) -> Type[ServiceStatus]:
        return ServiceStatus
