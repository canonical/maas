#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone


def utc_from_timestamp(timestamp: float) -> datetime:
    """Return UTC time from a timestamp."""
    return datetime.fromtimestamp(timestamp, timezone.utc)
