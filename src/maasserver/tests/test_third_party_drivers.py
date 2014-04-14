# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.third_party_drivers`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os

from maasserver import third_party_drivers
from maasserver.testing.factory import factory
from maasserver.third_party_drivers import (
    DriversConfig,
    get_third_party_driver,
    match_aliases_to_driver,
    node_modaliases,
    populate_kernel_opts,
    )
from maastesting import root
from maastesting.testcase import MAASTestCase
from metadataserver.fields import Bin
from metadataserver.models import (
    commissioningscript,
    NodeCommissionResult,
    )


class TestNodeModaliases(MAASTestCase):

    def test_uses_commissioning_modaliases(self):
        test_data = b'hulla\nbaloo'
        node = factory.make_node()
        NodeCommissionResult.objects.store_data(
            node, commissioningscript.LIST_MODALIASES_OUTPUT_NAME,
            0, Bin(test_data))

        aliases = node_modaliases(node)
        self.assertEqual(['hulla', 'baloo'], aliases)

    def test_survives_no_commissioning_data(self):
        node = factory.make_node()
        aliases = node_modaliases(node)
        self.assertEqual([], aliases)


class TestMatchAliasesToDriver(MAASTestCase):

    def test_finds_first_match(self):
        drivers = [
            {'modaliases': ['foo*'], 'comment': 'first'},
            {'modaliases': ['foo*'], 'comment': 'notfirst'},
        ]

        aliases = ['foobar']

        driver = match_aliases_to_driver(aliases, drivers)
        self.assertEqual(drivers[0], driver)

    def test_finds_no_match(self):
        drivers = [{'modaliases': ['foo*']}]
        aliases = ['bar']
        driver = match_aliases_to_driver(aliases, drivers)
        self.assertIsNone(driver)


class TestPopulateKernelOpts(MAASTestCase):

    def test_blacklist_provided(self):
        driver = {'blacklist': 'bad'}
        driver = populate_kernel_opts(driver)
        self.assertEqual('modprobe.blacklist=bad', driver['kernel_opts'])

    def test_no_blacklist_provided(self):
        driver = {}
        driver = populate_kernel_opts(driver)
        self.assertNotIn('kernel_opts', driver)


class TestGetThirdPartyCode(MAASTestCase):

    def test_finds_match(self):
        node = factory.make_node()
        mock = self.patch(third_party_drivers, 'match_aliases_to_driver')
        base_driver = dict(comment='hooray')
        mock.return_value = base_driver

        driver = get_third_party_driver(node)
        self.assertEqual(base_driver, driver)

        # ensure driver is a copy, not the original
        base_driver['comment'] = 'boo'
        self.assertEqual('hooray', driver['comment'])

    def test_finds_no_match(self):
        node = factory.make_node()
        mock = self.patch(third_party_drivers, 'match_aliases_to_driver')
        mock.return_value = None
        driver = get_third_party_driver(node)
        self.assertEqual({}, driver)


class TestDriversConfig(MAASTestCase):

    def test_get_defaults_returns_empty_drivers_list(self):
        observed = DriversConfig.get_defaults()
        self.assertEqual({'drivers': []}, observed)

    def test_load_from_yaml(self):
        filename = os.path.join(root, "etc", "maas", "drivers.yaml")
        for entry in DriversConfig.load(filename)['drivers']:
            self.assertItemsEqual(
                ['blacklist', 'comment', 'key_binary', 'modaliases',
                 'module', 'repository', 'package'],
                entry)
