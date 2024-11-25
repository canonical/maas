#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from operator import eq
from typing import Type

from sqlalchemy import Table

from maascommon.enums.service import ServiceName, ServiceStatusEnum
from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    ResourceBuilder,
)
from maasservicelayer.db.tables import ServiceStatusTable
from maasservicelayer.models.service_status import ServiceStatus


class ServiceStatusResourceBuilder(ResourceBuilder):
    def with_name(self, value: ServiceName) -> "ServiceStatusResourceBuilder":
        self._request.set_value(ServiceStatusTable.c.name.name, value)
        return self

    def with_status(
        self, value: ServiceStatusEnum
    ) -> "ServiceStatusResourceBuilder":
        self._request.set_value(ServiceStatusTable.c.status.name, value)
        return self

    def with_status_info(
        self, value: str = ""
    ) -> "ServiceStatusResourceBuilder":
        self._request.set_value(ServiceStatusTable.c.status_info.name, value)
        return self

    def with_node_id(self, value: int) -> "ServiceStatusResourceBuilder":
        self._request.set_value(ServiceStatusTable.c.node_id.name, value)
        return self


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
