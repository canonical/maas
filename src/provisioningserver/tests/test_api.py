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

from provisioningserver.api import ProvisioningAPI
from provisioningserver.interfaces import IProvisioningAPI
from provisioningserver.testing.fakeapi import FakeAsynchronousProvisioningAPI
from provisioningserver.testing.fakecobbler import make_fake_cobbler_session
from testtools import TestCase
from testtools.deferredruntest import AsynchronousDeferredRunTest
from twisted.internet.defer import inlineCallbacks
from zope.interface.verify import verifyObject


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
            expected[name] = {'name': name, 'profile': 'profile'}
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


class TestFakeProvisioningAPI(TestProvisioningAPI):
    """Test :class:`FakeAsynchronousProvisioningAPI`."""

    def get_provisioning_api(self):
        return FakeAsynchronousProvisioningAPI()
