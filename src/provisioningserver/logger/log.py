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
    "get_maas_logger",
    ]


import logging
from logging.handlers import SysLogHandler


def get_maas_logger(syslog_tag=None):
    """Return a MAAS logger that will log to syslog.

    :param syslog_tag: A string that will be used to prefix the message
        in syslog. Will be appended to "maas" in the form
        "maas.<syslog_tag>". If None, the syslog tag will simply be
        "maas". syslog_tag is also used to name the logger with the
        Python logging module; loggers will be named "maas.<syslog_tag>"
        unless syslog_tag is None.
    """
    if syslog_tag is None:
        logger_name = "maas"
    else:
        logger_name = "maas.%s" % syslog_tag
    maaslog = logging.getLogger(logger_name)
    # If the logger already has handlers, it's already been
    # instantiated, so we don't need to go through the setup dance
    # again.
    if len(maaslog.handlers) > 0:
        return maaslog

    maaslog.setLevel(logging.DEBUG)
    handler = SysLogHandler("/dev/log")
    maaslog.addHandler(handler)
    formatter = logging.Formatter(fmt=maaslog.name + ": %(message)s")
    handler.setFormatter(formatter)
    return maaslog
