#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from enum import IntEnum


class SwitchStatus(IntEnum):
    """The vocabulary of a `Switch`'s possible statuses."""

    # The switch has been created but not yet served a NOS image.
    NEW = 0
    # The switch has been served a NOS image.
    SERVED_NOS = 1
