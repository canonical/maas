# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from enum import IntEnum


class ScriptType(IntEnum):
    COMMISSIONING = 0
    # 1 is skipped to keep numbering the same as RESULT_TYPE
    TESTING = 2
    RELEASE = 3
    DEPLOYMENT = 4


class ScriptParallel(IntEnum):
    DISABLED = 0
    INSTANCE = 1
    ANY = 2
