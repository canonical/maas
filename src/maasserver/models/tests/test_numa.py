# Copyright 2013-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.core.exceptions import ValidationError

from maasserver.models.numa import NUMANodeHugepages
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestCreateDefaultNUMANode(MAASServerTestCase):
    def test_create_for_machine(self):
        node = factory.make_Node(memory=1024, cpu_count=4)
        # the default NUMA node is created automatically on node creation
        numa_node = node.default_numanode
        self.assertIs(numa_node.node, node)
        self.assertEqual(numa_node.index, 0)
        self.assertEqual(numa_node.memory, 1024)
        self.assertEqual(numa_node.cores, [0, 1, 2, 3])


class TestNUMANodeHugepages(MAASServerTestCase):
    def test_unique(self):
        numa_node = factory.make_NUMANode()
        NUMANodeHugepages.objects.create(
            numanode=numa_node, page_size=2048, total=20480
        )
        self.assertRaises(
            ValidationError,
            NUMANodeHugepages.objects.create,
            numanode=numa_node,
            page_size=2048,
            total=20480,
        )
