# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver models."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import os
import shutil

from django.conf import settings
from django.core.exceptions import ValidationError
from maasserver.exceptions import PermissionDenied
from maasserver.models import (
    GENERIC_CONSUMER,
    MACAddress,
    Node,
    NODE_STATUS,
    UserProfile,
    )
from maasserver.testing.factory import factory
from maastesting import TestCase
from piston.models import (
    Consumer,
    KEY_SIZE,
    Token,
    )


class NodeTest(TestCase):

    def test_system_id(self):
        """
        The generated system_id looks good.

        """
        node = factory.make_node()
        self.assertEqual(len(node.system_id), 41)
        self.assertTrue(node.system_id.startswith('node-'))

    def test_display_status(self):
        node = factory.make_node()
        self.assertEqual('New', node.display_status())

    def test_add_mac_address(self):
        node = factory.make_node()
        node.add_mac_address('AA:BB:CC:DD:EE:FF')
        macs = MACAddress.objects.filter(
            node=node, mac_address='AA:BB:CC:DD:EE:FF').count()
        self.assertEqual(1, macs)

    def test_remove_mac_address(self):
        node = factory.make_node()
        node.add_mac_address('AA:BB:CC:DD:EE:FF')
        node.remove_mac_address('AA:BB:CC:DD:EE:FF')
        macs = MACAddress.objects.filter(
            node=node, mac_address='AA:BB:CC:DD:EE:FF').count()
        self.assertEqual(0, macs)


class NodeManagerTest(TestCase):

    def make_node(self, user=None):
        """Create a node, allocated to `user` if given."""
        if user is None:
            status = NODE_STATUS.COMMISSIONED
        else:
            status = NODE_STATUS.DEPLOYED
        return factory.make_node(set_hostname=True, status=status, owner=user)

    def test_get_visible_nodes_for_user_lists_visible_nodes(self):
        """get_visible_nodes lists the nodes a user has access to.

        When run for a regular user it returns unowned nodes, and nodes
        owned by that user.

        """
        user = factory.make_user()
        visible_nodes = [self.make_node(owner) for owner in [None, user]]
        self.make_node(factory.make_user())
        self.assertItemsEqual(
            visible_nodes, Node.objects.get_visible_nodes(user))

    def test_get_visible_nodes_admin_lists_all_nodes(self):
        """get_visible_nodes for an admin lists all nodes."""
        admin = factory.make_admin()
        owners = [
            None,
            factory.make_user(),
            factory.make_admin(),
            admin,
            ]
        nodes = [self.make_node(owner) for owner in owners]
        self.assertItemsEqual(nodes, Node.objects.get_visible_nodes(admin))

    def test_get_visible_nodes_filters_by_id(self):
        """get_visible_nodes optionally filters nodes by system_id."""
        user = factory.make_user()
        nodes = [self.make_node(user) for counter in range(5)]
        ids = [node.system_id for node in nodes]
        wanted_slice = slice(0, 3)
        self.assertItemsEqual(
            nodes[wanted_slice],
            Node.objects.get_visible_nodes(user, ids=ids[wanted_slice]))

    def test_get_visible_nodes_with_ids_still_hides_invisible_nodes(self):
        """Even when passing ids, a user won't get nodes they can't see."""
        user = factory.make_user()
        visible_nodes = [self.make_node(user), self.make_node()]
        invisible_nodes = [self.make_node(factory.make_user())]
        all_ids = [
            node.system_id for node in (visible_nodes + invisible_nodes)]
        self.assertItemsEqual(
            visible_nodes, Node.objects.get_visible_nodes(user, ids=all_ids))

    def test_get_visible_node_or_404_ok(self):
        """get_visible_node_or_404 fetches nodes by system_id."""
        user = factory.make_user()
        node = self.make_node(user)
        self.assertEqual(
            node, Node.objects.get_visible_node_or_404(node.system_id, user))

    def test_get_visible_node_or_404_raises_PermissionDenied(self):
        """get_visible_node_or_404 raises PermissionDenied if the provided
        user cannot access the returned node."""
        user_node = self.make_node(factory.make_user())
        self.assertRaises(
            PermissionDenied,
            Node.objects.get_visible_node_or_404,
            user_node.system_id, factory.make_user())


class MACAddressTest(TestCase):

    def make_MAC(self, address):
        """Create a MAC address."""
        node = Node()
        node.save()
        return MACAddress(mac_address=address, node=node)

    def test_stores_to_database(self):
        mac = self.make_MAC('00:11:22:33:44:55')
        mac.save()
        self.assertEqual([mac], list(MACAddress.objects.all()))

    def test_invalid_address_raises_validation_error(self):
        mac = self.make_MAC('aa:bb:ccxdd:ee:ff')
        self.assertRaises(ValidationError, mac.full_clean)


class UserProfileTest(TestCase):

    def test_profile_creation(self):
        # A profile is created each time a user is created.
        user = factory.make_user()
        self.assertIsInstance(user.get_profile(), UserProfile)
        self.assertEqual(user, user.get_profile().user)

    def test_consumer_creation(self):
        # A generic consumer is created each time a user is created.
        user = factory.make_user()
        consumers = Consumer.objects.filter(user=user, name=GENERIC_CONSUMER)
        self.assertEqual([user], [consumer.user for consumer in consumers])
        self.assertEqual(
            consumers[0], user.get_profile().get_authorisation_consumer())
        self.assertEqual(GENERIC_CONSUMER, consumers[0].name)
        self.assertEqual(KEY_SIZE, len(consumers[0].key))
        # The generic consumer has an empty secret.
        self.assertEqual(0, len(consumers[0].secret))

    def test_token_creation(self):
        # A token is created each time a user is created.
        user = factory.make_user()
        tokens = Token.objects.filter(user=user)
        self.assertEqual([user], [token.user for token in tokens])
        self.assertEqual(
            tokens[0], user.get_profile().get_authorisation_token())
        self.assertIsInstance(tokens[0].key, unicode)
        self.assertEqual(KEY_SIZE, len(tokens[0].key))
        self.assertEqual(Token.ACCESS, tokens[0].token_type)


class FileStorageTest(TestCase):
    """Testing of the :class:`FileStorage` model."""

    FILEPATH = settings.MEDIA_ROOT

    def setUp(self):
        super(FileStorageTest, self).setUp()
        os.mkdir(self.FILEPATH)
        self.addCleanup(shutil.rmtree, self.FILEPATH)

    def test_creation(self):
        storage = factory.make_file_storage(filename="myfile", data="mydata")
        expected = ["myfile", "mydata"]
        actual = [storage.filename, storage.data.read()]
        self.assertEqual(expected, actual)

    def test_creation_writes_a_file(self):
        # The development settings say to write a file starting at
        # /var/tmp/maas, so check one is actually written there.  The field
        # itself is hard-coded to make a directory called "storage".
        factory.make_file_storage(filename="myfile", data="mydata")

        expected_filename = os.path.join(
            self.FILEPATH, "storage", "myfile")

        with open(expected_filename) as f:
            self.assertEqual("mydata", f.read())
