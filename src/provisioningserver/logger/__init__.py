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
    "get_maas_logger",
    "LoggingMode",
    "VerbosityOptions",
]

import enum
import functools
import logging
import logging.config
import logging.handlers
import sys
import time
import warnings

import crochet
from provisioningserver.config import is_dev_environment
from provisioningserver.logger._twisted import LegacyLogObserverWrapper
from provisioningserver.logger.log import get_maas_logger
from provisioningserver.utils import typed
from twisted import logger as twistedModern
from twisted.python import log as twistedLegacy
import twisted.python.usage

# This format roughly matches Twisted's default, so that combined Twisted and
# Django logs are consistent with one another.
DEFAULT_LOG_FORMAT = "%(asctime)s [%(name)s#%(levelname)s] %(message)s"
DEFAULT_LOG_FORMAT_DATE = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOG_VERBOSITY = 2

# Map verbosity numbers to `logging` levels.
DEFAULT_LOGGING_VERBOSITY_LEVELS = {
    # verbosity: level
    0: logging.ERROR,
    1: logging.WARN,
    2: logging.INFO,
    3: logging.DEBUG,
}

# Map verbosity numbers to `twisted.logger` levels.
DEFAULT_TWISTED_VERBOSITY_LEVELS = {
    # verbosity: level
    0: twistedModern.LogLevel.error,
    1: twistedModern.LogLevel.warn,
    2: twistedModern.LogLevel.info,
    3: twistedModern.LogLevel.debug,
}

# Belt-n-braces.
assert (
    DEFAULT_LOGGING_VERBOSITY_LEVELS.keys() ==
    DEFAULT_TWISTED_VERBOSITY_LEVELS.keys()
), "Verbosity maps are inconsistent."


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


@typed
def configure(verbosity: int=None, mode: LoggingMode=None):
    """Configure logging for both Twisted and Python.

    This is safe to call from within `twistd`, in a plain Python environment,
    and before setting-up Django or after. It will try to do the right thing
    in each instance, and also takes into consideration whether it it being
    called by a program running at an interactive terminal.

    Note that nothing is done to address time-zones. Both Twisted and Python's
    ``logging`` use local time by default.

    :param verbosity: See `get_logging_level`.
    :param mode: The mode in which to configure logging. If not provided this
        will be guessed at. See `LoggingMode`.
    """
    # Default verbosity is kind of noisy so we may want to revisit this.
    if verbosity is None:
        verbosity = DEFAULT_LOG_VERBOSITY
    # Automatically detect if we're at a stdio if not explicitly told.
    if mode is None:
        mode = LoggingMode.guess()
    # Fix-up the logging level names in the standard library. This is done
    # first to ensure they're consistent in most/all situations.
    make_logging_level_names_consistent()
    # Configure Twisted's logging systems.
    configure_twisted_logging(verbosity, mode)
    # Configure Django's logging machinery.
    configure_django_logging(verbosity, mode)
    # Get Python logging working with options consistent with Twisted.
    # NOTE CAREFULLY that `django.utils.log.DEFAULT_LOGGING` may have been
    # applied (if installed, if configured in this environment). Those
    # settings and the settings about to be applied must be mentally
    # combined to understand the resultant behaviour.
    configure_standard_logging(verbosity, mode)


