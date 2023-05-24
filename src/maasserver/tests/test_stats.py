# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import base64
import json
from random import randrange

from django.db import transaction
import requests as requests_module
from twisted.application.internet import TimerService
from twisted.internet.defer import fail

from maasserver import stats
from maasserver.enum import (
    BOOT_RESOURCE_FILE_TYPE,
    FILESYSTEM_GROUP_TYPE,
    IPADDRESS_TYPE,
    IPRANGE_TYPE,
    NODE_STATUS,
)
from maasserver.forms import AdminMachineForm
from maasserver.models import (
    BMC,
    BootResourceFile,
    Config,
    Fabric,
    Machine,
    OwnerData,
    ScriptResult,
    ScriptSet,
    Space,
    Subnet,
    VLAN,
)
from maasserver.secrets import SecretManager
from maasserver.stats import (
    get_bmc_stats,
    get_brownfield_stats,
    get_custom_images_deployed_stats,
    get_custom_images_uploaded_stats,
    get_dhcp_snippets_stats,
    get_lxd_initial_auth_stats,
    get_maas_stats,
    get_machine_stats,
    get_machines_by_architecture,
    get_request_params,
    get_storage_layouts_stats,
    get_tags_stats,
    get_tls_configuration_stats,
    get_vault_stats,
    get_vm_hosts_stats,
    get_vmcluster_stats,
    get_workload_annotations_stats,
    make_maas_user_agent_request,
)
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maastesting import get_testing_timeout
from maastesting.testcase import MAASTestCase
from maastesting.twisted import extract_result
from metadataserver.builtin_scripts import load_builtin_scripts
from metadataserver.enum import RESULT_TYPE, SCRIPT_STATUS
from provisioningserver.drivers.pod import DiscoveredPod
from provisioningserver.refresh.node_info_scripts import (
    COMMISSIONING_OUTPUT_NAME,
)
from provisioningserver.testing.certificates import get_sample_cert
from provisioningserver.utils.twisted import asynchronous

TIMEOUT = get_testing_timeout()


