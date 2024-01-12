# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for RBACSync models."""

from maasserver.models.rbacsync import RBACSync
from maasserver.testing.testcase import MAASServerTestCase


class TestRBACSync(MAASServerTestCase):
    """Test `RBACSync`."""

    def setUp(self):
        super().setUp()
        # These tests expect the RBACSync table to be empty.
        RBACSync.objects.all().delete()

    def test_changes(self):
        resource_type = "resource-pool"
        synced = [
            RBACSync.objects.create(resource_type=resource_type)
            for _ in range(3)
        ] + [RBACSync.objects.create(resource_type="")]
        self.assertEqual(synced, RBACSync.objects.changes(resource_type))

    def test_clear_does_nothing_when_nothing(self):
        self.assertEqual(RBACSync.objects.all().count(), 0)
        RBACSync.objects.clear("resource-pool")
        self.assertEqual(RBACSync.objects.all().count(), 0)

    def test_clear_removes_all(self):
        resource_type = "resource-pool"
        for _ in range(3):
            RBACSync.objects.create(resource_type=resource_type)
        RBACSync.objects.create(resource_type="")
        self.assertEqual(RBACSync.objects.all().count(), 4)
        RBACSync.objects.clear(resource_type)
        self.assertEqual(RBACSync.objects.all().count(), 0)