@typed
def configure_twisted_logging(verbosity: int, mode: LoggingMode):
    """Configure Twisted's legacy logging system.

    We do this because it's what `twistd` uses. When we switch to `twist` we
    can update this.

    :param verbosity: See `get_logging_level`.
    :param mode: The mode in which to configure logging. See `LoggingMode`.
    """
    # Convert `verbosity` into a Twisted `LogLevel`.
    level = get_twisted_logging_level(verbosity)
    # `LogLevel` is comparable, but this saves overall computation.
    levels = {
        ll for ll in twistedModern.LogLevel.iterconstants()
        if ll >= level
    }

    def filterByLevel(event, levels=levels):
        """Only log if event's level is in `levels`."""
        if event.get("log_level") in levels:
            return twistedModern.PredicateResult.maybe
        else:
            return twistedModern.PredicateResult.no

    # A list of markers for noise.
    noisy = (
        {"log_system": "-", "log_text": "Log opened."},
        {"log_system": "-", "log_text": "Main loop terminated."},
    )

    def filterByNoise(event, noisy=noisy):
        """Only log if event is not noisy."""
        for noise in noisy:
            if all(key in event and event[key] == noise[key] for key in noise):
                return twistedModern.PredicateResult.no
        else:
            return twistedModern.PredicateResult.maybe

    predicates = filterByLevel, filterByNoise

    # When `twistd` starts the reactor it initialises the legacy logging
    # system. Intercept this to wrap the observer in a level filter. We can
    # use this same approach when not running under `twistd` too.
    def startLoggingWithObserver(observer, setStdout=1):
        observer = twistedModern.FilteringLogObserver(observer, predicates)
        reallyStartLoggingWithObserver(observer, setStdout)

    reallyStartLoggingWithObserver = twistedLegacy.startLoggingWithObserver
    twistedLegacy.startLoggingWithObserver = startLoggingWithObserver

    # Customise warnings behaviour. Ensure that nothing else — neither the
    # standard library's `logging` module nor Django — clobbers this later.
    warn_unless(warnings.showwarning.__module__ == warnings.__name__, (
        "The warnings module has already been modified; please investigate!"))
    if mode == LoggingMode.TWISTD:
        twistedModern.globalLogBeginner.showwarning = show_warning_via_twisted
        twistedLegacy.theLogPublisher.showwarning = show_warning_via_twisted
    else:
        twistedModern.globalLogBeginner.showwarning = warnings.showwarning
        twistedLegacy.theLogPublisher.showwarning = warnings.showwarning

    # Globally override Twisted's log date format. It's tricky to get to the
    # FileLogObserver that twistd installs so that we can modify its config
    # alone, but we actually do want to make a global change anyway.
    warn_unless(hasattr(twistedLegacy.FileLogObserver, "timeFormat"), (
        "No FileLogObserver.timeFormat attribute found; please investigate!"))
    twistedLegacy.FileLogObserver.timeFormat = DEFAULT_LOG_FORMAT_DATE

    # Install a wrapper so that log events from `t.logger` are logged with a
    # namespace and level by the legacy logger in `t.python.log`. This needs
    # to be injected into the `t.p.log` module in order to process events as
    # they move from the legacy to the modern systems.
    LegacyLogObserverWrapper.install()

    # Prevent `crochet` from initialising Twisted's logging.
    warn_unless(hasattr(crochet._main, "_startLoggingWithObserver"), (
        "No _startLoggingWithObserver function found; please investigate!"))
    crochet._main._startLoggingWithObserver = None

    # Turn off some inadvisable defaults in Twisted and elsewhere.
    from twisted.internet.protocol import AbstractDatagramProtocol, Factory
    warn_unless(hasattr(AbstractDatagramProtocol, "noisy"), (
        "No AbstractDatagramProtocol.noisy attribute; please investigate!"))
    AbstractDatagramProtocol.noisy = False
    warn_unless(hasattr(Factory, "noisy"), (
        "No Factory.noisy attribute; please investigate!"))
    Factory.noisy = False

    # Start Twisted logging if we're running a command. Use `sys.__stdout__`,
    # the original standard out stream when this process was started. This
    # bypasses any wrapping or redirection that may have been done elsewhere.
    if mode == LoggingMode.COMMAND:
        twisted.python.log.startLogging(sys.__stdout__, setStdout=False)


@typed
def configure_django_logging(verbosity: int, mode: LoggingMode):
    """Do basic logging configuration for Django, if possible.

    Then destroy Django's ability to mess with logging configuration. We have
    to do this by monkey-patching because changing Django's settings at
    run-time is not supported. If Django is not installed this is a no-op.

    :param verbosity: See `get_logging_level`.
    :param mode: The mode in which to configure logging. See `LoggingMode`.
    """
    try:
        from django.utils import log
    except ImportError:
        # Django not installed; nothing to be done.
        return

    # Django's default logging configuration is not great. For example it
    # wants to email request errors and security issues to the site admins,
    # but fails silently. Throw it all away.
    warn_unless(hasattr(log, "DEFAULT_LOGGING"), (
        "No DEFAULT_LOGGING attribute found in Django; please investigate!"))
    log.DEFAULT_LOGGING = {'version': 1, 'disable_existing_loggers': False}

    # Prevent Django from meddling with `warnings`. There's no configuration
    # option for this so we have to get invasive. We also skip running-in
    # Django's default log configuration even though we threw it away already.
    def configure_logging(logging_config, logging_settings):
        """Reduced variant of Django's configure_logging."""
        if logging_config is not None:
            logging_config_func = log.import_string(logging_config)
            logging_config_func(logging_settings)

    warn_unless(hasattr(log, "configure_logging"), (
        "No configure_logging function found in Django; please investigate!"))
    log.configure_logging = configure_logging

    # Outside of the development environment ensure that deprecation warnings
    # from Django are silenced. End users are _not_ interested in deprecation
    # warnings from Django. Developers are, however.
    if not is_dev_environment():
        from django.utils.deprecation import RemovedInNextVersionWarning
        warnings.simplefilter("ignore", RemovedInNextVersionWarning)


