# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for logging."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "log_call",
]

from functools import wraps
import logging

from provisioningserver.logger.log import get_maas_logger


maaslog = get_maas_logger("calls")


def log_call(level=logging.INFO):
    """Log to the maaslog that something happened with a task.

    :param event: The event that we want to log.
    :param task_name: The name of the task.
    :**kwargs: A dict of args passed to the task.
    """
    def _decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            arg_string = "%s %s" % (args, kwargs)
            maaslog.log(
                level, "Starting task '%s' with args: %s" %
                (func.__name__, arg_string))
            func(*args, **kwargs)
            maaslog.log(
                level, "Finished task '%s' with args: %s" %
                (func.__name__, arg_string))
        return wrapper
    return _decorator
