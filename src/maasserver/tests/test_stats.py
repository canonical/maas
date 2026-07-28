# Copyright 2014-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import base64
import json
from pathlib import Path

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
    get_ansible_stats,
    get_bmc_stats,
    get_brownfield_stats,
    get_custom_images_deployed_stats,
    get_custom_images_uploaded_stats,
    get_dhcp_snippets_stats,
    get_maas_stats,
    get_machine_stats,
    get_machines_by_architecture,
    get_request_params,
    get_storage_layouts_stats,
    get_tags_stats,
    get_tls_configuration_stats,
    get_vault_stats,
    get_workload_annotations_stats,
    make_maas_user_agent_request,
)
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import post_commit_hooks
from maastesting import get_testing_timeout
from maastesting.fixtures import TempDirectory
from maastesting.testcase import MAASTestCase
from maastesting.twisted import extract_result
from metadataserver.builtin_scripts import load_builtin_scripts
from metadataserver.enum import RESULT_TYPE, SCRIPT_STATUS
from provisioningserver.refresh.node_info_scripts import (
    COMMISSIONING_OUTPUT_NAME,
)
from provisioningserver.testing.certificates import get_sample_cert
from provisioningserver.utils.twisted import asynchronous

TIMEOUT = get_testing_timeout()


class TestMAASStats(MAASServerTestCase):
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
            "storage_layouts": {},
            "tls_configuration": {
                "tls_cert_validity_days": None,
                "tls_enabled": False,
            },
            "bmcs": {
                "auto_detected": {},
                "user_created": {"virsh": 1},
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
            "ansible": {
                "ansible_installs": 0,
            },
            "site_manager_connection": {
                "connected": False,
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
            "ansible": {
                "ansible_installs": 0,
            },
            "site_manager_connection": {
                "connected": False,
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
            (
                factory.make_usable_boot_resource(
                    name="custom/%s" % factory.make_name("name"),
                    base_image="ubuntu/focal",
                ),
            )
        (
            factory.make_usable_boot_resource(
                name="custom/%s" % factory.make_name("name"),
                base_image="ubuntu/bionic",
            ),
        )
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

    def test_ansible_stats(self):
        tempdir = self.useFixture(TempDirectory())
        stat = Path(tempdir.path + "/.ansible")
        stat.write_text("")
        self.assertEqual(
            {
                "ansible_installs": 1,
            },
            get_ansible_stats(stat),
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
        with post_commit_hooks:
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

    def _update_commissioning(self, machine):
        commissioning_result = ScriptResult.objects.get(
            script_set=machine.current_commissioning_script_set,
            script_name=COMMISSIONING_OUTPUT_NAME,
        )
        commissioning_result.store_result(exit_status=0)

    def test_added_deployed(self):
        machine = self._make_brownfield_machine()
        machine.bmc = factory.make_BMC()

        with post_commit_hooks:
            machine.save()
        for _ in range(2):
            machine = self._make_brownfield_machine()
            machine.bmc = None
            with post_commit_hooks:
                machine.save()
        normal = self._make_normal_deployed_machine()
        factory.make_Machine(status=NODE_STATUS.READY)
        controller = factory.make_Controller()
        brownfield_machines = Machine.objects.filter(
            current_installation_script_set__isnull=True,
            dynamic=False,
        ).all()
        self.assertNotIn(normal, brownfield_machines)
        self.assertNotIn(controller, brownfield_machines)
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