class TestMAASStats(MAASServerTestCase):
    def make_pod(
        self,
        cpu=0,
        mem=0,
        cpu_over_commit=1,
        mem_over_commit=1,
        pod_type="virsh",
    ):
        # Make one pod
        zone = factory.make_Zone()
        pool = factory.make_ResourcePool()
        ip = factory.make_ipv4_address()
        power_parameters = {
            "power_address": "qemu+ssh://%s/system" % ip,
            "power_pass": "pass",
        }
        return factory.make_Pod(
            pod_type=pod_type,
            zone=zone,
            pool=pool,
            cores=cpu,
            memory=mem,
            cpu_over_commit_ratio=cpu_over_commit,
            memory_over_commit_ratio=mem_over_commit,
            parameters=power_parameters,
        )

    def test_get_machines_by_architecture(self):
        arches = [
            "amd64/generic",
            "s390x/generic",
            "ppc64el/generic",
            "arm64/generic",
            "i386/generic",
        ]
        for arch in arches:
            factory.make_Machine(architecture=arch)
        stats = get_machines_by_architecture()
        compare = {"amd64": 1, "i386": 1, "arm64": 1, "ppc64el": 1, "s390x": 1}
        self.assertEqual(stats, compare)

    def test_get_vm_hosts_stats(self):
        pod1 = self.make_pod(
            cpu=10, mem=100, cpu_over_commit=2, mem_over_commit=3
        )
        pod2 = self.make_pod(
            cpu=20, mem=200, cpu_over_commit=3, mem_over_commit=2
        )

        total_cores = pod1.cores + pod2.cores
        total_memory = pod1.memory + pod2.memory
        over_cores = (
            pod1.cores * pod1.cpu_over_commit_ratio
            + pod2.cores * pod2.cpu_over_commit_ratio
        )
        over_memory = (
            pod1.memory * pod1.memory_over_commit_ratio
            + pod2.memory * pod2.memory_over_commit_ratio
        )

        stats = get_vm_hosts_stats()
        compare = {
            "vm_hosts": 2,
            "vms": 0,
            "available_resources": {
                "cores": total_cores,
                "memory": total_memory,
                "over_cores": over_cores,
                "over_memory": over_memory,
                "storage": 0,
            },
            "utilized_resources": {"cores": 0, "memory": 0, "storage": 0},
        }
        self.assertEqual(compare, stats)

    def test_get_vm_hosts_stats_filtered(self):
        self.make_pod(cpu=10, mem=100, pod_type="lxd")
        self.make_pod(cpu=20, mem=200, pod_type="virsh")

        stats = get_vm_hosts_stats(power_type="lxd")
        compare = {
            "vm_hosts": 1,
            "vms": 0,
            "available_resources": {
                "cores": 10,
                "memory": 100,
                "over_cores": 10.0,
                "over_memory": 100.0,
                "storage": 0,
            },
            "utilized_resources": {"cores": 0, "memory": 0, "storage": 0},
        }
        self.assertEqual(compare, stats)

    def test_get_vm_hosts_stats_machine_usage(self):
        lxd_vm_host = self.make_pod(cpu=10, mem=100, pod_type="lxd")
        lxd_machine = factory.make_Machine(
            bmc=lxd_vm_host, cpu_count=1, memory=10
        )
        factory.make_VirtualMachine(bmc=lxd_vm_host, machine=lxd_machine)
        virsh_vm_host = self.make_pod(cpu=20, mem=200, pod_type="virsh")
        virsh_machine = factory.make_Machine(
            bmc=virsh_vm_host, cpu_count=2, memory=20
        )
        factory.make_VirtualMachine(bmc=virsh_vm_host, machine=virsh_machine)

        stats = get_vm_hosts_stats(power_type="lxd")
        compare = {
            "vm_hosts": 1,
            "vms": 1,
            "available_resources": {
                "cores": 10,
                "memory": 100,
                "over_cores": 10.0,
                "over_memory": 100.0,
                "storage": 0,
            },
            "utilized_resources": {"cores": 1, "memory": 10, "storage": 0},
        }
        self.assertEqual(compare, stats)

    def test_get_vm_hosts_stats_no_pod(self):
        self.assertEqual(
            get_vm_hosts_stats(),
            {
                "vm_hosts": 0,
                "vms": 0,
                "available_resources": {
                    "cores": 0,
                    "memory": 0,
                    "storage": 0,
                    "over_cores": 0,
                    "over_memory": 0,
                },
                "utilized_resources": {
                    "cores": 0,
                    "memory": 0,
                    "storage": 0,
                },
            },
        )

    def test_get_lxd_initial_auth_stats_empty(self):
        self.assertEqual(
            get_lxd_initial_auth_stats(),
            {
                "trust_password": 0,
                "no_trust_password": 0,
                "maas_generated_cert": 0,
                "user_provided_cert": 0,
                "cert_expiration_days": {
                    "10_days": 0,
                    "1_month": 0,
                    "3_months": 0,
                    "1_year": 0,
                    "2_years": 0,
                    "3_years": 0,
                    "10_years": 0,
                    "more_than_10_years": 0,
                },
            },
        )

    def test_get_lxd_initial_auth_stats_trust_password(self):
        factory.make_Pod(pod_type="virsh", created_with_trust_password=True)
        factory.make_Pod(pod_type="lxd", created_with_trust_password=None)
        for _ in range(3):
            factory.make_Pod(pod_type="lxd", created_with_trust_password=False)
        for _ in range(5):
            factory.make_Pod(pod_type="lxd", created_with_trust_password=True)
        stats = get_lxd_initial_auth_stats()
        self.assertEqual(5, stats["trust_password"])
        self.assertEqual(3, stats["no_trust_password"])

    def test_get_lxd_initial_auth_stats_maas_generated_cert(self):
        factory.make_Pod(
            pod_type="virsh", created_with_maas_generated_cert=True
        )
        factory.make_Pod(pod_type="lxd", created_with_maas_generated_cert=None)
        for _ in range(3):
            factory.make_Pod(
                pod_type="lxd", created_with_maas_generated_cert=False
            )
        for _ in range(5):
            factory.make_Pod(
                pod_type="lxd", created_with_maas_generated_cert=True
            )
        stats = get_lxd_initial_auth_stats()
        self.assertEqual(5, stats["maas_generated_cert"])
        self.assertEqual(3, stats["user_provided_cert"])

    def test_get_lxd_initial_auth_stats_cert_expiration(self):
        factory.make_Pod(pod_type="virsh", created_with_cert_expiration_days=1)
        factory.make_Pod(
            pod_type="lxd", created_with_cert_expiration_days=None
        )
        expected = {
            "10 days": (3, (0, 10)),
            "1 month": (5, (10, 31)),
            "3 months": (7, (31, 92)),
            "1 year": (9, (92, 366)),
            "2 years": (11, (366, 731)),
            "3 years": (13, (731, 1096)),
            "10 years": (17, (1096, 3653)),
            "more than 10 years": (31, (3653, 100000)),
        }
        for count, days_range in expected.values():
            for _ in range(count):
                factory.make_Pod(
                    pod_type="lxd",
                    created_with_cert_expiration_days=randrange(*days_range),
                )
        stats = get_lxd_initial_auth_stats()
        expirations = stats["cert_expiration_days"]
        self.assertEqual(3, expirations["10_days"])
        self.assertEqual(5, expirations["1_month"])
        self.assertEqual(7, expirations["3_months"])
        self.assertEqual(9, expirations["1_year"])
        self.assertEqual(11, expirations["2_years"])
        self.assertEqual(13, expirations["3_years"])
        self.assertEqual(17, expirations["10_years"])
        self.assertEqual(31, expirations["more_than_10_years"])

    def test_get_maas_stats(self):
        # Make one component of everything
        factory.make_RegionRackController()
        factory.make_RegionController()
        factory.make_RackController()
        factory.make_Machine(cpu_count=2, memory=200, status=NODE_STATUS.READY)
        factory.make_Machine(status=NODE_STATUS.READY)
        factory.make_Machine(status=NODE_STATUS.NEW)
        for _ in range(4):
            factory.make_Machine(status=NODE_STATUS.ALLOCATED)
        factory.make_Machine(
            cpu_count=3, memory=100, status=NODE_STATUS.FAILED_DEPLOYMENT
        )
        factory.make_Machine(status=NODE_STATUS.DEPLOYED)
        deployed_machine = factory.make_Machine(status=NODE_STATUS.DEPLOYED)
        OwnerData.objects.set_owner_data(deployed_machine, {"foo": "bar"})
        factory.make_Device()
        factory.make_Device()
        self.make_pod(cpu=10, mem=100, pod_type="lxd")
        self.make_pod(cpu=20, mem=200, pod_type="virsh")

        arch = make_usable_architecture(self)
        osname = factory.make_name()
        factory.make_Machine(
            status=NODE_STATUS.DEPLOYED, osystem="custom", distro_series=osname
        )
        resource = factory.make_custom_boot_resource(
            name=osname,
            architecture=arch,
            base_image="ubuntu/focal",
            filetype=BOOT_RESOURCE_FILE_TYPE.ROOT_DDRAW,
        )

        subnets = Subnet.objects.all()
        v4 = [net for net in subnets if net.get_ip_version() == 4]
        v6 = [net for net in subnets if net.get_ip_version() == 6]

        stats = get_maas_stats()
        machine_stats = get_machine_stats()

        # Due to floating point calculation subtleties, sometimes the value the
        # database returns is off by one compared to the value Python
        # calculates, so just get it directly from the database for the test.
        total_storage = machine_stats["total_storage"]

        expected = {
            "controllers": {"regionracks": 1, "regions": 1, "racks": 1},
            "nodes": {"machines": 11, "devices": 2},
            "machine_stats": {
                "total_cpu": 5,
                "total_mem": 300,
                "total_storage": total_storage,
            },
            "machine_status": {
                "new": 1,
                "ready": 2,
                "allocated": 4,
                "deployed": 3,
                "commissioning": 0,
                "testing": 0,
                "deploying": 0,
                "failed_deployment": 1,
                "failed_commissioning": 0,
                "failed_testing": 0,
                "broken": 0,
            },
            "network_stats": {
                "spaces": Space.objects.count(),
                "fabrics": Fabric.objects.count(),
                "vlans": VLAN.objects.count(),
                "subnets_v4": len(v4),
                "subnets_v6": len(v6),
            },
            "vm_hosts": {
                "lxd": {
                    "vm_hosts": 1,
                    "vms": 0,
                    "available_resources": {
                        "cores": 10,
                        "memory": 100,
                        "over_cores": 10.0,
                        "over_memory": 100.0,
                        "storage": 0,
                    },
                    "utilized_resources": {
                        "cores": 0,
                        "memory": 0,
                        "storage": 0,
                    },
                    "initial_auth": {
                        "trust_password": 0,
                        "no_trust_password": 0,
                        "maas_generated_cert": 0,
                        "user_provided_cert": 0,
                        "cert_expiration_days": {
                            "10_days": 0,
                            "1_month": 0,
                            "3_months": 0,
                            "1_year": 0,
                            "2_years": 0,
                            "3_years": 0,
                            "10_years": 0,
                            "more_than_10_years": 0,
                        },
                    },
                },
                "virsh": {
                    "vm_hosts": 1,
                    "vms": 0,
                    "available_resources": {
                        "cores": 20,
                        "memory": 200,
                        "over_cores": 20.0,
                        "over_memory": 200.0,
                        "storage": 0,
                    },
                    "utilized_resources": {
                        "cores": 0,
                        "memory": 0,
                        "storage": 0,
                    },
                },
            },
            "workload_annotations": {
                "annotated_machines": 1,
                "total_annotations": 1,
                "unique_keys": 1,
                "unique_values": 1,
            },
            "brownfield": {
                "machines_added_deployed_with_bmc": 3,
                "machines_added_deployed_without_bmc": 0,
                "commissioned_after_deploy_brownfield": 0,
                "commissioned_after_deploy_no_brownfield": 0,
            },
            "custom_images": {
                "deployed": 1,
                "uploaded": {
                    f"{resource.base_image}__{BOOT_RESOURCE_FILE_TYPE.ROOT_DDRAW}": 1
                },
            },
            "vmcluster": {
                "available_resources": {
                    "cores": 0,
                    "memory": 0,
                    "over_cores": 0,
                    "over_memory": 0,
                    "storage_local": 0,
                    "storage_shared": 0,
                },
                "projects": 0,
                "utilized_resources": {
                    "cores": 0,
                    "memory": 0,
                    "storage_local": 0,
                    "storage_shared": 0,
                },
                "vm_hosts": 0,
                "vms": 0,
            },
            "storage_layouts": {},
            "tls_configuration": {
                "tls_cert_validity_days": None,
                "tls_enabled": False,
            },
            "bmcs": {
                "auto_detected": {},
                "user_created": {"lxd": 1, "virsh": 2},
                "unknown": {},
            },
            "vault": {
                "enabled": False,
            },
            "dhcp_snippets": {
                "node_count": 0,
                "subnet_count": 0,
                "global_count": 0,
            },
            "tags": {
                "total_count": 0,
                "automatic_tag_count": 0,
                "with_kernel_opts_count": 0,
            },
        }
        self.assertEqual(stats, expected)

    def test_get_machine_stats_only_physical_storage(self):
        node = factory.make_Machine(with_boot_disk=False)
        factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_0
        )
        machine_stats = get_machine_stats()
        self.assertEqual(
            machine_stats["total_storage"],
            sum(disk.size for disk in node.physicalblockdevice_set.all()),
        )

    def test_get_machine_stats_no_storage(self):
        factory.make_Machine(cpu_count=4, memory=100, with_boot_disk=False)
        self.assertEqual(
            get_machine_stats(),
            {"total_cpu": 4, "total_mem": 100, "total_storage": 0},
        )

    def test_get_workload_annotations_stats_machines(self):
        machine1 = factory.make_Machine(status=NODE_STATUS.DEPLOYED)
        machine2 = factory.make_Machine(status=NODE_STATUS.DEPLOYED)
        machine3 = factory.make_Machine(status=NODE_STATUS.DEPLOYED)
        factory.make_Machine(status=NODE_STATUS.DEPLOYED)

        OwnerData.objects.set_owner_data(
            machine1, {"key1": "value1", "key2": "value2"}
        )
        OwnerData.objects.set_owner_data(machine2, {"key1": "value1"})
        OwnerData.objects.set_owner_data(machine3, {"key2": "value2"})

        workload_stats = get_workload_annotations_stats()
        self.assertEqual(3, workload_stats["annotated_machines"])

    def test_get_workload_annotations_stats_keys(self):
        machine1 = factory.make_Machine(status=NODE_STATUS.DEPLOYED)
        machine2 = factory.make_Machine(status=NODE_STATUS.DEPLOYED)
        machine3 = factory.make_Machine(status=NODE_STATUS.DEPLOYED)
        factory.make_Machine(status=NODE_STATUS.DEPLOYED)

        OwnerData.objects.set_owner_data(
            machine1, {"key1": "value1", "key2": "value2"}
        )
        OwnerData.objects.set_owner_data(machine2, {"key1": "value3"})
        OwnerData.objects.set_owner_data(machine3, {"key2": "value2"})

        workload_stats = get_workload_annotations_stats()
        self.assertEqual(4, workload_stats["total_annotations"])
        self.assertEqual(2, workload_stats["unique_keys"])
        self.assertEqual(3, workload_stats["unique_values"])

    def test_get_maas_stats_no_machines(self):
        expected = {
            "controllers": {"regionracks": 0, "regions": 0, "racks": 0},
            "nodes": {"machines": 0, "devices": 0},
            "machine_stats": {
                "total_cpu": 0,
                "total_mem": 0,
                "total_storage": 0,
            },
            "machine_status": {
                "new": 0,
                "ready": 0,
                "allocated": 0,
                "deployed": 0,
                "commissioning": 0,
                "testing": 0,
                "deploying": 0,
                "failed_deployment": 0,
                "failed_commissioning": 0,
                "failed_testing": 0,
                "broken": 0,
            },
            "network_stats": {
                "spaces": 0,
                "fabrics": Fabric.objects.count(),
                "vlans": VLAN.objects.count(),
                "subnets_v4": 0,
                "subnets_v6": 0,
            },
            "vm_hosts": {
                "lxd": {
                    "vm_hosts": 0,
                    "vms": 0,
                    "available_resources": {
                        "cores": 0,
                        "memory": 0,
                        "over_cores": 0.0,
                        "over_memory": 0.0,
                        "storage": 0,
                    },
                    "utilized_resources": {
                        "cores": 0,
                        "memory": 0,
                        "storage": 0,
                    },
                    "initial_auth": {
                        "trust_password": 0,
                        "no_trust_password": 0,
                        "maas_generated_cert": 0,
                        "user_provided_cert": 0,
                        "cert_expiration_days": {
                            "10_days": 0,
                            "1_month": 0,
                            "3_months": 0,
                            "1_year": 0,
                            "2_years": 0,
                            "3_years": 0,
                            "10_years": 0,
                            "more_than_10_years": 0,
                        },
                    },
                },
                "virsh": {
                    "vm_hosts": 0,
                    "vms": 0,
                    "available_resources": {
                        "cores": 0,
                        "memory": 0,
                        "over_cores": 0.0,
                        "over_memory": 0.0,
                        "storage": 0,
                    },
                    "utilized_resources": {
                        "cores": 0,
                        "memory": 0,
                        "storage": 0,
                    },
                },
            },
            "workload_annotations": {
                "annotated_machines": 0,
                "total_annotations": 0,
                "unique_keys": 0,
                "unique_values": 0,
            },
            "brownfield": {
                "machines_added_deployed_with_bmc": 0,
                "machines_added_deployed_without_bmc": 0,
                "commissioned_after_deploy_brownfield": 0,
                "commissioned_after_deploy_no_brownfield": 0,
            },
            "custom_images": {
                "deployed": 0,
                "uploaded": {},
            },
            "vmcluster": {
                "available_resources": {
                    "cores": 0,
                    "memory": 0,
                    "over_cores": 0,
                    "over_memory": 0,
                    "storage_local": 0,
                    "storage_shared": 0,
                },
                "projects": 0,
                "utilized_resources": {
                    "cores": 0,
                    "memory": 0,
                    "storage_local": 0,
                    "storage_shared": 0,
                },
                "vm_hosts": 0,
                "vms": 0,
            },
            "storage_layouts": {},
            "tls_configuration": {
                "tls_cert_validity_days": None,
                "tls_enabled": False,
            },
            "bmcs": {
                "auto_detected": {},
                "user_created": {},
                "unknown": {},
            },
            "vault": {
                "enabled": False,
            },
            "dhcp_snippets": {
                "node_count": 0,
                "subnet_count": 0,
                "global_count": 0,
            },
            "tags": {
                "total_count": 0,
                "automatic_tag_count": 0,
                "with_kernel_opts_count": 0,
            },
        }
        self.assertEqual(get_maas_stats(), expected)

    def test_get_request_params_returns_params(self):
        factory.make_RegionRackController()
        params = {
            "data": base64.b64encode(
                json.dumps(json.dumps(get_maas_stats())).encode()
            ).decode()
        }
        self.assertEqual(params, get_request_params())

    def test_make_user_agent_request(self):
        factory.make_RegionRackController()
        mock = self.patch(requests_module, "get")
        make_maas_user_agent_request()
        mock.assert_called_once()

    def test_get_custom_static_images_uploaded_stats(self):
        for _ in range(0, 2):
            factory.make_usable_boot_resource(
                name="custom/%s" % factory.make_name("name"),
                base_image="ubuntu/focal",
            ),
        factory.make_usable_boot_resource(
            name="custom/%s" % factory.make_name("name"),
            base_image="ubuntu/bionic",
        ),
        stats = get_custom_images_uploaded_stats()
        total = 0
        for stat in stats:
            total += stat["count"]
        expected_total = (
            BootResourceFile.objects.exclude(
                resource_set__resource__base_image__isnull=True,
                resource_set__resource__base_image="",
            )
            .distinct()
            .count()
        )
        self.assertEqual(total, expected_total)

    def test_get_custom_static_images_deployed_stats(self):
        for _ in range(0, 2):
            machine = factory.make_Machine(status=NODE_STATUS.DEPLOYED)
            machine.osystem = "custom"
            machine.distro_series = factory.make_name("name")
            machine.save()
        self.assertEqual(get_custom_images_deployed_stats(), 2)

    def test_vmcluster_stats(self):
        GiB = 2**30
        GB = 10**9

        # create clusters
        factory.make_VMCluster(
            pods=1,
            vms=2,
            memory=4096,
            cores=8,
            vm_memory=512,
            storage=100 * GB,
            disk_size=10 * GB,
        )
        factory.make_VMCluster(
            pods=2,
            vms=2,
            memory=4096,
            cores=8,
            vm_memory=512,
            storage=100 * GB,
            disk_size=10 * GB,
        )
        # create VMHost and VM not part of a cluster
        pod = factory.make_Pod()
        factory.make_VirtualMachine(bmc=pod)

        # only cluster elements should be counted
        cluster_stats = get_vmcluster_stats()
        self.assertEqual(cluster_stats["projects"], 2)
        self.assertEqual(cluster_stats["vm_hosts"], 3)
        self.assertEqual(cluster_stats["vms"], 6)
        self.assertEqual(cluster_stats["available_resources"]["cores"], 24)
        self.assertEqual(
            cluster_stats["available_resources"]["memory"], 12 * GiB
        )
        self.assertEqual(
            cluster_stats["available_resources"]["over_cores"], 24
        )
        self.assertEqual(
            cluster_stats["available_resources"]["over_memory"], 12 * GiB
        )
        self.assertEqual(
            cluster_stats["available_resources"]["storage_local"], 300 * GB
        )
        self.assertEqual(
            cluster_stats["available_resources"]["storage_shared"], 0
        )
        self.assertEqual(cluster_stats["utilized_resources"]["cores"], 12)
        self.assertEqual(
            cluster_stats["utilized_resources"]["memory"], 3 * GiB
        )
        self.assertEqual(
            cluster_stats["utilized_resources"]["storage_local"], 60 * GB
        )
        self.assertEqual(
            cluster_stats["utilized_resources"]["storage_shared"], 0
        )

    def test_get_storage_layouts_stats(self):
        counts = {
            "bcache": 5,
            "flat": 4,
            "lvm": 3,
        }
        for layout, count in counts.items():
            for _ in range(count):
                node = factory.make_Node()
                node.set_storage_layout(layout)
        # nodes with no storage layout applied are not reported
        for _ in range(2):
            factory.make_Node()
        self.assertEqual(get_storage_layouts_stats(), counts)

    def test_get_tls_configuration_stats(self):
        cert = get_sample_cert()
        SecretManager().set_composite_secret(
            "tls",
            {
                "key": cert.private_key_pem(),
                "cert": cert.certificate_pem(),
            },
        )
        self.assertEqual(
            {
                "tls_cert_validity_days": 3650,
                "tls_enabled": True,
            },
            get_tls_configuration_stats(),
        )

    def test_get_tls_configuration_stats_not_set(self):
        self.assertEqual(
            {
                "tls_cert_validity_days": None,
                "tls_enabled": False,
            },
            get_tls_configuration_stats(),
        )

    def test_get_vault_stats_vault_enabled(self):
        Config.objects.set_config("vault_enabled", True)
        self.assertEqual({"enabled": True}, get_vault_stats())

    def test_get_vault_stats_vault_disabled(self):
        Config.objects.set_config("vault_enabled", False)
        self.assertEqual({"enabled": False}, get_vault_stats())

    def test_get_dhcp_snippet_stats(self):
        for _ in range(3):
            node = factory.make_Node()
            factory.make_DHCPSnippet(node=node)

        for _ in range(4):
            subnet = factory.make_Subnet()
            factory.make_DHCPSnippet(subnet=subnet)

        for _ in range(5):
            factory.make_DHCPSnippet()

        self.assertEqual(
            {"node_count": 3, "subnet_count": 4, "global_count": 5},
            get_dhcp_snippets_stats(),
        )

    def test_get_tags_stats(self):
        for _ in range(2):
            factory.make_Tag(definition="", kernel_opts="")

        for _ in range(2):
            factory.make_Tag(definition="//node", kernel_opts="")

        for _ in range(3):
            factory.make_Tag(definition="", kernel_opts=factory.make_name())

        for _ in range(3):
            factory.make_Tag(
                definition="//node", kernel_opts=factory.make_name()
            )

        self.assertEqual(
            {
                "total_count": 10,
                "automatic_tag_count": 5,
                "with_kernel_opts_count": 6,
            },
            get_tags_stats(),
        )


