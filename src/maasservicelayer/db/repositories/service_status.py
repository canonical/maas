#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import ServiceStatusTable
from maasservicelayer.models.service_status import ServiceStatus


class ServiceStatusRepository(BaseRepository[ServiceStatus]):
    def get_repository_table(self) -> Table:
        return ServiceStatusTable

    def get_model_factory(self) -> Type[ServiceStatus]:
        return ServiceStatus