@typed
def configure_standard_logging(verbosity: int, mode: LoggingMode):
    """Configure the standard library's `logging` module.

    :param verbosity: See `get_logging_level`.
    :param mode: The mode in which to configure logging. See `LoggingMode`.
    """
    logging.config.dictConfig(get_logging_config(verbosity))
    # Make sure that `logging` is not configured to capture warnings.
    logging.captureWarnings(False)
    # If a logger is ever configured `propagate=False` but without handlers
    # `logging.Logger.callHandlers` will employ the `lastResort` handler in
    # order that the log is not lost. This goes to standard error by default.
    # Here we arrange for these situations to be logged more distinctively so
    # that they're easier to diagnose.
    logging.lastResort = (
        logging.StreamHandler(
            twistedModern.LoggingFile(
                logger=twistedModern.Logger("lost+found"),
                level=twistedModern.LogLevel.error)))


@typed
def get_logging_config(verbosity: int):
    """Return a configuration dict usable with `logging.config.dictConfig`.

    :param verbosity: See `get_logging_level`.
    """
    # Customise loggers and such depending on the environment.
    is_dev = is_dev_environment()
    # Build the configuration suitable for `dictConfig`.
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'stdout': {
                'format': DEFAULT_LOG_FORMAT,
                'datefmt': DEFAULT_LOG_FORMAT_DATE,
            },
            'syslog': {
                'format': '%(name)s: [%(levelname)s] %(message)s',
            },
        },
        'handlers': {
            'stdout': {
                'class': 'logging.StreamHandler',
                'stream': sys.__stdout__,
                'formatter': 'stdout',
            },
            'syslog': {
                'class': 'logging.handlers.SysLogHandler',
                'facility': logging.handlers.SysLogHandler.LOG_DAEMON,
                'address': '/dev/log',
                'formatter': 'syslog',
            },
        },
        'root': {
            'level': get_logging_level(verbosity),
            'handlers': ['stdout'],
        },
        'loggers': {
            # The `maas` logger is used to provide a "nice to read" log of
            # MAAS's toing and froings. It logs to syslog and syslog only in
            # production. In development environments it propagates only to
            # the root logger and does not go to syslog.
            'maas': {
                'level': get_logging_level(verbosity),
                'handlers': [] if is_dev else ['syslog'],
                'propagate': is_dev,
            },
            # The `requests` and `urllib3` modules talk too much.
            'requests': {
                'level': get_logging_level(verbosity - 1),
            },
            'urllib3': {
                'level': get_logging_level(verbosity - 1),
            },
            # Keep `nose` relatively quiet in tests.
            'nose': {
                'level': get_logging_level(verbosity - 1),
            },
        },
    }


@typed
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


@typed
def get_twisted_logging_level(verbosity: int):  # -> LogLevel
    """Return the Twisted logging level corresponding to `verbosity`.

    The level returned should be treated as *inclusive*. For example
    `LogLevel.info` means that informational messages ought to be logged as
    well as messages of a higher level.

    :param verbosity: 0, 1, 2, or 3, meaning very quiet logging, quiet
        logging, normal logging, and verbose/debug logging.
    """
    levels = DEFAULT_TWISTED_VERBOSITY_LEVELS
    v_min, v_max = min(levels), max(levels)
    if verbosity > v_max:
        return levels[v_max]
    elif verbosity < v_min:
        return levels[v_min]
    else:
        return levels[verbosity]


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


def show_warning_via_twisted(
        message, category, filename, lineno, file=None, line=None):
    """Replacement for `warnings.showwarning` that logs via Twisted."""
    if file is None:
        # Try to find a module name with which to log this warning.
        module = get_module_for_file(filename)
        logger = twistedModern.Logger(
            "global" if module is None else module.__name__)
        # `message` is/can be an instance of `category`, so stringify.
        logger.warn(
            "{category}: {message}", message=str(message),
            category=category.__qualname__, filename=filename,
            lineno=lineno, line=line)
    else:
        # It's not clear why and when `file` will be specified, but try to
        # honour the intention.
        warning = warnings.formatwarning(
            message, category, filename, lineno, line)
        try:
            file.write(warning)
            file.flush()
        except OSError:
            pass  # We tried.


@functools.lru_cache()
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


class VerbosityOptions(twisted.python.usage.Options):
    """Command-line logging verbosity options."""

    _verbosity_max = max(DEFAULT_TWISTED_VERBOSITY_LEVELS)
    _verbosity_min = min(DEFAULT_TWISTED_VERBOSITY_LEVELS)

    def __init__(self):
        super(VerbosityOptions, self).__init__()
        self["verbosity"] = DEFAULT_LOG_VERBOSITY
        self.longOpt.sort()  # https://twistedmatrix.com/trac/ticket/8866

    def opt_verbose(self):
        """Increase logging verbosity."""
        self["verbosity"] = min(
            self._verbosity_max, self["verbosity"] + 1)

    opt_v = opt_verbose

    def opt_quiet(self):
        """Decrease logging verbosity."""
        self["verbosity"] = max(
            self._verbosity_min, self["verbosity"] - 1)

    opt_q = opt_quiet


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
            asctime=time.strftime(DEFAULT_LOG_FORMAT_DATE, time.localtime()),
            name="global", levelname="warn", message=message)
        print(message, file=sys.__stdout__, flush=True)
