# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for RBACSync models."""

__all__ = []

from maasserver.models.rbacsync import RBACSync
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import (
    Equals,
    HasLength,
)


class TestRBACSync(MAASServerTestCase):
    """Test `RBACSync`."""

    def setUp(self):
        super(TestRBACSync, self).setUp()
        # These tests expect the RBACSync table to be empty.
        RBACSync.objects.all().delete()

    def test_changes(self):
        synced = [
            RBACSync.objects.create()
            for _ in range(3)
        ]
        self.assertThat(
            RBACSync.objects.changes(), Equals(synced))

    def test_clear_does_nothing_when_nothing(self):
        self.assertThat(RBACSync.objects.all(), HasLength(0))
        RBACSync.objects.clear()
        self.assertThat(RBACSync.objects.all(), HasLength(0))

    def test_clear_removes_all(self):
        for _ in range(3):
            RBACSync.objects.create()
        self.assertThat(RBACSync.objects.all(), HasLength(3))
        RBACSync.objects.clear()
        self.assertThat(RBACSync.objects.all(), HasLength(0))
