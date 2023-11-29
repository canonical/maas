# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import http.client
import random
from unittest.mock import MagicMock

from django.urls import reverse

from maasserver.models.vmcluster import VMCluster
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes


class VMClusterTestMixin:
    """Mixin to VMCluster tests."""

    def get_cluster_uri(self, cluster):
        """Get the API URI for `machine`."""
        return reverse("vm_cluster_handler", args=[cluster.id])


class TestVMClusters(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/vm-clusters/", reverse("vm_clusters_handler")
        )

    def test_read_lists_clusters(self):
        clusters = [factory.make_VMCluster() for _ in range(3)]
        response = self.client.get(reverse("vm_clusters_handler"))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertCountEqual(
            [cluster.name for cluster in clusters],
            [cluster.get("name") for cluster in parsed_result],
        )


class TestVMCluster(APITestCase.ForUser, VMClusterTestMixin):
    def test_handler_path(self):
        cluster_id = random.randint(0, 10)
        self.assertEqual(
            "/MAAS/api/2.0/vm-clusters/%d" % cluster_id,
            reverse("vm_cluster_handler", args=[cluster_id]),
        )

    def test_read_a_cluster(self):
        cluster = factory.make_VMCluster(pods=2, vms=2)
        response = self.client.get(self.get_cluster_uri(cluster))
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(cluster.name, parsed_result["name"])
        self.assertEqual(cluster.project, parsed_result["project"])
        resources = cluster.total_resources()
        self.assertEqual(
            resources.cores.total, parsed_result["total"]["cores"]
        )
        self.assertEqual(
            resources.memory.general.total, parsed_result["total"]["memory"]
        )
        self.assertEqual(
            resources.storage.total, parsed_result["total"]["local_storage"]
        )
        self.assertEqual(
            resources.cores.free, parsed_result["available"]["cores"]
        )
        self.assertEqual(
            resources.memory.general.free, parsed_result["available"]["memory"]
        )
        self.assertEqual(
            resources.storage.free, parsed_result["available"]["local_storage"]
        )
        self.assertEqual(
            resources.cores.allocated, parsed_result["used"]["cores"]
        )
        self.assertEqual(
            resources.memory.general.allocated, parsed_result["used"]["memory"]
        )
        self.assertEqual(
            resources.storage.allocated, parsed_result["used"]["local_storage"]
        )
        self.assertEqual(resources.vm_count.tracked, parsed_result["vm_count"])
        for name, pool in resources.storage_pools.items():
            self.assertIn(name, parsed_result["storage_pools"])

            parsed_pool = parsed_result["storage_pools"][name]
            self.assertEqual(pool.backend, parsed_pool["backend"])
            self.assertEqual(pool.path, parsed_pool["path"])
            self.assertEqual(pool.free, parsed_pool["free"])
            self.assertEqual(pool.total, parsed_pool["total"])
            self.assertEqual(
                pool.allocated_tracked, parsed_pool["allocated_tracked"]
            )
            self.assertEqual(
                pool.allocated_other, parsed_pool["allocated_other"]
            )

    def test_DELETE_calls_async_delete(self):
        cluster = factory.make_VMCluster()

        response = self.client.delete(self.get_cluster_uri(cluster))
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_PUT_calls_async_update(self):
        cluster = factory.make_VMCluster()

        response = self.client.put(
            self.get_cluster_uri(cluster),
            {"name": "new_name"},
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )


class TestVMClusterAdmin(APITestCase.ForAdmin, VMClusterTestMixin):
    def test_DELETE_calls_async_delete(self):
        cluster = factory.make_VMCluster()
        mock_eventual = MagicMock()
        mock_async_delete = self.patch(VMCluster, "async_delete")
        mock_async_delete.return_value = mock_eventual

        response = self.client.delete(self.get_cluster_uri(cluster))
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        mock_eventual.wait.assert_called_once_with(60)

    def test_UPDATE_calls_async_update(self):
        cluster = factory.make_VMCluster()
        new_name = factory.make_name("cluster")
        response = self.client.put(
            self.get_cluster_uri(cluster),
            {"name": new_name},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_output = json_load_bytes(response.content)
        self.assertEqual(new_name, parsed_output["name"])
