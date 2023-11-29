# Copyright 2016-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import http.client
import random
from unittest.mock import MagicMock

from django.urls import reverse
from twisted.internet.defer import succeed

from maasserver import vmhost
from maasserver.forms import pods
from maasserver.models.bmc import Pod
from maasserver.models.node import Machine
from maasserver.models.tag import Tag
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object
from provisioningserver.drivers.pod import (
    Capabilities,
    DiscoveredMachine,
    DiscoveredPod,
    DiscoveredPodHints,
)
from provisioningserver.enum import MACVLAN_MODE_CHOICES
from provisioningserver.testing.certificates import get_sample_cert

# No need to test multiple authentication mechanisms


class PodAPITestForUser(APITestCase.ForUser):
    def __init__(self, *args, **kwargs):
        self.clientfactories.pop("user+pass", None)
        super().__init__(*args, **kwargs)


class PodAPITestForAdmin(APITestCase.ForAdmin):
    def __init__(self, *args, **kwargs):
        self.clientfactories.pop("user+pass", None)
        super().__init__(*args, **kwargs)


class PodMixin:
    """Mixin to fake pod discovery."""

    def make_pod_info(self):
        # Use virsh pod type as the required fields are specific to the
        # type of pod being created.
        pod_type = "virsh"
        pod_ip_adddress = factory.make_ipv4_address()
        pod_power_address = "qemu+ssh://user@%s/system" % pod_ip_adddress
        pod_password = factory.make_name("password")
        pod_tags = [factory.make_name("tag") for _ in range(3)]
        pod_zone = factory.make_Zone()
        pod_cpu_over_commit_ratio = random.randint(0, 10)
        pod_memory_over_commit_ratio = random.randint(0, 10)
        return {
            "type": pod_type,
            "power_address": pod_power_address,
            "power_pass": pod_password,
            "ip_address": pod_ip_adddress,
            "tags": ",".join(pod_tags),
            "zone": pod_zone.name,
            "cpu_over_commit_ratio": pod_cpu_over_commit_ratio,
            "memory_over_commit_ratio": pod_memory_over_commit_ratio,
        }

    def fake_pod_discovery(self):
        discovered_pod = DiscoveredPod(
            architectures=["amd64/generic"],
            cores=random.randint(2, 4),
            memory=random.randint(1024, 4096),
            local_storage=random.randint(1024, 1024 * 1024),
            cpu_speed=random.randint(2048, 4048),
            hints=DiscoveredPodHints(
                cores=random.randint(2, 4),
                memory=random.randint(1024, 4096),
                local_storage=random.randint(1024, 1024 * 1024),
                cpu_speed=random.randint(2048, 4048),
            ),
        )
        discovered_rack_1 = factory.make_RackController()
        discovered_rack_2 = factory.make_RackController()
        failed_rack = factory.make_RackController()
        self.patch(vmhost, "discover_pod").return_value = (
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


class TestPodsAPIUser(PodAPITestForUser, PodMixin):
    def test_handler_path(self):
        self.assertEqual("/MAAS/api/2.0/pods/", reverse("pods_handler"))

    def test_read_lists_pods(self):
        factory.make_BMC()
        pods = [factory.make_Pod() for _ in range(3)]
        response = self.client.get(reverse("pods_handler"))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertCountEqual(
            [pod.id for pod in pods], [pod.get("id") for pod in parsed_result]
        )

    def test_read_returns_limited_fields(self):
        pod = factory.make_Pod(capabilities=[])
        for _ in range(3):
            factory.make_PodStoragePool(pod=pod)
        response = self.client.get(reverse("pods_handler"))
        parsed_result = json_load_bytes(response.content)
        self.assertCountEqual(
            [
                "id",
                "name",
                "tags",
                "type",
                "resource_uri",
                "capabilities",
                "architectures",
                "total",
                "used",
                "zone",
                "available",
                "cpu_over_commit_ratio",
                "memory_over_commit_ratio",
                "storage_pools",
                "pool",
                "host",
                "default_macvlan_mode",
                "version",
            ],
            list(parsed_result[0]),
        )
        self.assertCountEqual(
            [
                "cores",
                "memory",
                "local_storage",
            ],
            list(parsed_result[0]["total"]),
        )
        self.assertCountEqual(
            [
                "cores",
                "memory",
                "local_storage",
            ],
            list(parsed_result[0]["used"]),
        )
        self.assertCountEqual(
            [
                "cores",
                "memory",
                "local_storage",
            ],
            list(parsed_result[0]["available"]),
        )
        self.assertCountEqual(
            [
                "id",
                "name",
                "type",
                "path",
                "total",
                "used",
                "available",
                "default",
            ],
            list(parsed_result[0]["storage_pools"][0]),
        )

    def test_create_requires_admin(self):
        response = self.client.post(
            reverse("pods_handler"), self.make_pod_info()
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)


class TestPodsAPIAdmin(PodAPITestForAdmin, PodMixin):
    def test_create_creates_pod(self):
        self.patch(pods, "post_commit_do")
        discovered_pod, _, _ = self.fake_pod_discovery()
        pod_info = self.make_pod_info()
        response = self.client.post(reverse("pods_handler"), pod_info)
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(parsed_result["type"], pod_info["type"])

    def test_create_lxd_default_project(self):
        self.patch(pods, "post_commit_do")
        self.patch_autospec(
            pods, "generate_certificate"
        ).return_value = get_sample_cert()
        discovered_pod, _, _ = self.fake_pod_discovery()
        ip = factory.make_ipv4_address()
        info = {
            "type": "lxd",
            "power_address": ip,
            "power_pass": "sekret",
            "ip_address": ip,
        }
        response = self.client.post(reverse("pods_handler"), info)
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        pod = Pod.objects.get(id=parsed_result["id"])
        self.assertEqual(pod.get_power_parameters()["project"], "default")

    def test_create_creates_pod_with_default_resource_pool(self):
        self.patch(pods, "post_commit_do")
        discovered_pod, _, _ = self.fake_pod_discovery()
        pod_info = self.make_pod_info()
        pool = factory.make_ResourcePool()
        pod_info["pool"] = pool.name
        response = self.client.post(reverse("pods_handler"), pod_info)
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(pool.id, parsed_result["pool"]["id"])

    def test_create_duplicate_provides_nice_error(self):
        self.patch(pods, "post_commit_do")
        pod_info = self.make_pod_info()
        discovered_pod, _, _ = self.fake_pod_discovery()
        response = self.client.post(reverse("pods_handler"), pod_info)
        self.assertEqual(http.client.OK, response.status_code)
        response = self.client.post(reverse("pods_handler"), pod_info)
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_create_succeeds_on_refresh_failure(self):
        failed_rack = factory.make_RackController()
        self.patch(vmhost, "discover_pod").return_value = (
            {},
            {failed_rack.system_id: factory.make_exception()},
        )
        response = self.client.post(
            reverse("pods_handler"), self.make_pod_info()
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertTrue(Pod.objects.filter(id=parsed_result["id"]).exists())


def get_pod_uri(pod):
    """Return a pod URI on the API."""
    return reverse("pod_handler", args=[pod.id])


def make_pod_with_hints():
    architectures = [
        "{}/{}".format(factory.make_name("arch"), factory.make_name("subarch"))
        for _ in range(3)
    ]
    cores = random.randint(8, 16)
    memory = random.randint(4096, 8192)
    cpu_speed = random.randint(2000, 3000)
    pod = factory.make_Pod(
        architectures=architectures,
        cores=cores,
        memory=memory,
        cpu_speed=cpu_speed,
    )
    pod.capabilities = [Capabilities.COMPOSABLE]
    pod.save()
    pod.hints.cores = pod.cores
    pod.hints.memory = pod.memory
    pod.hints.save()
    return pod


def make_compose_machine_result(pod):
    composed_machine = DiscoveredMachine(
        hostname=factory.make_name("hostname"),
        architecture=pod.architectures[0],
        cores=1,
        memory=1024,
        cpu_speed=300,
        power_parameters={"instance_name": factory.make_name("instance")},
        block_devices=[],
        interfaces=[],
    )
    pod_hints = DiscoveredPodHints(
        cores=random.randint(0, 10),
        memory=random.randint(1024, 4096),
        cpu_speed=random.randint(1000, 3000),
        local_storage=0,
    )
    return composed_machine, pod_hints


class TestPodAPI(PodAPITestForUser, PodMixin):
    def test_handler_path(self):
        pod_id = random.randint(0, 10)
        self.assertEqual(
            "/MAAS/api/2.0/pods/%s/" % pod_id,
            reverse("pod_handler", args=[pod_id]),
        )

    def test_GET_reads_pod(self):
        pod = factory.make_Pod()
        response = self.client.get(get_pod_uri(pod))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_pod = json_load_bytes(response.content)
        self.assertEqual(pod.id, parsed_pod["id"])

    def test_PUT_requires_admin(self):
        pod = factory.make_Pod()
        response = self.client.put(get_pod_uri(pod))
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_refresh_requires_admin(self):
        pod = factory.make_Pod()
        response = self.client.post(get_pod_uri(pod), {"op": "refresh"})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_parameters_requires_admin(self):
        pod = factory.make_Pod()
        response = self.client.get(get_pod_uri(pod), {"op": "parameters"})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_compose_requires_admin(self):
        pod = make_pod_with_hints()
        response = self.client.post(get_pod_uri(pod), {"op": "compose"})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_DELETE_rejects_deletion_if_not_permitted(self):
        pod = factory.make_Pod()
        response = self.client.delete(get_pod_uri(pod))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertEqual(pod, reload_object(pod))

    def test_add_tag_requires_admin(self):
        pod = make_pod_with_hints()
        response = self.client.post(
            get_pod_uri(pod),
            {"op": "add_tag", "tag": factory.make_name("tag")},
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_remove_tag_requires_admin(self):
        pod = factory.make_Pod()
        response = self.client.post(
            get_pod_uri(pod),
            {"op": "remove_tag", "tag": factory.make_name("tag")},
        )

        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )


class TestPodAPIAdmin(PodAPITestForAdmin, PodMixin):
    def test_PUT_updates(self):
        self.patch(pods, "post_commit_do")
        pod = factory.make_Pod(pod_type="virsh")
        new_name = factory.make_name("pod")
        new_tags = [
            factory.make_name("tag"),
            factory.make_name("tag"),
            "pod-console-logging",
        ]
        new_pool = factory.make_ResourcePool()
        new_zone = factory.make_Zone()
        new_power_parameters = {
            "power_address": "qemu+ssh://1.2.3.4/system",
            "power_pass": factory.make_name("pass"),
        }
        discovered_pod, _, _ = self.fake_pod_discovery()
        response = self.client.put(
            get_pod_uri(pod),
            {
                "name": new_name,
                "tags": ",".join(new_tags),
                "power_address": new_power_parameters["power_address"],
                "power_pass": new_power_parameters["power_pass"],
                "zone": new_zone.name,
                "pool": new_pool.name,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        pod.refresh_from_db()
        self.assertIsNotNone(Tag.objects.get(name="pod-console-logging"))
        self.assertEqual(new_name, pod.name)
        self.assertEqual(new_pool, pod.pool)
        self.assertCountEqual(new_tags, pod.tags)
        self.assertEqual(new_power_parameters, pod.get_power_parameters())
        self.assertEqual(new_zone, pod.zone)

    def test_PUT_updates_discovers_syncs_and_returns_pod(self):
        self.patch(pods, "post_commit_do")
        pod_info = self.make_pod_info()
        pod = factory.make_Pod(pod_type=pod_info["type"])
        new_name = factory.make_name("pod")
        discovered_pod, _, _ = self.fake_pod_discovery()
        response = self.client.put(
            get_pod_uri(pod),
            {
                "name": new_name,
                "tags": pod_info["tags"],
                "power_address": pod_info["power_address"],
                "power_pass": pod_info["power_pass"],
                "zone": pod_info["zone"],
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_output = json_load_bytes(response.content)
        self.assertEqual(new_name, parsed_output["name"])
        self.assertEqual(discovered_pod.cores, parsed_output["total"]["cores"])

    def test_PUT_update_minimal(self):
        self.patch(pods, "post_commit_do")
        pod_info = self.make_pod_info()
        power_parameters = {
            "power_address": pod_info["power_address"],
            "power_pass": pod_info["power_pass"],
        }
        pod = factory.make_Pod(
            pod_type=pod_info["type"], parameters=power_parameters
        )
        new_name = factory.make_name("pool")
        self.fake_pod_discovery()
        response = self.client.put(get_pod_uri(pod), {"name": new_name})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        pod.refresh_from_db()
        self.assertIsNotNone(Tag.objects.get(name="pod-console-logging"))
        self.assertEqual(new_name, pod.name)
        self.assertEqual(power_parameters, pod.get_power_parameters())

    def test_PUT_update_updates_pod_default_macvlan_mode(self):
        self.patch(pods, "post_commit_do")
        pod_info = self.make_pod_info()
        pod = factory.make_Pod(pod_type=pod_info["type"])
        default_macvlan_mode = factory.pick_choice(MACVLAN_MODE_CHOICES)
        self.fake_pod_discovery()
        response = self.client.put(
            get_pod_uri(pod), {"default_macvlan_mode": default_macvlan_mode}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        pod.refresh_from_db()
        self.assertEqual(pod.default_macvlan_mode, default_macvlan_mode)

    def test_refresh_discovers_syncs_and_returns_pod(self):
        self.patch(pods, "post_commit_do")
        pod = factory.make_Pod()
        discovered_pod, _, _ = self.fake_pod_discovery()
        response = self.client.post(get_pod_uri(pod), {"op": "refresh"})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_output = json_load_bytes(response.content)
        self.assertEqual(discovered_pod.cores, parsed_output["total"]["cores"])

    def test_parameters_returns_pod_parameters(self):
        pod = factory.make_Pod()
        pod.set_power_parameters(
            {factory.make_name("key"): factory.make_name("value")}
        )
        pod.save()
        response = self.client.get(get_pod_uri(pod), {"op": "parameters"})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_params = json_load_bytes(response.content)
        self.assertEqual(pod.get_power_parameters(), parsed_params)

    def test_compose_not_allowed_on_none_composable_pod(self):
        pod = make_pod_with_hints()
        pod.capabilities = []
        pod.save()
        response = self.client.post(get_pod_uri(pod), {"op": "compose"})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            b"VM host does not support composability.", response.content
        )

    def test_compose_composes_with_defaults(self):
        self.patch(pods, "post_commit_do")
        pod = make_pod_with_hints()
        pod.pool = factory.make_ResourcePool()
        pod.save()

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        composed_machine, pod_hints = make_compose_machine_result(pod)
        mock_compose_machine = self.patch(pods, "compose_machine")
        mock_compose_machine.return_value = succeed(
            (composed_machine, pod_hints)
        )

        # Mock start_commissioning so it doesn't use post commit hooks.
        self.patch(Machine, "start_commissioning")

        response = self.client.post(get_pod_uri(pod), {"op": "compose"})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_machine = json_load_bytes(response.content)
        self.assertEqual(parsed_machine.keys(), {"resource_uri", "system_id"})
        machine = Machine.objects.get(system_id=parsed_machine["system_id"])
        self.assertEqual(machine.pool, pod.pool)

    def test_compose_composes_with_pool(self):
        self.patch(pods, "post_commit_do")
        pod = make_pod_with_hints()

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        composed_machine, pod_hints = make_compose_machine_result(pod)
        mock_compose_machine = self.patch(pods, "compose_machine")
        mock_compose_machine.return_value = succeed(
            (composed_machine, pod_hints)
        )

        # Mock start_commissioning so it doesn't use post commit hooks.
        self.patch(Machine, "start_commissioning")

        pool = factory.make_ResourcePool()
        response = self.client.post(
            get_pod_uri(pod), {"op": "compose", "pool": pool.id}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_machine = json_load_bytes(response.content)
        self.assertEqual(parsed_machine.keys(), {"resource_uri", "system_id"})
        machine = Machine.objects.get(system_id=parsed_machine["system_id"])
        self.assertEqual(machine.pool, pool)

    def test_compose_raises_error_when_to_large_request(self):
        pod = make_pod_with_hints()

        response = self.client.post(
            get_pod_uri(pod), {"op": "compose", "cores": pod.hints.cores + 1}
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_DELETE_calls_async_delete(self):
        pod = factory.make_Pod()
        for _ in range(3):
            factory.make_Machine(bmc=pod)
        mock_eventual = MagicMock()
        mock_async_delete = self.patch(Pod, "async_delete")
        mock_async_delete.return_value = mock_eventual
        response = self.client.delete(get_pod_uri(pod))
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        mock_eventual.wait.assert_called_once_with(60)

    def test_DELETE_calls_async_delete_decompose(self):
        pod = factory.make_Pod()
        for _ in range(3):
            factory.make_Machine(bmc=pod)
        mock_eventual = MagicMock()
        mock_async_delete = self.patch(Pod, "async_delete")
        mock_async_delete.return_value = mock_eventual
        response = self.client.delete(
            get_pod_uri(pod), query={"decompose": True}
        )
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        mock_eventual.wait.assert_called_once_with(60 * 4)

    def test_add_tag_to_pod(self):
        pod = factory.make_Pod()
        tag_to_be_added = factory.make_name("tag")
        response = self.client.post(
            get_pod_uri(pod), {"op": "add_tag", "tag": tag_to_be_added}
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertIn(tag_to_be_added, parsed_device["tags"])
        pod = reload_object(pod)
        self.assertIn(tag_to_be_added, pod.tags)

    def test_remove_tag_from_pod(self):
        pod = factory.make_Pod(
            tags=[factory.make_name("tag") for _ in range(3)]
        )
        tag_to_be_removed = pod.tags[0]
        response = self.client.post(
            get_pod_uri(pod), {"op": "remove_tag", "tag": tag_to_be_removed}
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertNotIn(tag_to_be_removed, parsed_device["tags"])
        pod = reload_object(pod)
        self.assertNotIn(tag_to_be_removed, pod.tags)
