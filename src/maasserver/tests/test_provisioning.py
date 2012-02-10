# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.provisioning`."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from fixtures import MonkeyPatch
from maasserver import provisioning
from maasserver.models import Node
from maastesting import TestCase
from provisioningserver.testing.fakeapi import FakeSynchronousProvisioningAPI


class TestProvisioning(TestCase):

    def patch_in_fake_papi(self):
        papi_fake = FakeSynchronousProvisioningAPI()
        patch = MonkeyPatch(
            "maasserver.provisioning.get_provisioning_api_proxy",
            lambda: papi_fake)
        self.useFixture(patch)
        return papi_fake

    def test_patch_in_fake_papi(self):
        # patch_in_fake_papi() patches in a fake provisioning API so that we
        # can observe what the signal handlers are doing.
        papi = provisioning.get_provisioning_api_proxy()
        papi_fake = self.patch_in_fake_papi()
        self.assertIsNot(provisioning.get_provisioning_api_proxy(), papi)
        self.assertIs(provisioning.get_provisioning_api_proxy(), papi_fake)
        # The fake has small database, and it's empty to begin with.
        self.assertEqual({}, papi_fake.distros)
        self.assertEqual({}, papi_fake.profiles)
        self.assertEqual({}, papi_fake.nodes)

    def test_provision_post_save_Node_create(self):
        # Creating and saving a node automatically creates a dummy distro and
        # profile too, and associates it with the new node.
        papi_fake = self.patch_in_fake_papi()
        node_model = Node(system_id="frank")
        provisioning.provision_post_save_Node(
            sender=Node, instance=node_model, created=True)
        self.assertEqual(["frank"], sorted(papi_fake.nodes))
        node = papi_fake.nodes["frank"]
        profile_name = node["profile"]
        self.assertIn(profile_name, papi_fake.profiles)
        profile = papi_fake.profiles[profile_name]
        distro_name = profile["distro"]
        self.assertIn(distro_name, papi_fake.distros)

    def test_provision_post_save_Node_update(self):
        # Saving an existing node does not change the profile or distro
        # associated with it.
        papi_fake = self.patch_in_fake_papi()
        node_model = Node(system_id="frank")
        provisioning.provision_post_save_Node(
            sender=Node, instance=node_model, created=True)
        # Record the current profile name.
        node = papi_fake.nodes["frank"]
        profile_name1 = node["profile"]
        # Update the model node.
        provisioning.provision_post_save_Node(
            sender=Node, instance=node_model, created=False)
        # The profile name is unchanged.
        node = papi_fake.nodes["frank"]
        profile_name2 = node["profile"]
        self.assertEqual(profile_name1, profile_name2)

    def test_provision_post_delete_Node(self):
        papi_fake = self.patch_in_fake_papi()
        node_model = Node(system_id="frank")
        provisioning.provision_post_save_Node(
            sender=Node, instance=node_model, created=True)
        provisioning.provision_post_delete_Node(
            sender=Node, instance=node_model)
        # The node is deleted, but the profile and distro remain.
        self.assertNotEqual({}, papi_fake.distros)
        self.assertNotEqual({}, papi_fake.profiles)
        self.assertEqual({}, papi_fake.nodes)
