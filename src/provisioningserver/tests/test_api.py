# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.api`.

Also tests `provisioningserver.testing.fakeapi`.
"""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from abc import (
    ABCMeta,
    abstractmethod,
    )
from itertools import (
    count,
    islice,
    )
from os import environ
from random import randint
from time import time
from unittest import skipIf
from urlparse import urlparse

from maasserver.testing.enum import map_enum
from provisioningserver.api import (
    cobbler_to_papi_distro,
    cobbler_to_papi_node,
    cobbler_to_papi_profile,
    mac_addresses_to_cobbler_deltas,
    postprocess_mapping,
    ProvisioningAPI,
    )
from provisioningserver.cobblerclient import (
    CobblerSession,
    CobblerSystem,
    )
from provisioningserver.enum import POWER_TYPE
from provisioningserver.interfaces import IProvisioningAPI
from provisioningserver.testing.fakeapi import FakeAsynchronousProvisioningAPI
from provisioningserver.testing.fakecobbler import make_fake_cobbler_session
from testtools import TestCase
from testtools.deferredruntest import AsynchronousDeferredRunTest
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
    )
from twisted.web.xmlrpc import Fault
from zope.interface.verify import verifyObject


names = ("test%d" % num for num in count(int(time())))

random_octet = lambda: randint(0, 255)
random_octets = iter(random_octet, None)


def fake_mac_address():
    """Return a random MAC address."""
    octets = islice(random_octets, 6)
    return ":".join(format(octet, "02x") for octet in octets)


def fake_name():
    """Return a fake name. Each call returns a different name."""
    return next(names)


def fake_node_metadata():
    """Produce fake metadata parameters for adding a node."""
    return {
        'maas-metadata-url': 'http://%s:8000/metadata/' % fake_name(),
        'maas-metadata-credentials': 'fake/%s' % fake_name(),
        }


class TestFunctions(TestCase):
    """Tests for the free functions in `provisioningserver.api`."""

    def test_postprocess_mapping(self):
        data = {
            "sad": "wings",
            "of": "destiny",
            }
        expected = {
            "sad": "Wings",
            "of": "Destiny",
            }
        observed = postprocess_mapping(data, unicode.capitalize)
        self.assertEqual(expected, observed)

    def test_cobbler_to_papi_node(self):
        data = {
            "name": "iced",
            "profile": "earth",
            "interfaces": {
                "eth0": {"mac_address": "12:34:56:78:9a:bc"},
                },
            "ju": "nk",
            }
        expected = {
            "name": "iced",
            "profile": "earth",
            "mac_addresses": ["12:34:56:78:9a:bc"],
            }
        observed = cobbler_to_papi_node(data)
        self.assertEqual(expected, observed)

    def test_cobbler_to_papi_node_without_interfaces(self):
        data = {
            "name": "iced",
            "profile": "earth",
            "ju": "nk",
            }
        expected = {
            "name": "iced",
            "profile": "earth",
            "mac_addresses": [],
            }
        observed = cobbler_to_papi_node(data)
        self.assertEqual(expected, observed)

    def test_cobbler_to_papi_profile(self):
        data = {
            "name": "paradise",
            "distro": "lost",
            "draconian": "times",
            }
        expected = {
            "name": "paradise",
            "distro": "lost",
            }
        observed = cobbler_to_papi_profile(data)
        self.assertEqual(expected, observed)

    def test_cobbler_to_papi_distro(self):
        data = {
            "name": "strapping",
            "initrd": "young",
            "kernel": "lad",
            "alien": "city",
            }
        expected = {
            "name": "strapping",
            "initrd": "young",
            "kernel": "lad",
            }
        observed = cobbler_to_papi_distro(data)
        self.assertEqual(expected, observed)


class TestInterfaceDeltas(TestCase):

    def test_mac_addresses_to_cobbler_deltas_set_1(self):
        current_interfaces = {
            "eth0": {
                "mac_address": "",
                },
            }
        mac_addresses_desired = ["12:34:56:78:90:12"]
        expected = [
            {"interface": "eth0",
             "mac_address": "12:34:56:78:90:12"},
            ]
        observed = list(
            mac_addresses_to_cobbler_deltas(
                current_interfaces, mac_addresses_desired))
        self.assertEqual(expected, observed)

    def test_mac_addresses_to_cobbler_deltas_set_2(self):
        current_interfaces = {
            "eth0": {
                "mac_address": "",
                },
            }
        mac_addresses_desired = [
            "11:11:11:11:11:11", "22:22:22:22:22:22"]
        expected = [
            {"interface": "eth0",
             "mac_address": "11:11:11:11:11:11"},
            {"interface": "eth1",
             "mac_address": "22:22:22:22:22:22"},
            ]
        observed = list(
            mac_addresses_to_cobbler_deltas(
                current_interfaces, mac_addresses_desired))
        self.assertEqual(expected, observed)

    def test_mac_addresses_to_cobbler_deltas_remove_1(self):
        current_interfaces = {
            "eth0": {
                "mac_address": "11:11:11:11:11:11",
                },
            "eth1": {
                "mac_address": "22:22:22:22:22:22",
                },
            }
        mac_addresses_desired = ["22:22:22:22:22:22"]
        expected = [
            {"interface": "eth0",
             "delete_interface": True},
            ]
        observed = list(
            mac_addresses_to_cobbler_deltas(
                current_interfaces, mac_addresses_desired))
        self.assertEqual(expected, observed)

    def test_mac_addresses_to_cobbler_deltas_set_1_remove_1(self):
        current_interfaces = {
            "eth0": {
                "mac_address": "11:11:11:11:11:11",
                },
            "eth1": {
                "mac_address": "22:22:22:22:22:22",
                },
            }
        mac_addresses_desired = [
            "22:22:22:22:22:22", "33:33:33:33:33:33"]
        expected = [
            {"interface": "eth0",
             "delete_interface": True},
            {"interface": "eth0",
             "mac_address": "33:33:33:33:33:33"},
            ]
        observed = list(
            mac_addresses_to_cobbler_deltas(
                current_interfaces, mac_addresses_desired))
        self.assertEqual(expected, observed)


class ProvisioningAPITests:
    """Tests for `provisioningserver.api.ProvisioningAPI`.

    Abstract base class.  To exercise these tests, derive a test case from
    this class as well as from TestCase.  Provide it with a
    ``get_provisioning_api`` method that returns an :class:`IProvisioningAPI`
    implementation that you want to test against.
    """

    __metaclass__ = ABCMeta

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    @abstractmethod
    def get_provisioning_api(self):
        """Create a real, or faked, ProvisoningAPI to run tests against.

        Override this in the test case that exercises this scenario.
        """

    @staticmethod
    def cleanup_objects(delete_func, *object_names):
        """Remove named objects from the PAPI.

        `delete_func` is expected to be one of the ``delete_*_by_name``
        methods of the Provisioning API. XML-RPC errors are ignored; this
        function does its best to remove the object but a failure to do so is
        not an error.
        """
        d = delete_func(object_names)
        d.addErrback(lambda failure: failure.trap(Fault))
        return d

    @inlineCallbacks
    def add_distro(self, papi, name=None):
        """Creates a new distro object via `papi`.

        Arranges for it to be deleted during test clean-up. If `name` is not
        specified, `fake_name` will be called to obtain one.
        """
        if name is None:
            name = fake_name()
        # For the initrd and kernel, use a file that we know will exist for a
        # running Cobbler instance (at least, on Ubuntu) so that we can test
        # against remote instances, like one in odev.
        initrd = "/etc/cobbler/settings"
        kernel = "/etc/cobbler/version"
        distro_name = yield papi.add_distro(name, initrd, kernel)
        self.addCleanup(
            self.cleanup_objects,
            papi.delete_distros_by_name,
            distro_name)
        returnValue(distro_name)

    @inlineCallbacks
    def add_profile(self, papi, name=None, distro_name=None):
        """Creates a new profile object via `papi`.

        Arranges for it to be deleted during test clean-up. If `name` is not
        specified, `fake_name` will be called to obtain one. If `distro_name`
        is not specified, one will be obtained by calling `add_distro`.
        """
        if name is None:
            name = fake_name()
        if distro_name is None:
            distro_name = yield self.add_distro(papi)
        profile_name = yield papi.add_profile(name, distro_name)
        self.addCleanup(
            self.cleanup_objects,
            papi.delete_profiles_by_name,
            profile_name)
        returnValue(profile_name)

    @inlineCallbacks
    def add_node(self, papi, name=None, profile_name=None, power_type=None,
                 metadata=None):
        """Creates a new node object via `papi`.

        Arranges for it to be deleted during test clean-up. If `name` is not
        specified, `fake_name` will be called to obtain one. If `profile_name`
        is not specified, one will be obtained by calling `add_profile`. If
        `metadata` is not specified, it will be obtained by calling
        `fake_node_metadata`.
        """
        if name is None:
            name = fake_name()
        if profile_name is None:
            profile_name = yield self.add_profile(papi)
        if power_type is None:
            power_type = POWER_TYPE.WAKE_ON_LAN
        if metadata is None:
            metadata = fake_node_metadata()
        node_name = yield papi.add_node(
            name, profile_name, power_type, metadata)
        self.addCleanup(
            self.cleanup_objects,
            papi.delete_nodes_by_name,
            node_name)
        returnValue(node_name)

    def test_ProvisioningAPI_interfaces(self):
        papi = self.get_provisioning_api()
        verifyObject(IProvisioningAPI, papi)

    @inlineCallbacks
    def test_add_distro(self):
        # Create a distro via the Provisioning API.
        papi = self.get_provisioning_api()
        distro_name = yield self.add_distro(papi)
        distros = yield papi.get_distros_by_name([distro_name])
        self.assertItemsEqual([distro_name], distros)

    @inlineCallbacks
    def test_add_profile(self):
        # Create a profile via the Provisioning API.
        papi = self.get_provisioning_api()
        profile_name = yield self.add_profile(papi)
        profiles = yield papi.get_profiles_by_name([profile_name])
        self.assertItemsEqual([profile_name], profiles)

    @inlineCallbacks
    def test_add_node(self):
        # Create a system/node via the Provisioning API.
        papi = self.get_provisioning_api()
        node_name = yield self.add_node(papi)
        nodes = yield papi.get_nodes_by_name([node_name])
        self.assertItemsEqual([node_name], nodes)

    @inlineCallbacks
    def _test_add_object_twice(self, method):
        # Adding an object twice is allowed.
        papi = self.get_provisioning_api()
        object_name1 = yield method(papi)
        object_name2 = yield method(papi, object_name1)
        self.assertEqual(object_name1, object_name2)

    def test_add_distro_twice(self):
        return self._test_add_object_twice(self.add_distro)

    def test_add_profile_twice(self):
        return self._test_add_object_twice(self.add_profile)

    def test_add_node_twice(self):
        return self._test_add_object_twice(self.add_node)

    @inlineCallbacks
    def test_modify_distros(self):
        papi = self.get_provisioning_api()
        distro_name = yield self.add_distro(papi)
        values = yield papi.get_distros_by_name([distro_name])
        # The kernel and initrd settings differ.
        self.assertNotEqual(
            values[distro_name]["kernel"],
            values[distro_name]["initrd"])
        # Swap the initrd and kernel settings.
        initrd_new = values[distro_name]["kernel"]
        kernel_new = values[distro_name]["initrd"]
        yield papi.modify_distros(
            {distro_name: {"initrd": initrd_new, "kernel": kernel_new}})
        values = yield papi.get_distros_by_name([distro_name])
        self.assertEqual(initrd_new, values[distro_name]["initrd"])
        self.assertEqual(kernel_new, values[distro_name]["kernel"])

    @inlineCallbacks
    def test_modify_profiles(self):
        papi = self.get_provisioning_api()
        distro1_name = yield self.add_distro(papi)
        distro2_name = yield self.add_distro(papi)
        profile_name = yield self.add_profile(papi, None, distro1_name)
        yield papi.modify_profiles({profile_name: {"distro": distro2_name}})
        values = yield papi.get_profiles_by_name([profile_name])
        self.assertEqual(distro2_name, values[profile_name]["distro"])

    @inlineCallbacks
    def test_modify_nodes(self):
        papi = self.get_provisioning_api()
        distro_name = yield self.add_distro(papi)
        profile1_name = yield self.add_profile(papi, None, distro_name)
        profile2_name = yield self.add_profile(papi, None, distro_name)
        node_name = yield self.add_node(papi, None, profile1_name)
        yield papi.modify_nodes({node_name: {"profile": profile2_name}})
        values = yield papi.get_nodes_by_name([node_name])
        self.assertEqual(profile2_name, values[node_name]["profile"])

    @inlineCallbacks
    def test_modify_nodes_set_mac_addresses(self):
        papi = self.get_provisioning_api()
        node_name = yield self.add_node(papi)
        mac_address = fake_mac_address()
        yield papi.modify_nodes(
            {node_name: {"mac_addresses": [mac_address]}})
        values = yield papi.get_nodes_by_name([node_name])
        self.assertEqual(
            [mac_address], values[node_name]["mac_addresses"])

    @inlineCallbacks
    def test_modify_nodes_remove_mac_addresses(self):
        papi = self.get_provisioning_api()
        node_name = yield self.add_node(papi)
        mac_address1 = fake_mac_address()
        mac_address2 = fake_mac_address()
        mac_addresses_from = [mac_address1, mac_address2]
        mac_addresses_to = [mac_address2]
        yield papi.modify_nodes(
            {node_name: {"mac_addresses": mac_addresses_from}})
        yield papi.modify_nodes(
            {node_name: {"mac_addresses": mac_addresses_to}})
        values = yield papi.get_nodes_by_name([node_name])
        self.assertEqual(
            [mac_address2], values[node_name]["mac_addresses"])

    @inlineCallbacks
    def test_delete_distros_by_name(self):
        # Create a distro via the Provisioning API.
        papi = self.get_provisioning_api()
        distro_name = yield self.add_distro(papi)
        # Delete it again via the Provisioning API.
        yield papi.delete_distros_by_name([distro_name])
        # It has gone, checked via the Cobbler session.
        distros = yield papi.get_distros_by_name([distro_name])
        self.assertEqual({}, distros)

    @inlineCallbacks
    def test_delete_profiles_by_name(self):
        # Create a profile via the Provisioning API.
        papi = self.get_provisioning_api()
        profile_name = yield self.add_profile(papi)
        # Delete it again via the Provisioning API.
        yield papi.delete_profiles_by_name([profile_name])
        # It has gone, checked via the Cobbler session.
        profiles = yield papi.get_profiles_by_name([profile_name])
        self.assertEqual({}, profiles)

    @inlineCallbacks
    def test_delete_nodes_by_name(self):
        # Create a node via the Provisioning API.
        papi = self.get_provisioning_api()
        node_name = yield self.add_node(papi)
        # Delete it again via the Provisioning API.
        yield papi.delete_nodes_by_name([node_name])
        # It has gone, checked via the Cobbler session.
        nodes = yield papi.get_nodes_by_name([node_name])
        self.assertEqual({}, nodes)

    @inlineCallbacks
    def test_get_distros(self):
        papi = self.get_provisioning_api()
        distros_before = yield papi.get_distros()
        # Create some distros via the Provisioning API.
        distros_expected = set()
        for num in range(3):
            distro_name = yield self.add_distro(papi)
            distros_expected.add(distro_name)
        distros_after = yield papi.get_distros()
        distros_created = set(distros_after) - set(distros_before)
        self.assertSetEqual(distros_expected, distros_created)

    @inlineCallbacks
    def test_get_profiles(self):
        papi = self.get_provisioning_api()
        distro_name = yield self.add_distro(papi)
        profiles_before = yield papi.get_profiles()
        # Create some profiles via the Provisioning API.
        profiles_expected = set()
        for num in range(3):
            profile_name = yield self.add_profile(papi, None, distro_name)
            profiles_expected.add(profile_name)
        profiles_after = yield papi.get_profiles()
        profiles_created = set(profiles_after) - set(profiles_before)
        self.assertSetEqual(profiles_expected, profiles_created)

    @inlineCallbacks
    def test_get_nodes_returns_all_nodes(self):
        papi = self.get_provisioning_api()
        profile_name = yield self.add_profile(papi)
        node_names = set()
        for num in range(3):
            node_name = yield self.add_node(papi, None, profile_name)
            node_names.add(node_name)
        nodes = yield papi.get_nodes()
        self.assertSetEqual(node_names, node_names.intersection(nodes))

    @inlineCallbacks
    def test_get_nodes_includes_node_attributes(self):
        papi = self.get_provisioning_api()
        node_name = yield self.add_node(papi)
        nodes = yield papi.get_nodes()
        self.assertIn(node_name, nodes)
        self.assertIn('name', nodes[node_name])
        self.assertIn('profile', nodes[node_name])
        self.assertIn('mac_addresses', nodes[node_name])

    @inlineCallbacks
    def test_get_nodes_by_name(self):
        papi = self.get_provisioning_api()
        nodes = yield papi.get_nodes_by_name([])
        self.assertEqual({}, nodes)
        # Create a node via the Provisioning API.
        node_name = yield self.add_node(papi)
        nodes = yield papi.get_nodes_by_name([node_name])
        # The response contains keys for all systems found.
        self.assertItemsEqual([node_name], nodes)

    @inlineCallbacks
    def test_get_distros_by_name(self):
        papi = self.get_provisioning_api()
        distros = yield papi.get_distros_by_name([])
        self.assertEqual({}, distros)
        # Create a distro via the Provisioning API.
        distro_name = yield self.add_distro(papi)
        distros = yield papi.get_distros_by_name([distro_name])
        # The response contains keys for all distributions found.
        self.assertItemsEqual([distro_name], distros)

    @inlineCallbacks
    def test_get_profiles_by_name(self):
        papi = self.get_provisioning_api()
        profiles = yield papi.get_profiles_by_name([])
        self.assertEqual({}, profiles)
        # Create a profile via the Provisioning API.
        profile_name = yield self.add_profile(papi)
        profiles = yield papi.get_profiles_by_name([profile_name])
        # The response contains keys for all profiles found.
        self.assertItemsEqual([profile_name], profiles)

    @inlineCallbacks
    def test_stop_nodes(self):
        papi = self.get_provisioning_api()
        node_name = yield self.add_node(papi)
        yield papi.stop_nodes([node_name])
        # The test is that we get here without error.
        pass

    @inlineCallbacks
    def test_start_nodes(self):
        papi = self.get_provisioning_api()
        node_name = yield self.add_node(papi)
        yield papi.start_nodes([node_name])
        # The test is that we get here without error.
        pass


class ProvisioningAPITestsWithCobbler:
    """Provisioning API tests that also access a real, or fake, Cobbler."""

    @inlineCallbacks
    def test_add_node_sets_power_type(self):
        papi = self.get_provisioning_api()
        power_types = list(map_enum(POWER_TYPE).values())
        # The DEFAULT value does not exist as far as the provisioning
        # server is concerned.
        power_types.remove(POWER_TYPE.DEFAULT)
        nodes = {}
        for power_type in power_types:
            nodes[power_type] = yield self.add_node(
                papi, power_type=power_type)
        cobbler_power_types = {}
        for power_type, node_id in nodes.items():
            attrs = yield CobblerSystem(papi.session, node_id).get_values()
            cobbler_power_types[power_type] = attrs['power_type']
        self.assertItemsEqual(
            dict(zip(power_types, power_types)), cobbler_power_types)


class TestFakeProvisioningAPI(ProvisioningAPITests, TestCase):
    """Test :class:`FakeAsynchronousProvisioningAPI`.

    Includes by inheritance all the tests in :class:`ProvisioningAPITests`.
    """

    def get_provisioning_api(self):
        """Return a fake ProvisioningAPI."""
        return FakeAsynchronousProvisioningAPI()


class TestProvisioningAPIWithFakeCobbler(ProvisioningAPITests,
                                         ProvisioningAPITestsWithCobbler,
                                         TestCase):
    """Test :class:`ProvisioningAPI` with a fake Cobbler instance.

    Includes by inheritance all the tests in :class:`ProvisioningAPITests`.
    """

    def get_provisioning_api(self):
        """Return a real ProvisioningAPI, but using a fake Cobbler session."""
        return ProvisioningAPI(make_fake_cobbler_session())

    @inlineCallbacks
    def test_add_node_preseeds_metadata(self):
        papi = self.get_provisioning_api()
        metadata = fake_node_metadata()
        node_name = yield self.add_node(papi, metadata=metadata)
        attrs = yield CobblerSystem(papi.session, node_name).get_values()
        preseed = attrs['ks_meta']['MAAS_PRESEED']
        self.assertIn(metadata['maas-metadata-url'], preseed)
        self.assertIn(metadata['maas-metadata-credentials'], preseed)


class TestProvisioningAPIWithRealCobbler(ProvisioningAPITests,
                                         ProvisioningAPITestsWithCobbler,
                                         TestCase):
    """Test :class:`ProvisioningAPI` with a real Cobbler instance.

    The URL for the Cobbler instance must be provided in the
    `PSERV_TEST_COBBLER_URL` environment variable.

    Includes by inheritance all the tests in :class:`ProvisioningAPITests`.
    """

    url = environ.get("PSERV_TEST_COBBLER_URL")

    @skipIf(
        url is None,
        "Set PSERV_TEST_COBBLER_URL to the URL for a Cobbler "
        "instance to test against, e.g. http://username:password"
        "@localhost/cobbler_api. Warning: this will modify your "
        "Cobbler database.")
    def get_provisioning_api(self):
        """Return a connected :class:`ProvisioningAPI`."""
        urlparts = urlparse(self.url)
        cobbler_session = CobblerSession(
            self.url, urlparts.username, urlparts.password)
        return ProvisioningAPI(cobbler_session)
