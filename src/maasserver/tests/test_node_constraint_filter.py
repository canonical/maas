# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test node filtering on specific constraints."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver.enum import ARCHITECTURE
from maasserver.exceptions import InvalidConstraint
from maasserver.models import Node
from maasserver.models.node_constraint_filter import (
    constrain_nodes,
    generate_architecture_wildcards,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from maasserver.utils import ignore_unused


class TestConstrainNodes(TestCase):

    def assertConstrainedNodes(self, expected_nodes, constraints):
        nodes = constrain_nodes(Node.objects.all(), constraints)
        self.assertItemsEqual(expected_nodes, nodes)

    def test_generate_architecture_wildcards(self):
        # Create a test architecture choice list of one architecture that only
        # has one available subarch (single_subarch) and two architectures that
        # have a matching primary architecture (double_subarch_{1,2})
        single_subarch = factory.make_name('arch'), factory.make_name('arch')
        double_subarch_1 = factory.make_name('arch'), factory.make_name('arch')
        double_subarch_2 = double_subarch_1[0], factory.make_name('arch')
        choices = (
            ('/'.join(single_subarch), None),
            ('/'.join(double_subarch_1), None),
            ('/'.join(double_subarch_2), None),
        )

        # single_subarch should end up in the dict essentially unchanged, and
        # the double_subarchs should have been flattened into a single dict
        # element with a list of them.
        self.assertEquals({
            single_subarch[0]: frozenset([choices[0][0]]),
            double_subarch_1[0]: frozenset([choices[1][0], choices[2][0]]),
            },
            generate_architecture_wildcards(choices=choices)
        )

    def test_no_constraints(self):
        node1 = factory.make_node()
        node2 = factory.make_node()
        self.assertConstrainedNodes([node1, node2], None)
        self.assertConstrainedNodes([node1, node2], {})

    def test_hostname(self):
        node1 = factory.make_node(set_hostname=True)
        node2 = factory.make_node(set_hostname=True)
        self.assertConstrainedNodes([node1], {'hostname': node1.hostname})
        self.assertConstrainedNodes([node2], {'hostname': node2.hostname})
        self.assertConstrainedNodes([], {'hostname': 'unknown-name'})

    def test_architecture(self):
        node1 = factory.make_node(architecture=ARCHITECTURE.i386)
        node2 = factory.make_node(architecture=ARCHITECTURE.armhf_highbank)
        self.assertConstrainedNodes([node1], {'architecture': 'i386'})
        self.assertConstrainedNodes([node1], {'architecture': 'i386/generic'})
        self.assertConstrainedNodes(
            [node2], {'architecture': 'arm'})
        self.assertConstrainedNodes(
            [node2], {'architecture': 'armhf'})
        self.assertConstrainedNodes(
            [node2], {'architecture': 'armhf/highbank'})
        self.assertRaises(InvalidConstraint,
            self.assertConstrainedNodes, [], {'architecture': 'armhf/generic'})
        self.assertRaises(InvalidConstraint,
            self.assertConstrainedNodes, [], {'architecture': 'sparc'})

    def test_cpu_count(self):
        node1 = factory.make_node(cpu_count=1)
        node2 = factory.make_node(cpu_count=2)
        self.assertConstrainedNodes([node1, node2], {'cpu_count': '0'})
        self.assertConstrainedNodes([node1, node2], {'cpu_count': '1'})
        self.assertConstrainedNodes([node2], {'cpu_count': '2'})
        self.assertConstrainedNodes([], {'cpu_count': '4'})
        self.assertConstrainedNodes([node2], {'cpu_count': '2.0'})
        self.assertConstrainedNodes([node2], {'cpu_count': '1.2'})
        self.assertRaises(InvalidConstraint,
            self.assertConstrainedNodes, [], {'cpu_count': 'notint'})

    def test_memory(self):
        node1 = factory.make_node(memory=1024)
        node2 = factory.make_node(memory=4096)
        self.assertConstrainedNodes([node1, node2], {'memory': '512'})
        self.assertConstrainedNodes([node1, node2], {'memory': '1024'})
        self.assertConstrainedNodes([node2], {'memory': '2048'})
        self.assertConstrainedNodes([node2], {'memory': '4096'})
        self.assertConstrainedNodes([], {'memory': '8192'})
        self.assertConstrainedNodes([node2], {'memory': '4096.0'})
        self.assertRaises(InvalidConstraint,
            self.assertConstrainedNodes, [], {'memory': 'notint'})

    def test_tags(self):
        tag_big = factory.make_tag(name='big')
        tag_burly = factory.make_tag(name='burly')
        node_big = factory.make_node()
        node_big.tags.add(tag_big)
        node_burly = factory.make_node()
        node_burly.tags.add(tag_burly)
        node_bignburly = factory.make_node()
        node_bignburly.tags.add(tag_big)
        node_bignburly.tags.add(tag_burly)
        self.assertConstrainedNodes([node_big, node_bignburly],
                                    {'tags': 'big'})
        self.assertConstrainedNodes([node_burly, node_bignburly],
                                    {'tags': 'burly'})
        self.assertConstrainedNodes([node_bignburly],
                                    {'tags': 'big,burly'})
        self.assertConstrainedNodes([node_bignburly],
                                    {'tags': 'big burly'})
        self.assertRaises(InvalidConstraint,
            self.assertConstrainedNodes, [], {'tags': 'big unknown'})

    def test_combined_constraints(self):
        tag_big = factory.make_tag(name='big')
        node_big = factory.make_node(architecture=ARCHITECTURE.i386)
        node_big.tags.add(tag_big)
        node_small = factory.make_node(architecture=ARCHITECTURE.i386)
        ignore_unused(node_small)
        node_big_arm = factory.make_node(
            architecture=ARCHITECTURE.armhf_highbank)
        node_big_arm.tags.add(tag_big)
        self.assertConstrainedNodes([node_big, node_big_arm],
                                    {'tags': 'big'})
        self.assertConstrainedNodes(
            [node_big], {'architecture': 'i386/generic', 'tags': 'big'})
