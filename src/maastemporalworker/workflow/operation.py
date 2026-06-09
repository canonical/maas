# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.workflows.operation import (
    UPDATE_OPERATION_STATUS_ACTIVITY_NAME,
    UpdateOperationStatusParam,
)
from maastemporalworker.workflow.activity import ActivityBase
from maastemporalworker.workflow.utils import activity_defn_with_context


class OperationActivity(ActivityBase):
    @activity_defn_with_context(name=UPDATE_OPERATION_STATUS_ACTIVITY_NAME)
    async def update_operation_status(
        self, param: UpdateOperationStatusParam
    ) -> None:
        async with self.start_transaction() as services:
            await services.operations.update_status(
                operation_uuid=param.operation_uuid,
                status=param.status,
                error=param.error,
            )