class FakeRequest:
    def __init__(self, user):
        self.user = user


class TestGetBrownfieldStats(MAASServerTestCase):
    def _make_brownfield_machine(self):
        admin = factory.make_admin()
        # Use the form to create the brownfield node, so that it gets
        # created in the same way as in a real MAAS deployement.
        form = AdminMachineForm(
            request=FakeRequest(admin),
            data={
                "hostname": factory.make_string(),
                "deployed": True,
            },
        )
        return form.save()

    def _make_normal_deployed_machine(self):
        machine = factory.make_Machine(
            status=NODE_STATUS.DEPLOYED, previous_status=NODE_STATUS.DEPLOYING
        )
        machine.current_commissioning_script_set = (
            ScriptSet.objects.create_commissioning_script_set(machine)
        )
        machine.current_installation_script_set = factory.make_ScriptSet(
            node=machine, result_type=RESULT_TYPE.INSTALLATION
        )
        factory.make_ScriptResult(
            script_set=machine.current_installation_script_set,
            status=SCRIPT_STATUS.PASSED,
            exit_status=0,
        )
        machine.save()
        return machine

    def _make_pod_machine(self):
        factory.make_usable_boot_resource(architecture="amd64/generic")
        pod = factory.make_Pod()
        mac_addresses = [factory.make_mac_address() for _ in range(3)]
        sync_user = factory.make_User()
        return pod.sync(
            DiscoveredPod(
                architectures=["amd64/generic"], mac_addresses=mac_addresses
            ),
            sync_user,
        )

    def _update_commissioning(self, machine):
        commissioning_result = ScriptResult.objects.get(
            script_set=machine.current_commissioning_script_set,
            script_name=COMMISSIONING_OUTPUT_NAME,
        )
        commissioning_result.store_result(exit_status=0)

    def test_added_deployed(self):
        machine = self._make_brownfield_machine()
        machine.bmc = factory.make_BMC()
        machine.save()
        for _ in range(2):
            machine = self._make_brownfield_machine()
            machine.bmc = None
            machine.save()
        normal = self._make_normal_deployed_machine()
        factory.make_Machine(status=NODE_STATUS.READY)
        # If pods and controllers are registered in MAAS, that don't
        # have a corresponding machine already, MAAS will basically
        # create them as brownfield nodes. We don't want those included
        # in the stats.
        pod = self._make_pod_machine()
        controller = factory.make_Controller()
        brownfield_machines = Machine.objects.filter(
            current_installation_script_set__isnull=True,
            dynamic=False,
        ).all()
        self.assertNotIn(normal, brownfield_machines)
        self.assertNotIn(controller, brownfield_machines)
        self.assertNotIn(pod, brownfield_machines)
        stats = get_brownfield_stats()
        self.assertEqual(1, stats["machines_added_deployed_with_bmc"])
        self.assertEqual(2, stats["machines_added_deployed_without_bmc"])

    def test_commission_after_deploy_brownfield(self):
        load_builtin_scripts()
        self._update_commissioning(self._make_brownfield_machine())
        self._make_brownfield_machine()
        for _ in range(2):
            self._update_commissioning(self._make_normal_deployed_machine())
        self._make_normal_deployed_machine()
        # If pods and controllers are registered in MAAS, that don't
        # have a corresponding machine already, MAAS will basically
        # create them as brownfield nodes. We don't want those included
        # in the stats.
        self._make_pod_machine()
        factory.make_Controller()
        stats = get_brownfield_stats()
        self.assertEqual(1, stats["commissioned_after_deploy_brownfield"])
        self.assertEqual(2, stats["commissioned_after_deploy_no_brownfield"])


