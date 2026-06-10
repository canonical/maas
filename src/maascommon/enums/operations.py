# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from enum import StrEnum


class OperationStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"


class OperationTaskStatus(StrEnum):
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class OperationType(StrEnum):
    MACHINE_COMMISSION = "machine.commission"
    MACHINE_DEPLOY = "machine.deploy"
    MACHINE_BULKDEPLOY = "machine.bulkdeploy"
    SELECTION_SYNC = "selection.sync"
