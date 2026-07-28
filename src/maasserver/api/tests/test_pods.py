# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

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
            {
                "uri_name": "pods_handler",
                "args": [],
                "gone_methods": ["get", "post"],
            },
        ),
        (
            "pod",
            {
                "uri_name": "pod_handler",
                "args": ["1"],
                "gone_methods": ["get", "put", "delete"],
            },
        ),
        (
            "vm_hosts",
            {
                "uri_name": "vm_hosts_handler",
                "args": [],
                "gone_methods": ["get", "post"],
            },
        ),
        (
            "vm_host",
            {
                "uri_name": "vm_host_handler",
                "args": ["1"],
                "gone_methods": ["get", "put", "delete"],
            },
        ),
        (
            "vm_clusters",
            {
                "uri_name": "vm_clusters_handler",
                "args": [],
                "gone_methods": ["get"],
            },
        ),
        (
            "vm_cluster",
            {
                "uri_name": "vm_cluster_handler",
                "args": ["1"],
                "gone_methods": ["get", "put", "delete"],
            },
        ),
        (
            "virtual_machines",
            {
                "uri_name": "virtual_machines_handler",
                "args": [],
                "gone_methods": ["get"],
            },
        ),
        (
            "virtual_machine",
            {
                "uri_name": "virtual_machine_handler",
                "args": ["1"],
                "gone_methods": ["get"],
            },
        ),
    )

    def test_endpoints_return_gone(self):
        uri = reverse(self.uri_name, args=self.args)
        for method in self.gone_methods:
            response = getattr(self.client, method)(uri)
            self.assertEqual(
                http.client.GONE,
                response.status_code,
                f"{method.upper()} {uri} did not return 410 Gone",
            )
            self.assertIn(b"removed", response.content)
