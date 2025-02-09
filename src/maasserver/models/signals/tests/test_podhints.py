# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test PodHints signals."""

from maasserver.models.signals import podhints as podhints_module
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestCreatePodChanged(MAASServerTestCase):
    def test_node_removed(self):
        self.patch(podhints_module, "post_commit_do")
        pod = factory.make_Pod()
        node = factory.make_Node(memory=2048)
        pod.hints.nodes.add(node)
        pod.sync_hints_from_nodes()
        self.assertEqual(2048, pod.memory)
        pod.hints.nodes.remove(node)
        self.assertEqual(0, reload_object(pod).memory)
