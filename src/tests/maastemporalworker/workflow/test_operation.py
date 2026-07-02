# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import (
    ApplicationError,
    CancelledError,
    WorkflowAlreadyStartedError,
)
from temporalio.service import RPCError, RPCStatusCode

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
    BulkOperationWorkflow,
    CREATE_CHILD_OPERATION_ACTIVITY_NAME,
    CreateChildOperationParam,
    OperationActivity,
    RECONCILE_IN_PROGRESS_ACTIVITY_NAME,
    RECONCILE_STUCK_ACCEPTED_ACTIVITY_NAME,
    ReconcileOperationsWorkflow,
    ROLLUP_BULK_STATUS_ACTIVITY_NAME,
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


def _make_operation(
    uuid: str,
    op_type: OperationType = OperationType.MACHINE_COMMISSION,
    status: OperationStatus = OperationStatus.ACCEPTED,
    parameters: dict | None = None,
) -> Operation:
    return Operation(
        id=1,
        uuid=uuid,
        op_type=op_type,
        status=status,
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

    async def test_reconcile_stuck_accepted_starts_mapped(
        self, services_mock: ServiceCollectionV3, monkeypatch
    ) -> None:
        services_mock.temporal = Mock(TemporalService)
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.list_stuck_accepted_operations = AsyncMock(
            return_value=[
                _make_operation("op-uuid", parameters={"system_id": "abc"})
            ]
        )
        services_mock.produce.return_value = services_mock
        monkeypatch.setattr(
            activity_module, "ServiceCollectionV3", services_mock
        )

        activity = self._operation_activity(Mock(Client))
        await activity.reconcile_stuck_accepted_operations()

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

    async def test_reconcile_stuck_accepted_swallows_already_started(
        self, services_mock: ServiceCollectionV3, monkeypatch
    ) -> None:
        services_mock.temporal = Mock(TemporalService)
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.list_stuck_accepted_operations = AsyncMock(
            return_value=[
                _make_operation("op-uuid", parameters={"system_id": "abc"})
            ]
        )
        services_mock.produce.return_value = services_mock
        monkeypatch.setattr(
            activity_module, "ServiceCollectionV3", services_mock
        )

        temporal_client = Mock(Client)
        temporal_client.start_workflow = AsyncMock(
            side_effect=WorkflowAlreadyStartedError("op-uuid", "commission")
        )
        activity = self._operation_activity(temporal_client)
        await activity.reconcile_stuck_accepted_operations()

    @pytest.mark.parametrize(
        "temporal_status, expected_status",
        [
            (WorkflowExecutionStatus.COMPLETED, OperationStatus.COMPLETED),
            (WorkflowExecutionStatus.FAILED, OperationStatus.FAILED),
            (WorkflowExecutionStatus.CANCELED, OperationStatus.CANCELLED),
            (WorkflowExecutionStatus.TERMINATED, OperationStatus.CANCELLED),
        ],
    )
    async def test_reconcile_in_progress_updates_terminal(
        self,
        services_mock: ServiceCollectionV3,
        monkeypatch,
        temporal_status,
        expected_status,
    ) -> None:
        services_mock.temporal = Mock(TemporalService)
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.list_in_progress_operations = AsyncMock(
            return_value=[
                _make_operation("op-uuid", status=OperationStatus.RUNNING)
            ]
        )
        services_mock.operations.update_status = AsyncMock()
        services_mock.produce.return_value = services_mock
        monkeypatch.setattr(
            activity_module, "ServiceCollectionV3", services_mock
        )

        temporal_client = Mock(Client)
        handle = Mock()
        handle.describe = AsyncMock(return_value=Mock(status=temporal_status))
        temporal_client.get_workflow_handle.return_value = handle
        activity = self._operation_activity(temporal_client)

        await activity.reconcile_in_progress_operations()

        temporal_client.get_workflow_handle.assert_called_once_with("op-uuid")
        services_mock.operations.update_status.assert_awaited_once_with(
            operation_uuid="op-uuid",
            status=expected_status,
        )

    async def test_reconcile_in_progress_skips_running(
        self, services_mock: ServiceCollectionV3, monkeypatch
    ) -> None:
        services_mock.temporal = Mock(TemporalService)
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.list_in_progress_operations = AsyncMock(
            return_value=[
                _make_operation("op-uuid", status=OperationStatus.RUNNING)
            ]
        )
        services_mock.operations.update_status = AsyncMock()
        services_mock.produce.return_value = services_mock
        monkeypatch.setattr(
            activity_module, "ServiceCollectionV3", services_mock
        )

        temporal_client = Mock(Client)
        handle = Mock()
        handle.describe = AsyncMock(
            return_value=Mock(status=WorkflowExecutionStatus.RUNNING)
        )
        temporal_client.get_workflow_handle.return_value = handle
        activity = self._operation_activity(temporal_client)

        await activity.reconcile_in_progress_operations()

        services_mock.operations.update_status.assert_not_awaited()

    @pytest.mark.parametrize(
        "operation_status, expected_status, expected_error",
        [
            (
                OperationStatus.RUNNING,
                OperationStatus.FAILED,
                "Workflow execution not found in Temporal.",
            ),
            (OperationStatus.CANCELLING, OperationStatus.CANCELLED, None),
        ],
    )
    async def test_reconcile_in_progress_when_workflow_not_found(
        self,
        services_mock: ServiceCollectionV3,
        monkeypatch,
        operation_status,
        expected_status,
        expected_error,
    ) -> None:
        services_mock.temporal = Mock(TemporalService)
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.list_in_progress_operations = AsyncMock(
            return_value=[_make_operation("op-uuid", status=operation_status)]
        )
        services_mock.operations.update_status = AsyncMock()
        services_mock.produce.return_value = services_mock
        monkeypatch.setattr(
            activity_module, "ServiceCollectionV3", services_mock
        )

        temporal_client = Mock(Client)
        handle = Mock()
        handle.describe = AsyncMock(
            side_effect=RPCError("not found", RPCStatusCode.NOT_FOUND, b"")
        )
        temporal_client.get_workflow_handle.return_value = handle
        activity = self._operation_activity(temporal_client)

        await activity.reconcile_in_progress_operations()

        services_mock.operations.update_status.assert_awaited_once_with(
            operation_uuid="op-uuid",
            status=expected_status,
            error=expected_error,
        )


@pytest.mark.asyncio
class TestReconcileOperationsWorkflow:
    async def test_run_executes_both_phases(self, monkeypatch) -> None:
        execute_activity = AsyncMock()
        monkeypatch.setattr(
            operation_module.workflow, "execute_activity", execute_activity
        )

        await ReconcileOperationsWorkflow().run()

        names = [call.args[0] for call in execute_activity.call_args_list]
        assert names == [
            RECONCILE_STUCK_ACCEPTED_ACTIVITY_NAME,
            RECONCILE_IN_PROGRESS_ACTIVITY_NAME,
        ]


@pytest.mark.asyncio
class TestBulkOperationActivities:
    def _operation_activity(self) -> OperationActivity:
        return OperationActivity(
            Mock(Database),
            CacheForServices(),
            connection=Mock(AsyncConnection),
            temporal_client=Mock(Client),
        )

    async def test_create_child_operation(
        self, services_mock: ServiceCollectionV3, monkeypatch
    ) -> None:
        services_mock.temporal = Mock(TemporalService)
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.create_child_operation_row = AsyncMock(
            return_value="child-uuid"
        )
        services_mock.produce.return_value = services_mock
        monkeypatch.setattr(
            activity_module, "ServiceCollectionV3", services_mock
        )

        activity = self._operation_activity()
        param = CreateChildOperationParam(
            op_type=OperationType.MACHINE_COMMISSION,
            parent_uuid="parent-uuid",
            resource_id=1,
        )
        result = await activity.create_child_operation(param)

        assert result == "child-uuid"
        services_mock.operations.create_child_operation_row.assert_awaited_once_with(
            op_type=OperationType.MACHINE_COMMISSION,
            parent_uuid="parent-uuid",
            resource_id=1,
            resource_type=None,
            parameters=None,
        )

    async def test_rollup_bulk_operation_status(
        self, services_mock: ServiceCollectionV3, monkeypatch
    ) -> None:
        services_mock.temporal = Mock(TemporalService)
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.update_bulk_status_from_children = AsyncMock()
        services_mock.produce.return_value = services_mock
        monkeypatch.setattr(
            activity_module, "ServiceCollectionV3", services_mock
        )

        activity = self._operation_activity()
        await activity.rollup_bulk_operation_status("parent-uuid")

        services_mock.operations.update_bulk_status_from_children.assert_awaited_once_with(
            "parent-uuid"
        )


@pytest.mark.asyncio
class TestBulkOperationWorkflow:
    def _set_operation_uuid(self, monkeypatch, operation_uuid):
        info = Mock()
        info.workflow_type = "BulkOperationWorkflow"
        info.typed_search_attributes.get.return_value = operation_uuid
        monkeypatch.setattr(operation_module.workflow, "info", lambda: info)

    async def test_run_schedules_children_then_rolls_up(
        self, monkeypatch
    ) -> None:
        self._set_operation_uuid(monkeypatch, "parent-uuid")
        local_activity = AsyncMock()
        monkeypatch.setattr(
            operation_module.workflow,
            "execute_local_activity",
            local_activity,
        )
        execute_activity = AsyncMock(
            side_effect=["child-uuid-1", "child-uuid-2", None]
        )
        monkeypatch.setattr(
            operation_module.workflow, "execute_activity", execute_activity
        )
        mock_handle = AsyncMock()
        start_child_workflow = AsyncMock(return_value=mock_handle)
        monkeypatch.setattr(
            operation_module.workflow,
            "start_child_workflow",
            start_child_workflow,
        )
        gather = AsyncMock()
        monkeypatch.setattr(operation_module.asyncio, "gather", gather)

        children = [
            {"op_type": OperationType.MACHINE_COMMISSION, "resource_id": 1},
            {"op_type": OperationType.MACHINE_COMMISSION, "resource_id": 2},
        ]
        await BulkOperationWorkflow().run({"children": children})

        running_param = local_activity.call_args.args[1]
        assert running_param.operation_uuid == "parent-uuid"
        assert running_param.status == OperationStatus.RUNNING

        create_calls = [
            call
            for call in execute_activity.call_args_list
            if call.args[0] == CREATE_CHILD_OPERATION_ACTIVITY_NAME
        ]
        assert len(create_calls) == 2

        assert start_child_workflow.call_count == 2
        gather.assert_awaited_once_with(
            mock_handle, mock_handle, return_exceptions=True
        )

        rollup_call = execute_activity.call_args_list[-1]
        assert rollup_call.args[0] == ROLLUP_BULK_STATUS_ACTIVITY_NAME
        assert rollup_call.args[1] == "parent-uuid"
