import asyncio
from typing import Any, Callable, Optional

from temporalio.client import Client

from maasservicelayer.services._base import Service


class TemporalService(Service):
    def __init__(
        self, temporal: Optional[Client] = None
    ):  # we shouldn't do anything inside workflows
        self._temporal = temporal
        self._post_commit_workflows = {}
        self._running_workflows = []

    async def post_commit(self) -> None:
        if not self._temporal:
            return

        for key, arguments in self._post_commit_workflows.items():
            workflow_name, parameter, workflow_id, wait, args, kwargs = (
                arguments
            )

            if wait:
                await self._temporal.execute_workflow(
                    workflow_name,
                    parameter,
                    workflow_id=workflow_id,
                    *args,
                    **kwargs,
                )
            else:
                fut = await self._temporal.start_workflow(
                    workflow_name,
                    parameter,
                    workflow_id=workflow_id,
                    *args,
                    **kwargs,
                )
                self._running_workflows.append(fut)
        self._post_commit_workflows = {}

    async def resolve_background_workflows(self) -> None:
        await asyncio.wait(*self._running_workflows)
        self._running_workflows = []

    def _make_key(self, workflow_name: str, workflow_id: str | None) -> str:
        if workflow_id:
            return f"{workflow_name}:{workflow_id}"
        return workflow_name

    def workflow_is_registered(
        self, workflow_name: str, workflow_id: Optional[str] = None
    ) -> bool:
        key = self._make_key(workflow_name, workflow_id)
        return key in self._post_commit_workflows

    def register_workflow_call(
        self,
        workflow_name: str,
        parameter: Any,
        workflow_id: Optional[str] = None,
        wait: Optional[bool] = True,
        *args: list[Any],
        **kwargs: dict[str, Any],
    ) -> None:
        if not self._temporal:
            return

        key = self._make_key(workflow_name, workflow_id)
        self._post_commit_workflows[key] = (
            workflow_name,
            parameter,
            workflow_id,
            wait,
            args,
            kwargs,
        )

    def register_or_update_workflow_call(
        self,
        workflow_name: str,
        parameter: Any,
        workflow_id: Optional[str] = None,
        wait: Optional[bool] = True,
        override_previous_parameters: Optional[bool] = False,
        parameter_merge_func: Optional[Callable] = None,
    ) -> None:
        if not self._temporal:
            return

        key = self._make_key(workflow_name, workflow_id)

        if self.workflow_is_registered(workflow_name, workflow_id=workflow_id):
            if not override_previous_parameters and not parameter_merge_func:
                raise ValueError(
                    "must either override or merge parameters with existing workflows"
                )

            if not override_previous_parameters:
                parameter = parameter_merge_func(
                    self._post_commit_workflows[key][1], parameter
                )

            self.register_workflow_call(
                workflow_name, parameter, workflow_id=workflow_id, wait=wait
            )
        else:
            self.register_workflow_call(
                workflow_name, parameter, workflow_id=workflow_id, wait=wait
            )
