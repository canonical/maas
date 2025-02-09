# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted-specific logging stuff."""

import os
import re
import sys
import warnings

import crochet
from twisted import logger as twistedModern
from twisted.python import log as twistedLegacy
from twisted.python import usage

from provisioningserver.logger._common import (
    DEFAULT_LOG_FORMAT,
    DEFAULT_LOG_VERBOSITY,
    DEFAULT_LOG_VERBOSITY_LEVELS,
    get_module_for_file,
    LoggingMode,
    warn_unless,
)

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
    DEFAULT_TWISTED_VERBOSITY_LEVELS.keys() == DEFAULT_LOG_VERBOSITY_LEVELS
), "Twisted verbosity map does not match expectations."


def set_twisted_verbosity(verbosity: int):
    """Reconfigure verbosity of the standard library's `logging` module."""
    # Convert `verbosity` into a Twisted `LogLevel`.
    level = get_twisted_logging_level(verbosity)
    # `LogLevel` is comparable, but this saves overall computation.
    global _filterByLevels
    _filterByLevels = {
        ll for ll in twistedModern.LogLevel.iterconstants() if ll >= level
    }


def configure_twisted_logging(verbosity: int, mode: LoggingMode):
    """Configure Twisted's legacy logging system.

    We do this because it's what `twistd` uses. When we switch to `twist` we
    can update this.

    :param verbosity: See `get_logging_level`.
    :param mode: The mode in which to configure logging. See `LoggingMode`.
    """
    set_twisted_verbosity(verbosity)

    warn_unless(
        hasattr(twistedLegacy, "startLoggingWithObserver"),
        "No startLoggingWithObserver function found; please investigate!",
    )
    twistedLegacy.startLoggingWithObserver = _startLoggingWithObserver

    # Set the legacy `logfile` namespace according to the environment in which
    # we guess we're running. This `logfile` is used primarily — in MAAS — by
    # Twisted's HTTP server machinery for combined access logging.
    twistedLegacy.logfile.log.namespace = _getCommandName(sys.argv)

    # Customise warnings behaviour. Ensure that nothing else — neither the
    # standard library's `logging` module nor Django — clobbers this later.
    warn_unless(
        warnings.showwarning.__module__ == warnings.__name__,
        "The warnings module has already been modified; please investigate!",
    )
    if mode == LoggingMode.TWISTD:
        twistedModern.globalLogBeginner.showwarning = show_warning_via_twisted
        twistedLegacy.theLogPublisher.showwarning = show_warning_via_twisted
    else:
        twistedModern.globalLogBeginner.showwarning = warnings.showwarning
        twistedLegacy.theLogPublisher.showwarning = warnings.showwarning

    # Prevent `crochet` from initialising Twisted's logging.
    warn_unless(
        hasattr(crochet._main, "_startLoggingWithObserver"),
        "No _startLoggingWithObserver function found; please investigate!",
    )
    crochet._main._startLoggingWithObserver = None

    # Turn off some inadvisable defaults in Twisted and elsewhere.
    from twisted.internet.protocol import AbstractDatagramProtocol, Factory

    warn_unless(
        hasattr(AbstractDatagramProtocol, "noisy"),
        "No AbstractDatagramProtocol.noisy attribute; please investigate!",
    )
    AbstractDatagramProtocol.noisy = False
    warn_unless(
        hasattr(Factory, "noisy"),
        "No Factory.noisy attribute; please investigate!",
    )
    Factory.noisy = False

    # Install filters for other noisy parts of Twisted itself.
    from twisted.internet import tcp, udp, unix

    LegacyLogger.install(tcp, observer=observe_twisted_internet_tcp)
    LegacyLogger.install(udp, observer=observe_twisted_internet_udp)
    LegacyLogger.install(unix, observer=observe_twisted_internet_unix)

    # Start Twisted logging if we're running a command. Use `sys.__stdout__`,
    # the original standard out stream when this process was started. This
    # bypasses any wrapping or redirection that may have been done elsewhere.
    if mode == LoggingMode.COMMAND:
        twistedModern.globalLogBeginner.beginLoggingTo(
            [EventLogger()], discardBuffer=False, redirectStandardIO=False
        )


def EventLogger(outFile=sys.__stdout__):
    """Factory returning a `t.logger.ILogObserver`.

    This logs to the real standard out using MAAS's logging conventions.

    Refer to this with `twistd`'s `--logger` argument.
    """
    return twistedModern.FilteringLogObserver(
        twistedModern.FileLogObserver(outFile, _formatModernEvent),
        (_filterByLevel, _filterByNoise),
    )


