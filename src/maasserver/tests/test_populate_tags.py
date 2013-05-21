# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the code that refreshes a node-group worker's information."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver import populate_tags as populate_tags_module
from maasserver.populate_tags import populate_tags
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
import mock


class TestPopulateTags(TestCase):

    def test_populate_tags_task_routed_to_nodegroup_worker(self):
        nodegroup = factory.make_node_group()
        tag = factory.make_tag()
        task = self.patch(populate_tags_module, 'update_node_tags')
        populate_tags(tag)
        args, kwargs = task.apply_async.call_args
        self.assertEqual(nodegroup.work_queue, kwargs['queue'])

    def test_populate_tags_task_routed_to_all_nodegroup_workers(self):
        nodegroups = [factory.make_node_group() for i in range(5)]
        tag = factory.make_tag()
        refresh = self.patch(populate_tags_module, 'refresh_worker')
        task = self.patch(populate_tags_module, 'update_node_tags')
        populate_tags(tag)
        refresh_calls = [mock.call(nodegroup) for nodegroup in nodegroups]
        refresh.assert_has_calls(refresh_calls, any_order=True)
        task_calls = [mock.call(queue=nodegroup.work_queue,
                               kwargs={
                                 'tag_name': tag.name,
                                 'tag_definition': tag.definition,
                                 })
                     for nodegroup in nodegroups]
        task.apply_async.assert_has_calls(task_calls, any_order=True)
