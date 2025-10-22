# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from temporalio.client import StartWorkflowInput
from temporalio.worker import ExecuteActivityInput, ExecuteWorkflowInput

from maascommon.workflows.interceptors import (
    ActivityInboundInterceptorWithTracing,
    ContextPropagationInterceptor,
    OutboundInterceptorWithTracing,
    TRACING_HEADER,
    WorkflowInboundInterceptorWithTracing,
)


@pytest.fixture
def mock_trace_id():
    return "trace-123"


@pytest.fixture
def dummy_payload(mock_trace_id):
    """A payload object returned by PayloadConverter.to_payload."""
    dummy = MagicMock()
    dummy.data = mock_trace_id.encode()
    return dummy


class TestContextPropagationInterceptor:
    def test_context_propagation_interceptor_workflow_interceptor_class(self):
        interceptor = ContextPropagationInterceptor()
        cls = interceptor.workflow_interceptor_class(MagicMock())
        assert cls == WorkflowInboundInterceptorWithTracing

    def test_context_propagation_interceptor_intercept_activity(self):
        interceptor = ContextPropagationInterceptor()
        result = interceptor.intercept_activity(MagicMock())
        assert isinstance(result, ActivityInboundInterceptorWithTracing)

    def test_context_propagation_interceptor_intercept_client(self):
        interceptor = ContextPropagationInterceptor()
        result = interceptor.intercept_client(MagicMock())
        assert isinstance(result, OutboundInterceptorWithTracing)


class TestOutboundInterceptorWithTracing:
    @pytest.mark.asyncio
    async def test_outbound_interceptor_does_not_add_trace_id_if_unset(self):
        with patch(
            "maascommon.workflows.interceptors.get_trace_id", return_value=""
        ):
            next_interceptor = AsyncMock()
            interceptor = OutboundInterceptorWithTracing(next_interceptor)

            interceptor.payload_converter.to_payload = MagicMock(
                return_value=dummy_payload
            )

            input_data = Mock(StartWorkflowInput)
            input_data.headers = {}

            await interceptor.start_workflow(input_data)

            assert TRACING_HEADER not in input_data.headers

            # Next interceptor is called
            next_interceptor.start_workflow.assert_awaited_once_with(
                input_data
            )

    @pytest.mark.asyncio
    async def test_outbound_interceptor_adds_trace_id(
        self, mock_trace_id, dummy_payload
    ):
        with patch(
            "maascommon.workflows.interceptors.get_trace_id",
            return_value=mock_trace_id,
        ):
            next_interceptor = AsyncMock()
            interceptor = OutboundInterceptorWithTracing(next_interceptor)

            interceptor.payload_converter.to_payload = MagicMock(
                return_value=dummy_payload
            )

            input_data = Mock(StartWorkflowInput)
            input_data.headers = {}

            await interceptor.start_workflow(input_data)

            # The trace id in the context is added into the workflow input by the interceptor
            assert TRACING_HEADER in input_data.headers
            assert (
                input_data.headers[TRACING_HEADER].data
                == mock_trace_id.encode()
            )

            # Next interceptor is called
            next_interceptor.start_workflow.assert_awaited_once_with(
                input_data
            )

    @pytest.mark.asyncio
    async def test_outbound_interceptor_preserves_existing_headers(
        self, mock_trace_id, dummy_payload
    ):
        with patch(
            "maascommon.workflows.interceptors.get_trace_id",
            return_value=mock_trace_id,
        ):
            next_interceptor = AsyncMock()
            interceptor = OutboundInterceptorWithTracing(next_interceptor)

            interceptor.payload_converter.to_payload = MagicMock(
                return_value=dummy_payload
            )

            input_data = Mock(StartWorkflowInput)
            input_data.headers = {"existing-key": "existing-value"}
            await interceptor.start_workflow(input_data)

            # Should keep old headers and add tracing header
            assert input_data.headers["existing-key"] == "existing-value"
            assert TRACING_HEADER in input_data.headers


class TestActivityInboundInterceptorWithTracing:
    @pytest.mark.asyncio
    async def test_activity_inbound_sets_trace_id(self, mock_trace_id):
        next_interceptor = AsyncMock()
        interceptor = ActivityInboundInterceptorWithTracing(next_interceptor)

        interceptor.payload_converter.from_payload = MagicMock(
            return_value=mock_trace_id
        )

        with patch(
            "maascommon.workflows.interceptors.set_trace_id"
        ) as mock_set_trace_id:
            input_data = Mock(ExecuteActivityInput)
            input_data.headers = {TRACING_HEADER: mock_trace_id}

            await interceptor.execute_activity(input_data)

            interceptor.payload_converter.from_payload.assert_called_once_with(
                mock_trace_id
            )
            mock_set_trace_id.assert_called_once_with(mock_trace_id)
            next_interceptor.execute_activity.assert_awaited_once_with(
                input_data
            )

    @pytest.mark.asyncio
    async def test_activity_inbound_without_header_does_not_set_trace_id(self):
        next_interceptor = AsyncMock()
        interceptor = ActivityInboundInterceptorWithTracing(next_interceptor)

        with patch(
            "maascommon.workflows.interceptors.set_trace_id"
        ) as mock_set_trace_id:
            input_data = Mock(ExecuteActivityInput)
            input_data.headers = {}

            await interceptor.execute_activity(input_data)

            mock_set_trace_id.assert_not_called()
            next_interceptor.execute_activity.assert_awaited_once_with(
                input_data
            )


class TestWorkflowInboundInterceptorWithTracing:
    @pytest.mark.asyncio
    async def test_workflow_inbound_sets_trace_id(self, mock_trace_id):
        next_interceptor = AsyncMock()
        interceptor = WorkflowInboundInterceptorWithTracing(next_interceptor)

        interceptor.payload_converter.from_payload = MagicMock(
            return_value=mock_trace_id
        )

        with patch(
            "maascommon.workflows.interceptors.set_trace_id"
        ) as mock_set_trace_id:
            input_data = Mock(ExecuteWorkflowInput)
            input_data.headers = {TRACING_HEADER: mock_trace_id}

            await interceptor.execute_workflow(input_data)

            interceptor.payload_converter.from_payload.assert_called_once_with(
                mock_trace_id
            )
            mock_set_trace_id.assert_called_once_with(mock_trace_id)
            next_interceptor.execute_workflow.assert_awaited_once_with(
                input_data
            )

    @pytest.mark.asyncio
    async def test_workflow_inbound_without_header_does_not_set_trace_id(self):
        next_interceptor = AsyncMock()
        interceptor = WorkflowInboundInterceptorWithTracing(next_interceptor)

        with patch(
            "maascommon.workflows.interceptors.set_trace_id"
        ) as mock_set_trace_id:
            input_data = Mock(ExecuteWorkflowInput)
            input_data.headers = {}

            await interceptor.execute_workflow(input_data)

            mock_set_trace_id.assert_not_called()
            next_interceptor.execute_workflow.assert_awaited_once_with(
                input_data
            )
