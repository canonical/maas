# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import http.client
import random

from django.urls import reverse

from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes


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


class TestVMCluster(APITestCase.ForUser):
    def test_handler_path(self):
        cluster_id = random.randint(0, 10)
        self.assertEqual(
            "/MAAS/api/2.0/vm-clusters/%d" % cluster_id,
            reverse("vm_cluster_handler", args=[cluster_id]),
        )

    def test_read_a_cluster(self):
        cluster = factory.make_VMCluster()
        response = self.client.get(
            reverse("vm_cluster_handler", args=[cluster.id])
        )
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
