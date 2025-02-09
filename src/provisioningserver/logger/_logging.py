# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Standard-library `logging`-specific stuff."""

import logging
import logging.config
import logging.handlers
import os
import sys

from twisted import logger as twistedModern

from provisioningserver.logger._common import (
    DEFAULT_LOG_FORMAT,
    DEFAULT_LOG_VERBOSITY_LEVELS,
    is_dev_environment,
    LoggingMode,
)

# Map verbosity numbers to `logging` levels.
DEFAULT_LOGGING_VERBOSITY_LEVELS = {
    # verbosity: level
    0: logging.ERROR,
    1: logging.WARN,
    2: logging.INFO,
    3: logging.DEBUG,
}

# Belt-n-braces.
assert (
    DEFAULT_LOGGING_VERBOSITY_LEVELS.keys() == DEFAULT_LOG_VERBOSITY_LEVELS
), "Logging verbosity map does not match expectations."


def set_standard_verbosity(verbosity: int):
    """Reconfigure verbosity of the standard library's `logging` module."""
    logging.config.dictConfig(get_logging_config(verbosity))


def configure_standard_logging(verbosity: int, mode: LoggingMode):
    """Configure the standard library's `logging` module.

    Get `logging` working with options consistent with Twisted. NOTE CAREFULLY
    that `django.utils.log.DEFAULT_LOGGING` may have been applied (though only
    if installed and if configured in this environment). Those settings and
    the settings this function applies must be mentally combined to understand
    the resultant behaviour.

    :param verbosity: See `get_logging_level`.
    :param mode: The mode in which to configure logging. See `LoggingMode`.
    """
    set_standard_verbosity(verbosity)
    # Make sure that `logging` is not configured to capture warnings.
    logging.captureWarnings(False)
    # If a logger is ever configured `propagate=False` but without handlers
    # `logging.Logger.callHandlers` will employ the `lastResort` handler in
    # order that the log is not lost. This goes to standard error by default.
    # Here we arrange for these situations to be logged more distinctively so
    # that they're easier to diagnose.
    logging.lastResort = logging.StreamHandler(
        twistedModern.LoggingFile(
            logger=twistedModern.Logger("lost+found"),
            level=twistedModern.LogLevel.error,
        )
    )


def get_syslog_address_path() -> str:
    """Return the path to the syslog unix socket."""
    path = os.getenv("MAAS_SYSLOG_CONFIG_DIR", "/var/lib/maas")
    if isinstance(path, bytes):
        fsenc = sys.getfilesystemencoding()
        path = path.decode(fsenc)
    return os.sep.join([path, "rsyslog", "log.sock"])


def get_logging_config(verbosity: int):
    """Return a configuration dict usable with `logging.config.dictConfig`.

    :param verbosity: See `get_logging_level`.
    """
    # Customise loggers and such depending on the environment.
    is_dev = is_dev_environment()
    # Build the configuration suitable for `dictConfig`.
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "stdout": {
                "format": DEFAULT_LOG_FORMAT,
                "datefmt": "",  # To prevent using the default format
            },
            "syslog": {"format": "%(name)s: [%(levelname)s] %(message)s"},
        },
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "stream": sys.__stdout__,
                "formatter": "stdout",
            },
            "syslog": {
                "class": "provisioningserver.logger.MAASSysLogHandler",
                "facility": logging.handlers.SysLogHandler.LOG_DAEMON,
                "address": get_syslog_address_path(),
                "formatter": "syslog",
            },
        },
        "root": {
            "level": get_logging_level(verbosity),
            "handlers": ["stdout"],
        },
        "loggers": {
            # The `maas` logger is used to provide a "nice to read" log of
            # MAAS's toing and froings. It logs to syslog and syslog only in
            # production. In development environments it propagates only to
            # the root logger and does not go to syslog.
            "maas": {
                "level": get_logging_level(verbosity),
                "handlers": [] if is_dev else ["syslog"],
                "propagate": is_dev,
            },
            # The `requests` and `urllib3` modules talk too much.
            "requests": {"level": get_logging_level(verbosity - 1)},
            "urllib3": {"level": get_logging_level(verbosity - 1)},
            # Keep `nose` relatively quiet in tests.
            "nose": {"level": get_logging_level(verbosity - 1)},
        },
    }


def get_logging_level(verbosity: int) -> int:
    """Return the `logging` level corresponding to `verbosity`.

    The level returned should be treated as *inclusive*. For example
    `logging.INFO` means that informational messages ought to be logged as
    well as messages of a higher level.

    :param verbosity: 0, 1, 2, or 3, meaning very quiet logging, quiet
        logging, normal logging, and verbose/debug logging.
    """
    levels = DEFAULT_LOGGING_VERBOSITY_LEVELS
    v_min, v_max = min(levels), max(levels)
    if verbosity > v_max:
        return levels[v_max]
    elif verbosity < v_min:
        return levels[v_min]
    else:
        return levels[verbosity]
