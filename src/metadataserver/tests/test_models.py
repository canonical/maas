# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model tests for metadata server."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver.testing.factory import factory
from maastesting import TestCase
from metadataserver.models import NodeKey


class TestNodeKeyManager(TestCase):
    """Test NodeKeyManager."""

    def test_create_key_registers_node_key(self):
        node = factory.make_node()
        token = NodeKey.objects.create_token(node)
        nodekey = NodeKey.objects.get(node=node, key=token.key)
        self.assertNotEqual(None, nodekey)

    def test_get_node_for_key_finds_node(self):
        node = factory.make_node()
        token = NodeKey.objects.create_token(node)
        self.assertEqual(node, NodeKey.objects.get_node_for_key(token.key))

    def test_get_node_for_key_raises_DoesNotExist_if_key_not_found(self):
        non_key = factory.getRandomString()
        self.assertRaises(
            NodeKey.DoesNotExist, NodeKey.objects.get_node_for_key, non_key)
