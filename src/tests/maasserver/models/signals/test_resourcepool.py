# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the behaviour of resourcepool signals."""

from django.db import connection

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestPostSaveResourcePoolSignal(MAASServerTestCase):
    def test_save_creates_openfga_tuple(self):
        pool = factory.make_ResourcePool()

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT _user, relation FROM openfga.tuple WHERE object_type = 'pool' AND object_id = '%s'",
                [pool.id],
            )
            openfga_tuple = cursor.fetchone()

        self.assertEqual("maas:0", openfga_tuple[0])
        self.assertEqual("parent", openfga_tuple[1])


class TestPostDeleteResourcePoolSignal(MAASServerTestCase):
    def test_delete_removes_openfga_tuple(self):
        pool = factory.make_ResourcePool()
        pool_id = pool.id

        pool.delete()

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT object_type, object_id, relation FROM openfga.tuple WHERE _user = 'pool:%s'",
                [pool_id],
            )
            openfga_tuple = cursor.fetchone()

        self.assertIsNone(openfga_tuple)
