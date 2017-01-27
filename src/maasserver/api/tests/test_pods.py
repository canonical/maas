# Copyright 2016-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for pods API."""

__all__ = []

import http.client
import random

from django.core.urlresolvers import reverse
from maasserver import forms
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object
from provisioningserver.drivers.pod import (
    Capabilities,
    DiscoveredPod,
    DiscoveredPodHints,
)


class TestPodsAPI(APITestCase.ForUser):

    def make_pod_info(self):
        # Use virsh pod type as the required fields are specific to the
        # type of pod being created.
        pod_type = 'virsh'
        pod_ip_adddress = factory.make_ipv4_address()
        pod_power_address = 'qemu+ssh://user@%s/system' % pod_ip_adddress
        pod_password = factory.make_name('password')
        return {
            'type': pod_type,
            'power_address': pod_power_address,
            'power_pass': pod_password,
            'ip_address': pod_ip_adddress,
        }

    def test_handler_path(self):
        self.assertEqual(
            '/api/2.0/pods/', reverse('pods_handler'))

    def test_read_lists_pods(self):
        factory.make_BMC()
        pods = [
            factory.make_Pod()
            for _ in range(3)
        ]
        response = self.client.get(reverse('pods_handler'))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertItemsEqual(
            [pod.id for pod in pods],
            [pod.get('id') for pod in parsed_result])

    def test_read_returns_limited_fields(self):
        factory.make_Pod(capabilities=[Capabilities.FIXED_LOCAL_STORAGE])
        response = self.client.get(reverse('pods_handler'))
        parsed_result = json_load_bytes(response.content)
        self.assertItemsEqual(
            [
                'id',
                'name',
                'type',
                'resource_uri',
                'capabilities',
                'architectures',
                'total',
                'used',
                'available',
            ],
            list(parsed_result[0]))
        self.assertItemsEqual(
            [
                'cores',
                'memory',
                'local_storage',
                'local_disks',
            ],
            list(parsed_result[0]['total']))
        self.assertItemsEqual(
            [
                'cores',
                'memory',
                'local_storage',
                'local_disks',
            ],
            list(parsed_result[0]['used']))
        self.assertItemsEqual(
            [
                'cores',
                'memory',
                'local_storage',
                'local_disks',
            ],
            list(parsed_result[0]['available']))

    def test_create_requires_admin(self):
        response = self.client.post(
            reverse('pods_handler'), self.make_pod_info())
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_create_creates_pod(self):
        self.become_admin()
        discovered_pod = DiscoveredPod(
            architectures=['amd64/generic'],
            cores=random.randint(2, 4), memory=random.randint(1024, 4096),
            local_storage=random.randint(1024, 1024 * 1024),
            cpu_speed=random.randint(2048, 4048),
            hints=DiscoveredPodHints(
                cores=random.randint(2, 4), memory=random.randint(1024, 4096),
                local_storage=random.randint(1024, 1024 * 1024),
                cpu_speed=random.randint(2048, 4048)))
        discovered_rack_1 = factory.make_RackController()
        discovered_rack_2 = factory.make_RackController()
        failed_rack = factory.make_RackController()
        self.patch(forms, "discover_pod").return_value = ({
            discovered_rack_1.system_id: discovered_pod,
            discovered_rack_2.system_id: discovered_pod,
        }, {
            failed_rack.system_id: factory.make_exception(),
        })
        pod_info = self.make_pod_info()
        response = self.client.post(reverse('pods_handler'), pod_info)
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(parsed_result['type'], pod_info['type'])

    def test_create_duplicate_provides_nice_error(self):
        self.become_admin()
        pod_info = self.make_pod_info()
        discovered_pod = DiscoveredPod(
            architectures=['amd64/generic'],
            cores=random.randint(2, 4), memory=random.randint(1024, 4096),
            local_storage=random.randint(1024, 1024 * 1024),
            cpu_speed=random.randint(2048, 4048),
            hints=DiscoveredPodHints(
                cores=random.randint(2, 4), memory=random.randint(1024, 4096),
                local_storage=random.randint(1024, 1024 * 1024),
                cpu_speed=random.randint(2048, 4048)))
        discovered_rack_1 = factory.make_RackController()
        discovered_rack_2 = factory.make_RackController()
        failed_rack = factory.make_RackController()
        self.patch(forms, "discover_pod").return_value = ({
            discovered_rack_1.system_id: discovered_pod,
            discovered_rack_2.system_id: discovered_pod,
        }, {
            failed_rack.system_id: factory.make_exception(),
        })
        response = self.client.post(reverse('pods_handler'), pod_info)
        self.assertEqual(http.client.OK, response.status_code)
        response = self.client.post(reverse('pods_handler'), pod_info)
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_create_proper_return_on_exception(self):
        self.become_admin()
        failed_rack = factory.make_RackController()
        self.patch(forms, "discover_pod").return_value = ({}, {
            failed_rack.system_id: factory.make_exception(),
        })

        response = self.client.post(
            reverse('pods_handler'), self.make_pod_info())
        self.assertEqual(http.client.SERVICE_UNAVAILABLE, response.status_code)


def get_pod_uri(pod):
    """Return a pod URI on the API."""
    return reverse('pod_handler', args=[pod.id])


class TestPodAPI(APITestCase.ForUser):

    def test_handler_path(self):
        pod_id = random.randint(0, 10)
        self.assertEqual(
            '/api/2.0/pods/%s/' % pod_id,
            reverse('pod_handler', args=[pod_id]))

    def test_GET_reads_pod(self):
        pod = factory.make_Pod()
        response = self.client.get(get_pod_uri(pod))
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_pod = json_load_bytes(response.content)
        self.assertEqual(pod.id, parsed_pod["id"])

    def test_DELETE_removes_pod(self):
        self.become_admin()
        pod = factory.make_Pod()
        response = self.client.delete(get_pod_uri(pod))
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(pod))

    def test_DELETE_rejects_deletion_if_not_permitted(self):
        pod = factory.make_Pod()
        response = self.client.delete(get_pod_uri(pod))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertEqual(pod, reload_object(pod))
