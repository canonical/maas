#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
import re

_SYSTEMD_DURATION_RE = re.compile(
    r"((?P<hours>\d+?)(\s?(hour(s?)|hr|h))\s?)?((?P<minutes>\d+?)(\s?(minute(s?)|min|m))\s?)?((?P<seconds>\d+?)(\s?(second(s?)|sec|s))\s?)?"
)


def systemd_interval_to_seconds(interval):
    duration = _SYSTEMD_DURATION_RE.match(interval)
    if not duration.group():
        raise ValueError(
            f"'{interval}' is not a valid interval. Only 'h|hr|hour|hours, m|min|minute|minutes."
            f"s|sec|second|seconds' are valid units"
        )
    duration = duration.groupdict()
    params = {name: int(t) for name, t in duration.items() if t}
    return timedelta(**params).total_seconds()
