# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
"""__init__ for the provisioningserver.logger package."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "basicConfig",
    "DEFAULT_LOG_FORMAT",
    "DEFAULT_LOG_FORMAT_DATE",
    "DEFAULT_LOG_LEVEL",
    "get_maas_logger"
    ]

import logging
import sys

from provisioningserver.logger.log import get_maas_logger
from twisted.python import log

# This format roughly matches Twisted's default, so that combined Twisted and
# Django logs are consistent with one another.
DEFAULT_LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
DEFAULT_LOG_FORMAT_DATE = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOG_LEVEL = logging.INFO


def basicConfig():
    """Configure basic logging for both Twisted and Python.

    This is useful during start-up, to get something going.

    Note that nothing is done to address time-zones. Both Twisted and Python's
    ``logging`` using local-time by default.
    """
    # Globally override Twisted's log date format. It's tricky to get to the
    # FileLogObserver that twistd installs so that we can modify its config
    # alone, but we actually do want to make a global change anyway.
    log.FileLogObserver.timeFormat = DEFAULT_LOG_FORMAT_DATE
    # Get basic Python logging working with options consistent with Twisted.
    logging.basicConfig(
        stream=sys.stdout, level=DEFAULT_LOG_LEVEL, format=DEFAULT_LOG_FORMAT,
        datefmt=DEFAULT_LOG_FORMAT_DATE)
