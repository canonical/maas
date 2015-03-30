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

from fixtures import EnvironmentVariableFixture
from maasserver import config
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
        self.assertEqual({"maas_url": example_url}, config.store)

    def test_set_maas_url_accepts_hostnames(self):
        config = RegionConfiguration({})
        example_url = factory.make_simple_http_url(
            netloc="%s:%d" % (factory.make_hostname(), factory.pick_port()))
        config.maas_url = example_url
        self.assertEqual(example_url, config.maas_url)
        self.assertEqual({"maas_url": example_url}, config.store)

    def test_set_maas_url_accepts_very_short_hostnames(self):
        config = RegionConfiguration({})
        example_url = factory.make_simple_http_url(
            netloc=factory.make_string(size=1))
        config.maas_url = example_url
        self.assertEqual(example_url, config.maas_url)
        self.assertEqual({"maas_url": example_url}, config.store)

    def test_set_maas_url_accepts_ipv6_addresses(self):
        config = RegionConfiguration({})
        example_url = factory.make_simple_http_url(
            netloc=factory.make_ipv6_address())
        config.maas_url = example_url
        self.assertEqual(example_url, config.maas_url)
        self.assertEqual({"maas_url": example_url}, config.store)

    def test_set_maas_url_accepts_ipv6_addresses_with_brackets(self):
        config = RegionConfiguration({})
        example_url = factory.make_simple_http_url(
            netloc="[%s]" % factory.make_ipv6_address())
        config.maas_url = example_url
        self.assertEqual(example_url, config.maas_url)
        self.assertEqual({"maas_url": example_url}, config.store)


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
        self.assertEqual({self.option: example_value}, config.store)

"""Tests for the maasregiond configuration interface."""


class TestConfig(MAASTestCase):

    """Tests for `maasserver.config`."""

    def test_is_dev_environment_returns_false(self):
        self.useFixture(EnvironmentVariableFixture(
            'DJANGO_SETTINGS_MODULE', 'Harry'))
        self.assertFalse(config.is_dev_environment())

    def test_is_dev_environment_returns_true(self):
        self.useFixture(EnvironmentVariableFixture(
            'DJANGO_SETTINGS_MODULE', 'maas.development'))
        self.assertTrue(config.is_dev_environment())
