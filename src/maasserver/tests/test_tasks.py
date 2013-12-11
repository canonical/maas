# Copyright 2013 Canonical Ltd.  This software is licensed under the
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

from fixtures import FakeLogger
from maasserver import tasks
from maasserver.enum import NODEGROUP_STATUS
from maasserver.testing.factory import factory
from maasserver.models import NodeGroup
from maastesting.celery import CeleryFixture
from maastesting.testcase import MAASTestCase
import mock
from testresources import FixtureResource
from testtools.matchers import Contains


class TestCleanupOldNonces(MAASTestCase):

    resources = (
        ("celery", FixtureResource(CeleryFixture())),
        )

    def test_cleanup_old_nonces_calls_cleanup_old_nonces(self):
        logger = self.useFixture(FakeLogger('maasserver'))
        nb_cleanups = 3
        fake = self.patch(tasks, 'nonces_cleanup')
        fake.cleanup_old_nonces.return_value = nb_cleanups
        tasks.cleanup_old_nonces()
        self.assertEqual(
            [mock.call()],
            fake.cleanup_old_nonces.mock_calls)
        message = "%d expired nonce(s) cleaned up." % nb_cleanups
        self.assertThat(logger.output, Contains(message))

    def test_import_boot_images_on_schedule_imports_images(self):
        self.patch(NodeGroup, 'import_boot_images')
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        tasks.import_boot_images_on_schedule()
        self.assertEqual(
            [mock.call()],
            nodegroup.import_boot_images.mock_calls)
