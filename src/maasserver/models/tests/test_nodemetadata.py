# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver NodeMetadata model."""


from django.core.exceptions import ValidationError

from maasserver.models import NodeMetadata
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maastesting.crochet import wait_for

wait_for_reactor = wait_for()


class TestNodeMetadata(MAASServerTestCase):
    def test_str(self):
        # A NodeMetadata object string representation references the parent
        # node hostname.
        node = factory.make_Machine(hostname="foobar")
        entry = factory.make_NodeMetadata(node=node, key="key")
        self.assertEqual("NodeMetadata (foobar/key)", str(entry))

    def test_unique_on_node_and_key(self):
        # We can only ever have one NodeMetadata object for a particular node
        # and key.
        entry = factory.make_NodeMetadata()
        self.assertRaises(
            ValidationError,
            factory.make_NodeMetadata,
            node=entry.node,
            key=entry.key,
        )

    def test_multiple_keys_on_node(self):
        # We can only ever have one NodeMetadata object for a particular node
        # and key.
        entry1 = factory.make_NodeMetadata(key="key1", value="value")
        entry2 = factory.make_NodeMetadata(
            node=entry1.node, key="key2", value="value"
        )
        self.assertNotEqual(entry1, entry2)

    def test_get(self):
        node = factory.make_Node()
        key = factory.make_name("key")
        default = factory.make_name("default")
        self.assertEqual(
            default,
            NodeMetadata.objects.get(node=node, key=key, default=default),
        )

    def test_release_volatile(self):
        from metadataserver.vendor_data import (
            LXD_CERTIFICATE_METADATA_KEY,
            VIRSH_PASSWORD_METADATA_KEY,
        )

        node = factory.make_Node()
        dummy = factory.make_NodeMetadata(node=node)
        cred_virsh = factory.make_NodeMetadata(
            key=VIRSH_PASSWORD_METADATA_KEY, node=node
        )
        cred_lxd = factory.make_NodeMetadata(
            key=LXD_CERTIFICATE_METADATA_KEY, node=node
        )

        NodeMetadata.objects.release_volatile(node)
        self.assertIsNotNone(reload_object(dummy))
        self.assertIsNone(reload_object(cred_virsh))
        self.assertIsNone(reload_object(cred_lxd))
