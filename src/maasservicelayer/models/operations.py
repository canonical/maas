# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime

from maascommon.enums.operations import (
    OperationStatus,
    OperationTaskStatus,
    OperationType,
)
from maasservicelayer.models.base import (
    generate_builder,
    MaasBaseModel,
    MaasTimestampedBaseModel,
)


@generate_builder()
class Operation(MaasTimestampedBaseModel):
    uuid: str
    op_type: OperationType
    resource_id: int | None = None
    resource_type: str | None = None
    status: OperationStatus
    started: datetime | None = None
    finished: datetime | None = None
    current_task: str | None = None
    parameters: dict | None = None
    result: dict | None = None
    is_bulk: bool
    parent_id: str | None = None
    user_id: int | None = None


class OperationTask(MaasBaseModel):
    started_at: datetime | None = None
    finished_at: datetime | None = None
    name: str
    status: OperationTaskStatus
    result: dict | None = None
    task_number: int
    operation_uuid: str
