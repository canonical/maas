#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the removed VM host (KVM) API endpoints.

VM host support has been removed from MAAS. The endpoints are kept for
backwards compatibility but must respond with HTTP 410 Gone.
"""

import http.client

from django.urls import reverse

from maasserver.testing.api import APITestCase


class TestVmHostEndpointsGone(APITestCase.ForUser):
    scenarios = (
        (
            "pods",
            {"uri_name": "pods_handler", "args": []},
        ),
        (
            "pod",
            {"uri_name": "pod_handler", "args": ["1"]},
        ),
        (
            "vm_hosts",
            {"uri_name": "vm_hosts_handler", "args": []},
        ),
        (
            "vm_host",
            {"uri_name": "vm_host_handler", "args": ["1"]},
        ),
        (
            "vm_clusters",
            {"uri_name": "vm_clusters_handler", "args": []},
        ),
        (
            "vm_cluster",
            {"uri_name": "vm_cluster_handler", "args": ["1"]},
        ),
        (
            "virtual_machines",
            {"uri_name": "virtual_machines_handler", "args": []},
        ),
        (
            "virtual_machine",
            {"uri_name": "virtual_machine_handler", "args": ["1"]},
        ),
    )

    def test_read_returns_gone(self):
        response = self.client.get(reverse(self.uri_name, args=self.args))
        self.assertEqual(http.client.GONE, response.status_code)
        self.assertIn(b"removed", response.content)
