# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.config`."""

import random

import formencode.api

from maasserver.config import RegionConfiguration
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase


class TestRegionConfiguration(MAASTestCase):
    """Tests for `RegionConfiguration`."""

    def test_default_maas_url(self):
        config = RegionConfiguration({})
        self.assertEqual("http://localhost:5240/MAAS", config.maas_url)

    def test_default_database_conn_max_age(self):
        config = RegionConfiguration({})
        self.assertEqual(60 * 5, config.database_conn_max_age)

    def test_set_and_get_maas_url(self):
        config = RegionConfiguration({})
        example_url = factory.make_simple_http_url()
        config.maas_url = example_url
        self.assertEqual(example_url, config.maas_url)
        # It's also stored in the configuration database.
        self.assertEqual({"maas_url": example_url}, config.store)

    def test_set_maas_url_accepts_hostnames(self):
        config = RegionConfiguration({})
        example_url = factory.make_simple_http_url()
        config.maas_url = example_url
        self.assertEqual(example_url, config.maas_url)
        self.assertEqual({"maas_url": example_url}, config.store)

    def test_set_maas_url_accepts_very_short_hostnames(self):
        config = RegionConfiguration({})
        example_url = factory.make_simple_http_url(
            netloc=factory.make_string(size=1)
        )
        config.maas_url = example_url
        self.assertEqual(example_url, config.maas_url)
        self.assertEqual({"maas_url": example_url}, config.store)

    def test_set_maas_url_rejects_bare_ipv6_addresses(self):
        config = RegionConfiguration({})
        example_url = factory.make_simple_http_url(
            netloc=factory.make_ipv6_address()
        )
        with self.assertRaisesRegex(
            formencode.api.Invalid, "^That is not a valid URL$"
        ):
            config.maas_url = example_url

    def test_set_maas_url_accepts_ipv6_addresses_with_brackets(self):
        config = RegionConfiguration({})
        example_url = factory.make_simple_http_url(
            netloc="[%s]" % factory.make_ipv6_address()
        )
        config.maas_url = example_url
        self.assertEqual(example_url, config.maas_url)
        self.assertEqual({"maas_url": example_url}, config.store)


class TestRegionConfigurationDatabaseOptions(MAASTestCase):
    """Tests for the database options in `RegionConfiguration`."""

    options_and_defaults = {
        "database_host": "localhost",
        "database_port": 5432,
        "database_name": "maasdb",
        "database_user": "maas",
        "database_pass": "",
        "database_conn_max_age": 5 * 60,
        "database_keepalive": True,
        "database_keepalive_idle": 15,
        "database_keepalive_interval": 15,
        "database_keepalive_count": 2,
    }

    scenarios = tuple(
        (name, {"option": name, "default": default})
        for name, default in options_and_defaults.items()
    )

    def test_default(self):
        config = RegionConfiguration({})
        self.assertEqual(self.default, getattr(config, self.option))

    def test_set_and_get(self):
        config = RegionConfiguration({})
        if isinstance(getattr(config, self.option), str):
            example_value = factory.make_name(self.option)
        elif self.option == "database_keepalive":
            example_value = random.choice([True, False])
        else:
            example_value = factory.pick_port()
        # Argument values will most often be passed in from the command-line,
        # so convert to a string before use to reflect that usage.
        setattr(config, self.option, str(example_value))
        self.assertEqual(example_value, getattr(config, self.option))
        # It's also stored in the configuration database.
        expected_value = example_value
        if example_value == "true":
            expected_value = True
        elif expected_value == "false":
            expected_value = False
        self.assertEqual({self.option: expected_value}, config.store)


class TestRegionConfigurationWorkerOptions(MAASTestCase):
    """Tests for the worker options in `RegionConfiguration`."""

    def test_default(self):
        config = RegionConfiguration({})
        self.assertEqual(4, config.num_workers)

    def test_set_and_get(self):
        config = RegionConfiguration({})
        workers = random.randint(8, 12)
        config.num_workers = workers
        self.assertEqual(workers, config.num_workers)
        # It's also stored in the configuration database.
        self.assertEqual({"num_workers": workers}, config.store)


class TestRegionConfigurationDebugOptions(MAASTestCase):
    """Tests for the debug options in `RegionConfiguration`."""

    options_and_defaults = {"debug": False, "debug_queries": False}

    scenarios = tuple(
        (name, {"option": name, "default": default})
        for name, default in options_and_defaults.items()
    )

    def test_default(self):
        config = RegionConfiguration({})
        self.assertEqual(self.default, getattr(config, self.option))

    def test_set_and_get(self):
        config = RegionConfiguration({})
        example_value = random.choice(["true", "yes", "True"])
        # Argument values will most often be passed in from the command-line,
        # so convert to a string before use to reflect that usage.
        setattr(config, self.option, example_value)
        self.assertTrue(getattr(config, self.option))
        # It's also stored in the configuration database.
        self.assertEqual({self.option: True}, config.store)
