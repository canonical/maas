# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime

from maascommon.enums.operations import OperationStatus, OperationType
from maasservicelayer.models.base import (
    generate_builder,
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
    result_errors: dict | None = None
    is_bulk: bool
    parent_id: str | None = None
    user_id: int | None = None
