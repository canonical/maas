# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Fixtures for working with local configuration in the region."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'RegionConfigurationFixture',
    ]

from maasserver.config import RegionConfiguration
from provisioningserver.testing.config import ConfigurationFixtureBase


class RegionConfigurationFixture(ConfigurationFixtureBase):
    """Fixture to configure local region settings in tests."""

    configuration = RegionConfiguration
