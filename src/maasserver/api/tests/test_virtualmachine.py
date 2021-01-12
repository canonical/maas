import http.client
import random

from django.urls import reverse

from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes


def get_vm_uri(vm_id):
    return reverse("virtual_machine_handler", args=[vm_id])


class TestVirtualMachineAPI(APITestCase.ForUser):
    def test_handler_path(self):
        vm_id = random.randint(0, 10)
        self.assertEqual(
            f"/MAAS/api/2.0/virtual-machines/{vm_id}",
            get_vm_uri(vm_id),
        )

    def test_GET_reads_vm(self):
        vm = factory.make_VirtualMachine(
            memory=1024, unpinned_cores=4, hugepages_backed=True
        )
        response = self.client.get(get_vm_uri(vm.id))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            json_load_bytes(response.content),
            {
                "id": vm.id,
                "identifier": vm.identifier,
                "bmc_id": vm.bmc_id,
                "project": vm.project,
                "hugepages_backed": True,
                "machine_id": None,
                "memory": 1024,
                "pinned_cores": [],
                "resource_uri": f"/MAAS/api/2.0/virtual-machines/{vm.id}",
                "unpinned_cores": 4,
            },
        )

    def test_GET_with_machine(self):
        machine = factory.make_Machine()
        vm = factory.make_VirtualMachine(machine=machine)
        response = self.client.get(get_vm_uri(vm.id))
        details = json_load_bytes(response.content)
        self.assertEqual(details["machine_id"], machine.id)


class TestVirtualMachinesAPI(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/virtual-machines/",
            reverse("virtual_machines_handler"),
        )

    def test_GET_reads_vms(self):
        vm1 = factory.make_VirtualMachine(
            memory=1024, unpinned_cores=4, hugepages_backed=True
        )
        vm2 = factory.make_VirtualMachine(
            memory=2048,
            pinned_cores=[0, 1, 2, 3],
            hugepages_backed=False,
        )
        response = self.client.get("/MAAS/api/2.0/virtual-machines/")
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            json_load_bytes(response.content),
            [
                {
                    "id": vm1.id,
                    "identifier": vm1.identifier,
                    "bmc_id": vm1.bmc_id,
                    "project": vm1.project,
                    "hugepages_backed": True,
                    "machine_id": None,
                    "memory": 1024,
                    "pinned_cores": [],
                    "resource_uri": f"/MAAS/api/2.0/virtual-machines/{vm1.id}",
                    "unpinned_cores": 4,
                },
                {
                    "id": vm2.id,
                    "identifier": vm2.identifier,
                    "bmc_id": vm2.bmc_id,
                    "project": vm2.project,
                    "hugepages_backed": False,
                    "machine_id": None,
                    "memory": 2048,
                    "pinned_cores": [0, 1, 2, 3],
                    "resource_uri": f"/MAAS/api/2.0/virtual-machines/{vm2.id}",
                    "unpinned_cores": 0,
                },
            ],
        )
