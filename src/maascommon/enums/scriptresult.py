#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from enum import IntEnum


class ScriptStatus(IntEnum):
    PENDING = 0
    RUNNING = 1
    PASSED = 2
    FAILED = 3
    TIMEDOUT = 4
    ABORTED = 5
    DEGRADED = 6
    INSTALLING = 7
    FAILED_INSTALLING = 8
    SKIPPED = 9
    APPLYING_NETCONF = 10
    FAILED_APPLYING_NETCONF = 11
