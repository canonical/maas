# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import dataclasses

from maascommon.enums.operations import OperationStatus

# Search attribute used to link a workflow execution to its operation.
OPERATION_UUID_SEARCH_ATTRIBUTE = "OperationUUID"

UPDATE_OPERATION_STATUS_ACTIVITY_NAME = "update-operation-status"


@dataclasses.dataclass
class UpdateOperationStatusParam:
    operation_uuid: str
    status: OperationStatus
    error: str | None = None
