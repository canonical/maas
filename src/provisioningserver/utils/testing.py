# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing helpers for provisioningserver.utils."""

__all__ = [
    "RegistryFixture",
]

from fixtures import Fixture
from provisioningserver.utils.registry import _registry


class RegistryFixture(Fixture):
    """Clears the global registry on entry, restores on exit."""

    def setUp(self):
        super(RegistryFixture, self).setUp()
        self.addCleanup(_registry.update, _registry.copy())
        self.addCleanup(_registry.clear)
        _registry.clear()
