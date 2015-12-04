# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the behaviour of node signals."""

__all__ = []

from maasserver.enum import NODE_STATUS
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from metadataserver.models.nodekey import NodeKey
from testtools.matchers import (
    Is,
    Not,
)


class TestNodeKeyPolicy(MAASServerTestCase):
    """Test that `NodeKey`s are cleared when nodes change ownership."""

    def test_changing_owner_clears_node_key(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Ensure the node has an owner.
        node.owner = factory.make_User()
        node.save()
        # Ensure there's a token.
        token = NodeKey.objects.get_token_for_node(node)
        self.assertThat(token, Not(Is(None)))
        # Change the owner.
        node.owner = factory.make_User()
        node.save()
        # The token has been deleted.
        token = reload_object(token)
        self.assertThat(token, Is(None))

    def test_clearing_owner_clears_node_key(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Ensure the node has an owner.
        node.owner = factory.make_User()
        node.save()
        # Ensure there's a token.
        token = NodeKey.objects.get_token_for_node(node)
        self.assertThat(token, Not(Is(None)))
        # Remove the owner.
        node.owner = None
        node.save()
        # The token has been deleted.
        token = reload_object(token)
        self.assertThat(token, Is(None))

    def test_setting_owner_clears_node_key(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Ensure the node has no owner.
        node.owner = None
        node.save()
        # Ensure there's a token.
        token = NodeKey.objects.get_token_for_node(node)
        self.assertThat(token, Not(Is(None)))
        # Set the owner.
        node.owner = factory.make_User()
        node.save()
        # The token has been deleted.
        token = reload_object(token)
        self.assertThat(token, Is(None))
