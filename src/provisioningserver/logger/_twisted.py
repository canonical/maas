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
