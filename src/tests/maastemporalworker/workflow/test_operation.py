# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import (
    ApplicationError,
    CancelledError,
    WorkflowAlreadyStartedError,
)

from maascommon.enums.operations import OperationStatus, OperationType
from maasservicelayer.db import Database
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.operations import Operation
from maasservicelayer.services import CacheForServices, ServiceCollectionV3
from maasservicelayer.services.operations import OperationsService
from maasservicelayer.services.temporal import TemporalService
from maastemporalworker.worker import REGION_TASK_QUEUE
import maastemporalworker.workflow.activity as activity_module
import maastemporalworker.workflow.operation as operation_module
from maastemporalworker.workflow.operation import (
    GET_STUCK_OPERATIONS_ACTIVITY_NAME,
    OperationActivity,
    ReconcileOperationsWorkflow,
    START_OPERATION_WORKFLOW_ACTIVITY_NAME,
    StuckOperation,
    track_operation_status,
    update_current_task,
    UpdateCurrentTaskParam,
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

    async def test_update_current_task(
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

        await activity.update_current_task(
            UpdateCurrentTaskParam(
                operation_uuid="op-uuid",
                name="task1",
                task_number=1,
            )
        )

        services_mock.operations.start_task.assert_called_once_with(
            operation_uuid="op-uuid",
            name="task1",
            task_number=1,
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
        info.typed_search_attributes.get.return_value = operation_uuid
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
        assert params[-1].error == "Operation op-uuid was cancelled."


@pytest.mark.asyncio
class TestUpdateCurrentTask:
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
        info.typed_search_attributes.get.return_value = operation_uuid
        monkeypatch.setattr(operation_module.workflow, "info", lambda: info)

    async def test_executes_activity_with_task(
        self, monkeypatch, local_activity_mock
    ):
        self._set_operation_uuid(monkeypatch, "op-uuid")

        await update_current_task("task1", 1)

        local_activity_mock.assert_awaited_once()
        param = local_activity_mock.call_args.args[1]
        assert param.operation_uuid == "op-uuid"
        assert param.name == "task1"
        assert param.task_number == 1

    async def test_missing_search_attribute_raises(
        self, monkeypatch, local_activity_mock
    ):
        self._set_operation_uuid(monkeypatch, None)

        with pytest.raises(ApplicationError):
            await update_current_task("task1", 1)
        local_activity_mock.assert_not_called()


def _make_operation(uuid: str, parameters: dict | None = None) -> Operation:
    return Operation(
        id=1,
        uuid=uuid,
        op_type=OperationType.MACHINE_COMMISSION,
        status=OperationStatus.ACCEPTED,
        is_bulk=False,
        parameters=parameters,
    )


@pytest.mark.asyncio
class TestReconcileOperationsActivities:
    def _operation_activity(self, temporal_client) -> OperationActivity:
        return OperationActivity(
            Mock(Database),
            CacheForServices(),
            connection=Mock(AsyncConnection),
            temporal_client=temporal_client,
        )

    async def test_get_stuck_operations(
        self, services_mock: ServiceCollectionV3, monkeypatch
    ) -> None:
        services_mock.temporal = Mock(TemporalService)
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.list_stuck_accepted_operations = AsyncMock(
            return_value=[_make_operation("op-uuid", {"system_id": "abc"})]
        )
        services_mock.produce.return_value = services_mock
        monkeypatch.setattr(
            activity_module, "ServiceCollectionV3", services_mock
        )

        activity = self._operation_activity(Mock(Client))
        result = await activity.get_stuck_operations()

        assert result == [
            StuckOperation(
                uuid="op-uuid",
                op_type=OperationType.MACHINE_COMMISSION,
                parameters={"system_id": "abc"},
            )
        ]
        services_mock.operations.list_stuck_accepted_operations.assert_awaited_once()

    async def test_start_operation_workflow_starts_mapped(self) -> None:
        activity = self._operation_activity(Mock(Client))

        await activity.start_operation_workflow(
            StuckOperation(
                uuid="op-uuid",
                op_type=OperationType.MACHINE_COMMISSION,
                parameters={"system_id": "abc"},
            )
        )

        activity.temporal_client.start_workflow.assert_awaited_once()
        call = activity.temporal_client.start_workflow.call_args
        assert call.args[0] == "commission"
        assert call.args[1] == {"system_id": "abc"}
        assert call.kwargs["id"] == "op-uuid"
        assert call.kwargs["task_queue"] == REGION_TASK_QUEUE
        assert (
            call.kwargs["id_reuse_policy"]
            == WorkflowIDReusePolicy.REJECT_DUPLICATE
        )

    async def test_start_operation_workflow_skips_unmapped(self) -> None:
        activity = self._operation_activity(Mock(Client))

        await activity.start_operation_workflow(
            StuckOperation(
                uuid="op-uuid",
                op_type=OperationType.SELECTION_SYNC,
            )
        )

        activity.temporal_client.start_workflow.assert_not_awaited()

    async def test_start_operation_workflow_swallows_already_started(
        self,
    ) -> None:
        temporal_client = Mock(Client)
        temporal_client.start_workflow = AsyncMock(
            side_effect=WorkflowAlreadyStartedError("op-uuid", "commission")
        )
        activity = self._operation_activity(temporal_client)

        await activity.start_operation_workflow(
            StuckOperation(
                uuid="op-uuid",
                op_type=OperationType.MACHINE_COMMISSION,
                parameters={"system_id": "abc"},
            )
        )


@pytest.mark.asyncio
class TestReconcileOperationsWorkflow:
    async def test_starts_workflow_for_each_stuck_operation(
        self, monkeypatch
    ) -> None:
        stuck = [
            StuckOperation(
                uuid="op-1", op_type=OperationType.MACHINE_COMMISSION
            ),
            StuckOperation(
                uuid="op-2", op_type=OperationType.MACHINE_COMMISSION
            ),
        ]

        async def fake_execute_activity(name, *args, **kwargs):
            if name == GET_STUCK_OPERATIONS_ACTIVITY_NAME:
                return stuck
            return None

        execute_activity = AsyncMock(side_effect=fake_execute_activity)
        monkeypatch.setattr(
            operation_module.workflow, "execute_activity", execute_activity
        )

        result = await ReconcileOperationsWorkflow().run()

        assert result == 2
        start_calls = [
            call
            for call in execute_activity.call_args_list
            if call.args[0] == START_OPERATION_WORKFLOW_ACTIVITY_NAME
        ]
        assert [call.args[1] for call in start_calls] == stuck
