# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing utilities for Temporal workflows.

Provides interceptors and assertions to track and validate activity and child workflow
calls during testing.

Usage
-----
Use the provided fixtures in your tests:

    async def test_my_workflow(temporal_calls: TemporalCalls, worker_test_interceptor):
        async with Worker(
            ...,
            ...,
            interceptors=[worker_test_interceptor],
        ):
            await client.execute_workflow(...)

            # Assert
            temporal_calls.assert_activity_called_once("activity1")
            temporal_calls.assert_activity_called_with("activity2", task_queue="test")
            temporal_calls.assert_activity_calls("validate", "process", "notify")

            temporal_calls.assert_child_workflow_not_called("my-wf")

See `TemporalCalls` for the full list of assertions.

"""

from dataclasses import asdict
from datetime import timedelta
from typing import Generic, Optional, Type, TypeVar

import pytest
from temporalio.client import WorkflowExecutionStatus
from temporalio.service import RPCError
from temporalio.worker import (
    Interceptor,
    StartActivityInput,
    StartChildWorkflowInput,
    WorkflowInboundInterceptor,
    WorkflowInterceptorClassInput,
    WorkflowOutboundInterceptor,
)
from temporalio.workflow import ActivityHandle, ChildWorkflowHandle

T = TypeVar("T", StartActivityInput, StartChildWorkflowInput)


class CallsList(list[T], Generic[T]):
    """Generic base class for tracking different types of calls."""

    def __init__(self, name_attr: str, id_attr: str):
        super().__init__()
        self._name_attr = name_attr
        self._id_attr = id_attr

    @property
    def names(self) -> list[str]:
        """Get list of all call names."""
        return [getattr(item, self._name_attr) for item in self]

    def get_by_name(self, name: str) -> list[T]:
        """Get all calls matching the given name."""
        return [
            item for item in self if getattr(item, self._name_attr) == name
        ]

    def count_by_name(self, name: str) -> int:
        """Count how many times a call with this name occurred."""
        return len(self.get_by_name(name))

    def has_name(self, name: str) -> bool:
        """Check if any call with this name exists."""
        return name in self.names


class ActivityCalls(CallsList[StartActivityInput]):
    def __init__(self):
        super().__init__(name_attr="activity", id_attr="activity_id")


class ChildWorkflowCalls(CallsList[StartChildWorkflowInput]):
    def __init__(self):
        super().__init__(name_attr="workflow", id_attr="id")


class TemporalCalls:
    """Tracker for all Temporal calls made during workflow execution.

    Currently keeps track only of child workflows and activities.
    """

    def __init__(self) -> None:
        self.activities = ActivityCalls()
        self.child_workflows = ChildWorkflowCalls()

    # Activity assertions
    def assert_activity_called(self, activity_name: str):
        """Assert that an activity was called at least once."""
        assert self.activities.has_name(activity_name), (
            f"Expected activity '{activity_name}' not found. "
            f"Activities executed: {self.activities.names}"
        )

    def assert_activity_called_times(self, activity_name: str, times: int):
        """Assert that an activity was called exactly N times."""
        actual_count = self.activities.count_by_name(activity_name)
        assert actual_count == times, (
            f"Expected activity '{activity_name}' to be called {times} times, "
            f"but it was called {actual_count} times. "
            f"Activities executed: {self.activities.names}"
        )

    def assert_activity_called_once(self, activity_name: str):
        """Assert that an activity was called exactly once."""
        return self.assert_activity_called_times(activity_name, times=1)

    def assert_activity_not_called(self, activity_name: str):
        """Assert that an activity was never called."""
        assert not self.activities.has_name(activity_name), (
            f"Expected activity '{activity_name}' to not be called, "
            f"but it was called {self.activities.count_by_name(activity_name)} times"
        )

    def assert_activity_called_with(
        self,
        activity_name: str,
        call_index: int = 0,
        **expected_args,
    ):
        """Assert that an activity was called with specific arguments.

        The arguments passed can be a subset of all the arguments.
        See `StartActivityInput` for the full list of arguments.
        """
        matches = self.activities.get_by_name(activity_name)
        assert matches, (
            f"Activity '{activity_name}' was never called. "
            f"Activities executed: {self.activities.names}"
        )
        assert call_index < len(matches), (
            f"Call index {call_index} out of range for activity '{activity_name}'. "
            f"Only {len(matches)} calls found"
        )

        actual_input = matches[call_index]
        actual_input_dict = asdict(actual_input)

        for key, value in expected_args.items():
            assert key in actual_input_dict, (
                f"{key} not found in activity input. Activity input: {actual_input}"
            )
            assert actual_input_dict[key] == value, (
                f"Wrong value for arg {key}. Expected: {value}, Actual: {actual_input_dict[key]}."
            )

    def assert_activity_calls(self, activity_names: list[str]):
        """Assert that only these activities were called (order matters)"""
        assert len(activity_names) == len(self.activities), (
            "Activities count mismatch. "
            f"Expected: {len(activity_names)}, Actual: {len(self.activities)}. "
            f"Activities executed: {self.activities.names}"
        )

        assert activity_names == self.activities.names, (
            "Activities order mismatch. "
            f"Expected: {activity_names}, Actual: {self.activities.names}"
        )

    # Child workflow assertions
    def assert_child_workflow_called(self, child_workflow_name: str):
        """Assert that a child workflow was started."""
        assert self.child_workflows.has_name(child_workflow_name), (
            f"Expected child workflow '{child_workflow_name}' not found. "
            f"Child workflows executed: {self.child_workflows.names}"
        )

    def assert_child_workflow_called_times(
        self, workflow_name: str, times: int
    ):
        """Assert that a child workflow was started exactly N times."""
        actual_count = self.child_workflows.count_by_name(workflow_name)
        assert actual_count == times, (
            f"Expected child workflow '{workflow_name}' to be started {times} times, "
            f"but it was started {actual_count} times. "
            f"Child workflows executed: {self.child_workflows.names}"
        )

    def assert_child_workflow_called_once(self, child_workflow_name: str):
        """Assert that a child workflow was started exactly once."""
        return self.assert_child_workflow_called_times(
            child_workflow_name, times=1
        )

    def assert_child_workflow_not_called(self, workflow_name: str):
        """Assert that a child workflow was never started."""
        assert not self.child_workflows.has_name(workflow_name), (
            f"Expected child workflow '{workflow_name}' to not be called, "
            f"but it was called {self.child_workflows.count_by_name(workflow_name)} times"
        )

    def assert_child_workflow_calls(self, workflow_names: list[str]):
        """Assert that only these child workflows were called (order matters)"""
        assert len(workflow_names) == len(self.child_workflows), (
            "Child workflows count mismatch. "
            f"Expected: {len(workflow_names)}, Actual: {len(self.child_workflows)}. "
            f"Child workflows executed: {self.child_workflows.names}"
        )

        assert workflow_names == self.child_workflows.names, (
            "Child workflows order mismatch. "
            f"Expected: {workflow_names}, Actual: {self.child_workflows.names}"
        )

    def assert_child_workflow_called_with(
        self,
        child_workflow_name: str,
        call_index: int = 0,
        **expected_args,
    ):
        """Assert that a child workflow was called with specific arguments.

        The arguments passed can be a subset of all the arguments.
        See `StartChildWorkflowInput` for the full list of arguments.
        """
        matches = self.child_workflows.get_by_name(child_workflow_name)
        assert matches, (
            f"Child workflow '{child_workflow_name}' was never called. "
            f"Child workflows executed: {self.child_workflows.names}"
        )
        assert call_index < len(matches), (
            f"Call index {call_index} out of range for child workflow '{child_workflow_name}'. "
            f"Only {len(matches)} calls found"
        )

        actual_input = matches[call_index]
        actual_input_dict = asdict(actual_input)

        for key, value in expected_args.items():
            assert key in actual_input_dict, (
                f"{key} not found in child workflow input. Child workflow input: {actual_input}"
            )
            assert actual_input_dict[key] == value, (
                f"Wrong value for arg {key}. Expected: {value}, Actual: {actual_input_dict[key]}."
            )

    # Utility methods
    def clear(self):
        """Clear all recorded calls. Useful for test isolation."""
        self.activities.clear()
        self.child_workflows.clear()


class WorkerTestInterceptor(Interceptor):
    def __init__(self, temporal_calls: TemporalCalls) -> None:
        super().__init__()
        self.temporal_calls = temporal_calls

    def workflow_interceptor_class(
        self, input: WorkflowInterceptorClassInput
    ) -> Optional[Type[WorkflowInboundInterceptor]]:
        temporal_calls = self.temporal_calls

        class WorkflowTestInboundInterceptor(WorkflowInboundInterceptor):
            def init(self, outbound: WorkflowOutboundInterceptor) -> None:
                return super().init(
                    WorkflowTestOutboundInterceptor(
                        outbound,
                        temporal_calls=temporal_calls,
                    )
                )

        return WorkflowTestInboundInterceptor


class WorkflowTestOutboundInterceptor(WorkflowOutboundInterceptor):
    def __init__(
        self, next: WorkflowOutboundInterceptor, temporal_calls: TemporalCalls
    ) -> None:
        super().__init__(next)
        self.temporal_calls = temporal_calls

    async def start_child_workflow(
        self, input: StartChildWorkflowInput
    ) -> ChildWorkflowHandle:
        self.temporal_calls.child_workflows.append(input)
        return await super().start_child_workflow(input)

    def start_activity(self, input: StartActivityInput) -> ActivityHandle:
        self.temporal_calls.activities.append(input)
        return super().start_activity(input)


@pytest.fixture
def temporal_calls() -> TemporalCalls:
    return TemporalCalls()


@pytest.fixture
def worker_test_interceptor(
    temporal_calls: TemporalCalls,
) -> WorkerTestInterceptor:
    return WorkerTestInterceptor(temporal_calls)


async def cancel_workflow_immediately(handle):
    """Calls `await handle.cancel()` until it succeeds.

    Use this with `asyncio.wait_for(cancel_workflow_immediately(h), timeout=X)`
    to specify a timeout and avoid to potentially run it forever.

    The function will then assert that the status of the workflow is canceled.
    """

    while (
        status := await get_workflow_status(handle)
    ) != WorkflowExecutionStatus.RUNNING:
        continue

    while True:
        try:
            await handle.cancel(rpc_timeout=timedelta(seconds=3))
            break
        except RPCError:
            continue

    # Iterate until the workflow is not running anymore: the cancellation is not
    # an immediate action and might take a bit of time.
    while (
        status := await get_workflow_status(handle)
    ) == WorkflowExecutionStatus.RUNNING:
        continue

    assert status == WorkflowExecutionStatus.CANCELED, (
        f"Workflow not in Canceled status. Status: {status}"
    )


async def get_workflow_status(handle) -> WorkflowExecutionStatus:
    while True:
        try:
            return (await handle.describe()).status
        except RPCError:
            continue
