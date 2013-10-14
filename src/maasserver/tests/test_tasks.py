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
from maastesting.celery import CeleryFixture
from maastesting.testcase import MAASTestCase
from testresources import FixtureResource
from testtools.matchers import Contains


class TestCleanupOldNonces(MAASTestCase):

    resources = (
        ("celery", FixtureResource(CeleryFixture())),
        )

    def test_cleanup_old_nonces_calls_cleanup_old_nonces(self):
        logger = self.useFixture(FakeLogger('maasserver'))
        nb_cleanups = 3
        mock = self.patch(tasks, 'nonces_cleanup')
        mock.cleanup_old_nonces.return_value = nb_cleanups
        tasks.cleanup_old_nonces()
        mock.cleanup_old_nonces.assert_called_once_with()
        message = "%d expired nonce(s) cleaned up." % nb_cleanups
        self.assertThat(logger.output, Contains(message))
