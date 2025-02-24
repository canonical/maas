#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from datetime import timedelta
from enum import IntEnum, StrEnum


class NetworkDiscoveryEnum(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"

    def __str__(self):
        return str(self.value)


def _timedelta_to_whole_seconds(**kwargs) -> int:
    """Convert arbitrary timedelta to whole seconds."""
    return int(timedelta(**kwargs).total_seconds())


class ActiveDiscoveryIntervalEnum(IntEnum):
    NEVER = 0
    EVERY_WEEK = _timedelta_to_whole_seconds(days=7)
    EVERY_DAY = _timedelta_to_whole_seconds(days=1)
    EVERY_12_HOURS = _timedelta_to_whole_seconds(hours=12)
    EVERY_6_HOURS = _timedelta_to_whole_seconds(hours=6)
    EVERY_3_HOURS = _timedelta_to_whole_seconds(hours=3)
    EVERY_HOUR = _timedelta_to_whole_seconds(hours=1)
    EVERY_30_MINUTES = _timedelta_to_whole_seconds(minutes=30)
    EVERY_10_MINUTES = _timedelta_to_whole_seconds(minutes=10)
