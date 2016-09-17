# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""maasserver fixtures."""

__all__ = [
    "IntroCompletedFixture",
    "PackageRepositoryFixture",
]

import fixtures
from maasserver.models.config import Config
from maasserver.testing.factory import factory


class PackageRepositoryFixture(fixtures.Fixture):
    """Insert the base PackageRepository entries."""

    def _setUp(self):
        factory.make_default_PackageRepositories()


class IntroCompletedFixture(fixtures.Fixture):
    """Mark intro as completed as default."""

    def _setUp(self):
        Config.objects.set_config("completed_intro", True)
