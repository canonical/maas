# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Optional
import uuid

from temporalio.client import Client

from maasserver.workflow.worker import (
    get_client_async as get_temporal_client_async,
)
from maasservicelayer.context import Context
from maasservicelayer.services.base import Service, ServiceCache


@dataclass(slots=True)
class TemporalServiceCache(ServiceCache):
    temporal_client: Client | None = None


class TemporalService(Service):
    def __init__(
        self, context: Context, cache: ServiceCache
    ):  # we shouldn't do anything inside workflows
        super().__init__(context, cache)
        self._post_commit_workflows = {}
        self._running_workflows = []

    @staticmethod
    def build_cache_object() -> ServiceCache:
        return TemporalServiceCache()

    @Service.from_cache_or_execute(attr="temporal_client")
    async def get_temporal_client(self) -> Client:
        return await get_temporal_client_async()

    async def post_commit(self) -> None:
        for key, arguments in self._post_commit_workflows.items():  # noqa: B007
            workflow_name, parameter, workflow_id, wait, args, kwargs = (
                arguments
            )
            if not workflow_id:
                workflow_id = str(uuid.uuid4())

            client = await self.get_temporal_client()
            # TODO: make the task_queue a workflow parameter instead of hardcoding it here.
            if wait:
                await client.execute_workflow(
                    workflow_name,
                    parameter,
                    id=workflow_id,
                    task_queue="region",
                    *args,  # noqa: B026
                    **kwargs,
                )
            else:
                fut = await client.start_workflow(
                    workflow_name,
                    parameter,
                    id=workflow_id,
                    task_queue="region",
                    *args,  # noqa: B026
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
        *args,
        **kwargs,
    ) -> None:
        key = self._make_key(workflow_name, workflow_id)

        if self.workflow_is_registered(workflow_name, workflow_id=workflow_id):
            if not override_previous_parameters:
                if parameter_merge_func is None:
                    raise ValueError(
                        "must either override or merge parameters with existing workflows"
                    )

                parameter = parameter_merge_func(
                    self._post_commit_workflows[key][1], parameter
                )

            self.register_workflow_call(
                workflow_name,
                parameter,
                workflow_id=workflow_id,
                wait=wait,
                *args,  # noqa: B026
                **kwargs,
            )
        else:
            self.register_workflow_call(
                workflow_name,
                parameter,
                workflow_id=workflow_id,
                wait=wait,
                *args,  # noqa: B026
                **kwargs,
            )
