# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import random

import crochet
from twisted.internet.defer import inlineCallbacks, succeed

from maasserver import vmhost as vmhost_module
from maasserver.enum import BMC_TYPE
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.threads import deferToDatabase
from provisioningserver.drivers.pod import (
    DiscoveredPod,
    DiscoveredPodHints,
    DiscoveredPodStoragePool,
)

wait_for_reactor = crochet.wait_for(30)  # 30 seconds.


class TestDiscoverAndSyncVMHost(MAASTransactionServerTestCase):
    def make_pod_info(self):
        pod_ip_adddress = factory.make_ipv4_address()
        pod_power_address = "qemu+ssh://user@%s/system" % pod_ip_adddress
        return {
            "type": "virsh",
            "power_address": pod_power_address,
            "ip_address": pod_ip_adddress,
        }

    def fake_pod_discovery(self):
        discovered_pod = DiscoveredPod(
            architectures=["amd64/generic"],
            cores=random.randint(2, 4),
            memory=random.randint(2048, 4096),
            local_storage=random.randint(1024, 1024 * 1024),
            cpu_speed=random.randint(2048, 4048),
            hints=DiscoveredPodHints(
                cores=random.randint(2, 4),
                memory=random.randint(1024, 4096),
                local_storage=random.randint(1024, 1024 * 1024),
                cpu_speed=random.randint(2048, 4048),
            ),
            storage_pools=[
                DiscoveredPodStoragePool(
                    id=factory.make_name("pool_id"),
                    name=factory.make_name("name"),
                    type=factory.make_name("type"),
                    path="/var/lib/path/%s" % factory.make_name("path"),
                    storage=random.randint(1024, 1024 * 1024),
                )
                for _ in range(3)
            ],
        )
        discovered_rack_1 = factory.make_RackController()
        discovered_rack_2 = factory.make_RackController()
        failed_rack = factory.make_RackController()
        self.patch(vmhost_module, "post_commit_do")
        self.patch(vmhost_module, "discover_pod").return_value = (
            {
                discovered_rack_1.system_id: discovered_pod,
                discovered_rack_2.system_id: discovered_pod,
            },
            {failed_rack.system_id: factory.make_exception()},
        )
        return (
            discovered_pod,
            [discovered_rack_1, discovered_rack_2],
            [failed_rack],
        )

    def test_existing_vmhost(self):
        (
            discovered_pod,
            discovered_racks,
            failed_racks,
        ) = self.fake_pod_discovery()
        zone = factory.make_Zone()
        pod_info = self.make_pod_info()
        power_parameters = {"power_address": pod_info["power_address"]}
        orig_vmhost = factory.make_Pod(
            zone=zone, pod_type=pod_info["type"], parameters=power_parameters
        )
        vmhost = vmhost_module.discover_and_sync_vmhost(
            orig_vmhost, factory.make_User()
        )
        self.assertEqual(vmhost.id, orig_vmhost.id)
        self.assertEqual(vmhost.bmc_type, BMC_TYPE.POD)
        self.assertEqual(vmhost.architectures, ["amd64/generic"])
        self.assertEqual(vmhost.name, orig_vmhost.name)
        self.assertEqual(vmhost.cores, discovered_pod.cores)
        self.assertEqual(vmhost.memory, discovered_pod.memory)
        self.assertEqual(vmhost.cpu_speed, discovered_pod.cpu_speed)
        self.assertEqual(vmhost.zone, zone)
        self.assertEqual(vmhost.power_type, "virsh")
        self.assertEqual(vmhost.power_parameters, power_parameters)
        self.assertEqual(vmhost.ip_address.ip, pod_info["ip_address"])
        routable_racks = [
            relation.rack_controller
            for relation in vmhost.routable_rack_relationships.all()
            if relation.routable
        ]
        not_routable_racks = [
            relation.rack_controller
            for relation in vmhost.routable_rack_relationships.all()
            if not relation.routable
        ]
        self.assertCountEqual(routable_racks, discovered_racks)
        self.assertCountEqual(not_routable_racks, failed_racks)

    @wait_for_reactor
    @inlineCallbacks
    def test_discover_in_twisted(self):
        discovered_pod, discovered_racks, failed_racks = yield deferToDatabase(
            self.fake_pod_discovery
        )
        vmhost_module.discover_pod.return_value = succeed(
            vmhost_module.discover_pod.return_value
        )
        zone = yield deferToDatabase(factory.make_Zone)
        pod_info = yield deferToDatabase(self.make_pod_info)
        power_parameters = {"power_address": pod_info["power_address"]}
        orig_vmhost = yield deferToDatabase(
            factory.make_Pod,
            zone=zone,
            pod_type=pod_info["type"],
            parameters=power_parameters,
        )
        user = yield deferToDatabase(factory.make_User)
        vmhost = yield vmhost_module.discover_and_sync_vmhost(
            orig_vmhost, user
        )
        self.assertEqual(vmhost.id, orig_vmhost.id)
        self.assertEqual(vmhost.bmc_type, BMC_TYPE.POD)
        self.assertEqual(vmhost.architectures, ["amd64/generic"])
        self.assertEqual(vmhost.name, orig_vmhost.name)
        self.assertEqual(vmhost.cores, discovered_pod.cores)
        self.assertEqual(vmhost.memory, discovered_pod.memory)
        self.assertEqual(vmhost.cpu_speed, discovered_pod.cpu_speed)
        self.assertEqual(vmhost.zone, zone)
        self.assertEqual(vmhost.power_type, "virsh")
        self.assertEqual(vmhost.power_parameters, power_parameters)
        self.assertEqual(vmhost.ip_address.ip, pod_info["ip_address"])

        def validate_rack_routes():
            routable_racks = [
                relation.rack_controller
                for relation in vmhost.routable_rack_relationships.all()
                if relation.routable
            ]
            not_routable_racks = [
                relation.rack_controller
                for relation in vmhost.routable_rack_relationships.all()
                if not relation.routable
            ]
            self.assertCountEqual(routable_racks, discovered_racks)
            self.assertCountEqual(not_routable_racks, failed_racks)

        yield deferToDatabase(validate_rack_routes)
