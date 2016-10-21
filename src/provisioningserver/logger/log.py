# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Logging for MAAS, redirects to syslog."""

__all__ = [
    "get_maas_logger",
    ]

import logging


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