class TestGetSubnetsUtilisationStats(MAASServerTestCase):
    def test_stats_totals(self):
        factory.make_Subnet(cidr="1.2.0.0/16", gateway_ip="1.2.0.254")
        factory.make_Subnet(cidr="::1/128", gateway_ip="")
        self.assertEqual(
            stats.get_subnets_utilisation_stats(),
            {
                "1.2.0.0/16": {
                    "available": 2**16 - 3,
                    "dynamic_available": 0,
                    "dynamic_used": 0,
                    "reserved_available": 0,
                    "reserved_used": 0,
                    "static": 0,
                    "unavailable": 1,
                },
                "::1/128": {
                    "available": 1,
                    "dynamic_available": 0,
                    "dynamic_used": 0,
                    "reserved_available": 0,
                    "reserved_used": 0,
                    "static": 0,
                    "unavailable": 0,
                },
            },
        )

    def test_stats_dynamic(self):
        subnet = factory.make_Subnet(cidr="1.2.0.0/16", gateway_ip="1.2.0.254")
        factory.make_IPRange(
            subnet=subnet,
            start_ip="1.2.0.11",
            end_ip="1.2.0.20",
            alloc_type=IPRANGE_TYPE.DYNAMIC,
        )
        factory.make_IPRange(
            subnet=subnet,
            start_ip="1.2.0.51",
            end_ip="1.2.0.60",
            alloc_type=IPRANGE_TYPE.DYNAMIC,
        )
        factory.make_StaticIPAddress(
            ip="1.2.0.15", alloc_type=IPADDRESS_TYPE.DHCP, subnet=subnet
        )
        factory.make_StaticIPAddress(
            ip="1.2.0.52", alloc_type=IPADDRESS_TYPE.DHCP, subnet=subnet
        )
        self.assertEqual(
            stats.get_subnets_utilisation_stats(),
            {
                "1.2.0.0/16": {
                    "available": 2**16 - 23,
                    "dynamic_available": 18,
                    "dynamic_used": 2,
                    "reserved_available": 0,
                    "reserved_used": 0,
                    "static": 0,
                    "unavailable": 21,
                }
            },
        )

    def test_stats_reserved(self):
        subnet = factory.make_Subnet(cidr="1.2.0.0/16", gateway_ip="1.2.0.254")
        factory.make_IPRange(
            subnet=subnet,
            start_ip="1.2.0.11",
            end_ip="1.2.0.20",
            alloc_type=IPRANGE_TYPE.RESERVED,
        )
        factory.make_IPRange(
            subnet=subnet,
            start_ip="1.2.0.51",
            end_ip="1.2.0.60",
            alloc_type=IPRANGE_TYPE.RESERVED,
        )
        factory.make_StaticIPAddress(
            ip="1.2.0.15",
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            subnet=subnet,
        )
        self.assertEqual(
            stats.get_subnets_utilisation_stats(),
            {
                "1.2.0.0/16": {
                    "available": 2**16 - 23,
                    "dynamic_available": 0,
                    "dynamic_used": 0,
                    "reserved_available": 19,
                    "reserved_used": 1,
                    "static": 0,
                    "unavailable": 21,
                }
            },
        )

    def test_stats_static(self):
        subnet = factory.make_Subnet(cidr="1.2.0.0/16", gateway_ip="1.2.0.254")
        for n in (10, 20, 30):
            factory.make_StaticIPAddress(
                ip=f"1.2.0.{n}",
                alloc_type=IPADDRESS_TYPE.STICKY,
                subnet=subnet,
            )
        self.assertEqual(
            stats.get_subnets_utilisation_stats(),
            {
                "1.2.0.0/16": {
                    "available": 2**16 - 6,
                    "dynamic_available": 0,
                    "dynamic_used": 0,
                    "reserved_available": 0,
                    "reserved_used": 0,
                    "static": 3,
                    "unavailable": 4,
                }
            },
        )

    def test_stats_all(self):
        subnet = factory.make_Subnet(cidr="1.2.0.0/16", gateway_ip="1.2.0.254")
        factory.make_IPRange(
            subnet=subnet,
            start_ip="1.2.0.11",
            end_ip="1.2.0.20",
            alloc_type=IPRANGE_TYPE.DYNAMIC,
        )
        factory.make_IPRange(
            subnet=subnet,
            start_ip="1.2.0.51",
            end_ip="1.2.0.70",
            alloc_type=IPRANGE_TYPE.RESERVED,
        )
        factory.make_StaticIPAddress(
            ip="1.2.0.12", alloc_type=IPADDRESS_TYPE.DHCP, subnet=subnet
        )
        for n in (60, 61):
            factory.make_StaticIPAddress(
                ip=f"1.2.0.{n}",
                alloc_type=IPADDRESS_TYPE.USER_RESERVED,
                subnet=subnet,
            )
        for n in (80, 90, 100):
            factory.make_StaticIPAddress(
                ip=f"1.2.0.{n}",
                alloc_type=IPADDRESS_TYPE.STICKY,
                subnet=subnet,
            )
        self.assertEqual(
            stats.get_subnets_utilisation_stats(),
            {
                "1.2.0.0/16": {
                    "available": 2**16 - 36,
                    "dynamic_available": 9,
                    "dynamic_used": 1,
                    "reserved_available": 18,
                    "reserved_used": 2,
                    "static": 3,
                    "unavailable": 34,
                }
            },
        )


