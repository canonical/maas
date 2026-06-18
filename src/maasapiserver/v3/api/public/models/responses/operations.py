# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Self

from pydantic import Field

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.operations import (
    OperationStatus,
    OperationTaskStatus,
    OperationType,
)
from maasservicelayer.models.operations import Operation, OperationTask


class OperationResponse(HalResponse[BaseHal]):
    kind: str = Field(default="Operation")
    uuid: str
    op_type: OperationType
    resource_id: int | None = None
    resource_type: str | None = None
    status: OperationStatus
    created: datetime
    updated: datetime
    started: datetime | None = None
    finished: datetime | None = None
    current_task: str | None = None
    parameters: dict | None = None
    result: dict | None = None
    is_bulk: bool
    parent_id: str | None = None
    user_id: int | None = None

    @classmethod
    def from_model(
        cls,
        operation: Operation,
        self_base_hyperlink: str,
    ) -> Self:
        return cls(
            uuid=operation.uuid,
            op_type=operation.op_type,
            resource_id=operation.resource_id,
            resource_type=operation.resource_type,
            status=operation.status,
            created=operation.created,
            updated=operation.updated,
            started=operation.started,
            finished=operation.finished,
            current_task=operation.current_task,
            parameters=operation.parameters,
            result=operation.result,
            is_bulk=operation.is_bulk,
            parent_id=operation.parent_id,
            user_id=operation.user_id,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{operation.uuid}"
                )
            ),
        )


class OperationTaskResponse(HalResponse[BaseHal]):
    kind: str = Field(default="OperationTask")
    id: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    name: str
    status: OperationTaskStatus
    result: dict | None = None
    task_number: int
    operation_uuid: str

    @classmethod
    def from_model(
        cls,
        task: OperationTask,
    ) -> Self:
        return cls(
            id=task.id,
            started_at=task.started_at,
            finished_at=task.finished_at,
            name=task.name,
            status=task.status,
            result=task.result,
            task_number=task.task_number,
            operation_uuid=task.operation_uuid,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=(
                        f"{V3_API_PREFIX}/operations/"
                        f"{task.operation_uuid}/tasks"
                    )
                )
            ),
        )


class OperationsListResponse(PaginatedResponse[OperationResponse]):
    kind: str = Field(default="OperationsList")


class OperationTasksListResponse(PaginatedResponse[OperationTaskResponse]):
    kind: str = Field(default="OperationTasksList")
