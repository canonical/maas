# Copyright 2012-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing helpers for `provisioningserver.logger`."""

import json
import random
import re
import time

from twisted.logger import LogLevel

from maastesting.factory import factory


def make_event(log_text=None, log_level=None, log_time=None, **other):
    """Make a minimal event dict for use with Twisted."""
    event = {
        "log_format": "{log_text}",
        "log_level": pick_log_level() if log_level is None else log_level,
        "log_text": make_log_text() if log_text is None else log_text,
        "log_time": pick_log_time() if log_time is None else log_time,
    }
    event.update(other)
    return event


def make_log_text():
    """Make some random log text."""
    return factory.make_unicode_string(size=50, spaces=True)


_log_levels = tuple(LogLevel.iterconstants())


def pick_log_level():
    """Pick a random `LogLevel`."""
    return random.choice(_log_levels)


def pick_log_time(noise=float(60 * 60)):
    """Pick a random time based on now, but with some noise."""
    return time.time() + (random.random() * noise) - (noise / 2)


# Matches lines like: 2016-10-18 14:23:55 namespace: [level] message
find_log_lines_re = re.compile(
    r"^(.*?): \[(.*)\] (.*)$",
    re.MULTILINE,
)


def find_log_lines(text, use_json_logging):
    """Find logs in `text` that match `find_log_lines_re`.

    Checks for well-formed date/times but throws them away.
    """
    if use_json_logging:
        results = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                # Try to match json, it should come from twisted.
                data = json.loads(line)
                name = data.get("name")
                level = data.get("level").lower()
                message = data.get("message")
                assert (
                    "twisted.logger" in message
                    or "twisted.python.log" in message
                    or "Printing" in message
                    or "UserWarning" in message
                ), (
                    f"The message {message} is not expected to be in a JSON format"
                )
                results.append((name, level, message))
            except json.JSONDecodeError:
                # Try to match plaintext, should come from syslog.
                groups = find_log_lines_re.findall(line)
                if groups:
                    message = groups[0]
                    assert (
                        "get_maas_logger" in message[2]
                        or "logging" in message[2]
                    ), (
                        "Only maassyslog and logging are supposed to be in plaintext."
                    )
                    results.append(message)
        return results
    return find_log_lines_re.findall(text)
