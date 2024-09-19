#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from enum import IntEnum


class BmcType(IntEnum):
    """Valid BMC types."""

    DEFAULT = 0
    BMC = 0
    POD = 1
