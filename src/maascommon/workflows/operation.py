#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.operations import OperationType
from maascommon.workflows.commission import COMMISSION_WORKFLOW_NAME

OPERATION_UUID_SEARCH_ATTRIBUTE = "OperationUUID"

OPERATION_TYPE_WORKFLOW_NAME: dict[OperationType, str] = {
    OperationType.MACHINE_COMMISSION: COMMISSION_WORKFLOW_NAME,
}
