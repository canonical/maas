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

from provisioningserver.api import (
    cobbler_to_papi_distro,
    cobbler_to_papi_node,
    cobbler_to_papi_profile,
    mac_addresses_to_cobbler_deltas,
    postprocess_mapping,
    ProvisioningAPI,
    )
from provisioningserver.interfaces import IProvisioningAPI
from provisioningserver.testing.fakeapi import FakeAsynchronousProvisioningAPI
from provisioningserver.testing.fakecobbler import make_fake_cobbler_session
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


class TestProvisioningAPI(TestCase):
    """Tests for `provisioningserver.api.ProvisioningAPI`."""

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def get_provisioning_api(self):
        session = make_fake_cobbler_session()
        return ProvisioningAPI(session)

    def test_ProvisioningAPI_interfaces(self):
        papi = self.get_provisioning_api()
        verifyObject(IProvisioningAPI, papi)

    @inlineCallbacks
    def test_add_distro(self):
        # Create a distro via the Provisioning API.
        papi = self.get_provisioning_api()
        distro = yield papi.add_distro(
            "distro", "an_initrd", "a_kernel")
        self.assertEqual("distro", distro)

    @inlineCallbacks
    def test_add_profile(self):
        # Create a profile via the Provisioning API.
        papi = self.get_provisioning_api()
        distro = yield papi.add_distro(
            "distro", "an_initrd", "a_kernel")
        profile = yield papi.add_profile("profile", distro)
        self.assertEqual("profile", profile)

    @inlineCallbacks
    def test_add_node(self):
        # Create a system/node via the Provisioning API.
        papi = self.get_provisioning_api()
        distro = yield papi.add_distro(
            "distro", "an_initrd", "a_kernel")
        profile = yield papi.add_profile("profile", distro)
        node = yield papi.add_node("node", profile)
        self.assertEqual("node", node)

    @inlineCallbacks
    def test_modify_distros(self):
        papi = self.get_provisioning_api()
        distro_name = yield papi.add_distro(
            "distro", "an_initrd", "a_kernel")
        yield papi.modify_distros(
            {distro_name: {"initrd": "zig", "kernel": "zag"}})
        values = yield papi.get_distros_by_name([distro_name])
        self.assertEqual("zig", values[distro_name]["initrd"])
        self.assertEqual("zag", values[distro_name]["kernel"])

    @inlineCallbacks
    def test_modify_profiles(self):
        papi = self.get_provisioning_api()
        distro1_name = yield papi.add_distro(
            "distro1", "an_initrd", "a_kernel")
        distro2_name = yield papi.add_distro(
            "distro2", "an_initrd", "a_kernel")
        profile_name = yield papi.add_profile("profile", distro1_name)
        yield papi.modify_profiles({profile_name: {"distro": distro2_name}})
        values = yield papi.get_profiles_by_name([profile_name])
        self.assertEqual(distro2_name, values[profile_name]["distro"])

    @inlineCallbacks
    def test_modify_nodes(self):
        papi = self.get_provisioning_api()
        distro_name = yield papi.add_distro(
            "distro", "an_initrd", "a_kernel")
        profile1_name = yield papi.add_profile("profile1", distro_name)
        profile2_name = yield papi.add_profile("profile2", distro_name)
        node_name = yield papi.add_node("node", profile1_name)
        yield papi.modify_nodes({node_name: {"profile": profile2_name}})
        values = yield papi.get_nodes_by_name([node_name])
        self.assertEqual(profile2_name, values[node_name]["profile"])

    @inlineCallbacks
    def test_modify_nodes_set_mac_addresses(self):
        papi = self.get_provisioning_api()
        distro_name = yield papi.add_distro(
            "distro", "an_initrd", "a_kernel")
        profile_name = yield papi.add_profile("profile1", distro_name)
        node_name = yield papi.add_node("node", profile_name)
        yield papi.modify_nodes(
            {node_name: {"mac_addresses": ["55:55:55:55:55:55"]}})
        values = yield papi.get_nodes_by_name([node_name])
        self.assertEqual(
            ["55:55:55:55:55:55"], values[node_name]["mac_addresses"])

    @inlineCallbacks
    def test_modify_nodes_remove_mac_addresses(self):
        papi = self.get_provisioning_api()
        distro_name = yield papi.add_distro(
            "distro", "an_initrd", "a_kernel")
        profile_name = yield papi.add_profile("profile1", distro_name)
        node_name = yield papi.add_node("node", profile_name)
        mac_addresses_from = ["55:55:55:55:55:55", "66:66:66:66:66:66"]
        mac_addresses_to = ["66:66:66:66:66:66"]
        yield papi.modify_nodes(
            {node_name: {"mac_addresses": mac_addresses_from}})
        yield papi.modify_nodes(
            {node_name: {"mac_addresses": mac_addresses_to}})
        values = yield papi.get_nodes_by_name([node_name])
        self.assertEqual(
            ["66:66:66:66:66:66"], values[node_name]["mac_addresses"])

    @inlineCallbacks
    def test_delete_distros_by_name(self):
        # Create a distro via the Provisioning API.
        papi = self.get_provisioning_api()
        distro = yield papi.add_distro(
            "distro", "an_initrd", "a_kernel")
        # Delete it again via the Provisioning API.
        yield papi.delete_distros_by_name([distro])
        # It has gone, checked via the Cobbler session.
        distros = yield papi.get_distros_by_name([distro])
        self.assertEqual({}, distros)

    @inlineCallbacks
    def test_delete_profiles_by_name(self):
        # Create a profile via the Provisioning API.
        papi = self.get_provisioning_api()
        distro = yield papi.add_distro(
            "distro", "an_initrd", "a_kernel")
        profile = yield papi.add_profile("profile", distro)
        # Delete it again via the Provisioning API.
        yield papi.delete_profiles_by_name([profile])
        # It has gone, checked via the Cobbler session.
        profiles = yield papi.get_profiles_by_name([profile])
        self.assertEqual({}, profiles)

    @inlineCallbacks
    def test_delete_nodes_by_name(self):
        # Create a node via the Provisioning API.
        papi = self.get_provisioning_api()
        distro = yield papi.add_distro(
            "distro", "an_initrd", "a_kernel")
        profile = yield papi.add_profile("profile", distro)
        node = yield papi.add_node("node", profile)
        # Delete it again via the Provisioning API.
        yield papi.delete_nodes_by_name([node])
        # It has gone, checked via the Cobbler session.
        nodes = yield papi.get_nodes_by_name([node])
        self.assertEqual({}, nodes)

    @inlineCallbacks
    def test_get_distros(self):
        papi = self.get_provisioning_api()
        distros = yield papi.get_distros()
        self.assertEqual({}, distros)
        # Create some distros via the Provisioning API.
        expected = {}
        for num in xrange(3):
            initrd = self.getUniqueString()
            kernel = self.getUniqueString()
            name = self.getUniqueString()
            yield papi.add_distro(name, initrd, kernel)
            expected[name] = {
                "initrd": initrd,
                "kernel": kernel,
                "name": name,
                }
        distros = yield papi.get_distros()
        self.assertEqual(expected, distros)

    @inlineCallbacks
    def test_get_profiles(self):
        papi = self.get_provisioning_api()
        distro = yield papi.add_distro(
            "distro", "an_initrd", "a_kernel")
        profiles = yield papi.get_profiles()
        self.assertEqual({}, profiles)
        # Create some profiles via the Provisioning API.
        expected = {}
        for num in xrange(3):
            name = self.getUniqueString()
            yield papi.add_profile(name, distro)
            expected[name] = {u'distro': u'distro', u'name': name}
        profiles = yield papi.get_profiles()
        self.assertEqual(expected, profiles)

    @inlineCallbacks
    def test_get_nodes(self):
        papi = self.get_provisioning_api()
        distro = yield papi.add_distro(
            "distro", "an_initrd", "a_kernel")
        profile = yield papi.add_profile("profile", distro)
        nodes = yield papi.get_nodes()
        self.assertEqual({}, nodes)
        # Create some nodes via the Provisioning API.
        expected = {}
        for num in xrange(3):
            name = self.getUniqueString()
            yield papi.add_node(name, profile)
            expected[name] = {
                'name': name,
                'profile': 'profile',
                'mac_addresses': [],
                }
        nodes = yield papi.get_nodes()
        self.assertEqual(expected, nodes)

    @inlineCallbacks
    def test_get_nodes_by_name(self):
        papi = self.get_provisioning_api()
        nodes = yield papi.get_nodes_by_name([])
        self.assertEqual({}, nodes)
        # Create a node via the Provisioning API.
        distro = yield papi.add_distro("distro", "initrd", "kernel")
        profile = yield papi.add_profile("profile", distro)
        yield papi.add_node("alice", profile)
        nodes = yield papi.get_nodes_by_name(["alice", "bob"])
        # The response contains keys for all systems found.
        self.assertSequenceEqual(["alice"], sorted(nodes))

    @inlineCallbacks
    def test_get_distros_by_name(self):
        papi = self.get_provisioning_api()
        distros = yield papi.get_distros_by_name([])
        self.assertEqual({}, distros)
        # Create a distro via the Provisioning API.
        yield papi.add_distro("alice", "initrd", "kernel")
        distros = yield papi.get_distros_by_name(["alice", "bob"])
        # The response contains keys for all distributions found.
        self.assertSequenceEqual(["alice"], sorted(distros))

    @inlineCallbacks
    def test_get_profiles_by_name(self):
        papi = self.get_provisioning_api()
        profiles = yield papi.get_profiles_by_name([])
        self.assertEqual({}, profiles)
        # Create a profile via the Provisioning API.
        distro = yield papi.add_distro("distro", "initrd", "kernel")
        yield papi.add_profile("alice", distro)
        profiles = yield papi.get_profiles_by_name(["alice", "bob"])
        # The response contains keys for all profiles found.
        self.assertSequenceEqual(["alice"], sorted(profiles))

    @inlineCallbacks
    def test_stop_nodes(self):
        papi = self.get_provisioning_api()
        distro = yield papi.add_distro("distro", "initrd", "kernel")
        profile = yield papi.add_profile("profile", distro)
        yield papi.add_node("alice", profile)
        yield papi.stop_nodes(["alice"])
        # The test is that we get here without error.
        pass


class TestFakeProvisioningAPI(TestProvisioningAPI):
    """Test :class:`FakeAsynchronousProvisioningAPI`."""

    def get_provisioning_api(self):
        return FakeAsynchronousProvisioningAPI()
