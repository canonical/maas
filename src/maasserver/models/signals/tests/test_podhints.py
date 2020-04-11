# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test PodHints signals."""


from twisted.internet import reactor

from maasserver.models.signals import podhints as podhints_module
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit_hooks, reload_object
from maastesting.matchers import MockCalledOnceWith


class TestCreatePodChanged(MAASServerTestCase):
    def test_node_added(self):
        node = factory.make_Node()
        pod = factory.make_Pod()
        mock_post_commit_do = self.patch(podhints_module, "post_commit_do")
        with post_commit_hooks:
            pod.hints.nodes.add(node)
        self.assertThat(
            mock_post_commit_do,
            MockCalledOnceWith(
                reactor.callLater,
                0,
                podhints_module.request_commissioning_results,
                pod,
                node,
            ),
        )

    def test_node_removed(self):
        self.patch(podhints_module, "post_commit_do")
        pod = factory.make_Pod()
        node = factory.make_Node(memory=2048)
        pod.hints.nodes.add(node)
        pod.sync_hints_from_nodes()
        self.assertEquals(2048, pod.memory)
        pod.hints.nodes.remove(node)
        self.assertEquals(0, reload_object(pod).memory)
