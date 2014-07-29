# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Logging for MAAS, redirects to syslog."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "maaslog",
    ]


import logging
from logging.handlers import SysLogHandler

maaslog = logging.getLogger("maas")
maaslog.setLevel(logging.DEBUG)
handler = SysLogHandler("/dev/log")
maaslog.addHandler(handler)
formatter = logging.Formatter(fmt="maas: %(message)s")
handler.setFormatter(formatter)
