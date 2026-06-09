# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio.client import Client

from maascommon.enums.operations import OperationStatus
from maascommon.workflows.operation import UpdateOperationStatusParam
from maasservicelayer.db import Database
from maasservicelayer.services import CacheForServices, ServiceCollectionV3
from maasservicelayer.services.operations import OperationsService
from maasservicelayer.services.temporal import TemporalService
import maastemporalworker.workflow.activity as activity_module
from maastemporalworker.workflow.operation import OperationActivity

ERROR_MESSAGE = "operation failed"


@pytest.mark.asyncio
@pytest.mark.usefixtures("maasdb")
class TestOperationActivity:
    async def test_update_operation_status(
        self, services_mock: ServiceCollectionV3, monkeypatch
    ) -> None:
        services_mock.temporal = Mock(TemporalService)
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.update_status = AsyncMock()
        services_mock.produce.return_value = services_mock
        monkeypatch.setattr(
            activity_module, "ServiceCollectionV3", services_mock
        )

        services_cache = CacheForServices()
        activity = OperationActivity(
            Mock(Database),
            services_cache,
            connection=Mock(AsyncConnection),
            temporal_client=Mock(Client),
        )

        await activity.update_operation_status(
            UpdateOperationStatusParam(
                operation_uuid="op-uuid",
                status=OperationStatus.FAILED,
                error=ERROR_MESSAGE,
            )
        )

        services_mock.operations.update_status.assert_called_once_with(
            operation_uuid="op-uuid",
            status=OperationStatus.FAILED,
            error=ERROR_MESSAGE,
        )
