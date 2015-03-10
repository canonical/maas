# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.config`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.config import RegionConfiguration
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase


class TestRegionConfiguration(MAASTestCase):
    """Tests for `RegionConfiguration`."""

    def test_default_maas_url(self):
        config = RegionConfiguration({})
        self.assertEqual("http://localhost:5240/MAAS", config.maas_url)

    def test_set_and_get_maas_url(self):
        config = RegionConfiguration({})
        example_url = factory.make_simple_http_url()
        config.maas_url = example_url
        self.assertEqual(example_url, config.maas_url)
        # It's also stored in the configuration database.
        self.assertEqual({"maas_url": example_url}, config.configdb)


class TestRegionConfigurationDatabaseOptions(MAASTestCase):
    """Tests for the database options in `RegionConfiguration`."""

    options_and_defaults = {
        "database_host": "localhost",
        "database_name": "maasdb",
        "database_user": "maas",
        "database_pass": "",
    }

    scenarios = tuple(
        (name, {"option": name, "default": default})
        for name, default in options_and_defaults.viewitems()
    )

    def test__default(self):
        config = RegionConfiguration({})
        self.assertEqual(self.default, getattr(config, self.option))

    def test__set_and_get(self):
        config = RegionConfiguration({})
        example_value = factory.make_name(self.option)
        setattr(config, self.option, example_value)
        self.assertEqual(example_value, getattr(config, self.option))
        # It's also stored in the configuration database.
        self.assertEqual({self.option: example_value}, config.configdb)
