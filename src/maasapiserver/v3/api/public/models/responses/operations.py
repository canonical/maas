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
from maascommon.enums.operations import OperationStatus, OperationType
from maasservicelayer.models.operations import Operation


class OperationResponse(HalResponse[BaseHal]):
    """Response model for a single operation.

    Represents an operation with its status and metadata.
    """

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
    result_errors: dict | None = None
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
            result_errors=operation.result_errors,
            is_bulk=operation.is_bulk,
            parent_id=operation.parent_id,
            user_id=operation.user_id,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{operation.uuid}"
                )
            ),
        )


class OperationsListResponse(PaginatedResponse[OperationResponse]):
    """Response model for a paginated list of operations."""

    kind: str = Field(default="OperationsList")
