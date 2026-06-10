# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from temporalio.exceptions import ApplicationError

from maascommon.enums.operations import OperationStatus
from maastemporalworker.workflow.operation import (
    OPERATION_UUID_SEARCH_ATTRIBUTE,
)
import maastemporalworker.workflow.utils as utils_module
from maastemporalworker.workflow.utils import (
    async_retry,
    track_operation_status,
)

ERROR_MESSAGE = "operation failed"


@pytest.mark.asyncio
class TestTrackOperationStatus:
    @pytest.fixture
    def local_activity_mock(self, monkeypatch) -> AsyncMock:
        mock = AsyncMock()
        monkeypatch.setattr(
            utils_module.workflow, "execute_local_activity", mock
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
        monkeypatch.setattr(utils_module.workflow, "info", lambda: info)

    async def test_tracks_running_then_completed(
        self, monkeypatch, local_activity_mock
    ):
        self._set_operation_uuid(monkeypatch, "op-uuid")

        @track_operation_status
        async def run(self, param):
            return "result"

        result = await run(Mock(), "param")

        assert result == "result"
        params = [c.args[1] for c in local_activity_mock.call_args_list]
        assert [p.status for p in params] == [
            OperationStatus.RUNNING,
            OperationStatus.COMPLETED,
        ]
        assert all(p.operation_uuid == "op-uuid" for p in params)

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


@pytest.mark.asyncio
class TestAsyncRetry:
    def test_async_retry_retries_async_function(self):
        mock = Mock()

        @async_retry(retries=2, backoff_ms=1)
        async def _fn():
            mock.fn()
            raise Exception()

        try:
            asyncio.run(_fn())
        except Exception:
            pass

        mock.fn.assert_called()
        assert mock.fn.call_count == 2

    def test_async_retry_does_not_retry_success(self):
        mock = Mock()

        @async_retry(retries=2, backoff_ms=1)
        async def _fn():
            mock.fn()

        asyncio.run(_fn())

        mock.fn.assert_called()
        assert mock.fn.call_count == 1
