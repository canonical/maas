# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""TFTP-specific logging stuff."""

from twisted.logger import globalLogPublisher, LogLevel

from provisioningserver.logger._common import LoggingMode
from provisioningserver.logger._twisted import LegacyLogger


def configure_tftp_logging(verbosity: int, mode: LoggingMode):
    """Configure logging in `python-tx-tftp`.

    This is done by monkey-patching `LegacyLogger`s into three of its modules.
    Each of these is connected to a custom observer, `observe_tftp`, that has
    an opportunity to filter or modify log events before passing them on to
    the global log publisher.

    :param verbosity: See `get_logging_level`.
    :param mode: The mode in which to configure logging. See `LoggingMode`.
    """
    try:
        from tftp import bootstrap, protocol, session
    except ImportError:
        # python-tx-tftp not installed; nothing to be done.
        return

    for module in (bootstrap, protocol, session):
        LegacyLogger.install(module, observer=observe_tftp)


def observe_tftp(event, forwardTo=globalLogPublisher):
    if "log_level" in event and event["log_level"] is LogLevel.info:
        # Informational messages emitted by `python-tx-tftp` are, in the
        # context of MAAS, debug level at most.
        event["log_level"] = LogLevel.debug
    forwardTo(event)