def _startLoggingWithObserver(observer, setStdout=1):
    """Replacement for `t.p.log.startLoggingWithObserver`.

    When `twistd` starts in 16.0 it initialises the legacy logging system.
    Intercept this to DTRT with either a modern or legacy observer.

    In Xenial (with Twisted 16.0) `observer` is probably a legacy observer,
    like twisted.python.log.FileLogObserver, but we should check if it's
    modern. In either case we should call through to the `globalLogBeginner`
    ourselves. In Yakkety (with Twisted 16.4) this function will not be
    called; `t.application.app.AppLogger` does the right thing already.
    """
    if not twistedModern.ILogObserver.providedBy(observer):
        observer = twistedModern.LegacyLogObserverWrapper(observer)
    twistedModern.globalLogBeginner.beginLoggingTo(
        [observer], discardBuffer=False, redirectStandardIO=bool(setStdout)
    )


_lineFormat = DEFAULT_LOG_FORMAT + "\n"


def _formatModernEvent(event):
    """Format a "modern" event according to MAAS's conventions."""
    text = twistedModern.formatEvent(event)
    if "log_failure" in event:
        try:
            traceback = event["log_failure"].getTraceback()
        except Exception:
            traceback = "(UNABLE TO OBTAIN TRACEBACK FROM EVENT)\n"
        text = "\n".join((text, traceback))
    level = event["log_level"] if "log_level" in event else None
    system = event["log_system"] if "log_system" in event else None
    if system is None and "log_namespace" in event:
        system = _getSystemName(event["log_namespace"])

    return _lineFormat % {
        "levelname": "-" if level is None else level.name,
        "message": "-" if text is None else text.replace("\n", "\n\t"),
        "name": "-" if system is None else system,
    }


def _getSystemName(system):
    """Return the "public" parts of `system`.

    `system` is a dot-separated name, e.g. a fully-qualified module name. This
    returns the leading parts of that name that are not pseudo-private, i.e.
    that start with an underscore. For example "a.b._c.d" would be transformed
    into "a.b".
    """
    if system is None or len(system) == 0 or system.startswith("_"):
        return None
    else:
        return system.split("._")[0]


def _getCommandName(argv):
    """Return a guess at the currently running command's name.

    When running under `twistd`, it will return "regiond", "rackd", or
    "daemon". The latter is unlikely to happen, but it's a safe default.

    Otherwise it assumes a command is being run and tries to derive a name
    from the script being run.
    """
    if any("twist" in arg for arg in argv):
        if any("maas-regiond" in arg for arg in argv):
            return "regiond"
        elif any("maas-rackd" in arg for arg in argv):
            return "rackd"
        else:
            # Return a safe default.
            return "daemon"
    else:
        candidates = map(os.path.basename, argv)
        try:
            command = next(candidates)
            if "python" in command:
                command = next(candidates)
        except StopIteration:
            # Return a safe default.
            return "command"
        else:
            if command.startswith("-"):
                # It's probably a command-line option.
                return "command"
            elif command.endswith(".py"):
                # Remove the .py suffix.
                return command[:-3]
            else:
                return command


class LegacyLogger(twistedModern.Logger):
    """Looks like a stripped-down `t.p.log` module, logs to a `Logger`.

    Use this with code that cannot easily be changed to use `twisted.logger`
    but over which we want a greater degree of control.
    """

    @classmethod
    def install(cls, module, attribute="log", *, source=None, observer=None):
        """Install a `LegacyLogger` at `module.attribute`.

        Warns if `module.attribute` does not exist, but carries on anyway.

        :param module: A module (or any other object with assignable
            attributes and a `__name__`).
        :param attribute: The name of the attribute on `module` to replace.
        :param source: See `Logger.__init__`.
        :param observer: See `Logger.__init__`.
        :return: The newly created `LegacyLogger`.
        """
        replacing = getattr(module, attribute, "<not-found>")
        warn_unless(
            replacing is twistedLegacy,
            (
                "Legacy logger being installed to replace %r but expected a "
                "reference to twisted.python.log module; please investigate!"
                % (replacing,)
            ),
        )
        logger = cls(module.__name__, source=source, observer=observer)
        setattr(module, attribute, logger)
        return logger

    def msg(self, *message, **kwargs):
        """Write a message to the log.

        See `twisted.python.log.msg`. This allows multiple messages to be
        supplied but says that this "only works (sometimes) by accident". Here
        we make sure it works all the time on purpose.
        """
        fmt = " ".join("{_message_%d}" % i for i, _ in enumerate(message))
        kwargs.update({"_message_%d" % i: m for i, m in enumerate(message)})
        self.info(fmt, **kwargs)

    def err(self, _stuff=None, _why=None, **kwargs):
        """Write a failure to the log.

        See `twisted.python.log.err`.
        """
        self.failure("{_why}", _stuff, _why=_why, **kwargs)


