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


class MAASLogger(logging.getLoggerClass()):
    """A Logger class that doesn't allow you to call exception()."""

    def exception(self, *args, **kwargs):
        raise NotImplementedError(
            "Don't log exceptions to maaslog; use the default "
            "Django logger instead")


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
    # This line is pure filth, but it allows us to return MAASLoggers
    # for any logger constructed by this function, whilst leaving all
    # other loggers to be the domain of the logging package.
    maaslog.__class__ = MAASLogger

    return maaslog


def configure_root_logger():
    # Configure the "root" handler. This is the only place where we need to
    # add the syslog handler and configure levels and formatting; sub-handlers
    # propagate up to this handler.
    root = get_maas_logger()
    if len(root.handlers) == 0:
        # It has not yet been configured.
        handler = SysLogHandler(
            "/dev/log", facility=SysLogHandler.LOG_DAEMON)
        handler.setFormatter(logging.Formatter(
            "%(name)s: [%(levelname)s] %(message)s"))
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        # Don't propagate logs up to the root logger.
        root.propagate = 0
    return root


configure_root_logger()
