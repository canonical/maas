# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, Optional, Type

from temporalio.client import (
    Interceptor as ClientInterceptor,  # type: ignore[attr-defined]
)
from temporalio.client import (  # type: ignore[attr-defined]
    OutboundInterceptor,
    StartWorkflowInput,
    WorkflowHandle,
)
from temporalio.converter import PayloadConverter
from temporalio.worker import (
    ActivityInboundInterceptor,
    ExecuteActivityInput,
    ExecuteWorkflowInput,
    WorkflowInboundInterceptor,
    WorkflowInterceptorClassInput,
)
from temporalio.worker import (
    Interceptor as WorkerInterceptor,  # type: ignore[attr-defined]
)

from maascommon.tracing import get_trace_id, set_trace_id

TRACING_HEADER = "MAAS-trace-id"


class ContextPropagationInterceptor(ClientInterceptor, WorkerInterceptor):
    def workflow_interceptor_class(
        self, input: WorkflowInterceptorClassInput
    ) -> Optional[Type[WorkflowInboundInterceptor]]:
        return WorkflowInboundInterceptorWithTracing

    def intercept_activity(
        self, next: ActivityInboundInterceptor
    ) -> ActivityInboundInterceptor:
        return ActivityInboundInterceptorWithTracing(next)

    def intercept_client(
        self, next: OutboundInterceptor
    ) -> OutboundInterceptor:
        return OutboundInterceptorWithTracing(next)


class OutboundInterceptorWithTracing(OutboundInterceptor):
    def __init__(self, next: OutboundInterceptor):
        super().__init__(next)
        self.payload_converter = PayloadConverter.default

    async def start_workflow(
        self,
        input: StartWorkflowInput,
    ) -> WorkflowHandle[Any, Any]:
        trace_id = get_trace_id()
        if trace_id:
            input.headers = {
                **input.headers,
                TRACING_HEADER: self.payload_converter.to_payload(
                    trace_id.encode()
                ),
            }
        return await super().start_workflow(input)


class ActivityInboundInterceptorWithTracing(ActivityInboundInterceptor):
    def __init__(self, next: ActivityInboundInterceptor):
        super().__init__(next)
        self.payload_converter = PayloadConverter.default

    async def execute_activity(self, input: ExecuteActivityInput) -> Any:
        if TRACING_HEADER in input.headers:
            set_trace_id(
                self.payload_converter.from_payload(
                    input.headers[TRACING_HEADER]
                )
            )
        return await self.next.execute_activity(input)


class WorkflowInboundInterceptorWithTracing(WorkflowInboundInterceptor):
    def __init__(self, next: WorkflowInboundInterceptor):
        super().__init__(next)
        self.payload_converter = PayloadConverter.default

    async def execute_workflow(self, input: ExecuteWorkflowInput) -> Any:
        if TRACING_HEADER in input.headers:
            set_trace_id(
                self.payload_converter.from_payload(
                    input.headers[TRACING_HEADER]
                )
            )
        return await self.next.execute_workflow(input)
