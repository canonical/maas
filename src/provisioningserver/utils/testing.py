# Copyright 2014-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pathlib import Path

from fixtures import Fixture, TempDir
from twisted.internet import defer

from maascommon.utils.registry import _registry
from provisioningserver.utils.env import MAAS_ID, MAAS_UUID
from provisioningserver.utils.twisted import call, callOut


class RegistryFixture(Fixture):
    """Clears the global registry on entry, restores on exit."""

    def setUp(self):
        super().setUp()
        self.addCleanup(_registry.update, _registry.copy())
        self.addCleanup(_registry.clear)
        _registry.clear()


class MAASFileBackedValueFixture(Fixture):
    FILE_BACKED_VALUE = None

    def __init__(self, value):
        super().__init__()
        self.value = value

    def _setUp(self):
        super()._setUp()
        orig_path = self.FILE_BACKED_VALUE._path
        self.FILE_BACKED_VALUE._path = lambda: (
            Path(self.useFixture(TempDir()).path) / self.FILE_BACKED_VALUE.name
        )
        self.addCleanup(
            self.FILE_BACKED_VALUE.set, self.FILE_BACKED_VALUE.get()
        )
        self.addCleanup(setattr, self.FILE_BACKED_VALUE, "_path", orig_path)
        self.FILE_BACKED_VALUE.set(self.value)


class MAASIDFixture(MAASFileBackedValueFixture):
    """Populate the `maas_id` file."""

    FILE_BACKED_VALUE = MAAS_ID


class MAASUUIDFixture(MAASFileBackedValueFixture):
    """Populate the `maas_uuid` file."""

    FILE_BACKED_VALUE = MAAS_UUID


def callWithServiceRunning(service, f, *args, **kwargs):
    """Call `f` with `service` running.

    The given service is a Twisted service. It is started, the given function
    called with the given arguments, then the service is stopped.

    Returns a `Deferred`, firing with the result of the call to `f`.
    """
    d = defer.maybeDeferred(service.startService)
    d.addCallback(call, f, *args, **kwargs)
    d.addBoth(callOut, service.stopService)
    return d
