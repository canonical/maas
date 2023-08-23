# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
"""Common parts of MAAS's logging machinery."""

import enum
import functools
import logging
import sys

# This format roughly matches Twisted's default, so that combined Twisted and
# Django logs are consistent with one another.
#
# For timestamps, rely on journald instead.
DEFAULT_LOG_FORMAT = "%(name)s: [%(levelname)s] %(message)s"
DEFAULT_LOG_VERBOSITY_LEVELS = {0, 1, 2, 3}
DEFAULT_LOG_VERBOSITY = 2


@enum.unique
class LoggingMode(enum.Enum):
    """The configuration mode for logging."""

    # A command-line invocation: initialise the Twisted legacy logging system,
    # but neither stdio nor warnings will be redirected.
    COMMAND = "COMMAND"

    # Running under `twistd`: the Twisted legacy logging system will be later
    # initialised by `twistd`, and both stdio and warnings will be redirected
    # to the log.
    TWISTD = "TWISTD"

    @classmethod
    def guess(cls):
        stdios = sys.stdin, sys.stdout, sys.stderr
        if any(fd.isatty() for fd in stdios):
            return cls.COMMAND  # We're at the command-line.
        else:
            return cls.TWISTD  # We're probably in `twistd`.


def make_logging_level_names_consistent():
    """Rename the standard library's logging levels to match Twisted's.

    Twisted's new logging system in `twisted.logger` that is.
    """
    for level in list(logging._levelToName):
        if level == logging.NOTSET:
            # When the logging level is not known in Twisted it's rendered as
            # a hyphen. This is not a common occurrence with `logging` but we
            # cater for it anyway.
            name = "-"
        elif level == logging.WARNING:
            # "Warning" is more consistent with the other level names than
            # "warn", so there is a fault in Twisted here. However it's easier
            # to change the `logging` module to match Twisted than vice-versa.
            name = "warn"
        else:
            # Twisted's level names are all lower-case.
            name = logging.getLevelName(level).lower()
        # For a preexisting level this will _replace_ the name.
        logging.addLevelName(level, name)


@functools.lru_cache
def get_module_for_file(filename):
    """Try to find the module from its file.

    The module must already be loaded. If it's not found, `None` is returned.
    """
    for module_name, module in sys.modules.items():
        # Some modules, like `_imp`, do not have a `__file__` attribute.
        if getattr(module, "__file__", None) == filename:
            return module
    else:
        return None


def warn_unless(predicate, message):
    """Warn with `message` unless `predicate` is truthy.

    This mimics the output of the intended final logging configuration, but
    does so without using any existing logging system. It also prints to
    `sys.__stdout__` rather than `sys.stdout` which may have been wrapped or
    redirected. This makes it suitable for warning about failures when
    configuring logging itself.
    """
    if not predicate:
        message = DEFAULT_LOG_FORMAT % dict(
            name="global",
            levelname="warn",
            message=message,
        )
        print(message, file=sys.__stdout__, flush=True)


def is_dev_environment():
    """Is this the development environment, or production?

    Lazy import to avoid circular import issues.
    """
    from provisioningserver.config import is_dev_environment

    return is_dev_environment()
