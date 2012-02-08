# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver models."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
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

    def make_user_and_node(self, admin=False):
        if admin:
            user = factory.make_admin()
        else:
            user = factory.make_user()
        node = factory.make_node(
            set_hostname=True, status=NODE_STATUS.DEPLOYED,
            owner=user)
        return user, node

    def test_get_visible_nodes_user(self):
        """get_visible_nodes returns the nodes a user has access to."""
        anon_node = factory.make_node()
        admin, admin_node = self.make_user_and_node(admin=True)
        user, user_node = self.make_user_and_node()

        visible_nodes = Node.objects.get_visible_nodes(user)

        self.assertSequenceEqual([anon_node, user_node], visible_nodes)

    def test_get_visible_nodes_admin(self):
        """get_visible_nodes returns all the nodes if the user used for the
        permission check is an admin."""
        anon_node = factory.make_node()
        user, user_node = self.make_user_and_node()
        admin, admin_node = self.make_user_and_node(admin=True)
        visible_nodes = Node.objects.get_visible_nodes(admin)

        self.assertSequenceEqual(
            [anon_node, user_node, admin_node], visible_nodes)

    def test_get_visible_node_or_404_ok(self):
        """get_visible_node_or_404 fetches nodes by system_id."""
        user, user_node = self.make_user_and_node()
        node = Node.objects.get_visible_node_or_404(user_node.system_id, user)

        self.assertEqual(user_node, node)

    def test_get_visible_node_or_404_raise_PermissionDenied(self):
        """get_visible_node_or_404 raise PermissionDenied if the provided user
        cannot access the returned node."""
        _, user_node = self.make_user_and_node()
        another_user = factory.make_user()

        self.assertRaises(
            PermissionDenied, Node.objects.get_visible_node_or_404,
            user_node.system_id, another_user)


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
        self.assertEqual(GENERIC_CONSUMER, consumers[0].name)
        self.assertEqual(KEY_SIZE, len(consumers[0].key))
        # The generic consumer has an empty secret.
        self.assertEqual(0, len(consumers[0].secret))

    def test_token_creation(self):
        # A token is created each time a user is created.
        user = factory.make_user()
        tokens = Token.objects.filter(user=user)
        self.assertEqual([user], [token.user for token in tokens])
        self.assertIsInstance(tokens[0].key, unicode)
        self.assertEqual(KEY_SIZE, len(tokens[0].key))
        self.assertEqual(Token.ACCESS, tokens[0].token_type)
