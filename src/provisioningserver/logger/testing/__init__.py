# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing helpers for `provisioningserver.logger`."""

__all__ = [
    "make_event",
    "make_log_text",
    "pick_log_level",
    "pick_log_time",
]

import random
import time

from maastesting.factory import factory
from twisted.logger import LogLevel


def make_event(log_text=None, log_level=None, log_time=None):
    """Make a minimal event dict for use with Twisted."""
    return {
        "log_format": "{log_text}",
        "log_level": pick_log_level() if log_level is None else log_level,
        "log_text": make_log_text() if log_text is None else log_text,
        "log_time": pick_log_time() if log_time is None else log_time,
    }


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
