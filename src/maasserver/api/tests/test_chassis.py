# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for chassis API."""

__all__ = []

import http.client
import random

from django.core.urlresolvers import reverse
from maasserver import forms
from maasserver.clusterrpc.driver_parameters import (
    DriverType,
    get_driver_choices,
)
from maasserver.enum import (
    NODE_STATUS,
    NODE_TYPE,
)
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object
from provisioningserver.drivers.chassis import (
    DiscoveredChassis,
    DiscoveredChassisHints,
)


class TestChassisAPI(APITestCase.ForUser):

    def test_handler_path(self):
        self.assertEqual(
            '/api/2.0/chassis/', reverse('chassis_handler'))

    def create_chassis(self, owner, nb=3):
        return [
            factory.make_Node(
                interface=True, node_type=NODE_TYPE.CHASSIS, owner=owner)
            for _ in range(nb)
        ]

    def test_read_lists_chassis(self):
        # The api allows for fetching the list of chassis.
        chassis = self.create_chassis(owner=self.user)
        factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.user)
        response = self.client.get(reverse('chassis_handler'))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertItemsEqual(
            [chassi.system_id for chassi in chassis],
            [chassi.get('system_id') for chassi in parsed_result])

    def test_read_ignores_nodes(self):
        factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.user)
        response = self.client.get(reverse('chassis_handler'))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            [],
            [chassi.get('system_id') for chassi in parsed_result])

    def test_read_with_id_returns_matching_chassis(self):
        # The "list" operation takes optional "id" parameters.  Only
        # chassis with matching ids will be returned.
        chassis = self.create_chassis(owner=self.user)
        ids = [chassi.system_id for chassi in chassis]
        matching_id = ids[0]
        response = self.client.get(reverse('chassis_handler'), {
            'id': [matching_id],
        })
        parsed_result = json_load_bytes(response.content)
        self.assertItemsEqual(
            [matching_id],
            [chassi.get('system_id') for chassi in parsed_result])

    def test_read_returns_limited_fields(self):
        self.create_chassis(owner=self.user)
        response = self.client.get(reverse('chassis_handler'))
        parsed_result = json_load_bytes(response.content)
        self.assertItemsEqual(
            [
                'hostname',
                'system_id',
                'architectures',
                'cpu_count',
                'memory',
                'chassis_type',
                'node_type',
                'node_type_name',
                'resource_uri',
            ],
            list(parsed_result[0]))

    def test_create_requires_admin(self):
        chassis_type = random.choice(
            get_driver_choices(driver_type=DriverType.chassis))[0]
        response = self.client.post(reverse('chassis_handler'), {
            "chassis_type": chassis_type,
        })
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_create_creates_chassis(self):
        self.become_admin()
        discovered_chassis = DiscoveredChassis(
            architecture='amd64/generic',
            cores=random.randint(2, 4), memory=random.randint(1024, 4096),
            local_storage=random.randint(1024, 1024 * 1024),
            cpu_speed=random.randint(2048, 4048),
            hints=DiscoveredChassisHints(
                cores=random.randint(2, 4), memory=random.randint(1024, 4096),
                local_storage=random.randint(1024, 1024 * 1024),
                cpu_speed=random.randint(2048, 4048)))
        discovered_rack_1 = factory.make_RackController()
        discovered_rack_2 = factory.make_RackController()
        failed_rack = factory.make_RackController()
        self.patch(forms, "discover_chassis").return_value = ({
            discovered_rack_1.system_id: discovered_chassis,
            discovered_rack_2.system_id: discovered_chassis,
        }, {
            failed_rack.system_id: factory.make_exception(),
        })
        chassis_type = random.choice(
            get_driver_choices(driver_type=DriverType.chassis))[0]

        response = self.client.post(reverse('chassis_handler'), {
            "chassis_type": chassis_type,
        })
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(parsed_result['chassis_type'], chassis_type)

    def test_create_proper_return_on_exception(self):
        self.become_admin()
        failed_rack = factory.make_RackController()
        self.patch(forms, "discover_chassis").return_value = ({}, {
            failed_rack.system_id: factory.make_exception(),
        })
        chassis_type = random.choice(
            get_driver_choices(driver_type=DriverType.chassis))[0]

        response = self.client.post(reverse('chassis_handler'), {
            "chassis_type": chassis_type,
        })
        self.assertEqual(http.client.SERVICE_UNAVAILABLE, response.status_code)


def get_chassi_uri(chassis):
    """Return a chassis URI on the API."""
    return reverse('chassi_handler', args=[chassis.system_id])


class TestChassiAPI(APITestCase.ForUser):

    def test_handler_path(self):
        system_id = factory.make_name('system-id')
        self.assertEqual(
            '/api/2.0/chassis/%s/' % system_id,
            reverse('chassi_handler', args=[system_id]))

    def test_GET_reads_chassis(self):
        chassis = factory.make_Node(
            node_type=NODE_TYPE.CHASSIS, owner=self.user)

        response = self.client.get(get_chassi_uri(chassis))
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_chassis = json_load_bytes(response.content)
        self.assertEqual(chassis.system_id, parsed_chassis["system_id"])

    def test_DELETE_removes_chassis(self):
        self.become_admin()
        chassis = factory.make_Node(
            node_type=NODE_TYPE.CHASSIS, owner=self.user)
        response = self.client.delete(get_chassi_uri(chassis))
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(chassis))

    def test_DELETE_rejects_deletion_if_not_permitted(self):
        chassis = factory.make_Node(
            node_type=NODE_TYPE.CHASSIS, owner=factory.make_User())
        response = self.client.delete(get_chassi_uri(chassis))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertEqual(chassis, reload_object(chassis))
