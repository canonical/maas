# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.core.exceptions import ValidationError

from maasserver.models.nodeconfig import NODE_CONFIG_TYPE, NodeConfig
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestCreateCommissioningNodeConfig(MAASServerTestCase):
    def test_create_for_node(self):
        node = factory.make_Node()
        [node_config] = node.nodeconfig_set.all()
        self.assertIs(node_config.node, node)
        self.assertEqual(node_config.name, "discovered")
        self.assertEqual(node_config, node.current_config)


class TestNodeConfig(MAASServerTestCase):
    def test_unique(self):
        node = factory.make_Node()
        self.assertRaises(
            ValidationError,
            NodeConfig.objects.create,
            node=node,
            name=NODE_CONFIG_TYPE.DISCOVERED,
        )
