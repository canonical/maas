# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.operations import (
    OperationStatus,
    OperationTaskStatus,
    OperationType,
)
from maasservicelayer.models.operations import Operation, OperationTask
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_operation_entry(
    fixture: Fixture,
    *,
    uuid: str = "test-uuid",
    op_type: OperationType = OperationType.MACHINE_DEPLOY,
    status: OperationStatus = OperationStatus.ACCEPTED,
    is_bulk: bool = False,
) -> Operation:
    now = utcnow()
    [row] = await fixture.create(
        "maasserver_operation",
        [
            {
                "uuid": uuid,
                "op_type": op_type.value,
                "status": status.value,
                "is_bulk": is_bulk,
                "created": now,
                "updated": now,
            }
        ],
    )
    return Operation(**row)


async def create_test_operation_task_entry(
    fixture: Fixture,
    *,
    operation_uuid: str,
    name: str = "test-task",
    status: OperationTaskStatus = OperationTaskStatus.WAITING,
    task_number: int = 0,
) -> OperationTask:
    [row] = await fixture.create(
        "maasserver_operation_task",
        [
            {
                "operation_uuid": operation_uuid,
                "name": name,
                "status": status.value,
                "task_number": task_number,
            }
        ],
    )
    return OperationTask(**row)
