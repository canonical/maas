# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing helpers for provisioningserver.utils."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
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
