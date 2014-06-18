# Copyright 2013-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Celery tasks."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver import tasks
from maasserver.enum import NODEGROUP_STATUS
from maasserver.models import NodeGroup
from maasserver.testing.factory import factory
from maastesting.celery import CeleryFixture
from maastesting.testcase import MAASTestCase
import mock
from testresources import FixtureResource


class TestTasks(MAASTestCase):

    resources = (
        ("celery", FixtureResource(CeleryFixture())),
        )

    def test_import_boot_images_on_schedule_imports_images(self):
        self.patch(NodeGroup, 'import_boot_images')
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        tasks.import_boot_images_on_schedule()
        self.assertEqual(
            [mock.call()],
            nodegroup.import_boot_images.mock_calls)