class VerbosityOptions(usage.Options):
    """Command-line logging verbosity options."""

    _verbosity_max = max(DEFAULT_TWISTED_VERBOSITY_LEVELS)
    _verbosity_min = min(DEFAULT_TWISTED_VERBOSITY_LEVELS)

    def __init__(self):
        super().__init__()
        self["verbosity"] = DEFAULT_LOG_VERBOSITY
        self.longOpt.sort()  # https://twistedmatrix.com/trac/ticket/8866

    def opt_verbose(self):
        """Increase logging verbosity."""
        self["verbosity"] = min(self._verbosity_max, self["verbosity"] + 1)

    opt_v = opt_verbose

    def opt_quiet(self):
        """Decrease logging verbosity."""
        self["verbosity"] = max(self._verbosity_min, self["verbosity"] - 1)

    opt_q = opt_quiet


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


def show_warning_via_twisted(
    message, category, filename, lineno, file=None, line=None
):
    """Replacement for `warnings.showwarning` that logs via Twisted."""
    if file is None:
        # Try to find a module name with which to log this warning.
        module = get_module_for_file(filename)
        logger = twistedModern.Logger(
            "global" if module is None else module.__name__
        )
        # `message` is/can be an instance of `category`, so stringify.
        logger.warn(
            "{category}: {message}",
            message=str(message),
            category=category.__qualname__,
            filename=filename,
            lineno=lineno,
            line=line,
        )
    else:
        # It's not clear why and when `file` will be specified, but try to
        # honour the intention.
        warning = warnings.formatwarning(
            message, category, filename, lineno, line
        )
        try:
            file.write(warning)
            file.flush()
        except OSError:
            pass  # We tried.


# Those levels for which we should emit log events.
_filterByLevels = frozenset()


def _filterByLevel(event):
    """Only log if event's level is in `_filterByLevels`."""
    if event.get("log_level") in _filterByLevels:
        return twistedModern.PredicateResult.maybe
    else:
        return twistedModern.PredicateResult.no


# A list of markers for noise.
_filterByNoises = (
    {"log_namespace": "log_legacy", "log_text": "Log opened."},
    {"log_namespace": "log_legacy", "log_text": "Main loop terminated."},
)


def _filterByNoise(event):
    """Only log if event is not noisy."""
    for noise in _filterByNoises:
        if all(key in event and event[key] == noise[key] for key in noise):
            return twistedModern.PredicateResult.no
    else:
        return twistedModern.PredicateResult.maybe


_observe_twisted_internet_tcp_noise = re.compile(
    r"^(?:[(].+ Port \d+ Closed[)]|.+ starting on \d+)"
)


def observe_twisted_internet_tcp(event):
    """Observe events from `twisted.internet.tcp` and filter out noise."""
    message = twistedModern.formatEvent(event)
    if _observe_twisted_internet_tcp_noise.match(message) is None:
        twistedModern.globalLogPublisher(event)


_observe_twisted_internet_udp_noise = re.compile(
    r"^(?:[(].+ Port \d+ Closed[)]|.+ starting on \d+)"
)


def observe_twisted_internet_udp(event):
    """Observe events from `twisted.internet.udp` and filter out noise."""
    message = twistedModern.formatEvent(event)
    if _observe_twisted_internet_udp_noise.match(message) is None:
        twistedModern.globalLogPublisher(event)


_observe_twisted_internet_unix_noise = re.compile(
    r"^(?:[(].+ Port .+ Closed[)]|.+ starting on .+)"
)


def observe_twisted_internet_unix(event):
    """Observe events from `twisted.internet.unix` and filter out noise."""
    message = twistedModern.formatEvent(event)
    if _observe_twisted_internet_unix_noise.match(message) is None:
        twistedModern.globalLogPublisher(event)
