# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing helpers for provisioningserver.utils."""

__all__ = [
    "MAASIDFixture",
    "RegistryFixture",
]

from fixtures import Fixture
from provisioningserver.utils import env
from provisioningserver.utils.registry import _registry


class RegistryFixture(Fixture):
    """Clears the global registry on entry, restores on exit."""

    def setUp(self):
        super(RegistryFixture, self).setUp()
        self.addCleanup(_registry.update, _registry.copy())
        self.addCleanup(_registry.clear)
        _registry.clear()


class MAASIDFixture(Fixture):
    """Populate the `maas_id` file."""

    def __init__(self, system_id):
        super(MAASIDFixture, self).__init__()
        self.system_id = system_id

    def _setUp(self):
        super(MAASIDFixture, self)._setUp()
        self.addCleanup(env.set_maas_id, env.get_maas_id())
        env.set_maas_id(self.system_id)
