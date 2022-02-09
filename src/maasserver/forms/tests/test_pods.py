# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from datetime import timedelta
import random
from unittest.mock import ANY, call, MagicMock

import crochet
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from testtools import ExpectedException
from testtools.matchers import (
    Equals,
    HasLength,
    Is,
    IsInstance,
    MatchesAll,
    MatchesListwise,
    MatchesSetwise,
    MatchesStructure,
)
from twisted.internet.defer import inlineCallbacks, succeed

from maasserver.enum import BMC_TYPE, INTERFACE_TYPE, NODE_STATUS
from maasserver.exceptions import PodProblem, StaticIPAddressUnavailable
from maasserver.forms import pods as pods_module
from maasserver.forms.pods import (
    ComposeMachineForm,
    ComposeMachineForPodsForm,
    DEFAULT_COMPOSED_CORES,
    DEFAULT_COMPOSED_MEMORY,
    DEFAULT_COMPOSED_STORAGE,
    get_known_host_interfaces,
    PodForm,
)
from maasserver.models import Config, Machine, StaticIPAddress
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.certificates import generate_certificate
from maasserver.utils.orm import reload_object
from maasserver.utils.threads import deferToDatabase
from maastesting.matchers import (
    MockCalledOnce,
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from provisioningserver.certificates import Certificate
from provisioningserver.drivers.pod import (
    Capabilities,
    DiscoveredMachine,
    DiscoveredMachineInterface,
    DiscoveredPod,
    DiscoveredPodHints,
    DiscoveredPodStoragePool,
    InterfaceAttachType,
    KnownHostInterface,
    RequestedMachine,
    RequestedMachineBlockDevice,
    RequestedMachineInterface,
)
from provisioningserver.enum import MACVLAN_MODE, MACVLAN_MODE_CHOICES

wait_for_reactor = crochet.wait_for(30)  # 30 seconds.
SAMPLE_CERT = Certificate.generate("maas-vmcluster")


def make_pod_with_hints(with_host=False, host=None, **pod_attributes):
    architectures = [
        "amd64/generic",
        "i386/generic",
        "arm64/generic",
        "armhf/generic",
    ]
    if with_host and host is None:
        host = factory.make_Machine_with_Interface_on_Subnet()

    if host is None:
        ip = factory.make_StaticIPAddress()
    else:
        ip = factory.make_StaticIPAddress(interface=host.boot_interface)
    pod = factory.make_Pod(
        architectures=architectures,
        cores=random.randint(8, 16),
        memory=random.randint(4096, 8192),
        ip_address=ip,
        cpu_speed=random.randint(2000, 3000),
        **pod_attributes,
    )
    for _ in range(3):
        pool = factory.make_PodStoragePool(pod)
    pod.default_storage_pool = pool
    pod.save()
    pod.hints.cores = pod.cores
    pod.hints.memory = pod.memory
    pod.hints.cpu_speed = pod.cpu_speed
    pod.hints.save()
    return pod


class TestPodForm(MAASTransactionServerTestCase):
    def setUp(self):
        super().setUp()
        self.request = MagicMock()
        self.request.user = factory.make_User()

    def make_pod_info(self, pod_type="virsh", **extra_power_parameters):
        assert pod_type in ["virsh", "lxd"], "Unsupported pod type"
        power_address = factory.make_ipv4_address()
        if pod_type == "virsh":
            power_address = "qemu+ssh://user@%s/system" % power_address
        pod_info = {
            "type": pod_type,
            "power_address": power_address,
        }
        pod_info.update(extra_power_parameters)
        return pod_info

    def make_discovered_pod(self):
        return DiscoveredPod(
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

    def test_contains_limited_set_of_fields(self):
        form = PodForm()
        self.assertEqual(
            {
                "name",
                "tags",
                "type",
                "zone",
                "pool",
                "cpu_over_commit_ratio",
                "memory_over_commit_ratio",
                "default_storage_pool",
                "default_macvlan_mode",
            },
            form.fields.keys(),
        )

    def test_creates_pod_with_provided_information(self):
        pod_info = self.make_pod_info()
        form = PodForm(data=pod_info, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertEqual(pod.power_type, pod_info["type"])
        self.assertEqual(
            pod.power_parameters["power_address"], pod_info["power_address"]
        )
        self.assertEqual(pod.cores, 0)
        self.assertEqual(pod.memory, 0)
        self.assertEqual(pod.cpu_speed, 0)

    def test_creates_pod_with_name(self):
        pod_info = self.make_pod_info()
        pod_name = factory.make_name("pod")
        pod_info["name"] = pod_name
        form = PodForm(data=pod_info, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertEqual(pod_name, pod.name)

    def test_creates_pod_with_power_parameters(self):
        pod_info = self.make_pod_info()
        pod_info["power_pass"] = factory.make_name("pass")
        form = PodForm(data=pod_info, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertEqual(
            pod_info["power_address"], pod.power_parameters["power_address"]
        )
        self.assertEqual(
            pod_info["power_pass"], pod.power_parameters["power_pass"]
        )

    def test_creates_pod_with_overcommit(self):
        pod_info = self.make_pod_info()
        pod_info["cpu_over_commit_ratio"] = random.randint(0, 10)
        pod_info["memory_over_commit_ratio"] = random.randint(0, 10)
        form = PodForm(data=pod_info, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertEqual(
            pod_info["cpu_over_commit_ratio"], pod.cpu_over_commit_ratio
        )
        self.assertEqual(
            pod_info["memory_over_commit_ratio"], pod.memory_over_commit_ratio
        )

    def test_creates_pod_with_tags(self):
        pod_info = self.make_pod_info()
        tags = [
            factory.make_name("tag"),
            factory.make_name("tag"),
            "pod-console-logging",
        ]
        pod_info["tags"] = ",".join(tags)
        form = PodForm(data=pod_info, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertCountEqual(tags, pod.tags)

    def test_creates_pod_with_zone(self):
        pod_info = self.make_pod_info()
        zone = factory.make_Zone()
        pod_info["zone"] = zone.name
        form = PodForm(data=pod_info, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertEqual(zone.id, pod.zone.id)

    def test_creates_pod_with_pool(self):
        pod_info = self.make_pod_info()
        pool = factory.make_ResourcePool()
        pod_info["pool"] = pool.name
        form = PodForm(data=pod_info, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertEqual(pool.id, pod.pool.id)

    def test_creates_lxd_with_generated_certificate(self):
        data = {
            "type": "lxd",
            "power_address": "1.2.3.4",
            "password": "secret",
        }
        form = PodForm(data=data, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        vmhost = form.save()
        cert = Certificate.from_pem(
            vmhost.power_parameters["certificate"],
            vmhost.power_parameters["key"],
        )
        self.assertEqual(cert.cn(), Config.objects.get_config("maas_name"))

    def test_creates_lxd_with_generated_certificate_with_name_in_cn(self):
        data = {
            "name": "lxd-server",
            "type": "lxd",
            "power_address": "1.2.3.4",
            "password": "secret",
        }
        form = PodForm(data=data, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        vmhost = form.save()
        cert = Certificate.from_pem(
            vmhost.power_parameters["certificate"],
            vmhost.power_parameters["key"],
        )
        self.assertEqual(
            cert.cn(), "lxd-server@" + Config.objects.get_config("maas_name")
        )

    def test_prevents_duplicate_pod(self):
        pod_info = self.make_pod_info()
        form = PodForm(data=pod_info, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        new_form = PodForm(data=pod_info)
        self.assertTrue(new_form.is_valid(), form._errors)
        self.assertRaises(ValidationError, new_form.save)

    def test_takes_over_bmc_with_pod(self):
        pod_info = self.make_pod_info()
        bmc = factory.make_BMC(
            power_type=pod_info["type"],
            power_parameters={
                "power_address": pod_info["power_address"],
                "power_pass": "",
            },
        )
        form = PodForm(data=pod_info, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertEqual(bmc.id, pod.id)
        self.assertEqual(BMC_TYPE.POD, reload_object(bmc).bmc_type)

    def test_updates_existing_pod_minimal(self):
        zone = factory.make_Zone()
        pool = factory.make_ResourcePool()
        cpu_over_commit = random.randint(0, 10)
        memory_over_commit = random.randint(0, 10)
        power_parameters = {
            "power_address": "qemu+ssh://1.2.3.4/system",
            "power_pass": "pass",
        }
        orig_pod = factory.make_Pod(
            pod_type="virsh",
            zone=zone,
            pool=pool,
            cpu_over_commit_ratio=cpu_over_commit,
            memory_over_commit_ratio=memory_over_commit,
            parameters=power_parameters,
        )
        new_name = factory.make_name("pod")
        form = PodForm(
            data={"name": new_name}, request=self.request, instance=orig_pod
        )
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertEqual(new_name, pod.name)
        self.assertEqual(zone, pod.zone)
        self.assertEqual(pool, pod.pool)
        self.assertEqual(cpu_over_commit, pod.cpu_over_commit_ratio)
        self.assertEqual(memory_over_commit, pod.memory_over_commit_ratio)
        self.assertEqual(memory_over_commit, pod.memory_over_commit_ratio)
        self.assertEqual(power_parameters, pod.power_parameters)

    def test_updates_existing_pod(self):
        zone = factory.make_Zone()
        pool = factory.make_ResourcePool()
        pod_info = self.make_pod_info()
        pod_info["zone"] = zone.name
        pod_info["pool"] = pool.name
        orig_pod = factory.make_Pod(pod_type=pod_info["type"])
        new_name = factory.make_name("pod")
        pod_info["name"] = new_name
        form = PodForm(data=pod_info, request=self.request, instance=orig_pod)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertEqual(pod.id, orig_pod.id)
        self.assertEqual(pod.zone, zone)
        self.assertEqual(pod.pool, pool)
        self.assertEqual(pod.name, new_name)

    def test_updates_default_storage_pool(self):
        discovered_pod = self.make_discovered_pod()
        default_storage_pool = random.choice(discovered_pod.storage_pools)
        pod = factory.make_Pod(pod_type="virsh")
        pod.sync(discovered_pod, self.request.user)
        form = PodForm(
            data={
                "default_storage_pool": default_storage_pool.id,
                "power_address": "qemu:///system",
            },
            request=self.request,
            instance=pod,
        )
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertEqual(
            pod.default_storage_pool.pool_id, default_storage_pool.id
        )

    def test_updates_default_macvlan_mode(self):
        discovered_pod = self.make_discovered_pod()
        default_macvlan_mode = factory.pick_choice(MACVLAN_MODE_CHOICES)
        pod = factory.make_Pod(pod_type="virsh")
        pod.sync(discovered_pod, self.request.user)
        form = PodForm(
            data={"default_macvlan_mode": default_macvlan_mode},
            request=self.request,
            instance=pod,
        )
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertEqual(pod.default_macvlan_mode, default_macvlan_mode)

    def test_updates_clustered_peers_certificates(self):
        cluster = factory.make_VMCluster(pods=0)
        vmhosts = [
            factory.make_Pod(pod_type="lxd", cluster=cluster) for _ in range(3)
        ]
        form = PodForm(
            data={
                "type": "lxd",
                "certificate": SAMPLE_CERT.certificate_pem(),
                "key": SAMPLE_CERT.private_key_pem(),
            },
            request=self.request,
            instance=vmhosts[0],
        )
        self.assertTrue(form.is_valid(), form._errors)
        result = form.save()
        updated_vmhosts = [vmhost for vmhost in result.hints.cluster.hosts()]
        for vmhost in updated_vmhosts:
            self.assertEqual(
                vmhost.power_parameters["certificate"],
                SAMPLE_CERT.certificate_pem().strip(),
            )
            self.assertEqual(
                vmhost.power_parameters["key"],
                SAMPLE_CERT.private_key_pem().strip(),
            )

    def test_creates_virsh_pod_with_no_metrics(self):
        pod_info = self.make_pod_info("virsh")
        form = PodForm(data=pod_info, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertIsNone(pod.created_with_trust_password)
        self.assertIsNone(pod.created_with_maas_generated_cert)
        self.assertIsNone(pod.created_with_cert_expiration_days)

    def test_creates_lxd_pod_with_trustpassword_metrics(self):
        pod_info = self.make_pod_info("lxd", password="mypass")
        form = PodForm(data=pod_info, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertTrue(pod.created_with_trust_password)

    def test_creates_lxd_pod_with_no_trustpassword_metrics(self):
        pod_info = self.make_pod_info("lxd")
        form = PodForm(data=pod_info, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertFalse(pod.created_with_trust_password)

    def test_creates_lxd_pod_with_maas_generated_cert_default(self):
        pod_info = self.make_pod_info("lxd")
        form = PodForm(data=pod_info, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertTrue(pod.created_with_maas_generated_cert)

    def test_creates_lxd_pod_with_cert_expiration_default(self):
        pod_info = self.make_pod_info("lxd")
        form = PodForm(data=pod_info, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertEqual(3649, pod.created_with_cert_expiration_days)

    def test_creates_lxd_pod_with_cert_expiration_supplied(self):
        pod_info = self.make_pod_info("lxd")
        maas_cert = Certificate.generate("mypod", validity=timedelta(days=10))
        pod_info["certificate"] = maas_cert.certificate_pem()
        pod_info["key"] = maas_cert.private_key_pem()
        form = PodForm(data=pod_info, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertEqual(9, pod.created_with_cert_expiration_days)

    def test_creates_lxd_pod_with_maas_generated_cert_supplied(self):
        pod_info = self.make_pod_info("lxd")
        maas_cert = generate_certificate("mypod")
        pod_info["certificate"] = maas_cert.certificate_pem()
        pod_info["key"] = maas_cert.private_key_pem()
        form = PodForm(data=pod_info, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertTrue(pod.created_with_maas_generated_cert)

    def test_creates_lxd_pod_with_not_maas_generated_cert(self):
        pod_info = self.make_pod_info("lxd")
        non_maas_cert = Certificate.generate("mycn")
        pod_info["certificate"] = non_maas_cert.certificate_pem()
        pod_info["key"] = non_maas_cert.private_key_pem()
        form = PodForm(data=pod_info, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertIsNotNone(pod.created_with_maas_generated_cert)
        self.assertFalse(pod.created_with_maas_generated_cert)

    def test_creates_lxd_pod_with_metrics_existing(self):
        pod_info = self.make_pod_info("lxd")
        pod = make_pod_with_hints(
            pod_type="lxd",
            created_with_trust_password=True,
            created_with_maas_generated_cert=True,
            created_with_cert_expiration_days=12,
        )
        pod_info["password"] = ""
        non_maas_cert = Certificate.generate(
            "mycn", validity=timedelta(days=24)
        )
        pod_info["certificate"] = non_maas_cert.certificate_pem()
        pod_info["key"] = non_maas_cert.private_key_pem()
        form = PodForm(instance=pod, data=pod_info, request=self.request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertTrue(pod.created_with_trust_password)
        self.assertTrue(pod.created_with_maas_generated_cert)
        self.assertEqual(12, pod.created_with_cert_expiration_days)


class TestComposeMachineForm(MAASTransactionServerTestCase):
    def make_requested_machine_result(self, pod):
        return RequestedMachine(
            hostname=factory.make_name("hostname"),
            architecture=factory.make_name("architecture"),
            cores=random.randint(1, 8),
            memory=random.randint(1024, 4096),
            block_devices=[RequestedMachineBlockDevice(size=4096)],
            interfaces=[RequestedMachineInterface()],
            known_host_interfaces=get_known_host_interfaces(pod),
        )

    def make_compose_machine_result(self, pod):
        composed_machine = DiscoveredMachine(
            hostname=factory.make_name("hostname"),
            power_parameters={"instance_name": factory.make_name("instance")},
            architecture=pod.architectures[0],
            cores=DEFAULT_COMPOSED_CORES,
            memory=DEFAULT_COMPOSED_MEMORY,
            cpu_speed=300,
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

    def test_requires_request_kwarg(self):
        error = self.assertRaises(ValueError, ComposeMachineForm)
        self.assertEqual("'request' kwargs is required.", str(error))

    def test_requires_pod_kwarg(self):
        request = MagicMock()
        error = self.assertRaises(
            ValueError, ComposeMachineForm, request=request
        )
        self.assertEqual("'pod' kwargs is required.", str(error))

    def test_sets_up_fields_based_on_pod(self):
        request = MagicMock()
        pod = make_pod_with_hints()
        form = ComposeMachineForm(request=request, pod=pod)
        self.assertThat(
            form.fields["cores"],
            MatchesStructure(
                required=Equals(False),
                validators=MatchesSetwise(
                    MatchesAll(
                        IsInstance(MaxValueValidator),
                        MatchesStructure(limit_value=Equals(pod.hints.cores)),
                    ),
                    MatchesAll(
                        IsInstance(MinValueValidator),
                        MatchesStructure(limit_value=Equals(1)),
                    ),
                ),
            ),
        )
        self.assertThat(
            form.fields["memory"],
            MatchesStructure(
                required=Equals(False),
                validators=MatchesSetwise(
                    MatchesAll(
                        IsInstance(MaxValueValidator),
                        MatchesStructure(limit_value=Equals(pod.hints.memory)),
                    ),
                    MatchesAll(
                        IsInstance(MinValueValidator),
                        MatchesStructure(limit_value=Equals(1024)),
                    ),
                ),
            ),
        )
        self.assertThat(
            form.fields["architecture"],
            MatchesStructure(
                required=Equals(False),
                choices=MatchesSetwise(
                    *[
                        Equals((architecture, architecture))
                        for architecture in pod.architectures
                    ]
                ),
            ),
        )
        self.assertThat(
            form.fields["cpu_speed"],
            MatchesStructure(
                required=Equals(False),
                validators=MatchesSetwise(
                    MatchesAll(
                        IsInstance(MaxValueValidator),
                        MatchesStructure(
                            limit_value=Equals(pod.hints.cpu_speed)
                        ),
                    ),
                    MatchesAll(
                        IsInstance(MinValueValidator),
                        MatchesStructure(limit_value=Equals(300)),
                    ),
                ),
            ),
        )

    def test_sets_up_fields_based_on_pod_no_max_cpu_speed(self):
        request = MagicMock()
        pod = make_pod_with_hints()
        pod.hints.cpu_speed = 0
        pod.save()
        form = ComposeMachineForm(request=request, pod=pod)
        self.assertThat(
            form.fields["cpu_speed"],
            MatchesStructure(
                required=Equals(False),
                validators=MatchesSetwise(
                    MatchesAll(
                        IsInstance(MinValueValidator),
                        MatchesStructure(limit_value=Equals(300)),
                    )
                ),
            ),
        )

    def test_sets_up_pool_default(self):
        request = MagicMock()
        pod = make_pod_with_hints()
        pool = factory.make_ResourcePool()
        pod.pool = pool
        pod.save()
        form = ComposeMachineForm(request=request, pod=pod)
        self.assertEqual(pool, form.initial["pool"])

    def test_get_machine_uses_all_initial_values(self):
        request = MagicMock()
        pod = make_pod_with_hints()
        form = ComposeMachineForm(data={}, request=request, pod=pod)
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine(
            get_known_host_interfaces(pod)
        )
        self.assertThat(
            request_machine,
            MatchesAll(
                IsInstance(RequestedMachine),
                MatchesStructure(
                    architecture=Equals(pod.architectures[0]),
                    cores=Equals(DEFAULT_COMPOSED_CORES),
                    pinned_cores=Equals([]),
                    memory=Equals(DEFAULT_COMPOSED_MEMORY),
                    hugepages_backed=Equals(False),
                    cpu_speed=Is(None),
                    block_devices=MatchesListwise(
                        [
                            MatchesAll(
                                IsInstance(RequestedMachineBlockDevice),
                                MatchesStructure(
                                    size=Equals(
                                        DEFAULT_COMPOSED_STORAGE * (1000 ** 3)
                                    )
                                ),
                            )
                        ]
                    ),
                    interfaces=MatchesListwise(
                        [IsInstance(RequestedMachineInterface)]
                    ),
                    known_host_interfaces=MatchesListwise([]),
                ),
            ),
        )

    def test_get_machine_uses_passed_values(self):
        request = MagicMock()
        pod = make_pod_with_hints()
        architecture = random.choice(pod.architectures)
        cores = random.randint(1, pod.hints.cores)
        memory = random.randint(1024, pod.hints.memory)
        cpu_speed = random.randint(300, pod.hints.cpu_speed)
        disk_1 = random.randint(8, 16) * (1000 ** 3)
        disk_1_tags = [factory.make_name("tag") for _ in range(3)]
        disk_2 = random.randint(8, 16) * (1000 ** 3)
        disk_2_tags = [factory.make_name("tag") for _ in range(3)]
        hugepages_backed = factory.pick_bool()
        storage = "root:%d(%s),extra:%d(%s)" % (
            disk_1 // (1000 ** 3),
            ",".join(disk_1_tags),
            disk_2 // (1000 ** 3),
            ",".join(disk_2_tags),
        )
        form = ComposeMachineForm(
            data={
                "architecture": architecture,
                "cores": cores,
                "memory": memory,
                "hugepages_backed": hugepages_backed,
                "cpu_speed": cpu_speed,
                "storage": storage,
            },
            request=request,
            pod=pod,
        )
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine(
            get_known_host_interfaces(pod)
        )
        self.assertThat(
            request_machine,
            MatchesAll(
                IsInstance(RequestedMachine),
                MatchesStructure(
                    architecture=Equals(architecture),
                    cores=Equals(cores),
                    memory=Equals(memory),
                    hugepages_backed=Equals(hugepages_backed),
                    cpu_speed=Equals(cpu_speed),
                    block_devices=MatchesListwise(
                        [
                            MatchesAll(
                                IsInstance(RequestedMachineBlockDevice),
                                MatchesStructure(
                                    size=Equals(disk_1),
                                    tags=Equals(disk_1_tags),
                                ),
                            ),
                            MatchesAll(
                                IsInstance(RequestedMachineBlockDevice),
                                MatchesStructure(
                                    size=Equals(disk_2),
                                    tags=Equals(disk_2_tags),
                                ),
                            ),
                        ]
                    ),
                    interfaces=MatchesListwise(
                        [IsInstance(RequestedMachineInterface)]
                    ),
                    known_host_interfaces=MatchesListwise([]),
                ),
            ),
        )

    def test_get_machine_pinned_cores(self):
        request = MagicMock()
        pod = make_pod_with_hints()
        pinned_cores = random.sample(range(pod.hints.cores), 3)
        form = ComposeMachineForm(
            data={"pinned_cores": pinned_cores},
            request=request,
            pod=pod,
        )
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine(
            get_known_host_interfaces(pod)
        )
        self.assertEqual(request_machine.pinned_cores, sorted(pinned_cores))

    def test_get_machine_pinned_cores_invalid(self):
        request = MagicMock()
        pod = make_pod_with_hints()
        form = ComposeMachineForm(
            data={"pinned_cores": [0, 1, 789]},
            request=request,
            pod=pod,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("pinned_cores", form.errors)

    def test_get_machine_handles_no_tags_in_storage(self):
        request = MagicMock()
        pod = make_pod_with_hints()
        disk_1 = random.randint(8, 16) * (1000 ** 3)
        disk_2 = random.randint(8, 16) * (1000 ** 3)
        storage = "root:%d,extra:%d" % (
            disk_1 // (1000 ** 3),
            disk_2 // (1000 ** 3),
        )
        form = ComposeMachineForm(
            data={"storage": storage}, request=request, pod=pod
        )
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine(
            get_known_host_interfaces(pod)
        )
        self.assertThat(
            request_machine,
            MatchesAll(
                IsInstance(RequestedMachine),
                MatchesStructure(
                    block_devices=MatchesListwise(
                        [
                            MatchesAll(
                                IsInstance(RequestedMachineBlockDevice),
                                MatchesStructure(
                                    size=Equals(disk_1), tags=Equals([])
                                ),
                            ),
                            MatchesAll(
                                IsInstance(RequestedMachineBlockDevice),
                                MatchesStructure(
                                    size=Equals(disk_2), tags=Equals([])
                                ),
                            ),
                        ]
                    )
                ),
            ),
        )

    def test_get_machine_with_interfaces_fails_no_dhcp_for_vlan(self):
        request = MagicMock()
        pod_host = factory.make_Machine_with_Interface_on_Subnet()
        pod_host.boot_interface.vlan.dhcp_on = False
        pod_host.boot_interface.vlan.save()
        pod = make_pod_with_hints(host=pod_host)
        interfaces = "eth0:subnet=%s" % (
            pod_host.boot_interface.vlan.subnet_set.first().cidr
        )
        form = ComposeMachineForm(
            data={"interfaces": interfaces}, request=request, pod=pod
        )
        self.assertTrue(form.is_valid(), form.errors)
        with ExpectedException(
            ValidationError, ".*DHCP must be enabled on at least one VLAN*"
        ):
            form.get_requested_machine(get_known_host_interfaces(pod))

    def test_get_machine_with_interfaces_fails_for_no_matching_network(self):
        request = MagicMock()
        pod = make_pod_with_hints(with_host=True)
        # Make a subnet that won't match the host via the constraint.
        subnet = factory.make_Subnet()
        interfaces = "eth0:subnet=%s" % (subnet.cidr)
        form = ComposeMachineForm(
            data={"interfaces": interfaces}, request=request, pod=pod
        )
        self.assertTrue(form.is_valid(), form.errors)
        with ExpectedException(
            ValidationError, ".*does not match the specified network.*"
        ):
            form.get_requested_machine(get_known_host_interfaces(pod))

    def test_get_machine_with_interfaces_by_subnet(self):
        request = MagicMock()
        pod_host = factory.make_Machine_with_Interface_on_Subnet()
        space = factory.make_Space("dmz")
        pod_host.boot_interface.vlan.space = space
        pod_host.boot_interface.vlan.save()
        pod = make_pod_with_hints(host=pod_host)
        # Test with a numeric label, since that's what Juju will pass in.
        interfaces = "0:subnet=%s" % (
            pod_host.boot_interface.vlan.subnet_set.first().cidr
        )
        form = ComposeMachineForm(
            data={"interfaces": interfaces}, request=request, pod=pod
        )
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine(
            get_known_host_interfaces(pod)
        )
        self.assertThat(
            request_machine,
            MatchesAll(
                IsInstance(RequestedMachine),
                MatchesStructure(
                    interfaces=MatchesListwise(
                        [
                            MatchesAll(
                                IsInstance(RequestedMachineInterface),
                                MatchesStructure(
                                    # Make sure the numeric label gets converted
                                    # to a sane interface name.
                                    ifname=Equals("eth0"),
                                    attach_name=Equals(
                                        pod_host.boot_interface.name
                                    ),
                                    attach_type=Equals(
                                        InterfaceAttachType.MACVLAN
                                    ),
                                    attach_options=Equals(MACVLAN_MODE.BRIDGE),
                                ),
                            )
                        ]
                    )
                ),
            ),
        )

    def test_get_machine_with_interfaces_with_empty_interfaces_input(self):
        request = MagicMock()
        host = factory.make_Machine_with_Interface_on_Subnet()
        space = factory.make_Space("dmz")
        host.boot_interface.vlan.space = space
        host.boot_interface.vlan.save()
        pod = make_pod_with_hints()
        pod.ip_address = host.boot_interface.ip_addresses.first()
        pod.save()
        form = ComposeMachineForm(
            data=dict(interfaces=""), request=request, pod=pod
        )
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine(
            get_known_host_interfaces(pod)
        )
        self.assertThat(
            request_machine,
            MatchesAll(
                IsInstance(RequestedMachine),
                MatchesStructure(
                    interfaces=MatchesListwise(
                        [
                            MatchesAll(
                                IsInstance(RequestedMachineInterface),
                                MatchesStructure(
                                    attach_name=Is(None),
                                    attach_type=Is(None),
                                    attach_options=Is(None),
                                ),
                            )
                        ]
                    )
                ),
            ),
        )

    def test_get_machine_with_interfaces_with_unreserved_ip(self):
        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        subnet = factory.make_Subnet()
        host = factory.make_Machine_with_Interface_on_Subnet(subnet=subnet)
        space = factory.make_Space("dmz")
        host.boot_interface.vlan.dhcp_on = True
        host.boot_interface.vlan.space = space
        host.boot_interface.vlan.save()
        pod = make_pod_with_hints(host=host)

        # Mock start_commissioning so it doesn't use post commit hooks.
        self.patch(Machine, "start_commissioning")

        # Mock the result of the composed machine.
        composed_machine, pod_hints = self.make_compose_machine_result(pod)
        composed_machine.interfaces = [
            DiscoveredMachineInterface(
                mac_address="00:01:02:03:04:05", boot=True
            )
        ]
        mock_compose_machine = self.patch(pods_module, "compose_machine")
        mock_compose_machine.return_value = succeed(
            (composed_machine, pod_hints)
        )
        request = MagicMock()
        ip = factory.make_StaticIPAddress(
            interface=host.get_boot_interface(), subnet=subnet
        )
        expected_ip = str(ip.ip)
        ip.delete()
        interfaces = "eth0:ip=%s" % expected_ip
        form = ComposeMachineForm(
            data={"interfaces": interfaces}, request=request, pod=pod
        )
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine(
            get_known_host_interfaces(pod)
        )
        self.assertThat(
            request_machine,
            MatchesAll(
                IsInstance(RequestedMachine),
                MatchesStructure(
                    interfaces=MatchesListwise(
                        [
                            MatchesAll(
                                IsInstance(RequestedMachineInterface),
                                MatchesStructure(
                                    requested_ips=Equals(["%s" % expected_ip]),
                                    ifname=Equals("eth0"),
                                    attach_name=Equals(
                                        host.boot_interface.name
                                    ),
                                    attach_type=Equals(
                                        InterfaceAttachType.MACVLAN
                                    ),
                                    attach_options=Equals(MACVLAN_MODE.BRIDGE),
                                ),
                            )
                        ]
                    )
                ),
            ),
        )

    def test_get_machine_with_interfaces_by_subnet_with_default_mode(self):
        request = MagicMock()
        pod_host = factory.make_Machine_with_Interface_on_Subnet()
        space = factory.make_Space("dmz")
        pod_host.boot_interface.vlan.space = space
        pod_host.boot_interface.vlan.save()
        pod = make_pod_with_hints(host=pod_host)
        attach_mode = factory.pick_choice(MACVLAN_MODE_CHOICES)
        pod.default_macvlan_mode = attach_mode
        pod.save()
        interfaces = "eth0:subnet=%s" % (
            pod_host.boot_interface.vlan.subnet_set.first().cidr
        )
        form = ComposeMachineForm(
            data={"interfaces": interfaces}, request=request, pod=pod
        )
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine(
            get_known_host_interfaces(pod)
        )
        self.assertThat(
            request_machine,
            MatchesAll(
                IsInstance(RequestedMachine),
                MatchesStructure(
                    interfaces=MatchesListwise(
                        [
                            MatchesAll(
                                IsInstance(RequestedMachineInterface),
                                MatchesStructure(
                                    attach_name=Equals(
                                        pod_host.boot_interface.name
                                    ),
                                    attach_type=Equals(
                                        InterfaceAttachType.MACVLAN
                                    ),
                                    attach_options=Equals(attach_mode),
                                ),
                            )
                        ]
                    )
                ),
            ),
        )

    def test_get_machine_with_interfaces_by_subnet_with_empty_mode(self):
        request = MagicMock()
        pod_host = factory.make_Machine_with_Interface_on_Subnet()
        space = factory.make_Space("dmz")
        pod_host.boot_interface.vlan.space = space
        pod_host.boot_interface.vlan.save()
        pod = make_pod_with_hints(host=pod_host)
        # We expect the macvlan mode to be the default choice...
        attach_mode = MACVLAN_MODE_CHOICES[0][1]
        # ... when the macvlan mode is set to the empty string.
        pod.default_macvlan_mode = ""
        pod.save()
        interfaces = "eth0:subnet=%s" % (
            pod_host.boot_interface.vlan.subnet_set.first().cidr
        )
        form = ComposeMachineForm(
            data={"interfaces": interfaces}, request=request, pod=pod
        )
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine(
            get_known_host_interfaces(pod)
        )
        self.assertThat(
            request_machine,
            MatchesAll(
                IsInstance(RequestedMachine),
                MatchesStructure(
                    interfaces=MatchesListwise(
                        [
                            MatchesAll(
                                IsInstance(RequestedMachineInterface),
                                MatchesStructure(
                                    attach_name=Equals(
                                        pod_host.boot_interface.name
                                    ),
                                    attach_type=Equals(
                                        InterfaceAttachType.MACVLAN
                                    ),
                                    attach_options=Equals(attach_mode),
                                ),
                            )
                        ]
                    )
                ),
            ),
        )

    def test_get_machine_with_interfaces_by_space(self):
        request = MagicMock()
        pod_host = factory.make_Machine_with_Interface_on_Subnet()
        space = factory.make_Space("dmz")
        pod_host.boot_interface.vlan.space = space
        pod_host.boot_interface.vlan.save()
        pod = make_pod_with_hints(host=pod_host)
        interfaces = "eth0:space=dmz"
        form = ComposeMachineForm(
            data={"interfaces": interfaces}, request=request, pod=pod
        )
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine(
            get_known_host_interfaces(pod)
        )
        self.assertThat(
            request_machine,
            MatchesAll(
                IsInstance(RequestedMachine),
                MatchesStructure(
                    interfaces=MatchesListwise(
                        [
                            MatchesAll(
                                IsInstance(RequestedMachineInterface),
                                MatchesStructure(
                                    attach_name=Equals(
                                        pod.host.boot_interface.name
                                    ),
                                    attach_type=Equals(
                                        InterfaceAttachType.MACVLAN
                                    ),
                                    attach_options=Equals(MACVLAN_MODE.BRIDGE),
                                ),
                            )
                        ]
                    )
                ),
            ),
        )

    def test_get_machine_with_interfaces_by_spaces(self):
        request = MagicMock()
        pod_host = factory.make_Machine_with_Interface_on_Subnet()
        dmz_space = factory.make_Space("dmz")
        storage_space = factory.make_Space("storage")
        # Because PXE booting from the DMZ is /always/ a great idea. ;-)
        pod_host.boot_interface.vlan.space = dmz_space
        pod_host.boot_interface.vlan.save()
        storage_vlan = factory.make_VLAN(space=storage_space, dhcp_on=True)
        storage_if = factory.make_Interface(node=pod_host, vlan=storage_vlan)
        pod = make_pod_with_hints(host=pod_host)
        interfaces = "eth0:space=dmz;eth1:space=storage"
        form = ComposeMachineForm(
            data={"interfaces": interfaces}, request=request, pod=pod
        )
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine(
            get_known_host_interfaces(pod)
        )
        self.assertThat(
            request_machine,
            MatchesAll(
                IsInstance(RequestedMachine),
                MatchesStructure(
                    interfaces=MatchesListwise(
                        [
                            MatchesAll(
                                IsInstance(RequestedMachineInterface),
                                MatchesStructure(
                                    attach_name=Equals(
                                        pod_host.boot_interface.name
                                    ),
                                    attach_type=Equals(
                                        InterfaceAttachType.MACVLAN
                                    ),
                                    attach_options=Equals(MACVLAN_MODE.BRIDGE),
                                ),
                            ),
                            MatchesAll(
                                IsInstance(RequestedMachineInterface),
                                MatchesStructure(
                                    attach_name=Equals(storage_if.name),
                                    attach_type=Equals(
                                        InterfaceAttachType.MACVLAN
                                    ),
                                    attach_options=Equals(MACVLAN_MODE.BRIDGE),
                                ),
                            ),
                        ]
                    )
                ),
            ),
        )

    def test_get_machine_with_interfaces_by_subnets_bridge(self):
        request = MagicMock()
        cidr1 = "10.0.0.0/24"
        cidr2 = "192.168.100.0/24"
        vlan = factory.make_VLAN(dhcp_on=True)
        subnet = factory.make_Subnet(cidr=cidr2, vlan=vlan)
        pod_host = factory.make_Machine_with_Interface_on_Subnet(cidr=cidr1)
        space = factory.make_Space("dmz")
        pod_host.boot_interface.vlan.space = space
        pod_host.boot_interface.vlan.save()

        # Create a bridge and non-bridge on the pod_host
        bridge = factory.make_Interface(
            iftype=INTERFACE_TYPE.BRIDGE,
            node=pod_host,
            subnet=pod_host.boot_interface.vlan.subnet_set.first(),
        )
        non_bridge = factory.make_Interface(node=pod_host, subnet=subnet)

        pod = make_pod_with_hints(host=pod_host)
        interfaces = f"eth0:subnet={cidr1};eth1:subnet={cidr2}"
        form = ComposeMachineForm(
            data={"interfaces": interfaces}, request=request, pod=pod
        )
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine(
            get_known_host_interfaces(pod)
        )
        self.assertThat(
            request_machine,
            MatchesAll(
                IsInstance(RequestedMachine),
                MatchesStructure(
                    interfaces=MatchesListwise(
                        [
                            MatchesAll(
                                IsInstance(RequestedMachineInterface),
                                MatchesStructure(
                                    attach_name=Equals(bridge.name),
                                    attach_type=Equals(
                                        InterfaceAttachType.BRIDGE
                                    ),
                                    attach_options=Equals(None),
                                ),
                            ),
                            MatchesAll(
                                IsInstance(RequestedMachineInterface),
                                MatchesStructure(
                                    attach_name=Equals(non_bridge.name),
                                    attach_type=Equals(
                                        InterfaceAttachType.MACVLAN
                                    ),
                                    attach_options=Equals(MACVLAN_MODE.BRIDGE),
                                ),
                            ),
                        ]
                    )
                ),
            ),
        )

    def test_get_machine_with_interfaces_by_subnets_bond(self):
        request = MagicMock()
        cidr1 = "10.0.0.0/24"
        cidr2 = "192.168.100.0/24"
        vlan = factory.make_VLAN(dhcp_on=True)
        subnet = factory.make_Subnet(cidr=cidr2, vlan=vlan)
        pod_host = factory.make_Machine_with_Interface_on_Subnet(cidr=cidr1)
        space = factory.make_Space("dmz")
        pod_host.boot_interface.vlan.space = space
        pod_host.boot_interface.vlan.save()

        # Create a bond and non-bond on the pod_host
        bond_if = factory.make_Interface(
            node=pod_host,
            subnet=pod_host.boot_interface.vlan.subnet_set.first(),
        )
        bond = factory.make_Interface(
            iftype=INTERFACE_TYPE.BOND,
            node=pod_host,
            parents=[pod_host.boot_interface, bond_if],
            subnet=pod_host.boot_interface.vlan.subnet_set.first(),
        )
        non_bond = factory.make_Interface(node=pod_host, subnet=subnet)

        pod = make_pod_with_hints(host=pod_host)
        interfaces = f"eth0:subnet={cidr1};eth1:subnet={cidr2}"
        form = ComposeMachineForm(
            data={"interfaces": interfaces}, request=request, pod=pod
        )
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine(
            get_known_host_interfaces(pod)
        )
        self.assertThat(
            request_machine,
            MatchesAll(
                IsInstance(RequestedMachine),
                MatchesStructure(
                    interfaces=MatchesListwise(
                        [
                            MatchesAll(
                                IsInstance(RequestedMachineInterface),
                                MatchesStructure(
                                    attach_name=Equals(bond.name),
                                    attach_type=Equals(
                                        InterfaceAttachType.MACVLAN
                                    ),
                                    attach_options=Equals(MACVLAN_MODE.BRIDGE),
                                ),
                            ),
                            MatchesAll(
                                IsInstance(RequestedMachineInterface),
                                MatchesStructure(
                                    attach_name=Equals(non_bond.name),
                                    attach_type=Equals(
                                        InterfaceAttachType.MACVLAN
                                    ),
                                    attach_options=Equals(MACVLAN_MODE.BRIDGE),
                                ),
                            ),
                        ]
                    )
                ),
            ),
        )

    def test_get_machine_with_interfaces_by_subnets_bond_inside_bridge(self):
        request = MagicMock()
        cidr1 = "10.0.0.0/24"
        cidr2 = "192.168.100.0/24"
        vlan = factory.make_VLAN(dhcp_on=True)
        subnet = factory.make_Subnet(cidr=cidr2, vlan=vlan)
        pod_host = factory.make_Machine_with_Interface_on_Subnet(cidr=cidr1)
        space = factory.make_Space("dmz")
        pod_host.boot_interface.vlan.space = space
        pod_host.boot_interface.vlan.save()

        # Create a bond and non-bond on the pod_host
        bond_if = factory.make_Interface(
            node=pod_host,
            subnet=pod_host.boot_interface.vlan.subnet_set.first(),
        )
        bond = factory.make_Interface(
            iftype=INTERFACE_TYPE.BOND,
            node=pod_host,
            parents=[pod_host.boot_interface, bond_if],
            subnet=pod_host.boot_interface.vlan.subnet_set.first(),
        )
        non_bond = factory.make_Interface(node=pod_host, subnet=subnet)
        # Create bridge using the bond
        bridge = factory.make_Interface(
            iftype=INTERFACE_TYPE.BRIDGE,
            node=pod_host,
            parents=[bond],
            subnet=pod_host.boot_interface.vlan.subnet_set.first(),
        )

        pod = make_pod_with_hints(host=pod_host)
        interfaces = f"eth0:subnet={cidr1};eth1:subnet={cidr2}"
        form = ComposeMachineForm(
            data={"interfaces": interfaces}, request=request, pod=pod
        )
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine(
            get_known_host_interfaces(pod)
        )
        self.assertThat(
            request_machine,
            MatchesAll(
                IsInstance(RequestedMachine),
                MatchesStructure(
                    interfaces=MatchesListwise(
                        [
                            MatchesAll(
                                IsInstance(RequestedMachineInterface),
                                MatchesStructure(
                                    attach_name=Equals(bridge.name),
                                    attach_type=Equals(
                                        InterfaceAttachType.BRIDGE
                                    ),
                                    attach_options=Equals(None),
                                ),
                            ),
                            MatchesAll(
                                IsInstance(RequestedMachineInterface),
                                MatchesStructure(
                                    attach_name=Equals(non_bond.name),
                                    attach_type=Equals(
                                        InterfaceAttachType.MACVLAN
                                    ),
                                    attach_options=Equals(MACVLAN_MODE.BRIDGE),
                                ),
                            ),
                        ]
                    )
                ),
            ),
        )

    def test_get_machine_with_interfaces_by_subnets_sriov(self):
        request = MagicMock()
        cidr1 = "10.0.0.0/24"
        cidr2 = "192.168.100.0/24"
        vlan = factory.make_VLAN(dhcp_on=True)
        subnet = factory.make_Subnet(cidr=cidr2, vlan=vlan)
        pod_host = factory.make_Machine_with_Interface_on_Subnet(cidr=cidr1)
        space = factory.make_Space("dmz")
        pod_host.boot_interface.vlan.space = space
        pod_host.boot_interface.vlan.save()
        pod_host.boot_interface.sriov_max_vf = 1
        pod_host.boot_interface.save()

        sriov_if = factory.make_Interface(
            node=pod_host,
            subnet=subnet,
            sriov_max_vf=1,
        )

        pod = make_pod_with_hints(host=pod_host)
        pod.power_type = "lxd"
        pod.save()
        interfaces = f"eth0:subnet={cidr1};eth1:subnet={cidr2}"
        form = ComposeMachineForm(
            data={"interfaces": interfaces}, request=request, pod=pod
        )
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine(
            get_known_host_interfaces(pod)
        )
        self.assertEqual(
            [
                RequestedMachineInterface(
                    ifname="eth0",
                    attach_name=pod_host.boot_interface.name,
                    attach_type=InterfaceAttachType.SRIOV,
                    attach_vlan=None,
                ),
                RequestedMachineInterface(
                    ifname="eth1",
                    attach_name=sriov_if.name,
                    attach_type=InterfaceAttachType.SRIOV,
                    attach_vlan=None,
                ),
            ],
            request_machine.interfaces,
        )

    def test_get_machine_with_interfaces_by_subnets_sriov_vlan(self):
        request = MagicMock()
        cidr1 = "10.0.0.0/24"
        cidr2 = "192.168.100.0/24"
        vlan1 = factory.make_VLAN()
        vlan2 = factory.make_VLAN(fabric=vlan1.fabric)
        subnet = factory.make_Subnet(cidr=cidr2, vlan=vlan2)
        pod_host = factory.make_Machine_with_Interface_on_Subnet(cidr=cidr1)
        space = factory.make_Space("dmz")
        pod_host.boot_interface.vlan.space = space
        pod_host.boot_interface.vlan.save()
        pod_host.boot_interface.sriov_max_vf = 1
        pod_host.boot_interface.save()

        sriov_if = factory.make_Interface(
            node=pod_host,
            sriov_max_vf=1,
            vlan=vlan1,
        )
        factory.make_Interface(
            node=pod_host,
            iftype=INTERFACE_TYPE.VLAN,
            parents=[sriov_if],
            subnet=subnet,
        )

        pod = make_pod_with_hints(host=pod_host)
        pod.power_type = "lxd"
        pod.save()
        interfaces = f"eth0:subnet={cidr1};eth1:subnet={cidr2}"
        form = ComposeMachineForm(
            data={"interfaces": interfaces}, request=request, pod=pod
        )
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine(
            get_known_host_interfaces(pod)
        )
        self.assertEqual(
            [
                RequestedMachineInterface(
                    ifname="eth0",
                    attach_name=pod_host.boot_interface.name,
                    attach_type=InterfaceAttachType.SRIOV,
                    attach_vlan=None,
                ),
                RequestedMachineInterface(
                    ifname="eth1",
                    attach_name=sriov_if.name,
                    attach_type=InterfaceAttachType.SRIOV,
                    attach_vlan=vlan2.vid,
                ),
            ],
            request_machine.interfaces,
        )

    def test_get_machine_with_interfaces_by_space_as_bridge(self):
        request = MagicMock()
        pod_host = factory.make_Machine_with_Interface_on_Subnet(
            status=NODE_STATUS.READY
        )
        space = factory.make_Space("dmz")
        pod_host.boot_interface.vlan.space = space
        pod_host.boot_interface.vlan.save()
        # This is just to make sure a bridge will be available for attachment.
        # We expect bridge mode to be preferred, when available.
        pod_host.acquire(factory.make_User(), bridge_all=True)
        pod = make_pod_with_hints(host=pod_host)
        interfaces = "eth0:space=dmz"
        form = ComposeMachineForm(
            data={"interfaces": interfaces}, request=request, pod=pod
        )
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine(
            get_known_host_interfaces(pod)
        )
        self.assertThat(
            request_machine,
            MatchesAll(
                IsInstance(RequestedMachine),
                MatchesStructure(
                    interfaces=MatchesListwise(
                        [
                            MatchesAll(
                                IsInstance(RequestedMachineInterface),
                                MatchesStructure(
                                    attach_name=Equals(
                                        "br-" + pod_host.boot_interface.name
                                    ),
                                    attach_type=Equals(
                                        InterfaceAttachType.BRIDGE
                                    ),
                                    attach_options=Is(None),
                                ),
                            )
                        ]
                    )
                ),
            ),
        )

    def test_get_machine_with_known_host_interfaces(self):
        # Need to test that it can actually find the pod host's data correctly
        # and that this matches what is expected.
        request = MagicMock()
        pod_host = factory.make_Machine_with_Interface_on_Subnet(
            interface_count=3
        )
        pod = make_pod_with_hints(host=pod_host)
        form = ComposeMachineForm(data={}, request=request, pod=pod)
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine(
            get_known_host_interfaces(pod)
        )
        self.assertThat(
            request_machine,
            MatchesAll(
                IsInstance(RequestedMachine),
                MatchesStructure(
                    known_host_interfaces=MatchesListwise(
                        [
                            MatchesAll(
                                IsInstance(KnownHostInterface),
                                MatchesStructure(
                                    ifname=Equals(interface.name),
                                    attach_type=Equals(
                                        InterfaceAttachType.BRIDGE
                                        if interface.type
                                        == INTERFACE_TYPE.BRIDGE
                                        else InterfaceAttachType.MACVLAN
                                    ),
                                    dhcp_enabled=Equals(
                                        interface.vlan.dhcp_on
                                        or interface.vlan.relay_vlan.dhcp_on
                                    ),
                                ),
                            )
                            for interface in pod.host.current_config.interface_set.all()
                        ]
                    )
                ),
            ),
        )

    def test_compose_with_interfaces_with_reserved_ip_fails(self):
        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        pod = make_pod_with_hints(with_host=True)

        # Mock start_commissioning so it doesn't use post commit hooks.
        self.patch(Machine, "start_commissioning")

        # Mock the result of the composed machine.
        composed_machine, pod_hints = self.make_compose_machine_result(pod)
        composed_machine.interfaces = [
            DiscoveredMachineInterface(
                mac_address="00:01:02:03:04:05",
                attach_type=InterfaceAttachType.NETWORK,
            )
        ]
        mock_compose_machine = self.patch(pods_module, "compose_machine")
        mock_compose_machine.return_value = succeed(
            (composed_machine, pod_hints)
        )

        request = MagicMock()
        subnet = pod.host.boot_interface.ip_addresses.first().subnet
        host = factory.make_Machine_with_Interface_on_Subnet(subnet=subnet)
        space = factory.make_Space("dmz")
        host.boot_interface.vlan.dhcp_on = True
        host.boot_interface.vlan.space = space
        host.boot_interface.vlan.save()
        ip = factory.make_StaticIPAddress(
            interface=host.get_boot_interface(), subnet=subnet
        )
        pod.ip_address = host.boot_interface.ip_addresses.first()
        pod.save()
        interfaces = "eth0:ip=%s" % str(ip.ip)
        form = ComposeMachineForm(
            data={"interfaces": interfaces}, request=request, pod=pod
        )
        self.assertTrue(form.is_valid(), form.errors)
        with ExpectedException(StaticIPAddressUnavailable):
            form.compose()

    def test_compose_with_interfaces_with_unreserved_ip(self):
        mock_post_commit_do = self.patch(pods_module, "post_commit_do")
        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        pod = make_pod_with_hints(with_host=True)

        # Mock start_commissioning so it doesn't use post commit hooks.
        self.patch(Machine, "start_commissioning")

        # Mock the result of the composed machine.
        composed_machine, pod_hints = self.make_compose_machine_result(pod)
        composed_machine.interfaces = [
            DiscoveredMachineInterface(
                mac_address="00:01:02:03:04:05",
                boot=True,
                attach_type=InterfaceAttachType.NETWORK,
            )
        ]
        mock_compose_machine = self.patch(pods_module, "compose_machine")
        mock_compose_machine.return_value = succeed(
            (composed_machine, pod_hints)
        )
        request = MagicMock()
        subnet = pod.host.boot_interface.ip_addresses.first().subnet
        host = factory.make_Machine_with_Interface_on_Subnet(subnet=subnet)
        space = factory.make_Space("dmz")
        host.boot_interface.vlan.dhcp_on = True
        host.boot_interface.vlan.space = space
        host.boot_interface.vlan.save()
        ip = factory.make_StaticIPAddress(
            interface=host.get_boot_interface(), subnet=subnet
        )
        expected_ip = str(ip.ip)
        ip.delete()
        pod.ip_address = host.boot_interface.ip_addresses.first()
        pod.save()
        interfaces = "eth0:ip=%s" % expected_ip
        form = ComposeMachineForm(
            data={"interfaces": interfaces}, request=request, pod=pod
        )
        self.assertTrue(form.is_valid(), form.errors)
        machine = form.compose()
        ip = StaticIPAddress.objects.filter(ip=expected_ip).first()
        self.assertEqual(
            ip.get_interface().node_config, machine.current_config
        )
        self.assertThat(mock_post_commit_do, MockCalledOnce())

    def test_compose_with_commissioning(self):
        mock_post_commit_do = self.patch(pods_module, "post_commit_do")
        request = MagicMock()
        pod = make_pod_with_hints()

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        composed_machine, pod_hints = self.make_compose_machine_result(pod)
        mock_compose_machine = self.patch(pods_module, "compose_machine")
        mock_compose_machine.return_value = succeed(
            (composed_machine, pod_hints)
        )

        # Mock start_commissioning so it doesn't use post commit hooks.
        mock_commissioning = self.patch(Machine, "start_commissioning")

        form = ComposeMachineForm(data={}, request=request, pod=pod)
        self.assertTrue(form.is_valid(), form.errors)
        created_machine = form.compose()
        self.assertThat(
            created_machine,
            MatchesAll(
                IsInstance(Machine),
                MatchesStructure(
                    cpu_count=Equals(DEFAULT_COMPOSED_CORES),
                    memory=Equals(DEFAULT_COMPOSED_MEMORY),
                    cpu_speed=Equals(300),
                ),
            ),
        )
        self.assertThat(mock_commissioning, MockCalledOnce())
        self.assertThat(mock_post_commit_do, MockCalledOnce())

    def test_compose_sends_default_storage_pool_id(self):
        mock_post_commit_do = self.patch(pods_module, "post_commit_do")
        request = MagicMock()
        pod = make_pod_with_hints()

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        composed_machine, pod_hints = self.make_compose_machine_result(pod)
        mock_compose_machine = self.patch(pods_module, "compose_machine")
        mock_compose_machine.return_value = succeed(
            (composed_machine, pod_hints)
        )

        # Mock start_commissioning so it doesn't use post commit hooks.
        self.patch(Machine, "start_commissioning")

        form = ComposeMachineForm(data={}, request=request, pod=pod)
        self.assertTrue(form.is_valid())
        form.compose()
        self.assertThat(
            mock_compose_machine,
            MockCalledOnceWith(
                ANY,
                pod.power_type,
                {
                    "power_address": ANY,
                    "default_storage_pool_id": pod.default_storage_pool.pool_id,
                },
                form.get_requested_machine(get_known_host_interfaces(pod)),
                pod_id=pod.id,
                name=pod.name,
            ),
        )
        self.assertThat(mock_post_commit_do, MockCalledOnce())

    def test_compose_duplicated_hostname(self):
        factory.make_Node(hostname="test")

        request = MagicMock()
        pod = make_pod_with_hints()

        form = ComposeMachineForm(
            data={"hostname": "test"}, request=request, pod=pod
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {"hostname": ['Node with hostname "test" already exists']},
            form.errors,
        )

    def test_compose_hostname_with_underscore(self):
        request = MagicMock()
        pod = make_pod_with_hints()

        form = ComposeMachineForm(
            data={"hostname": "testing_hostname"}, request=request, pod=pod
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "hostname": [
                    "Host label cannot contain underscore: 'testing_hostname'."
                ]
            },
            form.errors,
        )

    def test_compose_without_commissioning(self):
        mock_post_commit_do = self.patch(pods_module, "post_commit_do")
        request = MagicMock()
        pod = make_pod_with_hints()

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        composed_machine, pod_hints = self.make_compose_machine_result(pod)
        mock_compose_machine = self.patch(pods_module, "compose_machine")
        mock_compose_machine.return_value = succeed(
            (composed_machine, pod_hints)
        )

        # Mock start_commissioning so it doesn't use post commit hooks.
        mock_commissioning = self.patch(Machine, "start_commissioning")

        form = ComposeMachineForm(
            data={"skip_commissioning": "true"}, request=request, pod=pod
        )
        self.assertTrue(form.is_valid())
        created_machine = form.compose()
        self.assertThat(
            created_machine,
            MatchesAll(
                IsInstance(Machine),
                MatchesStructure(
                    cpu_count=Equals(DEFAULT_COMPOSED_CORES),
                    memory=Equals(DEFAULT_COMPOSED_MEMORY),
                    cpu_speed=Equals(300),
                ),
            ),
        )
        self.assertThat(mock_commissioning, MockNotCalled())
        self.assertThat(mock_post_commit_do, MockCalledOnce())

    def test_compose_with_skip_commissioning_passed(self):
        mock_post_commit_do = self.patch(pods_module, "post_commit_do")
        request = MagicMock()
        pod = make_pod_with_hints()

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        composed_machine, pod_hints = self.make_compose_machine_result(pod)
        mock_compose_machine = self.patch(pods_module, "compose_machine")
        mock_compose_machine.return_value = succeed(
            (composed_machine, pod_hints)
        )

        # Mock start_commissioning so it doesn't use post commit hooks.
        mock_commissioning = self.patch(Machine, "start_commissioning")

        form = ComposeMachineForm(data={}, request=request, pod=pod)
        self.assertTrue(form.is_valid())
        created_machine = form.compose(skip_commissioning=True)
        self.assertThat(
            created_machine,
            MatchesAll(
                IsInstance(Machine),
                MatchesStructure(
                    cpu_count=Equals(DEFAULT_COMPOSED_CORES),
                    memory=Equals(DEFAULT_COMPOSED_MEMORY),
                    cpu_speed=Equals(300),
                ),
            ),
        )
        self.assertThat(mock_commissioning, MockNotCalled())
        self.assertThat(mock_post_commit_do, MockCalledOnce())

    def test_compose_sets_domain_and_zone(self):
        mock_post_commit_do = self.patch(pods_module, "post_commit_do")
        request = MagicMock()
        pod = make_pod_with_hints()

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        composed_machine, pod_hints = self.make_compose_machine_result(pod)
        mock_compose_machine = self.patch(pods_module, "compose_machine")
        mock_compose_machine.return_value = succeed(
            (composed_machine, pod_hints)
        )

        domain = factory.make_Domain()
        zone = factory.make_Zone()
        form = ComposeMachineForm(
            data={
                "domain": domain.id,
                "zone": zone.id,
                "skip_commissioning": "true",
            },
            request=request,
            pod=pod,
        )
        self.assertTrue(form.is_valid())
        created_machine = form.compose()
        self.assertThat(
            created_machine,
            MatchesAll(
                IsInstance(Machine),
                MatchesStructure(domain=Equals(domain), zone=Equals(zone)),
            ),
        )
        self.assertThat(mock_post_commit_do, MockCalledOnce())

    def test_compose_sets_resource_pool(self):
        mock_post_commit_do = self.patch(pods_module, "post_commit_do")
        request = MagicMock()
        pod = make_pod_with_hints()

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        composed_machine, pod_hints = self.make_compose_machine_result(pod)
        mock_compose_machine = self.patch(pods_module, "compose_machine")
        mock_compose_machine.return_value = succeed(
            (composed_machine, pod_hints)
        )

        pool = factory.make_ResourcePool()
        form = ComposeMachineForm(
            data={"pool": pool.id, "skip_commissioning": "true"},
            request=request,
            pod=pod,
        )
        self.assertTrue(form.is_valid())
        created_machine = form.compose()
        self.assertEqual(pool, created_machine.pool)
        self.assertThat(mock_post_commit_do, MockCalledOnce())

    def test_compose_uses_pod_pool(self):
        mock_post_commit_do = self.patch(pods_module, "post_commit_do")
        request = MagicMock()
        pod = make_pod_with_hints()
        pod.pool = factory.make_ResourcePool()
        pod.save()

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        composed_machine, pod_hints = self.make_compose_machine_result(pod)
        mock_compose_machine = self.patch(pods_module, "compose_machine")
        mock_compose_machine.return_value = succeed(
            (composed_machine, pod_hints)
        )

        form = ComposeMachineForm(
            data={"skip_commissioning": "true"}, request=request, pod=pod
        )
        self.assertTrue(form.is_valid())
        created_machine = form.compose()
        self.assertEqual(pod.pool, created_machine.pool)
        self.assertThat(mock_post_commit_do, MockCalledOnce())

    def test_compose_check_over_commit_ratios_raises_error_for_cores(self):
        request = MagicMock()
        pod = make_pod_with_hints()
        pod.cores = 0
        pod.save()

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        form = ComposeMachineForm(data={}, request=request, pod=pod)
        self.assertTrue(form.is_valid())
        error = self.assertRaises(PodProblem, form.compose)
        self.assertEqual(
            "Unable to compose KVM instance in '%s'. "
            "CPU overcommit ratio is %s and there are %s "
            "available resources; %s requested."
            % (pod.name, pod.cpu_over_commit_ratio, pod.cores, 1),
            str(error),
        )

    def test_compose_check_over_commit_ratios_raises_error_for_memory(self):
        request = MagicMock()
        pod = make_pod_with_hints()
        pod.memory = 0
        pod.save()

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        form = ComposeMachineForm(data={}, request=request, pod=pod)
        self.assertTrue(form.is_valid())
        error = self.assertRaises(PodProblem, form.compose)
        self.assertEqual(
            "Unable to compose KVM instance in '%s'. "
            "Memory overcommit ratio is %s and there are %s "
            "available resources; %s requested."
            % (
                pod.name,
                pod.memory_over_commit_ratio,
                pod.memory,
                DEFAULT_COMPOSED_MEMORY,
            ),
            str(error),
        )

    def test_compose_handles_timeout_error(self):
        request = MagicMock()
        pod = make_pod_with_hints()

        # Mock the RPC client.
        client = MagicMock()
        client.side_effect = crochet.TimeoutError()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        form = ComposeMachineForm(data={}, request=request, pod=pod)
        self.assertTrue(form.is_valid())
        error = self.assertRaises(PodProblem, form.compose)
        self.assertEqual(
            "Unable to compose a machine because '%s' driver timed out "
            "after 120 seconds." % pod.power_type,
            str(error),
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_compose_with_commissioning_in_reactor(self):
        request = MagicMock()
        pod = yield deferToDatabase(make_pod_with_hints, with_host=True)
        mock_request_commissioning_results = self.patch(
            pods_module, "request_commissioning_results"
        )
        mock_request_commissioning_results.return_value = pod

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        composed_machine, pod_hints = self.make_compose_machine_result(pod)
        mock_compose_machine = self.patch(pods_module, "compose_machine")
        mock_compose_machine.return_value = succeed(
            (composed_machine, pod_hints)
        )

        # Mock start_commissioning so it doesn't use post commit hooks.
        mock_commissioning = self.patch(Machine, "start_commissioning")

        def get_free_ip():
            free_ip = factory.make_StaticIPAddress(
                interface=pod.host.boot_interface
            )
            requested_ip = free_ip.ip
            free_ip.delete()
            return requested_ip

        ip = yield deferToDatabase(get_free_ip)

        # Make sure to pass in 'interfaces' so that we fully test the functions
        # that must be deferred to the database.
        form = yield deferToDatabase(
            ComposeMachineForm,
            data=dict(interfaces="eth0:ip=%s" % ip),
            request=request,
            pod=pod,
        )
        is_valid = yield deferToDatabase(form.is_valid)
        self.assertTrue(is_valid)
        created_machine = yield form.compose()
        self.assertThat(
            created_machine,
            MatchesAll(
                IsInstance(Machine),
                MatchesStructure(
                    cpu_count=Equals(DEFAULT_COMPOSED_CORES),
                    memory=Equals(DEFAULT_COMPOSED_MEMORY),
                    cpu_speed=Equals(300),
                ),
            ),
        )
        self.assertThat(mock_commissioning, MockCalledOnce())
        self.assertThat(mock_request_commissioning_results, MockCalledOnce())

    def test_save_raises_AttributeError(self):
        request = MagicMock()
        pod = make_pod_with_hints()
        form = ComposeMachineForm(data={}, request=request, pod=pod)
        self.assertTrue(form.is_valid())
        self.assertRaises(AttributeError, form.save)


class TestComposeMachineForPodsForm(MAASServerTestCase):
    def make_data(self, pods):
        return {
            "cores": random.randint(1, min(pod.hints.cores for pod in pods)),
            "memory": random.randint(
                1024, min(pod.hints.memory for pod in pods)
            ),
            "architecture": random.choice(
                [
                    "amd64/generic",
                    "i386/generic",
                    "arm64/generic",
                    "armhf/generic",
                ]
            ),
        }

    def make_pods(self):
        return [make_pod_with_hints() for _ in range(3)]

    def test_requires_request_kwarg(self):
        error = self.assertRaises(ValueError, ComposeMachineForPodsForm)
        self.assertEqual("'request' kwargs is required.", str(error))

    def test_requires_pods_kwarg(self):
        request = MagicMock()
        error = self.assertRaises(
            ValueError, ComposeMachineForPodsForm, request=request
        )
        self.assertEqual("'pods' kwargs is required.", str(error))

    def test_sets_up_pod_forms_based_on_pods(self):
        request = MagicMock()
        pods = self.make_pods()
        data = self.make_data(pods)
        form = ComposeMachineForPodsForm(request=request, data=data, pods=pods)
        self.assertTrue(form.is_valid())
        self.assertThat(
            form.pod_forms,
            MatchesListwise(
                [
                    MatchesAll(
                        IsInstance(ComposeMachineForm),
                        MatchesStructure(
                            request=Equals(request),
                            data=Equals(data),
                            pod=Equals(pod),
                        ),
                    )
                    for pod in pods
                ]
            ),
        )

    def test_save_raises_AttributeError(self):
        request = MagicMock()
        pods = self.make_pods()
        data = self.make_data(pods)
        form = ComposeMachineForPodsForm(request=request, data=data, pods=pods)
        self.assertTrue(form.is_valid())
        self.assertRaises(AttributeError, form.save)

    def test_compose_uses_non_commit_forms_first(self):
        request = MagicMock()
        pods = self.make_pods()
        # Make it skip the first overcommitable pod
        pods[1].capabilities = [Capabilities.OVER_COMMIT]
        pods[1].save()
        data = self.make_data(pods)
        form = ComposeMachineForPodsForm(request=request, data=data, pods=pods)
        mock_form_compose = self.patch(ComposeMachineForm, "compose")
        mock_form_compose.side_effect = [factory.make_exception(), None]
        self.assertTrue(form.is_valid())

        form.compose()
        self.assertThat(
            mock_form_compose,
            MockCallsMatch(
                call(
                    skip_commissioning=True,
                    dynamic=True,
                ),
                call(
                    skip_commissioning=True,
                    dynamic=True,
                ),
            ),
        )

    def test_compose_uses_commit_forms_second(self):
        request = MagicMock()
        pods = self.make_pods()
        # Make it skip all pods.
        for pod in pods:
            pod.capabilities = [Capabilities.OVER_COMMIT]
            pod.save()
        data = self.make_data(pods)
        form = ComposeMachineForPodsForm(request=request, data=data, pods=pods)
        mock_form_compose = self.patch(ComposeMachineForm, "compose")
        mock_form_compose.side_effect = [
            factory.make_exception(),
            factory.make_exception(),
            factory.make_exception(),
            None,
        ]
        self.assertTrue(form.is_valid())

        form.compose()
        self.assertThat(
            mock_form_compose,
            MockCallsMatch(
                call(
                    skip_commissioning=True,
                    dynamic=True,
                ),
                call(
                    skip_commissioning=True,
                    dynamic=True,
                ),
                call(
                    skip_commissioning=True,
                    dynamic=True,
                ),
            ),
        )

    def test_clean_adds_error_for_no_matching_constraints(self):
        request = MagicMock()
        pods = self.make_pods()
        for pod in pods:
            pod.architectures = ["Not vaild architecture"]
            pod.save()
        data = self.make_data(pods)
        form = ComposeMachineForPodsForm(request=request, data=data, pods=pods)
        self.assertFalse(form.is_valid())


class TestGetKnownHostInterfaces(MAASServerTestCase):
    def test_returns_empty_list_if_no_host(self):
        pod = factory.make_Pod()
        pod.hints.nodes.clear()
        interfaces = get_known_host_interfaces(pod)
        self.assertEqual([], interfaces)

    def test_returns_empty_list_if_no_interfaces(self):
        node = factory.make_Machine_with_Interface_on_Subnet()
        node.current_config.interface_set.all().delete()
        interfaces = get_known_host_interfaces(factory.make_Pod(host=node))
        self.assertThat(interfaces, HasLength(0))

    def test_bridge_attach_type(self):
        node = factory.make_Machine_with_Interface_on_Subnet()
        vlan = factory.make_VLAN(dhcp_on=False)
        node.current_config.interface_set.all().delete()
        bridge = factory.make_Interface(
            iftype=INTERFACE_TYPE.BRIDGE, node=node, vlan=vlan
        )
        interfaces = get_known_host_interfaces(factory.make_Pod(host=node))
        self.assertCountEqual(
            interfaces,
            [
                KnownHostInterface(
                    ifname=bridge.name,
                    attach_type=InterfaceAttachType.BRIDGE,
                    attach_name=bridge.name,
                    attach_vlan=None,
                    dhcp_enabled=False,
                ),
            ],
        )

    def test_macvlan_physical_attach_type(self):
        node = factory.make_Machine_with_Interface_on_Subnet()
        vlan = factory.make_VLAN(dhcp_on=False)
        node.current_config.interface_set.all().delete()
        physical = factory.make_Interface(
            iftype=INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan
        )
        interfaces = get_known_host_interfaces(factory.make_Pod(host=node))
        self.assertCountEqual(
            interfaces,
            [
                KnownHostInterface(
                    ifname=physical.name,
                    attach_name=physical.name,
                    attach_vlan=None,
                    attach_type=InterfaceAttachType.MACVLAN,
                    dhcp_enabled=False,
                ),
            ],
        )

    def test_sriov_physical_attach_type_lxd(self):
        node = factory.make_Machine_with_Interface_on_Subnet()
        vlan = factory.make_VLAN(dhcp_on=False)
        node.current_config.interface_set.all().delete()
        physical = factory.make_Interface(
            iftype=INTERFACE_TYPE.PHYSICAL,
            node=node,
            vlan=vlan,
            sriov_max_vf=1,
        )
        interfaces = get_known_host_interfaces(
            factory.make_Pod(host=node, pod_type="lxd")
        )
        self.assertCountEqual(
            interfaces,
            [
                KnownHostInterface(
                    ifname=physical.name,
                    attach_type=InterfaceAttachType.SRIOV,
                    attach_name=physical.name,
                    attach_vlan=None,
                    dhcp_enabled=False,
                ),
            ],
        )

    def test_sriov_physical_attach_type_virsh(self):
        node = factory.make_Machine_with_Interface_on_Subnet()
        vlan = factory.make_VLAN(dhcp_on=False)
        node.current_config.interface_set.all().delete()
        physical = factory.make_Interface(
            iftype=INTERFACE_TYPE.PHYSICAL,
            node=node,
            vlan=vlan,
            sriov_max_vf=1,
        )
        interfaces = get_known_host_interfaces(
            factory.make_Pod(host=node, pod_type="virsh")
        )
        self.assertCountEqual(
            interfaces,
            [
                KnownHostInterface(
                    ifname=physical.name,
                    attach_type=InterfaceAttachType.MACVLAN,
                    attach_name=physical.name,
                    attach_vlan=None,
                    dhcp_enabled=False,
                ),
            ],
        )

    def test_sriov_vlan_attach_type_lxd(self):
        node = factory.make_Machine_with_Interface_on_Subnet()
        vlan1 = factory.make_VLAN(dhcp_on=False)
        vlan2 = factory.make_VLAN(dhcp_on=False, fabric=vlan1.fabric)
        node.current_config.interface_set.all().delete()
        physical = factory.make_Interface(
            iftype=INTERFACE_TYPE.PHYSICAL,
            node=node,
            vlan=vlan1,
            sriov_max_vf=1,
        )
        vlan_iface = factory.make_Interface(
            iftype=INTERFACE_TYPE.VLAN,
            node=node,
            vlan=vlan2,
            parents=[physical],
        )
        interfaces = get_known_host_interfaces(
            factory.make_Pod(host=node, pod_type="lxd")
        )
        self.assertCountEqual(
            interfaces,
            [
                KnownHostInterface(
                    ifname=physical.name,
                    attach_type=InterfaceAttachType.SRIOV,
                    attach_name=physical.name,
                    attach_vlan=None,
                    dhcp_enabled=False,
                ),
                KnownHostInterface(
                    ifname=vlan_iface.name,
                    attach_type=InterfaceAttachType.SRIOV,
                    attach_name=physical.name,
                    attach_vlan=vlan2.vid,
                    dhcp_enabled=False,
                ),
            ],
        )

    def test_sriov_vlan_attach_type_virsh(self):
        node = factory.make_Machine_with_Interface_on_Subnet()
        vlan1 = factory.make_VLAN(dhcp_on=False)
        vlan2 = factory.make_VLAN(dhcp_on=False, fabric=vlan1.fabric)
        node.current_config.interface_set.all().delete()
        physical = factory.make_Interface(
            iftype=INTERFACE_TYPE.PHYSICAL,
            node=node,
            vlan=vlan1,
            sriov_max_vf=1,
        )
        vlan_iface = factory.make_Interface(
            iftype=INTERFACE_TYPE.VLAN,
            node=node,
            vlan=vlan2,
            parents=[physical],
        )
        interfaces = get_known_host_interfaces(
            factory.make_Pod(host=node, pod_type="virsh")
        )
        self.assertCountEqual(
            interfaces,
            [
                KnownHostInterface(
                    ifname=physical.name,
                    attach_type=InterfaceAttachType.MACVLAN,
                    attach_name=physical.name,
                    attach_vlan=None,
                    dhcp_enabled=False,
                ),
                KnownHostInterface(
                    ifname=vlan_iface.name,
                    attach_type=InterfaceAttachType.MACVLAN,
                    attach_name=vlan_iface.name,
                    dhcp_enabled=False,
                ),
            ],
        )

    def test_behaves_correctly_when_vlan_is_none(self):
        node = factory.make_Machine_with_Interface_on_Subnet()
        node.current_config.interface_set.all().delete()
        bridge = factory.make_Interface(
            iftype=INTERFACE_TYPE.BRIDGE, node=node, link_connected=False
        )
        physical = factory.make_Interface(
            iftype=INTERFACE_TYPE.PHYSICAL, node=node, link_connected=False
        )
        interfaces = get_known_host_interfaces(factory.make_Pod(host=node))
        self.assertCountEqual(
            interfaces,
            [
                KnownHostInterface(
                    ifname=bridge.name,
                    attach_type=InterfaceAttachType.BRIDGE,
                    attach_name=bridge.name,
                    attach_vlan=None,
                    dhcp_enabled=False,
                ),
                KnownHostInterface(
                    ifname=physical.name,
                    attach_type=InterfaceAttachType.MACVLAN,
                    attach_name=physical.name,
                    attach_vlan=None,
                    dhcp_enabled=False,
                ),
            ],
        )

    def test_gets_dhcp_status_for_directly_enabled_vlan(self):
        node = factory.make_Machine_with_Interface_on_Subnet()
        vlan = factory.make_VLAN(dhcp_on=True)
        node.current_config.interface_set.all().delete()
        bridge = factory.make_Interface(
            iftype=INTERFACE_TYPE.BRIDGE, node=node, vlan=vlan
        )
        physical = factory.make_Interface(
            iftype=INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan
        )
        interfaces = get_known_host_interfaces(factory.make_Pod(host=node))
        self.assertCountEqual(
            interfaces,
            [
                KnownHostInterface(
                    ifname=bridge.name,
                    attach_type=InterfaceAttachType.BRIDGE,
                    attach_name=bridge.name,
                    attach_vlan=None,
                    dhcp_enabled=True,
                ),
                KnownHostInterface(
                    ifname=physical.name,
                    attach_type=InterfaceAttachType.MACVLAN,
                    attach_name=physical.name,
                    attach_vlan=None,
                    dhcp_enabled=True,
                ),
            ],
        )

    def test_gets_dhcp_status_for_indirectly_enabled_vlan(self):
        node = factory.make_Machine_with_Interface_on_Subnet()
        relay_vlan = factory.make_VLAN(dhcp_on=True)
        vlan = factory.make_VLAN(dhcp_on=False, relay_vlan=relay_vlan)
        node.current_config.interface_set.all().delete()
        bridge = factory.make_Interface(
            iftype=INTERFACE_TYPE.BRIDGE, node=node, vlan=vlan
        )
        physical = factory.make_Interface(
            iftype=INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan
        )
        interfaces = get_known_host_interfaces(factory.make_Pod(host=node))
        self.assertCountEqual(
            interfaces,
            [
                KnownHostInterface(
                    ifname=bridge.name,
                    attach_type=InterfaceAttachType.BRIDGE,
                    attach_name=bridge.name,
                    attach_vlan=None,
                    dhcp_enabled=True,
                ),
                KnownHostInterface(
                    ifname=physical.name,
                    attach_type=InterfaceAttachType.MACVLAN,
                    attach_name=physical.name,
                    attach_vlan=None,
                    dhcp_enabled=True,
                ),
            ],
        )
