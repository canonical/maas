#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.service_status import (
    ServiceStatusRepository,
)
from maasservicelayer.models.service_status import ServiceStatus
from maasservicelayer.services._base import Service


class ServiceStatusService(Service):
    def __init__(
        self,
        context: Context,
        service_status_repository: ServiceStatusRepository,
    ):
        super().__init__(context)
        self.service_status_repository = service_status_repository

    async def get_one(self, query: QuerySpec) -> ServiceStatus | None:
        return await self.service_status_repository.get_one(query=query)
