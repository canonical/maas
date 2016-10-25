# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted-specific logging stuff."""

__all__ = [
    'LegacyLogObserverWrapper',
]

from twisted import logger
from twisted.python import log


class LegacyLogObserverWrapper(logger.LegacyLogObserverWrapper):
    """Ensure that `log_system` is set in the event.

    This mimics what `twisted.logger.formatEventAsClassicLogText` does when
    `log_system` is not set, and constructs it from `log_namespace` and
    `log_level`.

    This `log_system` value is then seen by `LegacyLogObserverWrapper` and
    copied into the `system` key and then printed out in the logs by Twisted's
    legacy logging (`t.python.log`) machinery. This still used by `twistd`, so
    the net effect is that the logger's namespace and level are printed to the
    `twistd` log.
    """

    @classmethod
    def install(cls):
        """Install this wrapper in place of `log.LegacyLogObserverWrapper`.

        Inject this wrapper into the `t.python.log` module then remove and
        re-add all the legacy observers so that they're re-wrapped.
        """
        log.LegacyLogObserverWrapper = cls
        for observer in log.theLogPublisher.observers:
            log.theLogPublisher.removeObserver(observer)
            log.theLogPublisher.addObserver(observer)

    def __call__(self, event):
        # Be defensive: `system` could be missing or could have a value of
        # None. Same goes for `log_system`, `log_namespace`, and `log_level`.
        if event.get("system") is None and event.get("log_system") is None:
            namespace = event.get("log_namespace")
            level = event.get("log_level")
            event["log_system"] = "{namespace}#{level}".format(
                namespace=("-" if namespace is None else namespace),
                level=("-" if level is None else level.name))
        # Up-call, which will apply some more transformations.
        return super().__call__(event)


class LegacyLogger:
    """Looks like a stripped-down `t.p.log` module, logs to a `Logger`.

    Use this with code that cannot easily be changed to use `twisted.logger`
    but over which we want a greater degree of control.
    """

    def __init__(self, logger: logger.Logger):
        super(LegacyLogger, self).__init__()
        self.logger = logger

    def msg(self, *message, **kwargs):
        """Write a message to the log.

        See `twisted.python.log.msg`. This allows multiple messages to be
        supplied but says that this "only works (sometimes) by accident". Here
        we make sure it works all the time on purpose.
        """
        fmt = " ".join("{_message_%d}" % i for i, _ in enumerate(message))
        kwargs.update({"_message_%d" % i: m for i, m in enumerate(message)})
        self.logger.info(fmt, **kwargs)

    def err(self, _stuff=None, _why=None, **kwargs):
        """Write a failure to the log.

        See `twisted.python.log.err`.
        """
        self.logger.failure("{_why}", _stuff, _why=_why, **kwargs)
