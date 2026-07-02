#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.operations import OperationType
from maascommon.workflows.commission import COMMISSION_WORKFLOW_NAME

OPERATION_UUID_SEARCH_ATTRIBUTE = "OperationUUID"

RECONCILE_OPERATIONS_WORKFLOW_NAME = "reconcile-operations"
BULK_OPERATION_WORKFLOW_NAME = "bulk-operation"


OPERATION_TYPE_WORKFLOW_NAME: dict[OperationType, str] = {
    OperationType.MACHINE_COMMISSION: COMMISSION_WORKFLOW_NAME,
    OperationType.MACHINE_BULKDEPLOY: BULK_OPERATION_WORKFLOW_NAME,
}


def workflow_name_for_operation_type(op_type: OperationType) -> str | None:
    """Return the workflow name that fulfils ``op_type``, or None if unmapped."""
    return OPERATION_TYPE_WORKFLOW_NAME.get(op_type)
