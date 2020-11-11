# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing helpers for provisioningserver.utils."""


from fixtures import Fixture
from twisted.internet import defer

from provisioningserver.utils import env
from provisioningserver.utils.registry import _registry
from provisioningserver.utils.twisted import call, callOut


class RegistryFixture(Fixture):
    """Clears the global registry on entry, restores on exit."""

    def setUp(self):
        super().setUp()
        self.addCleanup(_registry.update, _registry.copy())
        self.addCleanup(_registry.clear)
        _registry.clear()


class MAASIDFixture(Fixture):
    """Populate the `maas_id` file."""

    def __init__(self, system_id):
        super().__init__()
        self.system_id = system_id

    def _setUp(self):
        super()._setUp()
        self.addCleanup(env.set_maas_id, env.get_maas_id())
        env.set_maas_id(self.system_id)


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