class TestGetBMCStats(MAASServerTestCase):
    def test_get_bmc_stats_no_bmcs(self):
        self.assertEqual(0, BMC.objects.all().count())
        self.assertEqual(
            {
                "auto_detected": {},
                "user_created": {},
                "unknown": {},
            },
            get_bmc_stats(),
        )

    def test_get_bmc_stats_with_bmcs(self):
        factory.make_BMC(power_type="redfish", created_by_commissioning=True)
        factory.make_BMC(power_type="ipmi", created_by_commissioning=False)
        factory.make_BMC(power_type="lxd", created_by_commissioning=None)
        self.assertEqual(
            {
                "auto_detected": {"redfish": 1},
                "user_created": {
                    "ipmi": 1,
                },
                "unknown": {
                    "lxd": 1,
                },
            },
            get_bmc_stats(),
        )


class TestStatsService(MAASTestCase):
    """Tests for `ImportStatsService`."""

    def test_is_a_TimerService(self):
        service = stats.StatsService()
        self.assertIsInstance(service, TimerService)

    def test_runs_once_a_day(self):
        service = stats.StatsService()
        self.assertEqual(86400, service.step)

    def test_calls__maybe_make_stats_request(self):
        service = stats.StatsService()
        self.assertEqual(
            (service.maybe_make_stats_request, (), {}), service.call
        )

    def test_maybe_make_stats_request_does_not_error(self):
        service = stats.StatsService()
        deferToDatabase = self.patch(stats, "deferToDatabase")
        exception_type = factory.make_exception_type()
        deferToDatabase.return_value = fail(exception_type())
        d = service.maybe_make_stats_request()
        self.assertIsNone(extract_result(d))


class TestStatsServiceAsync(MAASTransactionServerTestCase):
    """Tests for the async parts of `StatsService`."""

    def test_maybe_make_stats_request_makes_request(self):
        mock_call = self.patch(stats, "make_maas_user_agent_request")

        with transaction.atomic():
            Config.objects.set_config("enable_analytics", True)

        service = stats.StatsService()
        maybe_make_stats_request = asynchronous(
            service.maybe_make_stats_request
        )
        maybe_make_stats_request().wait(TIMEOUT)

        mock_call.assert_called_once()

    def test_maybe_make_stats_request_doesnt_make_request(self):
        mock_call = self.patch(stats, "make_maas_user_agent_request")

        with transaction.atomic():
            Config.objects.set_config("enable_analytics", False)

        service = stats.StatsService()
        maybe_make_stats_request = asynchronous(
            service.maybe_make_stats_request
        )
        maybe_make_stats_request().wait(TIMEOUT)

        mock_call.assert_not_called()
