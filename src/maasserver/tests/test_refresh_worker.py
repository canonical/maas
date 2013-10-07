# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the code that refreshes a node-group worker's information."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from apiclient.creds import convert_tuple_to_string
from maasserver import refresh_worker as refresh_worker_module
from maasserver.models.user import get_creds_tuple
from maasserver.refresh_worker import refresh_worker
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.fakemethod import FakeMethod
from provisioningserver import tasks


class TestRefreshWorker(MAASServerTestCase):

    def patch_refresh_functions(self):
        """Replace the worker refresh functions with a test double.

        The test double, which is returned for convenience, contains the
        same keys as the original, but each maps to a `FakeMethod`.

        To verify a refresh task's effect, all that a test needs to do
        is inspect the calls on these fakes.  If the test mis-spells an
        item's name, or tries to inspect a nonexistent item, it will
        fail to find a test double for that item.
        """
        playground_refresh_functions = {
            item: FakeMethod()
            for item in tasks.refresh_functions}
        self.patch(tasks, 'refresh_functions', playground_refresh_functions)
        return playground_refresh_functions

    def test_refreshes_api_credentials(self):
        refresh_functions = self.patch_refresh_functions()
        nodegroup = factory.make_node_group()
        refresh_worker(nodegroup)
        creds_string = convert_tuple_to_string(
            get_creds_tuple(nodegroup.api_token))
        self.assertEqual(
            [(creds_string, )],
            refresh_functions['api_credentials'].extract_args())

    def test_refreshes_nodegroup_uuid(self):
        refresh_functions = self.patch_refresh_functions()
        nodegroup = factory.make_node_group()
        refresh_worker(nodegroup)
        self.assertEqual(
            [(nodegroup.uuid, )],
            refresh_functions['nodegroup_uuid'].extract_args())

    def test_refresh_worker_task_routed_to_nodegroup_worker(self):
        nodegroup = factory.make_node_group()
        task = self.patch(refresh_worker_module, 'refresh_secrets')
        refresh_worker(nodegroup)
        args, kwargs = task.apply_async.call_args
        self.assertEqual(nodegroup.work_queue, kwargs['queue'])
