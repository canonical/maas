# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `rpc.services`."""


from fixtures import FakeLogger

from maasserver.enum import SERVICE_STATUS
from maasserver.models.service import RACK_SERVICES, Service
from maasserver.rpc import services
from maasserver.rpc.services import update_services
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from provisioningserver.rpc.exceptions import NoSuchCluster


class TestUpdateServices(MAASTransactionServerTestCase):
    def make_service(self, service_name, status=None, status_info=None):
        if status is None:
            status = factory.pick_enum(SERVICE_STATUS)
        if status_info is None:
            status_info = factory.make_name("status_info")
        return {
            "name": service_name,
            "status": status,
            "status_info": status_info,
        }

    def test_update_services_raises_NoSuchCluster(self):
        system_id = factory.make_name("system_id")
        self.assertRaises(NoSuchCluster, update_services, system_id, [])

    def test_update_services_logs_when_service_not_recognised(self):
        service_name = factory.make_name("service")
        service = self.make_service(service_name)
        rack_controller = factory.make_RackController()
        with FakeLogger(services.__name__) as logger:
            update_services(rack_controller.system_id, [service])
        self.assertEqual(
            logger.output,
            f"Rack {rack_controller.system_id} reported status for '{service_name}' but this is not a "
            f"recognised service (status='{service['status']}', info='{service['status_info']}').\n",
        )

    def test_update_services_updates_all_services(self):
        services = {
            service: self.make_service(service) for service in RACK_SERVICES
        }
        rack_controller = factory.make_RackController()
        update_services(rack_controller.system_id, services.values())
        for service_name in RACK_SERVICES:
            service = Service.objects.get(
                node=rack_controller, name=service_name
            )
            self.assertEqual(service.status, services[service_name]["status"])
            self.assertEqual(
                service.status_info, services[service_name]["status_info"]
            )
