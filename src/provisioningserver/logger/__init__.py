# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
"""Logging in MAAS: region, rack, and at the command-line.

Logging is complex:

- The standard library has a `logging` module that needs to be configured. It
  can be complex and needs an significant time investment to fully understand.
  The `logging.basicConfig` helper can be used to get going, but third-party
  libraries often have very different ideas of what an informational message
  is (they often overestimate their own importance and emit as informational
  what someone else would at best consider a debug message) so levels must be
  adjusted; it's not enough to just `basicConfig()` and go.

- Twisted has a "legacy" logging system in `twisted.python.log`. This is still
  widely used in Twisted (16.0) and is the primary logging mechanism used by
  `twistd`. It has no concept of logging beyond "message" and "error".

- Twisted has a new logging system in `twisted.logger`. This is richer than
  the legacy logging system, less complex than `logging`, and emphasises that
  logs are not merely lines of text, but are structured events.

- Parts of the legacy Twisted logging system has been reimplemented to use the
  modern system. It works but the wiring can be confusing.

- The standard library has a `warnings` module. It invites users to replace
  its `showwarning` function in order to change where warnings are reported,
  and the standard library's `logging` module can be asked to do just that,
  something that Django does. But Twisted also replaces `showwarning` when
  logging is initialised. The winner is the one that goes last, meaning it's
  important to initialise parts of the application in a stable order.

- `warnings` tests each warning against a list of filters. This is populated
  by two functions — `filterwarnings` and `simplefilter` — as well as by `-W`
  options given at the command-line. The winner is the last to add a filter,
  so the order of initialisation of the application is again a concern.

- Django configures both `logging` and `warnings` during initialisation. In
  MAAS, Django often gets initialised late in the start-up process. It can end
  up winning the configuration race — by coming last — unless steps are taken
  to prevent it.

- Log levels and log level names between Twisted and `logging` are not
  consistent, and need normalising in order to produce a consistent log when
  both systems are in use.

This module attempts to address *all* of these issues!

"""

__all__ = [
    "configure",
    "EventLogger",
    "get_maas_logger",
    "LegacyLogger",
    "LoggingMode",
    "MAASSysLogHandler",
    "set_verbosity",
    "VerbosityOptions",
]

from provisioningserver.logger._common import (
    DEFAULT_LOG_VERBOSITY,
    LoggingMode,
    make_logging_level_names_consistent,
)
from provisioningserver.logger._django import configure_django_logging
from provisioningserver.logger._logging import (
    configure_standard_logging,
    set_standard_verbosity,
)
from provisioningserver.logger._maaslog import (
    get_maas_logger,
    MAASSysLogHandler,
)
from provisioningserver.logger._tftp import configure_tftp_logging
from provisioningserver.logger._twisted import (
    configure_twisted_logging,
    EventLogger,
    LegacyLogger,
    set_twisted_verbosity,
    VerbosityOptions,
)

# Current verbosity level. Configured initial in `configure()` call.
# Can be set afterward at runtime with `set_verbosity()`.
# Default verbosity is kind of noisy, so we may want to revisit this.
current_verbosity = DEFAULT_LOG_VERBOSITY


def configure(verbosity: int = None, mode: LoggingMode = None):
    """Configure logging for both Twisted and Python.

    This is safe to call from within `twistd`, in a plain Python environment,
    and before setting-up Django or after. It will try to do the right thing
    in each instance, and also takes into consideration whether it it being
    called by a program running at an interactive terminal.

    Note that nothing is done to address time-zones. Both Twisted and Python's
    ``logging`` use local time by default.

    If the verbosity is not specified, it will be set to the default verbosity
    level.

    It is not necessary to call `set_verbosity()` after calling this function,
    unless the specified verbosity needs to be changed.

    :param verbosity: See `get_logging_level`.
    :param mode: The mode in which to configure logging. If not provided this
        will be guessed at. See `LoggingMode`.
    """
    global current_verbosity
    if verbosity is None:
        verbosity = DEFAULT_LOG_VERBOSITY
    current_verbosity = verbosity
    # Automatically detect if we're at a stdio if not explicitly told.
    if mode is None:
        mode = LoggingMode.guess()
    # Fix-up the logging level names in the standard library. This is done
    # first to ensure they're consistent in most/all situations.
    make_logging_level_names_consistent()
    # Now call each configurator in order.
    for configurator in configurators:
        configurator(verbosity, mode)


configurators = [
    configure_twisted_logging,
    configure_django_logging,
    configure_standard_logging,
    configure_tftp_logging,
]


def set_verbosity(verbosity: int = None):
    """Resets the logging verbosity to the specified level.

    This function is intended to be be called after `configure()` is called.

    If the verbosity is not specified, it will be set to the default verbosity
    level.

    :param verbosity: See `get_logging_level`.
    """
    global current_verbosity
    if verbosity is None:
        verbosity = DEFAULT_LOG_VERBOSITY
    current_verbosity = verbosity
    for verbosity_setter in verbosity_setters:
        verbosity_setter(verbosity)


verbosity_setters = [set_standard_verbosity, set_twisted_verbosity]
