# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.pod`"""

__all__ = []

import random
from unittest.mock import MagicMock

from crochet import wait_for
from maasserver.enum import NODE_TYPE
from maasserver.forms import pods
from maasserver.forms.pods import PodForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.utils.threads import deferToDatabase
from maasserver.websockets.base import dehydrate_datetime
from maasserver.websockets.handlers.pod import (
    ComposeMachineForm,
    PodHandler,
)
from maastesting.matchers import MockCalledOnceWith
from provisioningserver.drivers.pod import (
    Capabilities,
    DiscoveredMachine,
    DiscoveredPod,
    DiscoveredPodHints,
)
from testtools.matchers import Equals
from twisted.internet.defer import (
    inlineCallbacks,
    succeed,
)


wait_for_reactor = wait_for(30)  # 30 seconds.


class TestPodHandler(MAASTransactionServerTestCase):

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

    def fake_pod_discovery(self):
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
        self.patch(pods, "discover_pod").return_value = succeed(({
            discovered_rack_1.system_id: discovered_pod,
            discovered_rack_2.system_id: discovered_pod,
        }, {
            failed_rack.system_id: factory.make_exception(),
        }))

    def make_pod_with_hints(self):
        architectures = [
            "amd64/generic", "i386/generic", "arm64/generic",
            "armhf/generic"
        ]
        pod = factory.make_Pod(
            architectures=architectures, capabilities=[
                Capabilities.FIXED_LOCAL_STORAGE, Capabilities.ISCSI_STORAGE,
                Capabilities.COMPOSABLE])
        pod.hints.cores = random.randint(8, 16)
        pod.hints.memory = random.randint(4096, 8192)
        pod.hints.cpu_speed = random.randint(2000, 3000)
        pod.hints.save()
        return pod

    def make_compose_machine_result(self, pod):
        composed_machine = DiscoveredMachine(
            hostname=factory.make_name('hostname'),
            architecture=pod.architectures[0],
            cores=1, memory=1024, cpu_speed=300,
            block_devices=[], interfaces=[])
        pod_hints = DiscoveredPodHints(
            cores=random.randint(0, 10), memory=random.randint(1024, 4096),
            cpu_speed=random.randint(1000, 3000), local_storage=0)
        return composed_machine, pod_hints

    def dehydrate_pod(self, pod, admin=True):
        data = {
            "id": pod.id,
            "name": pod.name,
            "cpu_speed": pod.cpu_speed,
            "type": pod.power_type,
            "ip_address": pod.ip_address,
            "updated": dehydrate_datetime(pod.updated),
            "created": dehydrate_datetime(pod.created),
            "composed_machines_count": pod.node_set.filter(
                node_type=NODE_TYPE.MACHINE).count(),
            "total": {
                "cores": pod.cores,
                "memory": pod.memory,
                'memory_gb': '%.1f' % (pod.memory / 1024.0),
                "local_storage": pod.local_storage,
                'local_storage_gb': '%.1f' % (pod.local_storage / (1024 ** 3)),
                },
            "used": {
                "cores": pod.get_used_cores(),
                "memory": pod.get_used_memory(),
                'memory_gb': '%.1f' % (pod.get_used_memory() / 1024.0),
                "local_storage": pod.get_used_local_storage(),
                'local_storage_gb': '%.1f' % (
                    pod.get_used_local_storage() / (1024 ** 3)),
                },
            "available": {
                "cores": pod.cores - pod.get_used_cores(),
                "memory": pod.memory - pod.get_used_memory(),
                'memory_gb': '%.1f' % (
                    (pod.memory - pod.get_used_memory()) / 1024.0),
                "local_storage": (
                    pod.local_storage - pod.get_used_local_storage()),
                'local_storage_gb': '%.1f' % (
                    (pod.local_storage - pod.get_used_local_storage()) / (
                        (1024 ** 3))),
                },
            "default_pool": pod.default_pool.id,
            "capabilities": pod.capabilities,
            "architectures": pod.architectures,
            "hints": {
                'cores': pod.hints.cores,
                'cpu_speed': pod.hints.cpu_speed,
                'memory': pod.hints.memory,
                'memory_gb': '%.1f' % (pod.hints.memory / 1024.0),
                'local_storage': pod.hints.local_storage,
                'local_storage_gb': '%.1f' % (
                    pod.hints.local_storage / (1024 ** 3)),
                'local_disks': pod.hints.local_disks,
                'iscsi_storage': pod.hints.iscsi_storage,
                'iscsi_storage_gb': '%.1f' % (
                    pod.hints.iscsi_storage / (1024 ** 3)),
                }
            }
        if Capabilities.FIXED_LOCAL_STORAGE in pod.capabilities:
            data['total']['local_disks'] = pod.local_disks
            data['used']['local_disks'] = pod.get_used_local_disks()
            data['available']['local_disks'] = (
                pod.local_disks - pod.get_used_local_disks())
        if Capabilities.ISCSI_STORAGE in pod.capabilities:
            data['total']['iscsi_storage'] = pod.iscsi_storage
            data['total']['iscsi_storage_gb'] = '%.1f' % (
                pod.iscsi_storage / (1024 ** 3))
            data['used']['iscsi_storage'] = pod.get_used_iscsi_storage()
            data['used']['iscsi_storage_gb'] = '%.1f' % (
                pod.get_used_iscsi_storage() / (1024 ** 3))
            data['available']['iscsi_storage'] = (
                pod.iscsi_storage - pod.get_used_iscsi_storage())
            data['available']['iscsi_storage_gb'] = '%.1f' % (
                (pod.iscsi_storage - pod.get_used_iscsi_storage()) / (
                    1024 ** 3))
        if admin:
            data.update(pod.power_parameters)
        return data

    def test_get(self):
        admin = factory.make_admin()
        handler = PodHandler(admin, {})
        pod = self.make_pod_with_hints()
        expected_data = self.dehydrate_pod(pod)
        result = handler.get({"id": pod.id})
        self.assertThat(result, Equals(expected_data))

    def test_get_as_standard_user(self):
        user = factory.make_User()
        handler = PodHandler(user, {})
        pod = self.make_pod_with_hints()
        expected_data = self.dehydrate_pod(pod, admin=False)
        result = handler.get({"id": pod.id})
        self.assertThat(result, Equals(expected_data))

    @wait_for_reactor
    @inlineCallbacks
    def test_refresh(self):
        user = yield deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {})
        pod = yield deferToDatabase(self.make_pod_with_hints)
        mock_discover_and_sync_pod = self.patch(
            PodForm, 'discover_and_sync_pod')
        mock_discover_and_sync_pod.return_value = succeed(pod)
        expected_data = yield deferToDatabase(self.dehydrate_pod, pod)
        observed_data = yield handler.refresh({"id": pod.id})
        self.assertThat(
            mock_discover_and_sync_pod, MockCalledOnceWith())
        self.assertEqual(expected_data, observed_data)

    @wait_for_reactor
    @inlineCallbacks
    def test_delete(self):
        user = yield deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {})
        pod = yield deferToDatabase(self.make_pod_with_hints)
        yield handler.delete({"id": pod.id})
        expected_pod = yield deferToDatabase(reload_object, pod)
        self.assertIsNone(expected_pod)

    @wait_for_reactor
    @inlineCallbacks
    def test_create(self):
        user = yield deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {})
        pod_info = self.make_pod_info()
        yield deferToDatabase(self.fake_pod_discovery)
        created_pod = yield handler.create(pod_info)
        self.assertIsNotNone(created_pod['id'])

    @wait_for_reactor
    @inlineCallbacks
    def test_update(self):
        user = yield deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {})
        pod_info = self.make_pod_info()
        pod = yield deferToDatabase(
            factory.make_Pod, pod_type=pod_info['type'])
        pod_info['id'] = pod.id
        pod_info['name'] = factory.make_name('pod')
        yield deferToDatabase(self.fake_pod_discovery)
        updated_pod = yield handler.update(pod_info)
        self.assertEqual(pod_info['name'], updated_pod['name'])

    @wait_for_reactor
    @inlineCallbacks
    def test__compose(self):
        user = yield deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {})
        pod = yield deferToDatabase(self.make_pod_with_hints)

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        node = yield deferToDatabase(factory.make_Node)
        mock_compose_machine = self.patch(ComposeMachineForm, "compose")
        mock_compose_machine.return_value = succeed(node)

        observed_data = yield handler.compose({
            'id': pod.id,
            'skip_commissioning': True,
        })
        self.assertEqual(pod.id, observed_data['id'])
