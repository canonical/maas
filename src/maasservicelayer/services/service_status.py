#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.service_status import (
    ServiceStatusRepository,
)
from maasservicelayer.models.service_status import ServiceStatus
from maasservicelayer.services._base import BaseService


class ServiceStatusService(
    BaseService[ServiceStatus, ServiceStatusRepository]
):
    def __init__(
        self,
        context: Context,
        service_status_repository: ServiceStatusRepository,
    ):
        super().__init__(context, service_status_repository)
