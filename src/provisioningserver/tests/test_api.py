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
from base64 import b64decode
from unittest import skipIf

from maasserver.testing.enum import map_enum
from maastesting.factory import factory
from provisioningserver.api import (
    cobbler_to_papi_distro,
    cobbler_to_papi_node,
    cobbler_to_papi_profile,
    gen_cobbler_interface_deltas,
    postprocess_mapping,
    ProvisioningAPI,
    )
from provisioningserver.cobblerclient import CobblerSystem
from provisioningserver.enum import POWER_TYPE
from provisioningserver.interfaces import IProvisioningAPI
from provisioningserver.testing.factory import (
    fake_node_metadata,
    ProvisioningFakeFactory,
    )
from provisioningserver.testing.fakeapi import FakeAsynchronousProvisioningAPI
from provisioningserver.testing.fakecobbler import make_fake_cobbler_session
from provisioningserver.testing.realcobbler import RealCobbler
from testtools import TestCase
from testtools.deferredruntest import AsynchronousDeferredRunTest
from twisted.internet.defer import inlineCallbacks
from zope.interface.verify import verifyObject


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
            "hostname": "dystopia",
            "interfaces": {
                "eth0": {"mac_address": "12:34:56:78:9a:bc"},
                "eth1": {"mac_address": "  "},
                "eth2": {"mac_address": ""},
                "eth3": {"mac_address": None},
                },
            "power_type": "virsh",
            "ju": "nk",
            }
        expected = {
            "name": "iced",
            "profile": "earth",
            "hostname": "dystopia",
            "mac_addresses": ["12:34:56:78:9a:bc"],
            "power_type": "virsh",
            }
        observed = cobbler_to_papi_node(data)
        self.assertEqual(expected, observed)

    def test_cobbler_to_papi_node_without_interfaces(self):
        data = {
            "name": "iced",
            "profile": "earth",
            "hostname": "darksaga",
            "power_type": "ether_wake",
            "ju": "nk",
            }
        expected = {
            "name": "iced",
            "profile": "earth",
            "hostname": "darksaga",
            "mac_addresses": [],
            "power_type": "ether_wake",
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

    def test_gen_cobbler_interface_deltas_set_1_mac(self):
        # Specifying a single MAC address results in a delta to configure
        # eth0. The dns_name of the interface is also updated.
        current_interfaces = {
            "eth0": {
                "mac_address": "",
                "dns_name": "colony",
                },
            }
        hostname = "clayman"
        mac_addresses = [
            "12:34:56:78:90:12",
            ]
        expected = [
            {"interface": "eth0",
             "mac_address": mac_addresses[0],
             "dns_name": hostname},
            ]
        observed = gen_cobbler_interface_deltas(
            current_interfaces, hostname, mac_addresses)
        self.assertItemsEqual(expected, observed)

    def test_gen_cobbler_interface_deltas_set_2_macs(self):
        # Specifying multiple MAC addresses results in deltas to configure a
        # corresponding number of interfaces. The dns_name of the first
        # interface is updated to the given hostname; subsequent interfaces
        # have an empty dns_name.
        current_interfaces = {
            "eth0": {
                "mac_address": "",
                },
            }
        hostname = "crowbar"
        mac_addresses = [
            "11:11:11:11:11:11",
            "22:22:22:22:22:22",
            ]
        expected = [
            {"interface": "eth0",
             "mac_address": mac_addresses[0],
             "dns_name": hostname},
            {"interface": "eth1",
             "mac_address": mac_addresses[1],
             "dns_name": ""},
            ]
        observed = gen_cobbler_interface_deltas(
            current_interfaces, hostname, mac_addresses)
        self.assertItemsEqual(expected, observed)

    def test_gen_cobbler_interface_deltas_remove_first_mac(self):
        # Removing the first MAC address causes the MAC addressese of
        # subsequent interfaces to be shifted down (i.e. eth1's mac --> eth0),
        # and the last interface to be deleted.
        dns_name = "lifesblood"
        current_interfaces = {
            "eth0": {
                "mac_address": "11:11:11:11:11:11",
                "dns_name": dns_name,
                },
            "eth1": {
                "mac_address": "22:22:22:22:22:22",
                },
            }
        mac_addresses = [
            current_interfaces["eth1"]["mac_address"],
            ]
        expected = [
            {"interface": "eth0",
             "mac_address": mac_addresses[0],
             "dns_name": "lifesblood"},
            {"interface": "eth1",
             "delete_interface": True},
            ]
        observed = gen_cobbler_interface_deltas(
            current_interfaces, dns_name, mac_addresses)
        self.assertItemsEqual(expected, observed)

    def test_gen_cobbler_interface_deltas_remove_last_mac(self):
        # Removing the last MAC address causes the last interface to be
        # deleted.
        dns_name = "lifesblood"
        current_interfaces = {
            "eth0": {
                "mac_address": "11:11:11:11:11:11",
                "dns_name": dns_name,
                },
            "eth1": {
                "mac_address": "22:22:22:22:22:22",
                },
            }
        mac_addresses = [
            current_interfaces["eth0"]["mac_address"],
            ]
        expected = [
            {"interface": "eth1",
             "delete_interface": True},
            ]
        observed = gen_cobbler_interface_deltas(
            current_interfaces, dns_name, mac_addresses)
        self.assertItemsEqual(expected, observed)

    def test_gen_cobbler_interface_deltas_modify_first_mac(self):
        # Changing the first MAC address modifies the eth0 interface.
        current_interfaces = {
            "eth0": {
                "mac_address": "11:11:11:11:11:11",
                },
            "eth1": {
                "mac_address": "22:22:22:22:22:22",
                },
            }
        hostname = "necrophagist"
        mac_addresses = [
            "33:33:33:33:33:33",
            current_interfaces["eth1"]["mac_address"],
            ]
        expected = [
            {"interface": "eth0",
             "mac_address": mac_addresses[0],
             "dns_name": hostname},
            ]
        observed = gen_cobbler_interface_deltas(
            current_interfaces, hostname, mac_addresses)
        self.assertItemsEqual(expected, observed)

    def test_gen_cobbler_interface_deltas_remove_all_macs(self):
        # Removing all MAC addresses results in a delta to remove all but the
        # first interface. The first interface is instead deconfigured; this
        # is necessary to satisfy the Cobbler data model.
        current_interfaces = {
            "eth0": {
                "mac_address": "11:11:11:11:11:11",
                },
            "eth1": {
                "mac_address": "22:22:22:22:22:22",
                },
            }
        hostname = "empiricism"
        mac_addresses = []
        expected = [
            {"interface": "eth0",
             "mac_address": "",
             "dns_name": ""},
            {"interface": "eth1",
             "delete_interface": True},
            ]
        observed = gen_cobbler_interface_deltas(
            current_interfaces, hostname, mac_addresses)
        self.assertItemsEqual(expected, observed)


class ProvisioningAPITests(ProvisioningFakeFactory):
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
        node_name = yield self.add_node(papi, hostname="enthroned")
        nodes = yield papi.get_nodes_by_name([node_name])
        self.assertItemsEqual([node_name], nodes)
        node = nodes[node_name]
        self.assertEqual("enthroned", node["hostname"])
        self.assertEqual("ether_wake", node["power_type"])
        self.assertEqual([], node["mac_addresses"])

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
        mac_address = factory.getRandomMACAddress()
        yield papi.modify_nodes(
            {node_name: {"mac_addresses": [mac_address]}})
        values = yield papi.get_nodes_by_name([node_name])
        self.assertEqual(
            [mac_address], values[node_name]["mac_addresses"])

    @inlineCallbacks
    def test_modify_nodes_remove_mac_addresses(self):
        papi = self.get_provisioning_api()
        node_name = yield self.add_node(papi)
        mac_address1 = factory.getRandomMACAddress()
        mac_address2 = factory.getRandomMACAddress()
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
    def test_modify_nodes_remove_all_mac_addresses(self):
        papi = self.get_provisioning_api()
        node_name = yield self.add_node(papi)
        mac_address = factory.getRandomMACAddress()
        yield papi.modify_nodes(
            {node_name: {"mac_addresses": [mac_address]}})
        yield papi.modify_nodes(
            {node_name: {"mac_addresses": []}})
        values = yield papi.get_nodes_by_name([node_name])
        self.assertEqual(
            [], values[node_name]["mac_addresses"])

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
        preseed = b64decode(preseed)
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

    real_cobbler = RealCobbler()

    @skipIf(not real_cobbler.is_available(), RealCobbler.help_text)
    def get_provisioning_api(self):
        """Return a connected :class:`ProvisioningAPI`."""
        return ProvisioningAPI(self.real_cobbler.get_session())
