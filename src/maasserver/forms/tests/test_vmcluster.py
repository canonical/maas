# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import MagicMock

from maasserver.forms.vmcluster import UpdateVMClusterForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase


class TestVUpdateVMClusterForm(MAASTransactionServerTestCase):
    def setUp(self):
        super().setUp()
        self.request = MagicMock()
        self.request.user = factory.make_User()

    def test_updates_cluster(self):
        zone = factory.make_Zone()
        pool = factory.make_ResourcePool()

        orig_cluster = factory.make_VMCluster(
            zone=zone,
            pool=pool,
        )
        new_name = factory.make_name("cluster")
        form = UpdateVMClusterForm(
            data={"name": new_name},
            request=self.request,
            instance=orig_cluster,
        )
        self.assertTrue(form.is_valid(), form._errors)
        cluster = form.save()
        self.assertEqual(new_name, cluster.name)
        self.assertEqual(zone, cluster.zone)
        self.assertEqual(pool, cluster.pool)

    def test_updates_cluster_zone_and_pool(self):
        zone = factory.make_Zone()
        pool = factory.make_ResourcePool()
        new_name = factory.make_name("cluster")
        cluster_info = {
            "name": new_name,
            "zone": zone.name,
            "pool": pool.name,
        }
        orig_cluster = factory.make_VMCluster()
        form = UpdateVMClusterForm(
            data=cluster_info, request=self.request, instance=orig_cluster
        )
        self.assertTrue(form.is_valid(), form._errors)
        cluster = form.save()
        self.assertEqual(cluster.id, orig_cluster.id)
        self.assertEqual(cluster.zone, zone)
        self.assertEqual(cluster.pool, pool)
        self.assertEqual(cluster.name, new_name)
