# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio.client import Client
from temporalio.exceptions import ApplicationError, CancelledError

from maascommon.enums.operations import OperationStatus
from maascommon.workflows.operation import OPERATION_UUID_SEARCH_ATTRIBUTE
from maasservicelayer.db import Database
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.services import CacheForServices, ServiceCollectionV3
from maasservicelayer.services.operations import OperationsService
from maasservicelayer.services.temporal import TemporalService
import maastemporalworker.workflow.activity as activity_module
import maastemporalworker.workflow.operation as operation_module
from maastemporalworker.workflow.operation import (
    OperationActivity,
    track_operation_status,
    UpdateOperationStatusParam,
)

ERROR_MESSAGE = "operation failed"


@pytest.mark.asyncio
class TestOperationActivity:
    async def test_update_operation_status(
        self, services_mock: ServiceCollectionV3, monkeypatch
    ) -> None:
        services_mock.temporal = Mock(TemporalService)
        services_mock.operations = Mock(OperationsService)
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
            result=None,
            error=ERROR_MESSAGE,
        )

    async def test_update_operation_status_passes_result(
        self, services_mock: ServiceCollectionV3, monkeypatch
    ) -> None:
        services_mock.temporal = Mock(TemporalService)
        services_mock.operations = Mock(OperationsService)
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
                status=OperationStatus.COMPLETED,
                result={"deployed": True},
            )
        )

        services_mock.operations.update_status.assert_called_once_with(
            operation_uuid="op-uuid",
            status=OperationStatus.COMPLETED,
            result={"deployed": True},
            error=None,
        )

    async def test_update_operation_status_not_found_raises(
        self, services_mock: ServiceCollectionV3, monkeypatch
    ) -> None:
        services_mock.temporal = Mock(TemporalService)
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.update_status = AsyncMock(
            side_effect=NotFoundException()
        )
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

        with pytest.raises(NotFoundException):
            await activity.update_operation_status(
                UpdateOperationStatusParam(
                    operation_uuid="unknown-uuid",
                    status=OperationStatus.RUNNING,
                )
            )


@pytest.mark.asyncio
class TestTrackOperationStatus:
    @pytest.fixture
    def local_activity_mock(self, monkeypatch) -> AsyncMock:
        mock = AsyncMock()
        monkeypatch.setattr(
            operation_module.workflow, "execute_local_activity", mock
        )
        return mock

    def _set_operation_uuid(self, monkeypatch, operation_uuid):
        info = Mock()
        info.workflow_type = "TestWorkflow"
        info.search_attributes = (
            {OPERATION_UUID_SEARCH_ATTRIBUTE: [operation_uuid]}
            if operation_uuid is not None
            else {}
        )
        monkeypatch.setattr(operation_module.workflow, "info", lambda: info)

    async def test_tracks_running_then_completed(
        self, monkeypatch, local_activity_mock
    ):
        self._set_operation_uuid(monkeypatch, "op-uuid")

        @track_operation_status
        async def run(self, param):
            return {"deployed": True}

        result = await run(Mock(), "param")

        assert result == {"deployed": True}
        params = [c.args[1] for c in local_activity_mock.call_args_list]
        assert [p.status for p in params] == [
            OperationStatus.RUNNING,
            OperationStatus.COMPLETED,
        ]
        assert all(p.operation_uuid == "op-uuid" for p in params)
        assert params[-1].result == {"deployed": True}

    async def test_tracks_failed_and_reraises(
        self, monkeypatch, local_activity_mock
    ):
        self._set_operation_uuid(monkeypatch, "op-uuid")

        @track_operation_status
        async def run(self, param):
            raise ValueError(ERROR_MESSAGE)

        with pytest.raises(ValueError):
            await run(Mock(), "param")

        params = [c.args[1] for c in local_activity_mock.call_args_list]
        assert [p.status for p in params] == [
            OperationStatus.RUNNING,
            OperationStatus.FAILED,
        ]
        assert params[-1].error == ERROR_MESSAGE

    async def test_missing_search_attribute_raises(
        self, monkeypatch, local_activity_mock
    ):
        self._set_operation_uuid(monkeypatch, None)

        @track_operation_status
        async def run(self, param):
            return "result"

        with pytest.raises(ApplicationError):
            await run(Mock(), "param")
        local_activity_mock.assert_not_called()

    async def test_tracks_cancelled_and_reraises(
        self, monkeypatch, local_activity_mock
    ):
        self._set_operation_uuid(monkeypatch, "op-uuid")

        @track_operation_status
        async def run(self, param):
            raise CancelledError("workflow cancelled")

        with pytest.raises(CancelledError):
            await run(Mock(), "param")

        params = [c.args[1] for c in local_activity_mock.call_args_list]
        assert [p.status for p in params] == [
            OperationStatus.RUNNING,
            OperationStatus.CANCELLED,
        ]
        assert params[-1].error == "workflow cancelled"
