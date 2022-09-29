# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test Service model and manager."""


import random

from testtools.matchers import Equals, HasLength, MatchesStructure

from maasserver.enum import NODE_TYPE, SERVICE_STATUS, SERVICE_STATUS_CHOICES
from maasserver.models.service import (
    DEAD_STATUSES,
    RACK_SERVICES,
    REGION_SERVICES,
    Service,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestServiceManager(MAASServerTestCase):
    def test_create_services_for_machine(self):
        machine = factory.make_Node()
        Service.objects.create_services_for(machine)
        self.assertThat(Service.objects.filter(node=machine), HasLength(0))

    def test_create_services_for_device(self):
        device = factory.make_Device()
        Service.objects.create_services_for(device)
        self.assertThat(Service.objects.filter(node=device), HasLength(0))

    def test_create_services_for_rack_controller(self):
        controller = factory.make_RackController()
        Service.objects.create_services_for(controller)
        self.assertThat(
            Service.objects.filter(node=controller),
            HasLength(len(RACK_SERVICES)),
        )

    def test_create_services_for_region_controller(self):
        controller = factory.make_RegionController()
        Service.objects.create_services_for(controller)
        self.assertThat(
            Service.objects.filter(node=controller),
            HasLength(len(REGION_SERVICES)),
        )

    def test_create_services_for_region_rack_controller(self):
        controller = factory.make_RegionController()
        controller.node_type = NODE_TYPE.REGION_AND_RACK_CONTROLLER
        controller.save()
        Service.objects.create_services_for(controller)
        services = Service.objects.filter(node=controller)
        self.assertEqual(
            REGION_SERVICES | RACK_SERVICES,
            {service.name for service in services},
        )

    def test_create_services_removes_services(self):
        controller = factory.make_RegionController()
        Service.objects.create_services_for(controller)
        services = Service.objects.filter(node=controller)
        self.assertEqual(
            REGION_SERVICES, {service.name for service in services}
        )

        controller.node_type = NODE_TYPE.MACHINE
        controller.save()
        Service.objects.create_services_for(controller)
        services = Service.objects.filter(node=controller)
        self.assertThat({service.name for service in services}, HasLength(0))

    def test_create_services_replaces_services(self):
        controller = factory.make_RegionController()
        Service.objects.create_services_for(controller)
        services = Service.objects.filter(node=controller)
        self.assertEqual(
            REGION_SERVICES, {service.name for service in services}
        )

        controller.node_type = NODE_TYPE.RACK_CONTROLLER
        controller.save()
        Service.objects.create_services_for(controller)
        services = Service.objects.filter(node=controller)
        self.assertEqual(RACK_SERVICES, {service.name for service in services})

    def test_update_service_for_updates_service_status_and_info(self):
        controller = factory.make_RegionController()
        Service.objects.create_services_for(controller)
        service = random.choice(list(REGION_SERVICES))
        status = factory.pick_choice(SERVICE_STATUS_CHOICES)
        info = factory.make_name("info")
        observed = Service.objects.update_service_for(
            controller, service, status, info
        )
        self.assertThat(
            reload_object(observed),
            MatchesStructure.byEquality(
                node=controller, name=service, status=status, status_info=info
            ),
        )

    def test_mark_dead_for_region_controller(self):
        controller = factory.make_RegionController()
        Service.objects.create_services_for(controller)
        Service.objects.mark_dead(controller, dead_region=True)
        for service in Service.objects.filter(node=controller):
            self.expectThat(
                (service.status, service.status_info),
                Equals((DEAD_STATUSES[service.name], "")),
            )

    def test_mark_dead_for_rack_controller(self):
        controller = factory.make_RackController()
        Service.objects.create_services_for(controller)
        Service.objects.mark_dead(controller, dead_rack=True)
        for service in Service.objects.filter(node=controller):
            self.expectThat(
                (service.status, service.status_info),
                Equals((DEAD_STATUSES[service.name], "")),
            )

    def test_mark_dead_for_region_rack_controller_dead_rack_only(self):
        controller = factory.make_RegionController()
        controller.node_type = NODE_TYPE.REGION_AND_RACK_CONTROLLER
        controller.save()
        Service.objects.create_services_for(controller)
        Service.objects.mark_dead(controller, dead_rack=True)
        for service in Service.objects.filter(node=controller):
            if service.name in RACK_SERVICES:
                self.expectThat(
                    (service.status, service.status_info),
                    Equals((DEAD_STATUSES[service.name], "")),
                )
            else:
                self.expectThat(
                    (service.status, service.status_info),
                    Equals((SERVICE_STATUS.UNKNOWN, "")),
                )

    def test_mark_dead_for_region_rack_controller_dead_region_only(self):
        controller = factory.make_RegionController()
        controller.node_type = NODE_TYPE.REGION_AND_RACK_CONTROLLER
        controller.save()
        Service.objects.create_services_for(controller)
        Service.objects.mark_dead(controller, dead_region=True)
        for service in Service.objects.filter(node=controller):
            if service.name in REGION_SERVICES:
                self.expectThat(
                    (service.status, service.status_info),
                    Equals((DEAD_STATUSES[service.name], "")),
                )
            else:
                self.expectThat(
                    (service.status, service.status_info),
                    Equals((SERVICE_STATUS.UNKNOWN, "")),
                )

    def test_mark_dead_for_region_rack_controller_region_and_rack_dead(self):
        controller = factory.make_RegionController()
        controller.node_type = NODE_TYPE.REGION_AND_RACK_CONTROLLER
        controller.save()
        Service.objects.create_services_for(controller)
        Service.objects.mark_dead(controller, dead_region=True, dead_rack=True)
        for service in Service.objects.filter(node=controller):
            self.expectThat(
                (service.status, service.status_info),
                Equals((DEAD_STATUSES[service.name], "")),
            )
