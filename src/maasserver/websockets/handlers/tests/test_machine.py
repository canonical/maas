# Copyright 2016-2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from datetime import datetime, timedelta
import json
import logging
from operator import itemgetter
import random
import re
from types import FunctionType
from unittest.mock import ANY

from django.core.exceptions import ValidationError
from django.http import HttpRequest
from lxml import etree
from testtools.content import text_content
from twisted.internet.defer import inlineCallbacks

from maasserver.enum import (
    BMC_TYPE,
    BOND_MODE,
    BRIDGE_TYPE,
    BRIDGE_TYPE_CHOICES,
    CACHE_MODE_TYPE,
    FILESYSTEM_FORMAT_TYPE_CHOICES,
    FILESYSTEM_FORMAT_TYPE_CHOICES_DICT,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_STATUS_SHORT_LABEL_CHOICES,
    NODE_TYPE,
    PARTITION_TABLE_TYPE,
    POWER_STATE,
    SIMPLIFIED_NODE_STATUS,
    SIMPLIFIED_NODE_STATUS_CHOICES,
)
from maasserver.exceptions import NodeActionError, NodeStateViolation
from maasserver.forms import AdminMachineWithMACAddressesForm
from maasserver.models import (
    Bcache,
    CacheSet,
    Config,
    Filesystem,
    Interface,
    Machine,
    Node,
    OwnerData,
    Partition,
    RAID,
    VolumeGroup,
)
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.nodekey import NodeKey
from maasserver.models.nodeprobeddetails import (
    get_single_probed_details,
    script_output_nsmap,
)
from maasserver.models.partition import (
    MIN_PARTITION_SIZE,
    PARTITION_ALIGNMENT_SIZE,
)
from maasserver.models.scriptset import get_status_from_qs
import maasserver.node_action as node_action_module
from maasserver.node_action import compile_node_actions
from maasserver.permissions import NodePermission
from maasserver.rbac import FakeRBACClient, rbac
from maasserver.secrets import SecretManager
from maasserver.storage_layouts import (
    get_applied_storage_layout_for_node,
    MIN_BOOT_PARTITION_SIZE,
    STORAGE_LAYOUT_CHOICES,
    VMFS6StorageLayout,
    VMFS7StorageLayout,
)
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.fixtures import RBACForceOffFixture
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.tests.test_storage_layouts import LARGE_BLOCK_DEVICE
from maasserver.third_party_drivers import get_third_party_driver
from maasserver.utils.converters import (
    human_readable_bytes,
    round_size_to_nearest_block,
    XMLToYAML,
)
from maasserver.utils.orm import get_one, reload_object, transactional
from maasserver.utils.osystems import make_hwe_kernel_ui_text
from maasserver.utils.threads import deferToDatabase
from maasserver.websockets.base import (
    DATETIME_FORMAT,
    dehydrate_datetime,
    HandlerDoesNotExistError,
    HandlerError,
    HandlerPermissionError,
    HandlerValidationError,
)
from maasserver.websockets.handlers import machine as machine_module
from maasserver.websockets.handlers import node as node_module
from maasserver.websockets.handlers.event import dehydrate_event_type_level
from maasserver.websockets.handlers.machine import MachineHandler
from maasserver.websockets.handlers.machine import Node as node_model
from maasserver.websockets.handlers.node import NODE_TYPE_TO_LINK_TYPE
from maasserver.websockets.handlers.node_result import NodeResultHandler
from maasserver.workflow import power as power_workflow
from maastesting.crochet import wait_for
from maastesting.djangotestcase import count_queries
from maastesting.twisted import TwistedLoggerFixture
from metadataserver.enum import (
    HARDWARE_TYPE,
    HARDWARE_TYPE_CHOICES,
    RESULT_TYPE,
    SCRIPT_STATUS,
    SCRIPT_STATUS_FAILED,
    SCRIPT_TYPE,
)
from provisioningserver.refresh.node_info_scripts import (
    LIST_MODALIASES_OUTPUT_NAME,
    LLDP_OUTPUT_NAME,
)
from provisioningserver.rpc.exceptions import UnknownPowerType
from provisioningserver.tags import merge_details_cleanly
from provisioningserver.testing.certificates import get_sample_cert
from provisioningserver.utils.enum import map_enum_reverse

wait_for_reactor = wait_for()


class FakeRequest:
    def __init__(self, user):
        self.user = user


class TestMachineHandlerUtils:
    @staticmethod
    def get_blockdevice_status(handler, blockdevice):
        blockdevice_script_results = [
            script_result
            for results in handler._script_results.values()
            for script_results in results.values()
            for script_result in script_results
            if script_result.physical_blockdevice == blockdevice
        ]
        return get_status_from_qs(blockdevice_script_results)

    @staticmethod
    def dehydrate_node(node, handler, for_list=False):
        # Prime handler._script_results
        handler._script_results = {}
        if for_list:
            handler._cache_script_results_for_list([node])
        else:
            handler._cache_script_results([node])

        boot_interface = node.get_boot_interface()
        subnets = handler.get_all_subnets(node)

        blockdevices = [
            blockdevice.actual_instance
            for blockdevice in node.current_config.blockdevice_set.all()
        ]
        disks = [
            handler.dehydrate_blockdevice(blockdevice, node)
            for blockdevice in blockdevices
        ]
        disks = (
            disks
            + [
                handler.dehydrate_volume_group(volume_group)
                for volume_group in VolumeGroup.objects.filter_by_node(node)
            ]
            + [
                handler.dehydrate_cache_set(cache_set)
                for cache_set in CacheSet.objects.get_cache_sets_for_node(node)
            ]
        )
        disks = sorted(disks, key=itemgetter("name"))
        driver = get_third_party_driver(node)

        commissioning_scripts = node.get_latest_commissioning_script_results
        commissioning_scripts = commissioning_scripts.exclude(
            status=SCRIPT_STATUS.ABORTED
        )
        commissioning_start_time = None
        for script_result in commissioning_scripts:
            if commissioning_start_time is None or (
                script_result.started
                and script_result.started < commissioning_start_time
            ):
                commissioning_start_time = script_result.started
        testing_scripts = node.get_latest_testing_script_results
        testing_scripts = testing_scripts.exclude(status=SCRIPT_STATUS.ABORTED)
        log_results = set()
        for script_result in commissioning_scripts:
            if (
                script_result.name in script_output_nsmap
                and script_result.status == SCRIPT_STATUS.PASSED
            ):
                log_results.add(script_result.name)

        permissions = []
        if handler.user is not None and handler.user.has_perm(
            NodePermission.admin, node
        ):
            permissions = ["edit", "delete"]

        data = {
            "actions": list(compile_node_actions(node, handler.user).keys()),
            "architecture": node.architecture,
            "bmc": node.bmc_id,
            "boot_disk": node.boot_disk.id if node.boot_disk else None,
            "bios_boot_method": node.bios_boot_method,
            "commissioning_status": handler.dehydrate_test_statuses(
                commissioning_scripts
            ),
            "current_commissioning_script_set": (
                node.current_commissioning_script_set_id
            ),
            "commissioning_start_time": dehydrate_datetime(
                commissioning_start_time
            ),
            "current_testing_script_set": node.current_testing_script_set_id,
            "current_installation_script_set": (
                node.current_installation_script_set_id
            ),
            "installation_status": (
                handler.dehydrate_script_set_status(
                    node.current_installation_script_set
                )
            ),
            "current_release_script_set": node.current_release_script_set_id,
            "has_logs": (
                log_results.difference(script_output_nsmap.keys()) == set()
            ),
            "locked": node.locked,
            "cpu_count": node.cpu_count,
            "cpu_speed": node.cpu_speed,
            "created": dehydrate_datetime(node.created),
            "description": node.description,
            "devices": sorted(
                (
                    {
                        "fqdn": device.fqdn,
                        "interfaces": [
                            handler.dehydrate_interface(interface, device)
                            for interface in device.current_config.interface_set.all().order_by(
                                "id"
                            )
                        ],
                    }
                    for device in node.children.all().order_by("id")
                ),
                key=itemgetter("fqdn"),
            ),
            "domain": handler.dehydrate_domain(node.domain),
            "enable_hw_sync": node.enable_hw_sync,
            "permissions": permissions,
            "physical_disk_count": node.physicalblockdevice_set.count(),
            "disks": disks,
            "storage_layout_issues": node.storage_layout_issues(),
            "special_filesystems": [
                handler.dehydrate_filesystem(filesystem)
                for filesystem in node.current_config.special_filesystems.order_by(
                    "id"
                )
            ],
            "supported_filesystems": [
                {"key": key, "ui": ui}
                for key, ui in FILESYSTEM_FORMAT_TYPE_CHOICES
            ],
            "distro_series": node.distro_series,
            "error": node.error,
            "error_description": node.error_description,
            "events": handler.dehydrate_events(node),
            "extra_macs": sorted(
                "%s" % mac_address for mac_address in node.get_extra_macs()
            ),
            "link_speeds": sorted(
                {
                    interface.link_speed
                    for interface in node.current_config.interface_set.all()
                    if interface.link_speed > 0
                }
            ),
            "fqdn": node.fqdn,
            "hwe_kernel": make_hwe_kernel_ui_text(node.hwe_kernel),
            "hostname": node.hostname,
            "id": node.id,
            "interfaces": [
                handler.dehydrate_interface(interface, node)
                for interface in node.current_config.interface_set.all().order_by(
                    "name"
                )
            ],
            "on_network": node.on_network(),
            "license_key": node.license_key,
            "link_type": NODE_TYPE_TO_LINK_TYPE[node.node_type],
            "memory": node.display_memory(),
            "node_type_display": node.get_node_type_display(),
            "numa_nodes": [
                handler.dehydrate_numanode(numa_node)
                for numa_node in node.numanode_set.all().order_by("index")
            ],
            "min_hwe_kernel": node.min_hwe_kernel,
            "osystem": node.osystem,
            "owner": handler.dehydrate_owner(node.owner),
            "parent": node.parent,
            "power_parameters": handler.dehydrate_power_parameters(
                node.get_power_parameters()
            ),
            "power_bmc_node_count": node.bmc.node_set.count()
            if (node.bmc is not None)
            else 0,
            "power_state": node.power_state,
            "pxe_mac": (
                ""
                if boot_interface is None
                else "%s" % boot_interface.mac_address
            ),
            "show_os_info": handler.dehydrate_show_os_info(node),
            "status": node.display_status(),
            "status_code": node.status,
            "status_message": node.status_message(),
            "simple_status": node.simplified_status,
            "storage": round(
                sum(
                    blockdevice.size
                    for blockdevice in node.physicalblockdevice_set.all()
                )
                / (1000**3),
                1,
            ),
            "storage_tags": handler.get_all_storage_tags(blockdevices),
            "subnets": sorted(subnet.cidr for subnet in subnets),
            "fabrics": sorted(handler.get_all_fabric_names(node, subnets)),
            "spaces": sorted(handler.get_all_space_names(subnets)),
            "swap_size": node.swap_size,
            "system_id": node.system_id,
            "hardware_uuid": node.hardware_uuid,
            "tags": [tag.id for tag in node.tags.all()],
            "node_type": node.node_type,
            "updated": dehydrate_datetime(node.updated),
            "zone": handler.dehydrate_zone(node.zone),
            "pool": handler.dehydrate_pool(node.pool),
            "default_user": node.default_user,
            "workload_annotations": OwnerData.objects.get_owner_data(node),
            "last_applied_storage_layout": node.last_applied_storage_layout,
            "ephemeral_deploy": node.ephemeral_deploy,
        }
        if "module" in driver and "comment" in driver:
            data["third_party_driver"] = {
                "module": driver["module"],
                "comment": driver["comment"],
            }

        data["vlan"] = None
        if boot_interface:
            data["vlan"] = handler.dehydrate_vlan(node, boot_interface)

        data["power_type"] = None
        data["ip_addresses"] = None
        if data["pxe_mac"] != "":
            data["power_type"] = node.power_type
            data["ip_addresses"] = handler.dehydrate_all_ip_addresses(node)

        bmc = node.bmc
        data["pod"] = None
        if bmc is not None and bmc.bmc_type == BMC_TYPE.POD:
            data["pod"] = {"id": bmc.id, "name": bmc.name}

        if for_list:
            if node.node_type == NODE_TYPE.MACHINE:
                data["numa_nodes_count"] = len(data["numa_nodes"])
                data["sriov_support"] = any(
                    iface["sriov_max_vf"] > 0 for iface in data["interfaces"]
                )
            list_fields = set(MachineHandler.Meta.list_fields) - set(
                MachineHandler.Meta.list_exclude
            )
            allowed_fields = list_fields.union(
                {
                    "actions",
                    "architecture",
                    "commissioning_script_count",
                    "dhcp_on",
                    "distro_series",
                    "ephemeral_deploy",
                    "extra_macs",
                    "fabrics",
                    "fqdn",
                    "ip_addresses",
                    "link_type",
                    "metadata",
                    "osystem",
                    "permissions",
                    "physical_disk_count",
                    "pod",
                    "power_type",
                    "pxe_mac",
                    "pxe_mac_vendor",
                    "spaces",
                    "simple_status",
                    "status",
                    "status_code",
                    "status_message",
                    "storage",
                    "tags",
                    "testing_script_count",
                    "testing_status",
                    "vlan",
                }
            )
            for key in list(data):
                if key not in allowed_fields:
                    del data[key]
        else:
            _, applied_layout = get_applied_storage_layout_for_node(node)
            data.update(
                {
                    "dhcp_on": node.current_config.interface_set.filter(
                        vlan__dhcp_on=True
                    ).exists(),
                    "grouped_storages": handler.get_grouped_storages(
                        blockdevices
                    ),
                    "detected_storage_layout": applied_layout,
                    "metadata": {},
                }
            )
        if not for_list:
            data["testing_status"] = handler.dehydrate_test_statuses(
                testing_scripts
            )

            cpu_script_results = [
                script_result
                for script_result in handler._script_results.get(
                    node.id, {}
                ).get(HARDWARE_TYPE.CPU, [])
                if script_result.script_set.result_type == RESULT_TYPE.TESTING
            ]
            data["cpu_test_status"] = handler.dehydrate_test_statuses(
                cpu_script_results
            )

            memory_script_results = [
                script_result
                for script_result in handler._script_results.get(
                    node.id, {}
                ).get(HARDWARE_TYPE.MEMORY, [])
                if script_result.script_set.result_type == RESULT_TYPE.TESTING
            ]
            data["memory_test_status"] = handler.dehydrate_test_statuses(
                memory_script_results
            )

            network_script_results = [
                script_result
                for script_result in handler._script_results.get(
                    node.id, {}
                ).get(HARDWARE_TYPE.NETWORK, [])
                if script_result.script_set.result_type == RESULT_TYPE.TESTING
            ]
            data["network_test_status"] = handler.dehydrate_test_statuses(
                network_script_results
            )

            storage_script_results = [
                script_result
                for script_result in handler._script_results.get(
                    node.id, {}
                ).get(HARDWARE_TYPE.STORAGE, [])
                if script_result.script_set.result_type == RESULT_TYPE.TESTING
            ]
            data["storage_test_status"] = handler.dehydrate_test_statuses(
                storage_script_results
            )
        else:
            all_test_results = []
            if node.id in handler._script_results_for_list:
                for results in handler._script_results_for_list[
                    node.id
                ].values():
                    all_test_results += results

            data["testing_status"] = handler.dehydrate_test_statuses_for_list(
                all_test_results
            )

            data["cpu_test_status"] = handler.dehydrate_test_statuses_for_list(
                handler._script_results_for_list.get(node.id, {}).get(
                    HARDWARE_TYPE.CPU, None
                )
            )
            data[
                "memory_test_status"
            ] = handler.dehydrate_test_statuses_for_list(
                handler._script_results_for_list.get(node.id, {}).get(
                    HARDWARE_TYPE.MEMORY, None
                )
            )
            data[
                "network_test_status"
            ] = handler.dehydrate_test_statuses_for_list(
                handler._script_results_for_list.get(node.id, {}).get(
                    HARDWARE_TYPE.NETWORK, None
                )
            )
            data[
                "storage_test_status"
            ] = handler.dehydrate_test_statuses_for_list(
                handler._script_results_for_list.get(node.id, {}).get(
                    HARDWARE_TYPE.STORAGE
                )
            )

        if not for_list:
            interface_script_results = [
                script_result
                for script_result in handler._script_results.get(
                    node.id, {}
                ).get(HARDWARE_TYPE.NETWORK, [])
                if script_result.script_set.result_type == RESULT_TYPE.TESTING
            ]
            data["interface_test_status"] = handler.dehydrate_test_statuses(
                interface_script_results
            )

            node_script_results = [
                script_result
                for script_result in handler._script_results.get(
                    node.id, {}
                ).get(HARDWARE_TYPE.NODE, [])
                if script_result.script_set.result_type == RESULT_TYPE.TESTING
            ]
            data["other_test_status"] = handler.dehydrate_test_statuses(
                node_script_results
            )

        if node.enable_hw_sync:
            data.update(
                {
                    "last_sync": dehydrate_datetime(node.last_sync),
                    "sync_interval": node.sync_interval,
                    "next_sync": dehydrate_datetime(node.next_sync),
                    "is_sync_healthy": node.is_sync_healthy,
                }
            )

        # Clear cache
        handler._script_results = {}

        return data

    @staticmethod
    def make_nodes(number):
        """Create `number` of new nodes."""
        for counter in range(number):
            node = factory.make_Node(interface=True, status=NODE_STATUS.READY)
            factory.make_PhysicalBlockDevice(node=node)
            # Make some devices.
            for _ in range(3):
                factory.make_Node(
                    node_type=NODE_TYPE.DEVICE, parent=node, interface=True
                )


class TestMachineHandler(MAASServerTestCase):
    maxDiff = None

    def test_allowed_methods(self):
        not_allowed_methods = [
            "dehydrate",
            "dehydrate_all_ip_addresses",
            "dehydrate_blockdevice",
            "dehydrate_cache_set",
            "dehydrate_created",
            "dehydrate_device",
            "dehydrate_domain",
            "dehydrate_events",
            "dehydrate_filesystem",
            "dehydrate_hugepages",
            "dehydrate_interface",
            "dehydrate_ip_address",
            "dehydrate_last_image_sync",
            "dehydrate_numanode",
            "dehydrate_owner",
            "dehydrate_partitions",
            "dehydrate_pod",
            "dehydrate_pool",
            "dehydrate_power_parameters",
            "dehydrate_script_set_status",
            "dehydrate_show_os_info",
            "dehydrate_test_statuses",
            "dehydrate_test_statuses_for_list",
            "dehydrate_updated",
            "dehydrate_vlan",
            "dehydrate_volume_group",
            "dehydrate_zone",
            "delete",
            "execute",
            "full_dehydrate",
            "full_hydrate",
            "get_all_fabric_names",
            "get_all_space_names",
            "get_all_storage_tags",
            "get_all_subnets",
            "get_blockdevices_for",
            "get_form_class",
            "get_grouped_storages",
            "get_object",
            "get_own_object",
            "get_providing_dhcp",
            "get_queryset",
            "hydrate",
            "listen",
            "on_listen",
            "on_listen_for_active_pk",
            "preprocess_form",
            "preprocess_node_form",
            "refetch",
            "update_blockdevice_filesystem",
            "update_partition_filesystem",
            "set_script_result_suppressed_value",
        ]
        [
            self.assertIn(attr, MachineHandler.Meta.allowed_methods)
            for attr in dir(MachineHandler)
            if isinstance(getattr(MachineHandler, attr), FunctionType)
            and attr not in not_allowed_methods
            and not attr.startswith("_")
        ]

    def test_list_ids(self):
        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=user)
        handler = MachineHandler(user, {}, None)

        list_results = handler.list_ids({})
        list_items = list_results["groups"][0]["items"]

        assert len(list_items) == 1
        assert len(list_items[0]["permissions"]) == 0
        assert len(list_items[0]["actions"]) > 0
        assert list_items[0]["id"] == node.id

    def test_get_refresh_script_result_cache(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PASSED,
            script_set=factory.make_ScriptSet(node=node),
        )
        # Create an 'Aborted' script result.
        # This will not make it into the _script_results.
        aborted_script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.ABORTED,
            script_set=factory.make_ScriptSet(node=node),
        )
        cached_node = factory.make_Node(owner=owner)
        factory.make_ScriptResult(
            status=SCRIPT_STATUS.FAILED,
            script_set=factory.make_ScriptSet(node=cached_node),
        )

        cached_content = {
            factory.make_name("cached-key"): factory.make_name("cached-value")
        }
        handler = MachineHandler(owner, {}, None)
        handler._script_results[cached_node.id] = cached_content
        handler._cache_pks([node])
        handler._load_extra_data_before_dehydrate([node])

        self.assertEqual(
            script_result.id,
            handler._script_results[node.id][
                script_result.script.hardware_type
            ][0].id,
        )
        self.assertNotIn(
            aborted_script_result,
            [
                result
                for results in handler._script_results.values()
                for result in results
            ],
        )
        self.assertEqual(
            cached_content, handler._script_results[cached_node.id]
        )

    def test_get_refresh_script_result_cache_clears_aborted(self):
        # Regression test for LP:1731350
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PENDING,
            script_set=factory.make_ScriptSet(node=node),
        )

        handler = MachineHandler(owner, {}, None)
        handler._script_results_for_list[node.id] = {
            script_result.script.hardware_type: [script_result.status]
        }
        # Simulate aborting commissioning/testing
        script_result.status = SCRIPT_STATUS.ABORTED
        script_result.save()
        handler._load_extra_data_before_dehydrate([node])

        self.assertEqual(
            [],
            handler._script_results[node.id][
                script_result.script.hardware_type
            ],
        )

    def test_get_power_params_certificate(self):
        sample_cert = get_sample_cert()
        node = factory.make_Node(
            power_type="lxd",
            power_parameters={
                "power_address": "lxd.maas",
                "certificate": sample_cert.certificate_pem(),
                "key": sample_cert.private_key_pem(),
            },
        )
        handler = MachineHandler(factory.make_User(), {}, None)
        result = handler.get({"system_id": node.system_id})
        self.assertEqual(
            result["certificate"],
            {
                "CN": sample_cert.cn(),
                "fingerprint": sample_cert.cert_hash(),
                "expiration": sample_cert.expiration().strftime(
                    DATETIME_FORMAT
                ),
            },
        )

    def test_get_num_queries_is_the_expected_number(self):
        owner = factory.make_User()
        vlan = factory.make_VLAN(space=factory.make_Space())
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=owner, vlan=vlan
        )
        commissioning_script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.COMMISSIONING
        )
        testing_script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.TESTING
        )
        node.current_commissioning_script_set = commissioning_script_set
        node.current_testing_script_set = testing_script_set
        node.save()
        for __ in range(2):
            factory.make_ScriptResult(
                status=SCRIPT_STATUS.PASSED,
                script_set=commissioning_script_set,
            )
            factory.make_ScriptResult(
                status=SCRIPT_STATUS.PASSED, script_set=testing_script_set
            )
        for __ in range(random.randint(4, 16)):
            factory.make_NUMANode(node=node)

        handler = MachineHandler(owner, {}, None)
        queries, _ = count_queries(handler.get, {"system_id": node.system_id})
        self.assertEqual(
            queries,
            60,
            "Number of queries has changed; make sure this is expected.",
        )

    def test_trigger_update_updates_script_result_cache(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        commissioning_script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.COMMISSIONING
        )
        testing_script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.TESTING
        )
        node.current_commissioning_script_set = commissioning_script_set
        node.current_testing_script_set = testing_script_set
        node.save()
        num_scripts = 2
        for _ in range(num_scripts):
            factory.make_ScriptResult(
                status=SCRIPT_STATUS.PASSED,
                script_set=commissioning_script_set,
            )
            factory.make_ScriptResult(
                status=SCRIPT_STATUS.PASSED, script_set=testing_script_set
            )

        handler = MachineHandler(owner, {}, None)
        # Simulate a trigger pushing an update to the UI
        handler.cache = {"active_pk": node.system_id}
        _, _, ret = handler.on_listen_for_active_pk(
            "update", node.system_id, node
        )
        self.assertEqual(ret["commissioning_status"]["passed"], num_scripts)
        self.assertEqual(ret["testing_status"]["passed"], num_scripts)

    def test_dehydrate_owner_empty_when_None(self):
        owner = factory.make_User()
        handler = MachineHandler(owner, {}, None)
        self.assertEqual("", handler.dehydrate_owner(None))

    def test_dehydrate_owner_username(self):
        owner = factory.make_User()
        handler = MachineHandler(owner, {}, None)
        self.assertEqual(owner.username, handler.dehydrate_owner(owner))

    def test_dehydrate_zone(self):
        owner = factory.make_User()
        handler = MachineHandler(owner, {}, None)
        zone = factory.make_Zone()
        self.assertEqual(
            {"id": zone.id, "name": zone.name}, handler.dehydrate_zone(zone)
        )

    def test_dehydrate_pool_none(self):
        owner = factory.make_User()
        handler = MachineHandler(owner, {}, None)
        self.assertIsNone(handler.dehydrate_pool(None))

    def test_dehydrate_pool(self):
        owner = factory.make_User()
        handler = MachineHandler(owner, {}, None)
        pool = factory.make_ResourcePool()
        self.assertEqual(
            handler.dehydrate_pool(pool), {"id": pool.id, "name": pool.name}
        )

    def test_dehydrate_pod(self):
        owner = factory.make_User()
        handler = MachineHandler(owner, {}, None)
        pod = factory.make_Pod()
        self.assertEqual(
            handler.dehydrate_pod(pod), {"id": pod.id, "name": pod.name}
        )

    def test_dehydrate_node_with_pod(self):
        owner = factory.make_User()
        handler = MachineHandler(owner, {}, None)
        pod = factory.make_Pod()
        node = factory.make_Node()
        node.bmc = pod
        data = {}
        handler.dehydrate(node, data)
        self.assertEqual(data["pod"], {"id": pod.id, "name": pod.name})

    def test_dehydrate_node_with_parent(self):
        owner = factory.make_User()
        handler = MachineHandler(owner, {}, None)
        parent = factory.make_Node()
        node = factory.make_Node(parent=parent)
        data = {}
        handler.dehydrate(node, data)
        self.assertEqual(parent.system_id, data["parent"])

    def test_dehydrate_node_without_parent(self):
        owner = factory.make_User()
        handler = MachineHandler(owner, {}, None)
        node = factory.make_Node(parent=None)
        data = {}
        handler.dehydrate(node, data)
        self.assertIsNone(data["parent"])

    def test_dehydrate_with_vmfs6_layout_sets_reserved(self):
        owner = factory.make_User()
        node = factory.make_Node(with_boot_disk=False)
        node.boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS6StorageLayout(node)
        layout.configure()
        handler = MachineHandler(owner, {}, None)
        for disk in handler.dehydrate(node, {})["disks"]:
            if disk["id"] == node.boot_disk.id:
                for partition in disk["partitions"]:
                    if partition["name"].endswith("-part3"):
                        self.assertEqual(
                            "VMFS extent for datastore1", partition["used_for"]
                        )
                    else:
                        self.assertEqual(
                            "VMware ESXi OS partition", partition["used_for"]
                        )
                        self.assertDictEqual(
                            {
                                "id": -1,
                                "label": "RESERVED",
                                "mount_point": "RESERVED",
                                "mount_options": None,
                                "fstype": None,
                                "is_format_fstype": False,
                            },
                            partition["filesystem"],
                        )

    def test_dehydrate_with_vmfs7_layout_sets_reserved(self):
        owner = factory.make_User()
        node = factory.make_Node(with_boot_disk=False)
        node.boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS7StorageLayout(node)
        layout.configure()
        handler = MachineHandler(owner, {}, None)
        for disk in handler.dehydrate(node, {})["disks"]:
            if disk["id"] == node.boot_disk.id:
                for partition in disk["partitions"]:
                    if partition["name"].endswith("-part8"):
                        self.assertEqual(
                            "VMFS extent for datastore1", partition["used_for"]
                        )
                    else:
                        self.assertEqual(
                            "VMware ESXi OS partition", partition["used_for"]
                        )
                        self.assertDictEqual(
                            {
                                "id": -1,
                                "label": "RESERVED",
                                "mount_point": "RESERVED",
                                "mount_options": None,
                                "fstype": None,
                                "is_format_fstype": False,
                            },
                            partition["filesystem"],
                        )

    def test_dehydrate_power_parameters_returns_None_when_empty(self):
        owner = factory.make_User()
        handler = MachineHandler(owner, {}, None)
        self.assertIsNone(handler.dehydrate_power_parameters(""))

    def test_dehydrate_power_parameters_returns_params(self):
        owner = factory.make_User()
        handler = MachineHandler(owner, {}, None)
        params = {
            factory.make_name("key"): factory.make_name("value")
            for _ in range(3)
        }
        self.assertEqual(params, handler.dehydrate_power_parameters(params))

    def test_dehydrate_show_os_info_returns_true(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner, status=NODE_STATUS.DEPLOYED)
        handler = MachineHandler(owner, {}, None)
        self.assertTrue(handler.dehydrate_show_os_info(node))

    def test_dehydrate_show_os_info_returns_false(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner, status=NODE_STATUS.READY)
        handler = MachineHandler(owner, {}, None)
        self.assertFalse(handler.dehydrate_show_os_info(node))

    def test_dehydrate_device(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = MachineHandler(owner, {}, None)
        device = factory.make_Node(node_type=NODE_TYPE.DEVICE, parent=node)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device
        )
        self.assertEqual(
            {
                "fqdn": device.fqdn,
                "interfaces": [handler.dehydrate_interface(interface, device)],
            },
            handler.dehydrate_device(device),
        )

    def test_dehydrate_block_device_with_PhysicalBlockDevice_with_ptable(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = MachineHandler(owner, {}, None)
        blockdevice = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(block_device=blockdevice)
        is_boot = blockdevice.id == node.get_boot_disk().id
        test_status = TestMachineHandlerUtils.get_blockdevice_status(
            handler, blockdevice
        )
        self.assertEqual(
            {
                "id": blockdevice.id,
                "is_boot": is_boot,
                "name": blockdevice.get_name(),
                "numa_node": blockdevice.numa_node.index,
                "tags": blockdevice.tags,
                "type": blockdevice.type,
                "path": blockdevice.path,
                "size": blockdevice.size,
                "used_size": blockdevice.used_size,
                "available_size": blockdevice.available_size,
                "block_size": blockdevice.block_size,
                "model": blockdevice.model,
                "serial": blockdevice.serial,
                "firmware_version": blockdevice.firmware_version,
                "partition_table_type": partition_table.table_type,
                "used_for": blockdevice.used_for,
                "filesystem": handler.dehydrate_filesystem(
                    blockdevice.get_effective_filesystem()
                ),
                "partitions": handler.dehydrate_partitions(
                    blockdevice.get_partitiontable()
                ),
                "test_status": test_status,
            },
            handler.dehydrate_blockdevice(blockdevice, node),
        )

    def test_dehydrate_block_device_no_boot_disk(self):
        # regression test for LP:1952216
        owner = factory.make_User()
        node = factory.make_Node(owner=owner, with_boot_disk=False)
        handler = MachineHandler(owner, {}, None)
        # disk is too small to be a boot disk
        size = MIN_BOOT_PARTITION_SIZE - 1024
        blockdevice = factory.make_PhysicalBlockDevice(node=node, size=size)
        result = handler.dehydrate_blockdevice(blockdevice, node)
        # disk info gets serialized correctly
        self.assertEqual(result["id"], blockdevice.id)

    def test_dehydrate_block_device_with_PhysicalBlockDevice_wo_ptable(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = MachineHandler(owner, {}, None)
        blockdevice = factory.make_PhysicalBlockDevice(node=node)
        is_boot = blockdevice.id == node.get_boot_disk().id
        test_status = TestMachineHandlerUtils.get_blockdevice_status(
            handler, blockdevice
        )
        self.assertEqual(
            {
                "id": blockdevice.id,
                "is_boot": is_boot,
                "name": blockdevice.get_name(),
                "numa_node": blockdevice.numa_node.index,
                "tags": blockdevice.tags,
                "type": blockdevice.type,
                "path": blockdevice.path,
                "size": blockdevice.size,
                "used_size": blockdevice.used_size,
                "available_size": blockdevice.available_size,
                "block_size": blockdevice.block_size,
                "model": blockdevice.model,
                "serial": blockdevice.serial,
                "firmware_version": blockdevice.firmware_version,
                "partition_table_type": "",
                "used_for": blockdevice.used_for,
                "filesystem": handler.dehydrate_filesystem(
                    blockdevice.get_effective_filesystem()
                ),
                "partitions": handler.dehydrate_partitions(
                    blockdevice.get_partitiontable()
                ),
                "test_status": test_status,
            },
            handler.dehydrate_blockdevice(blockdevice, node),
        )

    def test_dehydrate_block_device_with_VirtualBlockDevice(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = MachineHandler(owner, {}, None)
        blockdevice = factory.make_VirtualBlockDevice(node=node)
        test_status = TestMachineHandlerUtils.get_blockdevice_status(
            handler, blockdevice
        )
        self.assertEqual(
            {
                "id": blockdevice.id,
                "is_boot": False,
                "name": blockdevice.get_name(),
                "numa_node": None,
                "tags": blockdevice.tags,
                "type": blockdevice.type,
                "path": blockdevice.path,
                "size": blockdevice.size,
                "used_size": blockdevice.used_size,
                "available_size": blockdevice.available_size,
                "block_size": blockdevice.block_size,
                "model": "",
                "serial": "",
                "firmware_version": "",
                "partition_table_type": "",
                "used_for": blockdevice.used_for,
                "filesystem": handler.dehydrate_filesystem(
                    blockdevice.get_effective_filesystem()
                ),
                "partitions": handler.dehydrate_partitions(
                    blockdevice.get_partitiontable()
                ),
                "parent": {
                    "id": blockdevice.filesystem_group.id,
                    "type": blockdevice.filesystem_group.group_type,
                    "uuid": blockdevice.filesystem_group.uuid,
                },
                "test_status": test_status,
            },
            handler.dehydrate_blockdevice(blockdevice, node),
        )

    def test_dehydrate_volume_group(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = MachineHandler(owner, {}, None)
        volume_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, node=node
        )
        self.assertEqual(
            {
                "id": volume_group.id,
                "name": volume_group.name,
                "tags": [],
                "type": volume_group.group_type,
                "path": "",
                "size": volume_group.get_size(),
                "used_size": volume_group.get_lvm_allocated_size(),
                "available_size": volume_group.get_lvm_free_space(),
                "block_size": volume_group.get_virtual_block_device_block_size(),
                "model": "",
                "serial": "",
                "partition_table_type": "",
                "used_for": "volume group",
                "filesystem": None,
                "partitions": None,
                "numa_nodes": [0],
            },
            handler.dehydrate_volume_group(volume_group),
        )

    def test_dehydrate_volume_group_multiple_numa_nodes(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        numa_nodes = [
            node.default_numanode,
            factory.make_NUMANode(node=node),
            factory.make_NUMANode(node=node),
        ]
        block_devices = [
            factory.make_PhysicalBlockDevice(numa_node=numa_node)
            for numa_node in numa_nodes
        ]
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV, block_device=block_device
            )
            for block_device in block_devices
        ]
        volume_group = factory.make_FilesystemGroup(
            node=node,
            filesystems=filesystems,
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
        )
        handler = MachineHandler(owner, {}, None)
        self.assertEqual(
            handler.dehydrate_volume_group(volume_group)["numa_nodes"],
            [0, 1, 2],
        )

    def test_dehydrate_cache_set(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = MachineHandler(owner, {}, None)
        cache_set = factory.make_CacheSet(node=node)
        backings = []
        for _ in range(3):
            backing = factory.make_PhysicalBlockDevice(node=node)
            fs = factory.make_Filesystem(
                block_device=backing, fstype=FILESYSTEM_TYPE.BCACHE_BACKING
            )
            backings.append(
                factory.make_FilesystemGroup(
                    group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
                    filesystems=[fs],
                    cache_set=cache_set,
                )
            )
        self.assertEqual(
            {
                "id": cache_set.id,
                "name": cache_set.name,
                "tags": [],
                "type": "cache-set",
                "path": "",
                "size": cache_set.get_device().size,
                "used_size": cache_set.get_device().get_used_size(),
                "available_size": cache_set.get_device().get_available_size(),
                "block_size": cache_set.get_device().get_block_size(),
                "model": "",
                "serial": "",
                "partition_table_type": "",
                "used_for": ", ".join(
                    sorted(backing_device.name for backing_device in backings)
                ),
                "filesystem": None,
                "partitions": None,
                "numa_nodes": [0],
            },
            handler.dehydrate_cache_set(cache_set),
        )

    def test_dehydrate_cache_set_multiple_numa_nodes(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        numa_nodes = [
            node.default_numanode,
            factory.make_NUMANode(node=node),
            factory.make_NUMANode(node=node),
        ]
        cache_set = factory.make_CacheSet(node=node)
        for numa_node in numa_nodes:
            backing = factory.make_PhysicalBlockDevice(numa_node=numa_node)
            fs = factory.make_Filesystem(
                block_device=backing, fstype=FILESYSTEM_TYPE.BCACHE_BACKING
            )
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
                filesystems=[fs],
                cache_set=cache_set,
            )
        handler = MachineHandler(owner, {}, None)
        self.assertEqual(
            handler.dehydrate_cache_set(cache_set)["numa_nodes"], [0, 1, 2]
        )

    def test_dehydrate_partitions_returns_None(self):
        owner = factory.make_User()
        handler = MachineHandler(owner, {}, None)
        self.assertIsNone(handler.dehydrate_partitions(None))

    def test_dehydrate_partitions_returns_list_of_partitions(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = MachineHandler(owner, {}, None)
        blockdevice = factory.make_PhysicalBlockDevice(
            node=node, size=10 * 1024**3, block_size=512
        )
        partition_table = factory.make_PartitionTable(block_device=blockdevice)
        partitions = [
            factory.make_Partition(
                partition_table=partition_table, size=1 * 1024**3
            )
            for _ in range(3)
        ]
        expected = []
        for partition in partitions:
            expected.append(
                {
                    "filesystem": handler.dehydrate_filesystem(
                        partition.get_effective_filesystem()
                    ),
                    "name": partition.get_name(),
                    "path": partition.path,
                    "type": partition.type,
                    "id": partition.id,
                    "size": partition.size,
                    "used_for": partition.used_for,
                    "tags": partition.tags,
                }
            )
        self.assertCountEqual(
            expected, handler.dehydrate_partitions(partition_table)
        )

    def test_dehydrate_filesystem_returns_None(self):
        owner = factory.make_User()
        handler = MachineHandler(owner, {}, None)
        self.assertIsNone(handler.dehydrate_filesystem(None))

    def test_dehydrate_filesystem(self):
        owner = factory.make_User()
        handler = MachineHandler(owner, {}, None)
        filesystem = factory.make_Filesystem()
        self.assertEqual(
            {
                "id": filesystem.id,
                "label": filesystem.label,
                "mount_point": filesystem.mount_point,
                "mount_options": filesystem.mount_options,
                "fstype": filesystem.fstype,
                "is_format_fstype": (
                    filesystem.fstype in FILESYSTEM_FORMAT_TYPE_CHOICES_DICT
                ),
            },
            handler.dehydrate_filesystem(filesystem),
        )

    def test_dehydrate_interface_for_multinic_node(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner, status=NODE_STATUS.READY)
        handler = MachineHandler(owner, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=factory.make_Subnet(),
            interface=interface,
        )
        interface2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        expected_links = interface.get_links()
        for link in expected_links:
            link["subnet_id"] = link.pop("subnet").id
        self.assertEqual(
            {
                "id": interface.id,
                "type": interface.type,
                "name": interface.name,
                "numa_node": interface.numa_node.index,
                "enabled": interface.is_enabled(),
                "tags": interface.tags,
                "is_boot": True,
                "mac_address": "%s" % interface.mac_address,
                "vlan_id": interface.vlan_id,
                "params": interface.params,
                "parents": [nic.id for nic in interface.parents.all()],
                "children": [
                    nic.child.id
                    for nic in interface.children_relationships.all()
                ],
                "links": expected_links,
                "interface_speed": interface.interface_speed,
                "link_connected": interface.link_connected,
                "link_speed": interface.link_speed,
                "vendor": interface.vendor,
                "product": interface.product,
                "firmware_version": interface.firmware_version,
                "sriov_max_vf": interface.sriov_max_vf,
            },
            handler.dehydrate_interface(interface, node),
        )
        expected_links = interface2.get_links()
        self.assertEqual(
            {
                "id": interface2.id,
                "type": interface2.type,
                "name": interface2.name,
                "numa_node": interface2.numa_node.index,
                "enabled": interface2.is_enabled(),
                "tags": interface2.tags,
                "is_boot": False,
                "mac_address": "%s" % interface2.mac_address,
                "vlan_id": interface2.vlan_id,
                "params": interface2.params,
                "parents": [nic.id for nic in interface2.parents.all()],
                "children": [
                    nic.child.id
                    for nic in interface2.children_relationships.all()
                ],
                "links": expected_links,
                "interface_speed": interface2.interface_speed,
                "link_connected": interface2.link_connected,
                "link_speed": interface2.link_speed,
                "vendor": interface2.vendor,
                "product": interface2.product,
                "firmware_version": interface2.firmware_version,
                "sriov_max_vf": interface.sriov_max_vf,
            },
            handler.dehydrate_interface(interface2, node),
        )

    def test_dehydrate_interface_for_ready_node(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner, status=NODE_STATUS.READY)
        handler = MachineHandler(owner, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=factory.make_Subnet(),
            interface=interface,
        )
        expected_links = interface.get_links()
        for link in expected_links:
            link["subnet_id"] = link.pop("subnet").id
        self.assertEqual(
            {
                "id": interface.id,
                "type": interface.type,
                "name": interface.name,
                "numa_node": interface.numa_node.index,
                "tags": interface.tags,
                "enabled": interface.is_enabled(),
                "is_boot": interface == node.get_boot_interface(),
                "mac_address": "%s" % interface.mac_address,
                "vlan_id": interface.vlan_id,
                "params": interface.params,
                "parents": [nic.id for nic in interface.parents.all()],
                "children": [
                    nic.child.id
                    for nic in interface.children_relationships.all()
                ],
                "links": expected_links,
                "interface_speed": interface.interface_speed,
                "link_connected": interface.link_connected,
                "link_speed": interface.link_speed,
                "vendor": interface.vendor,
                "product": interface.product,
                "firmware_version": interface.firmware_version,
                "sriov_max_vf": interface.sriov_max_vf,
            },
            handler.dehydrate_interface(interface, node),
        )

    def test_dehydrate_interface_for_commissioning_node(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner, status=NODE_STATUS.COMMISSIONING)
        handler = MachineHandler(owner, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=factory.make_Subnet(),
            interface=interface,
        )
        expected_links = interface.get_links()
        for link in expected_links:
            link["subnet_id"] = link.pop("subnet").id
        discovered_subnet = factory.make_Subnet()
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            ip=factory.pick_ip_in_network(discovered_subnet.get_ipnetwork()),
            subnet=discovered_subnet,
            interface=interface,
        )
        expected_discovered = interface.get_discovered()
        for discovered in expected_discovered:
            discovered["subnet_id"] = discovered.pop("subnet").id
        self.assertEqual(
            {
                "id": interface.id,
                "type": interface.type,
                "name": interface.name,
                "numa_node": interface.numa_node.index,
                "tags": interface.tags,
                "enabled": interface.is_enabled(),
                "is_boot": interface == node.get_boot_interface(),
                "mac_address": "%s" % interface.mac_address,
                "vlan_id": interface.vlan_id,
                "params": interface.params,
                "parents": [nic.id for nic in interface.parents.all()],
                "children": [
                    nic.child.id
                    for nic in interface.children_relationships.all()
                ],
                "links": expected_links,
                "discovered": expected_discovered,
                "interface_speed": interface.interface_speed,
                "link_connected": interface.link_connected,
                "link_speed": interface.link_speed,
                "vendor": interface.vendor,
                "product": interface.product,
                "firmware_version": interface.firmware_version,
                "sriov_max_vf": interface.sriov_max_vf,
            },
            handler.dehydrate_interface(interface, node),
        )

    def test_dehydrate_interface_includes_params(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner, status=NODE_STATUS.COMMISSIONING)
        handler = MachineHandler(owner, {}, None)
        eth0 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=eth0.vlan
        )
        bond_params = {
            "bond_downdelay": 0,
            "bond_lacp_rate": "fast",
            "bond_miimon": 100,
            "bond_mode": "balance-xor",
            "bond_num_grat_arp": 1,
            "bond_updelay": 0,
            "bond_xmit_hash_policy": "layer3+4",
        }
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND,
            node=node,
            parents=[eth0, eth1],
            params=bond_params,
        )
        bridge_params = {
            "bridge_type": BRIDGE_TYPE.STANDARD,
            "bridge_fd": 5,
            "bridge_stp": True,
        }
        br_bond0 = factory.make_Interface(
            INTERFACE_TYPE.BRIDGE,
            node=node,
            parents=[bond0],
            params=bridge_params,
        )
        bond_json = handler.dehydrate_interface(bond0, node)
        bridge_json = handler.dehydrate_interface(br_bond0, node)
        self.assertEqual(bond_params, bond_json["params"])
        self.assertEqual(bridge_params, bridge_json["params"])

    def test_dehydrate_interface_for_rescue_mode_node(self):
        owner = factory.make_User()
        node = factory.make_Node(
            owner=owner,
            status=random.choice(
                [
                    NODE_STATUS.ENTERING_RESCUE_MODE,
                    NODE_STATUS.RESCUE_MODE,
                    NODE_STATUS.EXITING_RESCUE_MODE,
                ]
            ),
        )
        handler = MachineHandler(owner, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=factory.make_Subnet(),
            interface=interface,
        )
        expected_links = interface.get_links()
        for link in expected_links:
            link["subnet_id"] = link.pop("subnet").id
        discovered_subnet = factory.make_Subnet()
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            ip=factory.pick_ip_in_network(discovered_subnet.get_ipnetwork()),
            subnet=discovered_subnet,
            interface=interface,
        )
        expected_discovered = interface.get_discovered()
        for discovered in expected_discovered:
            discovered["subnet_id"] = discovered.pop("subnet").id
        self.assertEqual(
            {
                "id": interface.id,
                "type": interface.type,
                "name": interface.name,
                "numa_node": interface.numa_node.index,
                "tags": interface.tags,
                "enabled": interface.is_enabled(),
                "is_boot": interface == node.get_boot_interface(),
                "mac_address": "%s" % interface.mac_address,
                "vlan_id": interface.vlan_id,
                "params": interface.params,
                "parents": [nic.id for nic in interface.parents.all()],
                "children": [
                    nic.child.id
                    for nic in interface.children_relationships.all()
                ],
                "links": expected_links,
                "discovered": expected_discovered,
                "interface_speed": interface.interface_speed,
                "link_connected": interface.link_connected,
                "link_speed": interface.link_speed,
                "vendor": interface.vendor,
                "product": interface.product,
                "firmware_version": interface.firmware_version,
                "sriov_max_vf": interface.sriov_max_vf,
            },
            handler.dehydrate_interface(interface, node),
        )

    def test_dehydrate_interface_for_testing_node(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner, status=NODE_STATUS.TESTING)
        handler = MachineHandler(owner, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=factory.make_Subnet(),
            interface=interface,
        )
        expected_links = interface.get_links()
        for link in expected_links:
            link["subnet_id"] = link.pop("subnet").id
        discovered_subnet = factory.make_Subnet()
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            ip=factory.pick_ip_in_network(discovered_subnet.get_ipnetwork()),
            subnet=discovered_subnet,
            interface=interface,
        )
        expected_discovered = interface.get_discovered()
        for discovered in expected_discovered:
            discovered["subnet_id"] = discovered.pop("subnet").id
        self.assertEqual(
            {
                "id": interface.id,
                "type": interface.type,
                "name": interface.name,
                "numa_node": interface.numa_node.index,
                "tags": interface.tags,
                "enabled": interface.is_enabled(),
                "is_boot": interface == node.get_boot_interface(),
                "mac_address": "%s" % interface.mac_address,
                "vlan_id": interface.vlan_id,
                "params": interface.params,
                "parents": [nic.id for nic in interface.parents.all()],
                "children": [
                    nic.child.id
                    for nic in interface.children_relationships.all()
                ],
                "links": expected_links,
                "discovered": expected_discovered,
                "interface_speed": interface.interface_speed,
                "link_connected": interface.link_connected,
                "link_speed": interface.link_speed,
                "vendor": interface.vendor,
                "product": interface.product,
                "firmware_version": interface.firmware_version,
                "sriov_max_vf": interface.sriov_max_vf,
            },
            handler.dehydrate_interface(interface, node),
        )

    def test_dehydrate_interface_for_failed_testing_node(self):
        owner = factory.make_User()
        node = factory.make_Node(
            owner=owner,
            status=NODE_STATUS.FAILED_TESTING,
            power_state=POWER_STATE.ON,
        )
        handler = MachineHandler(owner, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=factory.make_Subnet(),
            interface=interface,
        )
        expected_links = interface.get_links()
        for link in expected_links:
            link["subnet_id"] = link.pop("subnet").id
        discovered_subnet = factory.make_Subnet()
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            ip=factory.pick_ip_in_network(discovered_subnet.get_ipnetwork()),
            subnet=discovered_subnet,
            interface=interface,
        )
        expected_discovered = interface.get_discovered()
        for discovered in expected_discovered:
            discovered["subnet_id"] = discovered.pop("subnet").id
        self.assertEqual(
            {
                "id": interface.id,
                "type": interface.type,
                "name": interface.name,
                "numa_node": interface.numa_node.index,
                "tags": interface.tags,
                "enabled": interface.is_enabled(),
                "is_boot": interface == node.get_boot_interface(),
                "mac_address": "%s" % interface.mac_address,
                "vlan_id": interface.vlan_id,
                "params": interface.params,
                "parents": [nic.id for nic in interface.parents.all()],
                "children": [
                    nic.child.id
                    for nic in interface.children_relationships.all()
                ],
                "links": expected_links,
                "discovered": expected_discovered,
                "interface_speed": interface.interface_speed,
                "link_connected": interface.link_connected,
                "link_speed": interface.link_speed,
                "vendor": interface.vendor,
                "product": interface.product,
                "firmware_version": interface.firmware_version,
                "sriov_max_vf": interface.sriov_max_vf,
            },
            handler.dehydrate_interface(interface, node),
        )

    def test_dehydrate_interface_discovered_bond_not_primary(self):
        # If a bond interface doesn't have an observed IP, the
        # observered addresses for the bond's parent interfaces are
        # included.
        owner = factory.make_User()
        node = factory.make_Node(
            owner=owner,
            status=NODE_STATUS.RESCUE_MODE,
            power_state=POWER_STATE.ON,
        )
        handler = MachineHandler(owner, {}, None)
        interface1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        interface2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=interface1.vlan
        )
        bond = factory.make_Interface(
            INTERFACE_TYPE.BOND, node=node, parents=[interface1, interface2]
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=factory.make_Subnet(),
            interface=bond,
        )
        interface2_subnet = factory.make_Subnet()
        interface2_ip = factory.pick_ip_in_network(
            interface2_subnet.get_ipnetwork()
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            ip=interface2_ip,
            subnet=interface2_subnet,
            interface=interface2,
        )
        dehydrated_interface = handler.dehydrate_interface(bond, node)
        self.assertEqual(
            [{"subnet_id": interface2_subnet.id, "ip_address": interface2_ip}],
            dehydrated_interface["discovered"],
        )

    def test_dehydrate_interface_discovered_bond_primary(self):
        # If a bond interface does have an observed IP, the
        # observered addresses for the bond's parent interfaces are
        # not included.
        owner = factory.make_User()
        node = factory.make_Node(
            owner=owner,
            status=NODE_STATUS.RESCUE_MODE,
            power_state=POWER_STATE.ON,
        )
        handler = MachineHandler(owner, {}, None)
        interface1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        interface2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=interface1.vlan
        )
        bond = factory.make_Interface(
            INTERFACE_TYPE.BOND, node=node, parents=[interface1, interface2]
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=factory.make_Subnet(),
            interface=bond,
        )
        bond_subnet = factory.make_Subnet()
        bond_ip = factory.pick_ip_in_network(bond_subnet.get_ipnetwork())
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            ip=bond_ip,
            subnet=bond_subnet,
            interface=bond,
        )
        interface2_subnet = factory.make_Subnet()
        interface2_ip = factory.pick_ip_in_network(
            interface2_subnet.get_ipnetwork()
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            ip=interface2_ip,
            subnet=interface2_subnet,
            interface=interface2,
        )
        dehydrated_interface = handler.dehydrate_interface(bond, node)
        self.assertEqual(
            [{"subnet_id": bond_subnet.id, "ip_address": bond_ip}],
            dehydrated_interface["discovered"],
        )

    def test_dehydrate_interface_include_model_firmware_version(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = MachineHandler(owner, {}, None)
        product = factory.make_name("product")
        firmware_version = factory.make_name("version")
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            product=product,
            firmware_version=firmware_version,
            node=node,
        )
        dehydrated_interface = handler.dehydrate_interface(interface, node)
        self.assertEqual(dehydrated_interface["vendor"], interface.vendor)
        self.assertEqual(dehydrated_interface["product"], interface.product)
        self.assertEqual(
            dehydrated_interface["firmware_version"],
            interface.firmware_version,
        )

    def test_dehydrate_interface_include_sriov_max_vf(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = MachineHandler(owner, {}, None)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, sriov_max_vf=10
        )
        dehydrated_interface = handler.dehydrate_interface(interface, node)
        self.assertEqual(dehydrated_interface["sriov_max_vf"], 10)

    def test_get_summary_xml_returns_empty_string(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = MachineHandler(owner, {}, None)
        observed = handler.get_summary_xml({"system_id": node.system_id})
        self.assertEqual("", observed)

    def test_dehydrate_summary_xml_returns_data(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner, with_empty_script_sets=True)
        handler = MachineHandler(owner, {}, None)
        lldp_data = b"<foo>bar</foo>"
        script_set = node.current_commissioning_script_set
        script_result = script_set.find_script_result(
            script_name=LLDP_OUTPUT_NAME
        )
        script_result.store_result(exit_status=0, stdout=lldp_data)
        observed = handler.get_summary_xml({"system_id": node.system_id})
        probed_details = merge_details_cleanly(get_single_probed_details(node))
        self.assertEqual(
            etree.tostring(probed_details, encoding=str, pretty_print=True),
            observed,
        )

    def test_get_summary_yaml_returns_empty_string(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = MachineHandler(owner, {}, None)
        observed = handler.get_summary_yaml({"system_id": node.system_id})
        self.assertEqual("", observed)

    def test_dehydrate_summary_yaml_returns_data(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner, with_empty_script_sets=True)
        handler = MachineHandler(owner, {}, None)
        lldp_data = b"<foo>bar</foo>"
        script_set = node.current_commissioning_script_set
        script_result = script_set.find_script_result(
            script_name=LLDP_OUTPUT_NAME
        )
        script_result.store_result(exit_status=0, stdout=lldp_data)
        observed = handler.get_summary_yaml({"system_id": node.system_id})
        probed_details = merge_details_cleanly(get_single_probed_details(node))
        self.assertEqual(
            XMLToYAML(
                etree.tostring(probed_details, encoding=str, pretty_print=True)
            ).convert(),
            observed,
        )

    def test_dehydrate_events_only_includes_latest_50(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = MachineHandler(owner, {}, None)
        event_type = factory.make_EventType(level=logging.INFO)
        events = [
            factory.make_Event(node=node, type=event_type) for _ in range(51)
        ]
        expected = [
            {
                "id": event.id,
                "type": {
                    "id": event_type.id,
                    "name": event_type.name,
                    "description": event_type.description,
                    "level": dehydrate_event_type_level(event_type.level),
                },
                "description": event.description,
                "created": dehydrate_datetime(event.created),
            }
            for event in list(reversed(events))[:50]
        ]
        self.assertEqual(expected, handler.dehydrate_events(node))

    def test_dehydrate_events_doesnt_include_debug(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = MachineHandler(owner, {}, None)
        event_type = factory.make_EventType(level=logging.DEBUG)
        for _ in range(5):
            factory.make_Event(node=node, type=event_type)
        self.assertEqual([], handler.dehydrate_events(node))

    def make_node_with_subnets(self):
        user = factory.make_User()
        handler = MachineHandler(user, {}, None)
        space1 = factory.make_Space()
        fabric1 = factory.make_Fabric(name=factory.make_name("fabric"))
        vlan1 = factory.make_VLAN(fabric=fabric1)
        subnet1 = factory.make_Subnet(space=space1, vlan=vlan1)
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet1, vlan=vlan1
        )
        node.save()

        # Bond interface with a VLAN on top. With the bond set to STATIC
        # and the VLAN set to AUTO.
        fabric2 = factory.make_Fabric(name=factory.make_name("fabric"))
        vlan2 = factory.make_VLAN(fabric=fabric2)
        space2 = factory.make_Space()
        bond_subnet = factory.make_Subnet(space=space1, vlan=vlan1)
        vlan_subnet = factory.make_Subnet(space=space2, vlan=vlan2)
        nic1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan1
        )
        nic2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan2
        )
        bond = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[nic1, nic2], vlan=vlan1
        )
        vlan_int = factory.make_Interface(
            INTERFACE_TYPE.VLAN, vlan=vlan2, parents=[bond]
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(bond_subnet.get_ipnetwork()),
            subnet=bond_subnet,
            interface=bond,
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip="",
            subnet=vlan_subnet,
            interface=vlan_int,
        )

        # LINK_UP interface with no subnet.
        fabric3 = factory.make_Fabric(name=factory.make_name("fabric"))
        vlan3 = factory.make_VLAN(fabric=fabric3)
        nic3 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan3, node=node
        )
        nic3_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip="",
            subnet=None,
            interface=nic3,
        )
        nic3_ip.subnet = None
        nic3_ip.save()

        boot_interface = node.get_boot_interface()
        node.boot_interface = boot_interface
        node.save()

        subnets = [subnet1, bond_subnet, vlan_subnet]
        fabrics = [fabric1, fabric2, fabric3]
        spaces = [space1, space2]
        return (handler, node, subnets, fabrics, spaces)

    def test_get_all_subnets(self):
        (handler, node, subnets, _, _) = self.make_node_with_subnets()
        self.assertCountEqual(subnets, handler.get_all_subnets(node))

    def test_get_all_fabric_names(self):
        (handler, node, _, fabrics, _) = self.make_node_with_subnets()
        fabric_names = [fabric.name for fabric in fabrics]
        node_subnets = handler.get_all_subnets(node)
        self.assertCountEqual(
            fabric_names, handler.get_all_fabric_names(node, node_subnets)
        )

    def test_get_all_space_names(self):
        (handler, node, _, _, spaces) = self.make_node_with_subnets()
        space_names = [space.name for space in spaces]
        node_subnets = handler.get_all_subnets(node)
        self.assertCountEqual(
            space_names, handler.get_all_space_names(node_subnets)
        )

    def test_get(self):
        user = factory.make_User()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node_with_Interface_on_Subnet(
            with_empty_script_sets=True
        )
        factory.make_FilesystemGroup(node=node)
        node.owner = user
        node.save()
        for _ in range(5):
            factory.make_Event(node=node)
        lldp_data = b"<foo>bar</foo>"
        script_set = node.current_commissioning_script_set
        script_result = script_set.find_script_result(
            script_name=LLDP_OUTPUT_NAME
        )
        script_result.store_result(exit_status=0, stdout=lldp_data)
        factory.make_PhysicalBlockDevice(node=node)
        Config.objects.set_config(
            name="enable_third_party_drivers", value=True
        )
        data = "pci:v00001590d00000047sv00001590sd00000047bc*sc*i*"
        script_result = script_set.find_script_result(
            script_name=LIST_MODALIASES_OUTPUT_NAME
        )
        script_result.store_result(exit_status=0, stdout=data.encode("utf-8"))

        # Bond interface with a VLAN on top. With the bond set to STATIC
        # and the VLAN set to AUTO.
        bond_subnet = factory.make_Subnet()
        vlan_subnet = factory.make_Subnet()
        nic1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        nic2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        bond = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[nic1, nic2]
        )
        vlan = factory.make_Interface(INTERFACE_TYPE.VLAN, parents=[bond])
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(bond_subnet.get_ipnetwork()),
            subnet=bond_subnet,
            interface=bond,
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip="",
            subnet=vlan_subnet,
            interface=vlan,
        )

        # LINK_UP interface with no subnet.
        nic3 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        nic3_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip="",
            subnet=None,
            interface=nic3,
        )
        nic3_ip.subnet = None
        nic3_ip.save()

        # Make some devices.
        for _ in range(3):
            factory.make_Node(
                node_type=NODE_TYPE.DEVICE, parent=node, interface=True
            )

        boot_interface = node.get_boot_interface()
        node.boot_interface = boot_interface
        node.save()

        observed = handler.get({"system_id": node.system_id})
        expected = TestMachineHandlerUtils.dehydrate_node(node, handler)
        self.assertEqual(observed, expected)

    def test_get_hardware_sync_fields(self):
        user = factory.make_User()
        handler = MachineHandler(user, {}, None)
        Config.objects.set_config(name="hardware_sync_interval", value="10m")
        node = factory.make_Node_with_Interface_on_Subnet(enable_hw_sync=True)
        node.last_sync = datetime.now()
        node.save()
        observed = handler.get({"system_id": node.system_id})
        self.assertEqual(
            observed["last_sync"], dehydrate_datetime(node.last_sync)
        )
        self.assertEqual(
            observed["sync_interval"], timedelta(minutes=10).total_seconds()
        )
        self.assertEqual(
            observed["next_sync"],
            dehydrate_datetime(node.last_sync + timedelta(minutes=10)),
        )
        self.assertTrue(observed["is_sync_healthy"])

    def test_get_driver_for_series(self):
        user = factory.make_User()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node_with_Interface_on_Subnet(
            with_empty_script_sets=True
        )
        node.distro_series = "bionic"
        node.save()
        Config.objects.set_config(
            name="enable_third_party_drivers", value=True
        )
        mock_get_third_party_driver = self.patch(
            node_module, "get_third_party_driver"
        )
        handler.dehydrate(node, {})
        mock_get_third_party_driver.assert_called_with(
            node, detected_aliases=[], series="bionic"
        )

    def test_get_numa_node_only_physical_interfaces(self):
        user = factory.make_User()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node()
        nic = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_Interface(INTERFACE_TYPE.VLAN, parents=[nic])
        result = handler.get({"system_id": node.system_id})
        for interface in result["interfaces"]:
            if interface["type"] == "physical":
                self.assertEqual(interface["numa_node"], 0)
            else:
                self.assertIsNone(interface["numa_node"])

    def test_get_numa_node_only_physical_blockdevices(self):
        user = factory.make_User()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node()
        factory.make_PhysicalBlockDevice(node=node)
        factory.make_VirtualBlockDevice(node=node)
        result = handler.get({"system_id": node.system_id})
        for disk in result["disks"]:
            if disk["type"] == "physical":
                self.assertEqual(disk["numa_node"], 0)
            else:
                # None for LVM VGs, doesn't exist for other virtual devices
                self.assertIsNone(disk.get("numa_node"))

    def test_get_ephemeral_deployment(self):
        user = factory.make_User()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(
            status=NODE_STATUS.READY, ephemeral_deploy=True
        )
        result = handler.get({"system_id": node.system_id})
        assert result["ephemeral_deploy"] is True

    def test_get_includes_not_acquired_special_filesystems(self):
        owner = factory.make_User()
        handler = MachineHandler(owner, {}, None)
        machine = factory.make_Node(owner=owner)
        filesystem = factory.make_Filesystem(
            node_config=machine.current_config,
            label="not-acquired",
            acquired=False,
        )
        factory.make_Filesystem(
            node_config=machine.current_config, label="acquired", acquired=True
        )
        self.assertEqual(
            handler.get({"system_id": machine.system_id})[
                "special_filesystems"
            ],
            [handler.dehydrate_filesystem(filesystem)],
        )

    def test_get_includes_acquired_special_filesystems(self):
        owner = factory.make_User()
        handler = MachineHandler(owner, {}, None)
        machine = factory.make_Node(owner=owner, status=NODE_STATUS.DEPLOYED)
        factory.make_Filesystem(
            node_config=machine.current_config,
            label="not-acquired",
            acquired=False,
        )
        filesystem = factory.make_Filesystem(
            node_config=machine.current_config, label="acquired", acquired=True
        )
        self.assertEqual(
            handler.get({"system_id": machine.system_id})[
                "special_filesystems"
            ],
            [handler.dehydrate_filesystem(filesystem)],
        )

    def test_get_includes_static_ip_addresses(self):
        user = factory.make_User()
        machine = factory.make_Machine(owner=user)
        [interface1, interface2] = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=machine)
            for _ in range(2)
        ]
        ip_address1 = factory.make_StaticIPAddress(interface=interface1)
        ip_address2 = factory.make_StaticIPAddress(interface=interface2)
        handler = MachineHandler(user, {}, None)
        dehydrated_machine = handler.get({"system_id": machine.system_id})
        dehydrated_ips = [
            info["ip"] for info in dehydrated_machine["ip_addresses"]
        ]
        self.assertCountEqual(dehydrated_ips, [ip_address1.ip, ip_address2.ip])

    def test_get_numa_nodes_prefetched(self):
        user = factory.make_User()
        machine1 = factory.make_Machine(owner=user)
        for __ in range(4):
            factory.make_NUMANode(node=machine1)
        machine2 = factory.make_Machine(owner=user)
        for __ in range(16):
            factory.make_NUMANode(node=machine2)
        handler = MachineHandler(user, {}, None)
        count1, _ = count_queries(
            handler.get, {"system_id": machine1.system_id}
        )
        count2, _ = count_queries(
            handler.get, {"system_id": machine1.system_id}
        )
        # there's a 1-query difference between counts because of caching
        self.assertEqual(count1, count2 + 1)

    def test_get_numa_nodes_for_machine(self):
        user = factory.make_User()
        machine = factory.make_Machine(owner=user)
        memory_cores_hugepages = (
            (512, [0, 1], 1024),
            (1024, [2, 3], 2048),
            (2048, [4, 5], 0),
        )
        for memory, cores, hugepages in memory_cores_hugepages:
            numa_node = factory.make_NUMANode(
                node=machine, memory=memory, cores=cores
            )
            factory.make_NUMANodeHugepages(
                numa_node=numa_node, total=hugepages, page_size=1024
            )
        handler = MachineHandler(user, {}, None)
        result = handler.get({"system_id": machine.system_id})
        self.assertEqual(
            result["numa_nodes"],
            [
                {
                    "id": numa_node.id - 3,
                    "index": 0,
                    "memory": 0,
                    "cores": [],
                    "hugepages_set": [],
                },
                {
                    "id": numa_node.id - 2,
                    "index": 1,
                    "memory": 512,
                    "cores": [0, 1],
                    "hugepages_set": [{"page_size": 1024, "total": 1024}],
                },
                {
                    "id": numa_node.id - 1,
                    "index": 2,
                    "memory": 1024,
                    "cores": [2, 3],
                    "hugepages_set": [{"page_size": 1024, "total": 2048}],
                },
                {
                    "id": numa_node.id,
                    "index": 3,
                    "memory": 2048,
                    "cores": [4, 5],
                    "hugepages_set": [{"page_size": 1024, "total": 0}],
                },
            ],
        )

    def test_list_includes_static_ip_addresses(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        [interface1, interface2] = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            for _ in range(2)
        ]
        ip_address1 = factory.make_StaticIPAddress(interface=interface1)
        ip_address2 = factory.make_StaticIPAddress(interface=interface2)
        handler = MachineHandler(user, {}, None)
        self.assertCountEqual(
            [
                {"ip": ip_address1.ip, "is_boot": True},
                {"ip": ip_address2.ip, "is_boot": False},
            ],
            TestMachineHandlerUtils.dehydrate_node(
                node, handler, for_list=True
            )["ip_addresses"],
        )

    def test_list_includes_dynamic_ip_if_no_static(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        ip_address = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, interface=interface
        )
        handler = MachineHandler(user, {}, None)
        self.assertEqual(
            [{"ip": ip_address.ip, "is_boot": True}],
            TestMachineHandlerUtils.dehydrate_node(
                node, handler, for_list=True
            )["ip_addresses"],
        )

    def test_list_includes_vlan_with_boot_interface(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        fabric = factory.make_Fabric(name=factory.make_name("fabric"))
        vlan = factory.make_VLAN(fabric=fabric)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=node
        )
        handler = MachineHandler(user, {}, None)
        self.assertEqual(
            {
                "id": interface.vlan_id,
                "name": interface.vlan.name,
                "fabric_id": interface.vlan.fabric.id,
                "fabric_name": "%s" % interface.vlan.fabric.name,
            },
            TestMachineHandlerUtils.dehydrate_node(
                node, handler, for_list=True
            )["vlan"],
        )

    def test_list_excludes_vlan_without_boot_interface(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        handler = MachineHandler(user, {}, None)
        self.assertIsNone(
            TestMachineHandlerUtils.dehydrate_node(
                node, handler, for_list=True
            )["vlan"]
        )

    def test_get_object_returns_node_if_super_user(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        self.assertEqual(
            node, handler.get_object({"system_id": node.system_id})
        )

    def test_get_object_returns_node_if_owner(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        handler = MachineHandler(user, {}, None)
        self.assertEqual(
            node, handler.get_object({"system_id": node.system_id})
        )

    def test_get_object_returns_node_if_owner_empty(self):
        user = factory.make_User()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        self.assertEqual(
            node, handler.get_object({"system_id": node.system_id})
        )

    def test_get_object_raises_error_if_owner_by_another_user(self):
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        handler = MachineHandler(user, {}, None)
        self.assertRaises(
            HandlerDoesNotExistError,
            handler.get_object,
            {"system_id": node.system_id},
        )

    def test_get_object_returns_error_if_not_allowed(self):
        SecretManager().set_composite_secret(
            "external-auth", {"rbac-url": "http://rbac.example.com"}
        )
        rbac._store.client = FakeRBACClient()
        rbac._store.cleared = False  # Prevent re-creation of the client.
        user = factory.make_User()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        self.assertRaises(
            HandlerDoesNotExistError,
            handler.get_object,
            {"system_id": node.system_id},
        )

    def test_get_form_class_for_create(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        self.assertEqual(
            AdminMachineWithMACAddressesForm, handler.get_form_class("create")
        )

    def test_get_form_class_for_update(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        self.assertEqual(
            AdminMachineWithMACAddressesForm, handler.get_form_class("update")
        )

    def test_get_form_class_raises_error_for_unknown_action(self):
        user = factory.make_User()
        handler = MachineHandler(user, {}, None)
        self.assertRaises(
            HandlerError, handler.get_form_class, factory.make_name()
        )

    def test_create_raise_permissions_error_for_non_admin(self):
        user = factory.make_User()
        handler = MachineHandler(user, {}, None)
        self.assertRaises(HandlerPermissionError, handler.create, {})

    def test_create_creates_node(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        zone = factory.make_Zone()
        mac = factory.make_mac_address()
        hostname = factory.make_name("hostname")
        architecture = make_usable_architecture(self)
        description = factory.make_name("description")

        self.patch(node_model, "start_commissioning")

        created_node = handler.create(
            {
                "hostname": hostname,
                "pxe_mac": mac,
                "architecture": architecture,
                "description": description,
                "zone": {"name": zone.name},
                "power_type": "manual",
                "power_parameters": {},
            }
        )
        self.assertEqual(created_node["hostname"], hostname)
        self.assertEqual(created_node["pxe_mac"], mac)
        self.assertEqual(created_node["extra_macs"], [])
        self.assertEqual(created_node["link_speeds"], [])
        self.assertEqual(created_node["architecture"], architecture)
        self.assertEqual(created_node["description"], description)
        self.assertEqual(created_node["zone"]["id"], zone.id)
        self.assertEqual(created_node["power_type"], "manual")
        self.assertEqual(created_node["power_parameters"], {})

    def test_create_starts_auto_commissioning(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        zone = factory.make_Zone()
        mac = factory.make_mac_address()
        hostname = factory.make_name("hostname")
        architecture = make_usable_architecture(self)

        mock_start_commissioning = self.patch(
            node_model, "start_commissioning"
        )

        handler.create(
            {
                "hostname": hostname,
                "pxe_mac": mac,
                "architecture": architecture,
                "zone": {"name": zone.name},
                "power_type": "manual",
                "power_parameters": {},
            }
        )
        mock_start_commissioning.assert_called_once_with(user)

    def test_create_creates_deployed_node(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, FakeRequest(user))
        hostname = factory.make_name("hostname")
        description = factory.make_name("description")
        zone = factory.make_Zone()

        mock_start_commissioning = self.patch(
            node_model, "start_commissioning"
        )

        created_node = handler.create(
            {
                "hostname": hostname,
                "description": description,
                "zone": {"name": zone.name},
                "deployed": True,
            }
        )
        # the commissioning process is not started
        mock_start_commissioning.assert_not_called()
        self.assertEqual(created_node["status"], "Deployed")
        node = Node.objects.get(system_id=created_node["system_id"])
        self.assertIsNotNone(node.current_commissioning_script_set)
        self.assertTrue(NodeKey.objects.filter(node=node).exists())
        self.assertEqual(node.status, NODE_STATUS.DEPLOYED)
        self.assertEqual(user, node.owner)

    def test_update_raise_permissions_error_for_non_admin(self):
        user = factory.make_User()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        self.assertRaises(
            HandlerPermissionError,
            handler.update,
            {"system_id": node.system_id},
        )

    def test_update_raise_permissions_error_for_locked_node(self):
        user = factory.make_admin()
        node = factory.make_Node(locked=True)
        handler = MachineHandler(user, {}, None)
        self.assertRaises(
            HandlerPermissionError,
            handler.update,
            {"system_id": node.system_id},
        )

    def test_update_raises_validation_error_for_invalid_architecture(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(interface=True, power_type="manual")
        node_data = TestMachineHandlerUtils.dehydrate_node(node, handler)
        arch = factory.make_name("arch")
        node_data["architecture"] = arch
        error = self.assertRaises(
            HandlerValidationError, handler.update, node_data
        )
        self.assertEqual(
            error.message_dict,
            {
                "architecture": [
                    f"'{arch}' is not a valid architecture.  It should be one of: ''."
                ]
            },
        )

    def test_update_updates_node(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(interface=True)
        node_data = TestMachineHandlerUtils.dehydrate_node(node, handler)
        new_zone = factory.make_Zone()
        new_pool = factory.make_ResourcePool()
        new_hostname = factory.make_name("hostname")
        new_architecture = make_usable_architecture(self)
        new_description = factory.make_name("description")
        power_id = factory.make_name("power_id")
        power_pass = factory.make_name("power_pass")
        power_address = factory.make_ipv4_address()
        node_data["hostname"] = new_hostname
        node_data["architecture"] = new_architecture
        node_data["description"] = new_description
        node_data["zone"] = {"name": new_zone.name}
        node_data["pool"] = {"name": new_pool.name}
        node_data["power_type"] = "virsh"
        node_data["power_parameters"] = {
            "power_id": power_id,
            "power_pass": power_pass,
            "power_address": power_address,
        }
        updated_node = handler.update(node_data)
        self.assertEqual(updated_node["hostname"], new_hostname)
        self.assertEqual(updated_node["architecture"], new_architecture)
        self.assertEqual(updated_node["description"], new_description)
        self.assertEqual(updated_node["zone"]["id"], new_zone.id)
        self.assertEqual(updated_node["pool"]["id"], new_pool.id)
        self.assertEqual(updated_node["power_type"], "virsh")
        self.assertEqual(
            updated_node["power_parameters"],
            {
                "power_id": power_id,
                "power_pass": power_pass,
                "power_address": power_address,
            },
        )

    def test_update_no_pool(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(interface=True)
        node_data = TestMachineHandlerUtils.dehydrate_node(node, handler)
        new_zone = factory.make_Zone()
        new_hostname = factory.make_name("hostname")
        new_architecture = make_usable_architecture(self)
        power_id = factory.make_name("power_id")
        power_pass = factory.make_name("power_pass")
        power_address = factory.make_ipv4_address()
        node_data["hostname"] = new_hostname
        node_data["architecture"] = new_architecture
        node_data["zone"] = {"name": new_zone.name}
        # Entry is present but not passed
        node_data["pool"] = None
        node_data["power_type"] = "virsh"
        node_data["power_parameters"] = {
            "power_id": power_id,
            "power_pass": power_pass,
            "power_address": power_address,
        }
        updated_node = handler.update(node_data)
        self.assertEqual(updated_node["pool"]["id"], node.pool.id)

    def test_update_adds_tags_to_node(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True, architecture=architecture, power_type="manual"
        )
        tags = [factory.make_Tag(definition="").id for _ in range(3)]
        node_data = TestMachineHandlerUtils.dehydrate_node(node, handler)
        node_data["tags"] = tags
        updated_node = handler.update(node_data)
        self.assertCountEqual(tags, updated_node["tags"])

    def test_update_removes_tag_from_node(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True, architecture=architecture, power_type="manual"
        )
        tags = {}
        for _ in range(3):
            tag = factory.make_Tag(definition="")
            tag.node_set.add(node)
            tag.save()
            tags[tag.id] = tag.name
        node_data = TestMachineHandlerUtils.dehydrate_node(node, handler)
        removed_tag_id = random.choice(list(tags))
        tags.pop(removed_tag_id)
        node_data["tags"].remove(removed_tag_id)
        updated_node = handler.update(node_data)
        self.assertCountEqual(list(tags), updated_node["tags"])

    def test_update_doesnt_update_tags_for_node_if_not_set_in_parameters(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True, architecture=architecture, power_type="manual"
        )
        node_data = TestMachineHandlerUtils.dehydrate_node(node, handler)
        updated_node = handler.update(node_data)
        self.assertEqual([], updated_node["tags"])

    def test_update_fails_associating_defined_tag(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True, architecture=architecture, power_type="manual"
        )
        tag = factory.make_Tag(definition="//foo/bar")
        node_data = TestMachineHandlerUtils.dehydrate_node(node, handler)
        node_data["tags"].append(tag.id)
        error = self.assertRaises(HandlerError, handler.update, node_data)
        self.assertEqual(
            str(error),
            f"Cannot add tag {tag.name} to node because it has a definition",
        )

    def test_update_disk_for_physical_block_device(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED,
        )
        block_device = factory.make_PhysicalBlockDevice(node=node)
        new_name = factory.make_name("new")
        new_tags = [factory.make_name("tag") for _ in range(3)]
        handler.update_disk(
            {
                "system_id": node.system_id,
                "block_id": block_device.id,
                "name": new_name,
                "tags": new_tags,
            }
        )
        block_device = reload_object(block_device)
        self.assertEqual(new_name, block_device.name)
        self.assertCountEqual(new_tags, block_device.tags)

    def test_update_disk_for_block_device_with_filesystem(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED,
        )
        block_device = factory.make_PhysicalBlockDevice(node=node)
        new_name = factory.make_name("new")
        new_tags = [factory.make_name("tag") for _ in range(3)]
        new_fstype = factory.pick_filesystem_type()
        new_mount_point = factory.make_absolute_path()
        new_mount_options = factory.make_name("options")
        handler.update_disk(
            {
                "system_id": node.system_id,
                "block_id": block_device.id,
                "name": new_name,
                "tags": new_tags,
                "fstype": new_fstype,
                "mount_point": new_mount_point,
                "mount_options": new_mount_options,
            }
        )
        block_device = reload_object(block_device)
        self.assertEqual(new_name, block_device.name)
        self.assertCountEqual(new_tags, block_device.tags)
        efs = block_device.get_effective_filesystem()
        self.assertEqual(efs.fstype, new_fstype)
        self.assertEqual(efs.mount_point, new_mount_point)
        self.assertEqual(efs.mount_options, new_mount_options)

    def test_update_disk_for_virtual_block_device(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED,
        )
        block_device = factory.make_VirtualBlockDevice(node=node)
        new_name = factory.make_name("new")
        new_tags = [factory.make_name("tag") for _ in range(3)]
        handler.update_disk(
            {
                "system_id": node.system_id,
                "block_id": block_device.id,
                "name": new_name,
                "tags": new_tags,
            }
        )
        block_device = reload_object(block_device)
        self.assertEqual(new_name, block_device.name)
        self.assertCountEqual(new_tags, block_device.tags)

    def test_update_disk_locked_raises_permission_error(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(locked=True)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        new_name = factory.make_name("new")
        params = {
            "system_id": node.system_id,
            "block_id": block_device.id,
            "name": new_name,
        }
        self.assertRaises(HandlerPermissionError, handler.update_disk, params)

    def test_delete_disk(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED,
        )
        block_device = factory.make_PhysicalBlockDevice(node=node)
        handler.delete_disk(
            {"system_id": node.system_id, "block_id": block_device.id}
        )
        self.assertIsNone(reload_object(block_device))

    def test_delete_disk_locked_raises_permission_error(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(locked=True)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        params = {"system_id": node.system_id, "block_id": block_device.id}
        self.assertRaises(HandlerPermissionError, handler.delete_disk, params)

    def test_delete_partition(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED,
        )
        partition = factory.make_Partition(node=node)
        handler.delete_partition(
            {"system_id": node.system_id, "partition_id": partition.id}
        )
        self.assertIsNone(reload_object(partition))

    def test_delete_renumbers_others(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(block_device=device)
        p1 = partition_table.add_partition(size=MIN_PARTITION_SIZE)
        p2 = partition_table.add_partition(size=MIN_PARTITION_SIZE)
        p3 = partition_table.add_partition(size=MIN_PARTITION_SIZE)

        handler.delete_partition(
            {"system_id": node.system_id, "partition_id": p1.id}
        )
        self.assertEqual(reload_object(p2).index, 1)
        self.assertEqual(reload_object(p3).index, 2)

    def test_delete_partition_locked_raises_permission_error(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(locked=True)
        partition = factory.make_Partition(node=node)
        params = {"system_id": node.system_id, "partition_id": partition.id}
        self.assertRaises(
            HandlerPermissionError, handler.delete_partition, params
        )

    def test_delete_volume_group(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED,
        )
        volume_group = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.LVM_VG
        )
        handler.delete_volume_group(
            {"system_id": node.system_id, "volume_group_id": volume_group.id}
        )
        self.assertIsNone(reload_object(volume_group))

    def test_delete_volume_group_locked_raises_permission_error(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(locked=True)
        volume_group = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.LVM_VG
        )
        params = {
            "system_id": node.system_id,
            "volume_group_id": volume_group.id,
        }
        self.assertRaises(
            HandlerPermissionError, handler.delete_volume_group, params
        )

    def test_delete_cache_set(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED,
        )
        cache_set = factory.make_CacheSet(node=node)
        handler.delete_cache_set(
            {"system_id": node.system_id, "cache_set_id": cache_set.id}
        )
        self.assertIsNone(reload_object(cache_set))

    def test_delete_cache_set_locked_raises_permission_error(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(locked=True)
        cache_set = factory.make_CacheSet(node=node)
        params = {"system_id": node.system_id, "cache_set_id": cache_set.id}
        self.assertRaises(
            HandlerPermissionError, handler.delete_cache_set, params
        )

    def test_delete_filesystem_deletes_blockdevice_filesystem(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED,
        )
        block_device = factory.make_BlockDevice(node=node)
        filesystem = factory.make_Filesystem(
            block_device=block_device, fstype=FILESYSTEM_TYPE.EXT4
        )
        handler.delete_filesystem(
            {
                "system_id": node.system_id,
                "blockdevice_id": block_device.id,
                "filesystem_id": filesystem.id,
            }
        )
        self.assertIsNone(reload_object(filesystem))
        self.assertIsNotNone(reload_object(block_device))

    def test_delete_filesystem_deletes_partition_filesystem(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED,
        )
        partition = factory.make_Partition(node=node)
        filesystem = factory.make_Filesystem(
            partition=partition, fstype=FILESYSTEM_TYPE.EXT4
        )
        handler.delete_filesystem(
            {
                "system_id": node.system_id,
                "partition_id": partition.id,
                "filesystem_id": filesystem.id,
            }
        )
        self.assertIsNone(reload_object(filesystem))
        self.assertIsNotNone(reload_object(partition))

    def test_delete_filesystem_locked_raises_permission_error(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(locked=True)
        partition = factory.make_Partition(node=node)
        filesystem = factory.make_Filesystem(
            partition=partition, fstype=FILESYSTEM_TYPE.EXT4
        )
        params = {
            "system_id": node.system_id,
            "partition_id": partition.id,
            "filesystem_id": filesystem.id,
        }
        self.assertRaises(
            HandlerPermissionError, handler.delete_filesystem, params
        )

    def test_delete_vmfs_datastore(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node()
        vmfs = factory.make_VMFS(node=node)
        params = {
            "system_id": node.system_id,
            "vmfs_datastore_id": vmfs.virtual_device.id,
        }
        handler.delete_vmfs_datastore(params)
        self.assertIsNone(reload_object(vmfs))

    def test_delete_vmfs_datastore_invalid_id(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node()
        vmfs = factory.make_VMFS(node=node)
        params = {"system_id": node.system_id, "vmfs_datastore_id": 999}
        self.assertRaises(
            HandlerDoesNotExistError, handler.delete_vmfs_datastore, params
        )
        self.assertIsNotNone(reload_object(vmfs))

    def test_update_vmfs_datastore(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node()
        vmfs = factory.make_VMFS(node=node)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = factory.make_Partition(partition_table=partition_table)
        factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV,
            partition=partition,
            filesystem_group=vmfs,
        )
        params = {
            "system_id": node.system_id,
            "vmfs_datastore_id": vmfs.virtual_device.id,
            "remove_partitions": [partition.id],
        }
        handler.update_vmfs_datastore(params)
        self.assertIsNone(partition.get_effective_filesystem())

    def test_update_vmfs_datastore_invalid_id(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node()
        vmfs = factory.make_VMFS(node=node)
        params = {"system_id": node.system_id, "vmfs_datastore_id": 999}
        self.assertRaises(
            HandlerDoesNotExistError, handler.update_vmfs_datastore, params
        )
        self.assertIsNotNone(reload_object(vmfs))

    def test_update_vmfs_datastore_raises_errors(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node()
        vmfs = factory.make_VMFS(node=node)
        params = {
            "system_id": node.system_id,
            "vmfs_datastore_id": vmfs.id,
            "remove_partitions": [999],
        }
        self.assertRaises(HandlerError, handler.update_vmfs_datastore, params)

    def test_create_partition(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED,
        )
        block_device = factory.make_BlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device, node=node
        )
        size = partition_table.block_device.size // 2
        tags = [factory.make_name("tag") for _ in range(3)]
        handler.create_partition(
            {
                "system_id": node.system_id,
                "block_id": partition_table.block_device_id,
                "partition_size": size,
                "tags": tags,
            }
        )
        partition = partition_table.partitions.first()
        self.assertEqual(2, Partition.objects.count())
        self.assertEqual(
            human_readable_bytes(
                round_size_to_nearest_block(
                    size, PARTITION_ALIGNMENT_SIZE, False
                )
            ),
            human_readable_bytes(partition.size),
        )
        self.assertCountEqual(tags, partition.tags)

    def test_create_partition_with_filesystem(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED,
        )
        block_device = factory.make_BlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device, node=node
        )
        partition = partition_table.partitions.first()
        size = partition_table.block_device.size // 2
        fstype = factory.pick_filesystem_type()
        mount_point = factory.make_absolute_path()
        mount_options = factory.make_name("options")
        handler.create_partition(
            {
                "system_id": node.system_id,
                "block_id": partition_table.block_device_id,
                "partition_size": size,
                "fstype": fstype,
                "mount_point": mount_point,
                "mount_options": mount_options,
            }
        )
        partition = partition_table.partitions.first()
        self.assertEqual(2, Partition.objects.count())
        self.assertEqual(
            human_readable_bytes(
                round_size_to_nearest_block(
                    size, PARTITION_ALIGNMENT_SIZE, False
                )
            ),
            human_readable_bytes(partition.size),
        )
        efs = partition.get_effective_filesystem()
        self.assertEqual(efs.fstype, fstype)
        self.assertEqual(efs.mount_point, mount_point)
        self.assertEqual(efs.mount_options, mount_options)

    def test_create_partition_locked_raises_permission_error(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(locked=True)
        block_device = factory.make_BlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device, node=node
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device, node=node
        )
        size = partition_table.block_device.size // 2
        fstype = factory.pick_filesystem_type()
        mount_point = factory.make_absolute_path()
        mount_options = factory.make_name("options")
        params = {
            "system_id": node.system_id,
            "block_id": partition_table.block_device_id,
            "partition_size": size,
            "fstype": fstype,
            "mount_point": mount_point,
            "mount_options": mount_options,
        }
        self.assertRaises(
            HandlerPermissionError, handler.create_partition, params
        )

    def test_create_cache_set_for_partition(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        partition = factory.make_Partition(node=node)
        handler.create_cache_set(
            {"system_id": node.system_id, "partition_id": partition.id}
        )
        cache_set = CacheSet.objects.get_cache_sets_for_node(node).first()
        self.assertIsNotNone(cache_set)
        self.assertEqual(partition, cache_set.get_filesystem().partition)

    def test_create_cache_set_for_block_device(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        handler.create_cache_set(
            {"system_id": node.system_id, "block_id": block_device.id}
        )
        cache_set = CacheSet.objects.get_cache_sets_for_node(node).first()
        self.assertIsNotNone(cache_set)
        self.assertEqual(
            block_device.id, cache_set.get_filesystem().block_device.id
        )

    def test_create_cache_set_locked_raises_permission_error(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(locked=True)
        partition = factory.make_Partition(node=node)
        params = {"system_id": node.system_id, "partition_id": partition.id}
        self.assertRaises(
            HandlerPermissionError, handler.create_cache_set, params
        )

    def test_create_bcache_for_partition(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        partition = factory.make_Partition(node=node)
        name = factory.make_name("bcache")
        cache_set = factory.make_CacheSet(node=node)
        cache_mode = factory.pick_enum(CACHE_MODE_TYPE)
        tags = [factory.make_name("tag") for _ in range(3)]
        handler.create_bcache(
            {
                "system_id": node.system_id,
                "partition_id": partition.id,
                "block_id": partition.partition_table.block_device.id,
                "name": name,
                "cache_set": cache_set.id,
                "cache_mode": cache_mode,
                "tags": tags,
            }
        )
        bcache = Bcache.objects.filter_by_node(node).first()
        self.assertIsNotNone(bcache)
        self.assertEqual(name, bcache.name)
        self.assertEqual(cache_set, bcache.cache_set)
        self.assertEqual(cache_mode, bcache.cache_mode)
        self.assertEqual(
            partition, bcache.get_bcache_backing_filesystem().partition
        )
        self.assertCountEqual(tags, bcache.virtual_device.tags)

    def test_create_bcache_for_partition_with_filesystem(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        partition = factory.make_Partition(node=node)
        name = factory.make_name("bcache")
        cache_set = factory.make_CacheSet(node=node)
        cache_mode = factory.pick_enum(CACHE_MODE_TYPE)
        fstype = factory.pick_filesystem_type()
        mount_point = factory.make_absolute_path()
        mount_options = factory.make_name("options")
        handler.create_bcache(
            {
                "system_id": node.system_id,
                "partition_id": partition.id,
                "block_id": partition.partition_table.block_device.id,
                "name": name,
                "cache_set": cache_set.id,
                "cache_mode": cache_mode,
                "fstype": fstype,
                "mount_point": mount_point,
                "mount_options": mount_options,
            }
        )
        bcache = Bcache.objects.filter_by_node(node).first()
        self.assertIsNotNone(bcache)
        self.assertEqual(name, bcache.name)
        self.assertEqual(cache_set, bcache.cache_set)
        self.assertEqual(cache_mode, bcache.cache_mode)
        self.assertEqual(
            partition, bcache.get_bcache_backing_filesystem().partition
        )
        efs = bcache.virtual_device.get_effective_filesystem()
        self.assertEqual(efs.fstype, fstype)
        self.assertEqual(efs.mount_point, mount_point)
        self.assertEqual(efs.mount_options, mount_options)

    def test_create_bcache_for_block_device(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        name = factory.make_name("bcache")
        cache_set = factory.make_CacheSet(node=node)
        cache_mode = factory.pick_enum(CACHE_MODE_TYPE)
        tags = [factory.make_name("tag") for _ in range(3)]
        handler.create_bcache(
            {
                "system_id": node.system_id,
                "block_id": block_device.id,
                "name": name,
                "cache_set": cache_set.id,
                "cache_mode": cache_mode,
                "tags": tags,
            }
        )
        bcache = Bcache.objects.filter_by_node(node).first()
        self.assertIsNotNone(bcache)
        self.assertEqual(name, bcache.name)
        self.assertEqual(cache_set, bcache.cache_set)
        self.assertEqual(cache_mode, bcache.cache_mode)
        self.assertEqual(
            block_device.id,
            bcache.get_bcache_backing_filesystem().block_device.id,
        )
        self.assertCountEqual(tags, bcache.virtual_device.tags)

    def test_create_bcache_for_block_device_with_filesystem(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        name = factory.make_name("bcache")
        cache_set = factory.make_CacheSet(node=node)
        cache_mode = factory.pick_enum(CACHE_MODE_TYPE)
        fstype = factory.pick_filesystem_type()
        mount_point = factory.make_absolute_path()
        mount_options = factory.make_name("options")
        handler.create_bcache(
            {
                "system_id": node.system_id,
                "block_id": block_device.id,
                "name": name,
                "cache_set": cache_set.id,
                "cache_mode": cache_mode,
                "fstype": fstype,
                "mount_point": mount_point,
                "mount_options": mount_options,
            }
        )
        bcache = Bcache.objects.filter_by_node(node).first()
        self.assertIsNotNone(bcache)
        self.assertEqual(name, bcache.name)
        self.assertEqual(cache_set, bcache.cache_set)
        self.assertEqual(cache_mode, bcache.cache_mode)
        self.assertEqual(
            block_device.id,
            bcache.get_bcache_backing_filesystem().block_device.id,
        )
        efs = bcache.virtual_device.get_effective_filesystem()
        self.assertEqual(efs.fstype, fstype)
        self.assertEqual(efs.mount_point, mount_point)
        self.assertEqual(efs.mount_options, mount_options)

    def test_create_bcache_set_locked_raises_permission_error(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(locked=True)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        name = factory.make_name("bcache")
        cache_set = factory.make_CacheSet(node=node)
        cache_mode = factory.pick_enum(CACHE_MODE_TYPE)
        fstype = factory.pick_filesystem_type()
        mount_point = factory.make_absolute_path()
        mount_options = factory.make_name("options")
        params = {
            "system_id": node.system_id,
            "block_id": block_device.id,
            "name": name,
            "cache_set": cache_set.id,
            "cache_mode": cache_mode,
            "fstype": fstype,
            "mount_point": mount_point,
            "mount_options": mount_options,
        }
        self.assertRaises(
            HandlerPermissionError, handler.create_bcache, params
        )

    def test_create_raid(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        disk0 = factory.make_PhysicalBlockDevice(node=node)
        disk1 = factory.make_PhysicalBlockDevice(node=node)
        disk2 = factory.make_PhysicalBlockDevice(node=node)
        spare_disk = factory.make_PhysicalBlockDevice(node=node)
        name = factory.make_name("md")
        tags = [factory.make_name("tag") for _ in range(3)]
        handler.create_raid(
            {
                "system_id": node.system_id,
                "name": name,
                "level": "raid-5",
                "block_devices": [disk0.id, disk1.id, disk2.id],
                "spare_devices": [spare_disk.id],
                "tags": tags,
            }
        )
        raid = RAID.objects.filter_by_node(node).first()
        self.assertIsNotNone(raid)
        self.assertEqual(name, raid.name)
        self.assertEqual("raid-5", raid.group_type)
        self.assertCountEqual(tags, raid.virtual_device.tags)

    def test_create_raid_with_filesystem(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        disk0 = factory.make_PhysicalBlockDevice(node=node)
        disk1 = factory.make_PhysicalBlockDevice(node=node)
        disk2 = factory.make_PhysicalBlockDevice(node=node)
        spare_disk = factory.make_PhysicalBlockDevice(node=node)
        name = factory.make_name("md")
        fstype = factory.pick_filesystem_type()
        mount_point = factory.make_absolute_path()
        mount_options = factory.make_name("options")
        handler.create_raid(
            {
                "system_id": node.system_id,
                "name": name,
                "level": "raid-5",
                "block_devices": [disk0.id, disk1.id, disk2.id],
                "spare_devices": [spare_disk.id],
                "fstype": fstype,
                "mount_point": mount_point,
                "mount_options": mount_options,
            }
        )
        raid = RAID.objects.filter_by_node(node).first()
        self.assertIsNotNone(raid)
        self.assertEqual(name, raid.name)
        self.assertEqual("raid-5", raid.group_type)
        efs = raid.virtual_device.get_effective_filesystem()
        self.assertEqual(efs.fstype, fstype)
        self.assertEqual(efs.mount_point, mount_point)
        self.assertEqual(efs.mount_options, mount_options)

    def test_create_raid_locked_raises_permission_error(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(locked=True)
        disk0 = factory.make_PhysicalBlockDevice(node=node)
        disk1 = factory.make_PhysicalBlockDevice(node=node)
        params = {
            "system_id": node.system_id,
            "name": factory.make_name("md"),
            "level": "raid-1",
            "block_devices": [disk0.id, disk1.id],
        }
        self.assertRaises(HandlerPermissionError, handler.create_raid, params)

    def test_create_volume_group(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        disk = factory.make_PhysicalBlockDevice(node=node)
        partition = factory.make_Partition(node=node)
        name = factory.make_name("vg")
        handler.create_volume_group(
            {
                "system_id": node.system_id,
                "name": name,
                "block_devices": [disk.id],
                "partitions": [partition.id],
            }
        )
        volume_group = VolumeGroup.objects.filter_by_node(node).first()
        self.assertIsNotNone(volume_group)
        self.assertEqual(name, volume_group.name)

    def test_create_logical_volume(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        volume_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, node=node
        )
        name = factory.make_name("lv")
        size = volume_group.get_lvm_free_space()
        tags = [factory.make_name("tag") for _ in range(3)]
        handler.create_logical_volume(
            {
                "system_id": node.system_id,
                "name": name,
                "volume_group_id": volume_group.id,
                "size": size,
                "tags": tags,
            }
        )
        logical_volume = volume_group.virtual_devices.first()
        self.assertIsNotNone(logical_volume)
        self.assertEqual(
            f"{volume_group.name}-{name}", logical_volume.get_name()
        )
        self.assertEqual(size, logical_volume.size)
        self.assertCountEqual(tags, logical_volume.tags)

    def test_create_logical_volume_with_filesystem(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        volume_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, node=node
        )
        name = factory.make_name("lv")
        size = volume_group.get_lvm_free_space()
        fstype = factory.pick_filesystem_type()
        mount_point = factory.make_absolute_path()
        mount_options = factory.make_name("options")
        handler.create_logical_volume(
            {
                "system_id": node.system_id,
                "name": name,
                "volume_group_id": volume_group.id,
                "size": size,
                "fstype": fstype,
                "mount_point": mount_point,
                "mount_options": mount_options,
            }
        )
        logical_volume = volume_group.virtual_devices.first()
        self.assertIsNotNone(logical_volume)
        self.assertEqual(
            f"{volume_group.name}-{name}", logical_volume.get_name()
        )
        self.assertEqual(size, logical_volume.size)
        efs = logical_volume.get_effective_filesystem()
        self.assertEqual(efs.fstype, fstype)
        self.assertEqual(efs.mount_point, mount_point)
        self.assertEqual(efs.mount_options, mount_options)

    def test_create_logical_volume_locked_raises_permission_error(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(locked=True)
        volume_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, node=node
        )
        size = volume_group.get_lvm_free_space()
        params = {
            "system_id": node.system_id,
            "name": factory.make_name("lv"),
            "volume_group_id": volume_group.id,
            "size": size,
        }
        self.assertRaises(
            HandlerPermissionError, handler.create_logical_volume, params
        )

    def test_create_vmfs_datastore(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(with_boot_disk=False)
        node.boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS6StorageLayout(node)
        layout.configure()
        bd_ids = [
            factory.make_PhysicalBlockDevice(node=node).id for _ in range(3)
        ]
        params = {
            "system_id": node.system_id,
            "name": "datastore2",
            "block_devices": bd_ids,
        }
        handler.create_vmfs_datastore(params)
        vbd = node.virtualblockdevice_set.get(name="datastore2")
        vmfs = vbd.filesystem_group
        self.assertCountEqual(
            bd_ids,
            [
                fs.partition.partition_table.block_device_id
                for fs in vmfs.filesystems.all()
            ],
        )

    def test_create_vmfs_datastore_raises_errors(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node()
        self.assertRaises(
            HandlerError,
            handler.create_vmfs_datastore,
            {"system_id": node.system_id},
        )

    def test_set_boot_disk(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        boot_disk = factory.make_PhysicalBlockDevice(node=node)
        handler.set_boot_disk(
            {"system_id": node.system_id, "block_id": boot_disk.id}
        )
        self.assertEqual(boot_disk.id, reload_object(node).get_boot_disk().id)

    def test_set_boot_disk_raises_error_for_none_physical(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        boot_disk = factory.make_VirtualBlockDevice(node=node)
        error = self.assertRaises(
            HandlerError,
            handler.set_boot_disk,
            {"system_id": node.system_id, "block_id": boot_disk.id},
        )
        self.assertEqual(
            str(error), "Only a physical disk can be set as the boot disk."
        )

    def test_set_boot_disk_locked_raises_permission_error(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(locked=True)
        boot_disk = factory.make_PhysicalBlockDevice(node=node)
        params = {"system_id": node.system_id, "block_id": boot_disk.id}
        self.assertRaises(
            HandlerPermissionError, handler.set_boot_disk, params
        )

    def test_apply_storage_layout(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(with_boot_disk=False)
        node.boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=40 * 1024**3
        )
        factory.make_PhysicalBlockDevice(node=node, size=20 * 1024**3)
        storage_layout = factory.pick_choice(
            STORAGE_LAYOUT_CHOICES,
            but_not=("blank", "custom"),
        )
        self.addDetail("storage_layout", text_content(storage_layout))
        params = {
            "system_id": node.system_id,
            "storage_layout": storage_layout,
        }
        handler.apply_storage_layout(params)
        self.assertTrue(node.boot_disk.partitiontable_set.exists())

    def test_apply_storage_layout_validates_layout_name(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node()
        params = {
            "system_id": node.system_id,
            "storage_layout": factory.make_name("storage_layout"),
        }
        self.assertRaises(HandlerError, handler.apply_storage_layout, params)

    def test_apply_storage_layout_raises_missing_boot_disk_error(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(with_boot_disk=False)
        params = {
            "system_id": node.system_id,
            "storage_layout": factory.pick_choice(STORAGE_LAYOUT_CHOICES),
        }
        self.assertRaises(HandlerError, handler.apply_storage_layout, params)

    def test_apply_storage_layout_raises_errors(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(size=1024**3)
        params = {
            "system_id": node.system_id,
            "storage_layout": factory.pick_choice(STORAGE_LAYOUT_CHOICES),
        }
        self.assertRaises(HandlerError, handler.apply_storage_layout, params)

    def test_update_raise_HandlerError_if_tag_has_definition(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        tag = factory.make_Tag()
        node_data = TestMachineHandlerUtils.dehydrate_node(node, handler)
        node_data["tags"].append(tag.name)
        self.assertRaises(HandlerError, handler.update, node_data)

    def test_missing_action_raises_error(self):
        user = factory.make_User()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        self.assertRaises(
            NodeActionError, handler.action, {"system_id": node.system_id}
        )

    def test_invalid_action_raises_error(self):
        user = factory.make_User()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        self.assertRaises(
            NodeActionError,
            handler.action,
            {"system_id": node.system_id, "action": "unknown"},
        )

    def test_not_available_action_raises_error(self):
        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, owner=user)
        handler = MachineHandler(user, {}, None)
        self.assertRaises(
            NodeActionError,
            handler.action,
            {"system_id": node.system_id, "action": "unknown"},
        )

    def test_action_performs_action(self):
        admin = factory.make_admin()
        request = HttpRequest()
        request.user = admin
        factory.make_SSHKey(admin)
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=admin)
        handler = MachineHandler(admin, {}, request)
        handler.action(
            {
                "request": request,
                "system_id": node.system_id,
                "action": "delete",
            }
        )
        self.assertIsNone(reload_object(node))

    def test_action_performs_action_passing_extra(self):
        factory.make_RegionController()
        user = factory.make_User()
        request = HttpRequest()
        request.user = user
        factory.make_SSHKey(user)
        self.patch(Machine, "on_network").return_value = True
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=user, interface=True
        )
        self.patch(Machine, "_start").return_value = None
        self.patch(node_action_module, "get_curtin_config")
        self.patch(
            power_workflow, "get_temporal_task_queue_for_bmc"
        ).return_value = "vlan-1"
        osystem, releases = make_usable_osystem(self)
        handler = MachineHandler(user, {}, request)
        handler.action(
            {
                "request": request,
                "system_id": node.system_id,
                "action": "deploy",
                "extra": {
                    "osystem": osystem,
                    "distro_series": releases[0],
                },
            }
        )
        node = reload_object(node)
        self.assertEqual(osystem, node.osystem)
        self.assertEqual(releases[0], node.distro_series)

    def test_clone_errors_bundled(self):
        user = factory.make_admin()
        node = factory.make_Node()

        handler = MachineHandler(user, {}, None)
        exc = self.assertRaises(
            NodeActionError,
            handler.action,
            {
                "system_id": node.system_id,
                "action": "clone",
                "extra": {
                    "storage": False,
                    "interfaces": False,
                    "destinations": [],
                },
            },
        )
        (errors,) = exc.args
        self.assertEqual(
            json.loads(errors),
            {
                "destinations": [
                    {
                        "message": "This field is required.",
                        "code": "required",
                    }
                ],
                "__all__": [
                    {
                        "message": "Either storage or interfaces must be true.",
                        "code": "required",
                    }
                ],
            },
        )

    def test_clone_errors_storage(self):
        user = factory.make_admin()
        request = HttpRequest()
        request.user = user
        source = factory.make_Machine(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=source, size=8 * 1024**3, name="sda"
        )
        destination1 = factory.make_Machine(
            status=NODE_STATUS.READY, with_boot_disk=False
        )
        factory.make_PhysicalBlockDevice(
            node=destination1, size=1024**3, name="sda"
        )
        destination2 = factory.make_Machine(
            status=NODE_STATUS.FAILED_TESTING,
            with_boot_disk=False,
        )
        factory.make_PhysicalBlockDevice(
            node=destination2, size=1024**3, name="sda"
        )

        handler = MachineHandler(user, {}, request)
        exc = self.assertRaises(
            NodeActionError,
            handler.action,
            {
                "system_id": source.system_id,
                "action": "clone",
                "extra": {
                    "storage": True,
                    "interfaces": False,
                    "destinations": [
                        destination1.system_id,
                        destination2.system_id,
                    ],
                },
            },
        )
        (errors,) = exc.args
        self.assertEqual(
            json.loads(errors),
            {
                "destinations": [
                    {
                        "message": f"{destination1} is invalid: destination boot disk(sda) is smaller than source boot disk(sda)",
                        "code": "storage",
                        "system_id": destination1.system_id,
                    },
                    {
                        "message": f"{destination2} is invalid: destination boot disk(sda) is smaller than source boot disk(sda)",
                        "code": "storage",
                        "system_id": destination2.system_id,
                    },
                ],
            },
        )

    def test_clone_success(self):
        user = factory.make_admin()
        request = HttpRequest()
        request.user = user
        source = factory.make_Machine(with_boot_disk=False)
        source_boot_disk = factory.make_PhysicalBlockDevice(
            node=source, size=8 * 1024**3, name="sda"
        )
        partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.MBR, block_device=source_boot_disk
        )
        factory.make_Partition(
            partition_table=partition_table,
            uuid="6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398",
            size=512 * 1024**2,
            bootable=True,
        )
        factory.make_Partition(
            partition_table=partition_table,
            uuid="f74ff260-2a5b-4a36-b1b8-37f746b946bf",
            size=2 * 1024**3,
            bootable=False,
        )
        destination = factory.make_Machine(
            status=NODE_STATUS.READY, with_boot_disk=False
        )
        factory.make_PhysicalBlockDevice(
            node=destination, size=8 * 1024**3, name="sda"
        )
        pt = (
            destination.current_config.blockdevice_set.first().get_partitiontable()
        )
        self.assertIsNone(pt)  # Pre-condition check
        handler = MachineHandler(user, {}, request)
        handler.action(
            {
                "system_id": source.system_id,
                "action": "clone",
                "extra": {
                    "storage": True,
                    "interfaces": False,
                    "destinations": [
                        destination.system_id,
                    ],
                },
            },
        )
        pt = (
            destination.current_config.blockdevice_set.first().get_partitiontable()
        )
        self.assertIsNotNone(pt)

    def test_clone_with_filter(self):
        user = factory.make_admin()
        request = HttpRequest()
        request.user = user
        source = factory.make_Machine(with_boot_disk=False)
        source_boot_disk = factory.make_PhysicalBlockDevice(
            node=source, size=8 * 1024**3, name="sda"
        )
        partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.MBR, block_device=source_boot_disk
        )
        factory.make_Partition(
            partition_table=partition_table,
            uuid="6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398",
            size=512 * 1024**2,
            bootable=True,
        )
        factory.make_Partition(
            partition_table=partition_table,
            uuid="f74ff260-2a5b-4a36-b1b8-37f746b946bf",
            size=2 * 1024**3,
            bootable=False,
        )
        destination = factory.make_Machine(
            status=NODE_STATUS.READY, with_boot_disk=False
        )
        factory.make_PhysicalBlockDevice(
            node=destination, size=8 * 1024**3, name="sda"
        )
        pt = (
            destination.current_config.blockdevice_set.first().get_partitiontable()
        )
        self.assertIsNone(pt)  # Pre-condition check
        handler = MachineHandler(user, {}, request)
        handler.action(
            {
                "system_id": source.system_id,
                "action": "clone",
                "extra": {
                    "storage": True,
                    "interfaces": False,
                },
                "filter": {"id": destination.system_id},
            },
        )
        pt = (
            destination.current_config.blockdevice_set.first().get_partitiontable()
        )
        self.assertIsNotNone(pt)

    def test_clone_where_possible(self):
        user = factory.make_admin()
        request = HttpRequest()
        request.user = user
        source = factory.make_Machine(with_boot_disk=False)
        boot_disk = factory.make_PhysicalBlockDevice(
            node=source, size=8 * 1024**3, name="sda"
        )
        partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.MBR, block_device=boot_disk
        )
        efi_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398",
            size=512 * 1024**2,
            bootable=True,
        )
        root_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="f74ff260-2a5b-4a36-b1b8-37f746b946bf",
            size=2 * 1024**3,
            bootable=False,
        )
        destination1 = factory.make_Machine(
            status=NODE_STATUS.READY, with_boot_disk=False
        )
        factory.make_PhysicalBlockDevice(
            node=destination1, size=1024**3, name="sda"
        )
        destination2 = factory.make_Machine(
            status=NODE_STATUS.FAILED_TESTING,
            with_boot_disk=False,
        )
        factory.make_PhysicalBlockDevice(
            node=destination2, size=8 * 1024**3, name="sda"
        )

        handler = MachineHandler(user, {}, request)
        exc = self.assertRaises(
            NodeActionError,
            handler.action,
            {
                "system_id": source.system_id,
                "action": "clone",
                "extra": {
                    "storage": True,
                    "interfaces": False,
                    "destinations": [
                        destination1.system_id,
                        destination2.system_id,
                    ],
                },
            },
        )
        (errors,) = exc.args
        self.assertEqual(
            json.loads(errors),
            {
                "destinations": [
                    {
                        "message": f"{destination1} is invalid: destination boot disk(sda) is smaller than source boot disk(sda)",
                        "code": "storage",
                        "system_id": destination1.system_id,
                    },
                ],
            },
        )
        partition_table = (
            destination2.current_config.blockdevice_set.first().get_partitiontable()
        )
        self.assertIsNotNone(partition_table)
        partitions = partition_table.partitions
        maybe_efi, maybe_root, *rest = partitions.all()
        self.assertEqual(rest, [])
        self.assertEqual(maybe_efi.size, efi_partition.size)
        self.assertTrue(maybe_efi.bootable)

        self.assertEqual(maybe_root.size, root_partition.size)
        self.assertFalse(maybe_root.bootable)

    def test_create_physical_creates_interface(self):
        user = factory.make_admin()
        node = factory.make_Node(interface=False)
        handler = MachineHandler(user, {}, None)
        name = factory.make_name("eth")
        mac_address = factory.make_mac_address()
        vlan = factory.make_VLAN()
        handler.create_physical(
            {
                "system_id": node.system_id,
                "name": name,
                "mac_address": mac_address,
                "vlan": vlan.id,
            }
        )
        self.assertEqual(
            1,
            node.current_config.interface_set.count(),
            "Should have one interface on the node.",
        )

    def test_create_physical_creates_link_auto(self):
        user = factory.make_admin()
        node = factory.make_Node(interface=False)
        handler = MachineHandler(user, {}, None)
        name = factory.make_name("eth")
        mac_address = factory.make_mac_address()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        handler.create_physical(
            {
                "system_id": node.system_id,
                "name": name,
                "mac_address": mac_address,
                "vlan": vlan.id,
                "mode": INTERFACE_LINK_TYPE.AUTO,
                "subnet": subnet.id,
            }
        )
        new_interface = node.current_config.interface_set.first()
        self.assertIsNotNone(new_interface)
        auto_ip = new_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO, subnet=subnet
        )
        self.assertIsNotNone(auto_ip)

    def test_create_physical_creates_link_up(self):
        user = factory.make_admin()
        node = factory.make_Node(interface=False)
        handler = MachineHandler(user, {}, None)
        name = factory.make_name("eth")
        mac_address = factory.make_mac_address()
        vlan = factory.make_VLAN()
        handler.create_physical(
            {
                "system_id": node.system_id,
                "name": name,
                "mac_address": mac_address,
                "vlan": vlan.id,
                "mode": INTERFACE_LINK_TYPE.LINK_UP,
            }
        )
        new_interface = node.current_config.interface_set.first()
        self.assertIsNotNone(new_interface)
        link_up_ip = new_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=None
        )
        self.assertIsNotNone(link_up_ip)

    def test_create_physical_creates_link_up_with_subnet(self):
        user = factory.make_admin()
        node = factory.make_Node(interface=False)
        handler = MachineHandler(user, {}, None)
        name = factory.make_name("eth")
        mac_address = factory.make_mac_address()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        handler.create_physical(
            {
                "system_id": node.system_id,
                "name": name,
                "mac_address": mac_address,
                "vlan": vlan.id,
                "mode": INTERFACE_LINK_TYPE.LINK_UP,
                "subnet": subnet.id,
            }
        )
        new_interface = node.current_config.interface_set.first()
        self.assertIsNotNone(new_interface)
        link_up_ip = new_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=None, subnet=subnet
        )
        self.assertIsNotNone(link_up_ip)

    def test_create_vlan_creates_vlan(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        vlan = factory.make_VLAN()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan
        )
        handler.create_vlan(
            {
                "system_id": node.system_id,
                "parent": interface.id,
                "vlan": vlan.id,
            }
        )
        vlan_interface = get_one(
            Interface.objects.filter(
                node_config=node.current_config,
                type=INTERFACE_TYPE.VLAN,
                parents=interface,
            )
        )
        self.assertIsNotNone(vlan_interface)

    def test_create_physical_locked_raises_permission_error(self):
        user = factory.make_admin()
        node = factory.make_Node(locked=True)
        handler = MachineHandler(user, {}, None)
        vlan = factory.make_VLAN()
        params = {
            "system_id": node.system_id,
            "name": factory.make_name("eth"),
            "mac_address": factory.make_mac_address(),
            "vlan": vlan.id,
        }
        self.assertRaises(
            HandlerPermissionError, handler.create_physical, params
        )

    def test_create_vlan_creates_link_auto(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        vlan = factory.make_VLAN()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan
        )
        new_subnet = factory.make_Subnet(vlan=vlan)
        handler.create_vlan(
            {
                "system_id": node.system_id,
                "parent": interface.id,
                "vlan": vlan.id,
                "mode": INTERFACE_LINK_TYPE.AUTO,
                "subnet": new_subnet.id,
            }
        )
        vlan_interface = get_one(
            Interface.objects.filter(
                node_config=node.current_config,
                type=INTERFACE_TYPE.VLAN,
                parents=interface,
            )
        )
        self.assertIsNotNone(vlan_interface)
        auto_ip = vlan_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO, subnet=new_subnet
        )
        self.assertIsNotNone(auto_ip)

    def test_create_vlan_creates_link_up(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        vlan = factory.make_VLAN()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan
        )
        handler.create_vlan(
            {
                "system_id": node.system_id,
                "parent": interface.id,
                "vlan": vlan.id,
                "mode": INTERFACE_LINK_TYPE.LINK_UP,
            }
        )
        vlan_interface = get_one(
            Interface.objects.filter(
                node_config=node.current_config,
                type=INTERFACE_TYPE.VLAN,
                parents=interface,
            )
        )
        self.assertIsNotNone(vlan_interface)
        link_up_ip = vlan_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=None
        )
        self.assertIsNotNone(link_up_ip)

    def test_create_vlan_creates_link_up_with_subnet(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        vlan = factory.make_VLAN()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan
        )
        new_subnet = factory.make_Subnet(vlan=vlan)
        handler.create_vlan(
            {
                "system_id": node.system_id,
                "parent": interface.id,
                "vlan": vlan.id,
                "mode": INTERFACE_LINK_TYPE.LINK_UP,
                "subnet": new_subnet.id,
            }
        )
        vlan_interface = get_one(
            Interface.objects.filter(
                node_config=node.current_config,
                type=INTERFACE_TYPE.VLAN,
                parents=interface,
            )
        )
        self.assertIsNotNone(vlan_interface)
        link_up_ip = vlan_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=None, subnet=new_subnet
        )
        self.assertIsNotNone(link_up_ip)

    def test_create_vlan_locked_raises_permission_error(self):
        user = factory.make_admin()
        node = factory.make_Node(locked=True)
        handler = MachineHandler(user, {}, None)
        vlan = factory.make_VLAN()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan
        )
        new_subnet = factory.make_Subnet(vlan=vlan)
        params = {
            "system_id": node.system_id,
            "parent": interface.id,
            "vlan": vlan.id,
            "mode": INTERFACE_LINK_TYPE.AUTO,
            "subnet": new_subnet.id,
        }
        self.assertRaises(HandlerPermissionError, handler.create_vlan, params)

    def test_create_bond_creates_bond(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        nic1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        nic2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=nic1.vlan
        )
        bond_mode = factory.pick_enum(BOND_MODE)
        name = factory.make_name("bond")
        handler.create_bond(
            {
                "system_id": node.system_id,
                "name": name,
                "parents": [nic1.id, nic2.id],
                "mac_address": "%s" % nic1.mac_address,
                "vlan": nic1.vlan.id,
                "bond_mode": bond_mode,
            }
        )
        bond_interface = get_one(
            Interface.objects.filter(
                node_config=node.current_config,
                type=INTERFACE_TYPE.BOND,
                parents=nic1,
                name=name,
                vlan=nic1.vlan,
            )
        )
        self.assertIsNotNone(bond_interface)
        self.assertEqual(bond_mode, bond_interface.params["bond_mode"])

    def test_create_bond_raises_ValidationError(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        nic1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        nic2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=nic1.vlan
        )
        with self.assertRaisesRegex(ValidationError, "This field is required"):
            handler.create_bond(
                {"system_id": node.system_id, "parents": [nic1.id, nic2.id]}
            )

    def test_create_bond_locked_raises_permission_error(self):
        user = factory.make_admin()
        node = factory.make_Node(locked=True)
        handler = MachineHandler(user, {}, None)
        nic1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        nic2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=nic1.vlan
        )
        bond_mode = factory.pick_enum(BOND_MODE)
        params = {
            "system_id": node.system_id,
            "name": factory.make_name("bond"),
            "parents": [nic1.id, nic2.id],
            "mac_address": "%s" % nic1.mac_address,
            "vlan": nic1.vlan.id,
            "bond_mode": bond_mode,
        }
        self.assertRaises(HandlerPermissionError, handler.create_bond, params)

    def test_create_bridge_creates_bridge(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        nic1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        name = factory.make_name("br")
        bridge_type = factory.pick_choice(BRIDGE_TYPE_CHOICES)
        bridge_stp = factory.pick_bool()
        bridge_fd = random.randint(0, 15)
        handler.create_bridge(
            {
                "system_id": node.system_id,
                "name": name,
                "parents": [nic1.id],
                "mac_address": "%s" % nic1.mac_address,
                "vlan": nic1.vlan.id,
                "bridge_type": bridge_type,
                "bridge_stp": bridge_stp,
                "bridge_fd": bridge_fd,
            }
        )
        bridge_interface = get_one(
            Interface.objects.filter(
                node_config=node.current_config,
                type=INTERFACE_TYPE.BRIDGE,
                parents=nic1,
                name=name,
                vlan=nic1.vlan,
            )
        )
        self.assertIsNotNone(bridge_interface)
        self.assertEqual(bridge_type, bridge_interface.params["bridge_type"])
        self.assertEqual(bridge_stp, bridge_interface.params["bridge_stp"])
        self.assertEqual(bridge_fd, bridge_interface.params["bridge_fd"])

    def test_create_bridge_raises_ValidationError(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        nic1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        with self.assertRaisesRegex(ValidationError, "This field is required"):
            handler.create_bridge(
                {"system_id": node.system_id, "parents": [nic1.id]}
            )

    def test_create_bridge_locked_raises_permission_error(self):
        user = factory.make_admin()
        node = factory.make_Node(locked=True)
        handler = MachineHandler(user, {}, None)
        nic1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        params = {
            "system_id": node.system_id,
            "name": factory.make_name("br"),
            "parents": [nic1.id],
            "mac_address": "%s" % nic1.mac_address,
            "vlan": nic1.vlan.id,
            "bridge_type": factory.pick_choice(BRIDGE_TYPE_CHOICES),
            "bridge_stp": factory.pick_bool(),
            "bridge_fd": random.randint(0, 15),
        }
        self.assertRaises(
            HandlerPermissionError, handler.create_bridge, params
        )

    def test_update_interface(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        new_name = factory.make_name("name")
        new_vlan = factory.make_VLAN()
        new_interface_speed = random.randint(1000, 10000)
        new_link_connected = True
        new_link_speed = random.randint(1000, new_interface_speed)
        handler._script_results = {}
        handler._cache_pks([node])
        handler.update_interface(
            {
                "system_id": node.system_id,
                "interface_id": interface.id,
                "name": new_name,
                "vlan": new_vlan.id,
                "interface_speed": new_interface_speed,
                "link_connected": new_link_connected,
                "link_speed": new_link_speed,
            }
        )
        interface = reload_object(interface)
        self.assertEqual(new_name, interface.name)
        self.assertEqual(new_vlan, interface.vlan)
        self.assertEqual(new_interface_speed, interface.interface_speed)
        self.assertEqual(new_link_connected, interface.link_connected)
        self.assertEqual(new_link_speed, interface.link_speed)

    def test_update_interface_for_deployed_node(self):
        user = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        handler = MachineHandler(user, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        new_name = factory.make_name("name")
        new_interface_speed = random.randint(1000, 10000)
        new_link_connected = True
        new_link_speed = random.randint(1000, new_interface_speed)
        handler._script_results = {}
        handler._cache_pks([node])
        handler.update_interface(
            {
                "system_id": node.system_id,
                "interface_id": interface.id,
                "name": new_name,
                "interface_speed": new_interface_speed,
                "link_connected": new_link_connected,
                "link_speed": new_link_speed,
            }
        )
        interface = reload_object(interface)
        self.assertEqual(new_name, interface.name)
        self.assertEqual(new_interface_speed, interface.interface_speed)
        self.assertEqual(new_link_connected, interface.link_connected)
        self.assertEqual(new_link_speed, interface.link_speed)

    def test_update_interface_raises_ValidationError(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        new_name = factory.make_name("name")
        with self.assertRaisesRegex(
            ValidationError,
            "Select a valid choice. That choice is not one of the available choices.",
        ):
            handler.update_interface(
                {
                    "system_id": node.system_id,
                    "interface_id": interface.id,
                    "name": new_name,
                    "vlan": random.randint(1000, 5000),
                }
            )

    def test_update_interface_locked_raises_permission_error(self):
        user = factory.make_admin()
        node = factory.make_Node(locked=True)
        handler = MachineHandler(user, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        handler._script_results = {}
        handler._cache_pks([node])
        params = {
            "system_id": node.system_id,
            "interface_id": interface.id,
            "name": factory.make_name("name"),
        }
        self.assertRaises(
            HandlerPermissionError, handler.update_interface, params
        )

    def test_delete_interface(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        handler.delete_interface(
            {"system_id": node.system_id, "interface_id": interface.id}
        )
        self.assertIsNone(reload_object(interface))

    def test_delete_interface_locked_raises_permission_error(self):
        user = factory.make_admin()
        node = factory.make_Node(locked=True)
        handler = MachineHandler(user, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        params = {"system_id": node.system_id, "interface_id": interface.id}
        self.assertRaises(
            HandlerPermissionError, handler.delete_interface, params
        )

    def test_link_subnet_calls_update_link_by_id_if_link_id(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        subnet = factory.make_Subnet()
        sip = factory.make_StaticIPAddress(interface=interface)
        link_id = sip.id
        mode = factory.pick_enum(INTERFACE_LINK_TYPE)
        ip_address = factory.make_ip_address()
        self.patch_autospec(Interface, "update_link_by_id")
        handler.link_subnet(
            {
                "system_id": node.system_id,
                "interface_id": interface.id,
                "link_id": link_id,
                "subnet": subnet.id,
                "mode": mode,
                "ip_address": ip_address,
            }
        )
        Interface.update_link_by_id.assert_called_once_with(
            ANY, link_id, mode, subnet, ip_address=ip_address
        )

    def test_link_subnet_calls_nothing_if_link_id_is_deleted(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        subnet = factory.make_Subnet()
        sip = factory.make_StaticIPAddress(interface=interface)
        link_id = sip.id
        sip.delete()
        mode = factory.pick_enum(INTERFACE_LINK_TYPE)
        ip_address = factory.make_ip_address()
        self.patch_autospec(Interface, "update_link_by_id")
        handler.link_subnet(
            {
                "system_id": node.system_id,
                "interface_id": interface.id,
                "link_id": link_id,
                "subnet": subnet.id,
                "mode": mode,
                "ip_address": ip_address,
            }
        )
        Interface.update_link_by_id.assert_not_called()

    def test_link_subnet_calls_link_subnet_if_not_link_id(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        subnet = factory.make_Subnet()
        mode = factory.pick_enum(INTERFACE_LINK_TYPE)
        ip_address = factory.make_ip_address()
        self.patch_autospec(Interface, "link_subnet")
        handler.link_subnet(
            {
                "system_id": node.system_id,
                "interface_id": interface.id,
                "subnet": subnet.id,
                "mode": mode,
                "ip_address": ip_address,
            }
        )
        Interface.link_subnet.assert_called_once_with(
            ANY, mode, subnet, ip_address=ip_address
        )

    def test_link_subnet_locked_raises_permission_error(self):
        user = factory.make_admin()
        node = factory.make_Node(locked=True)
        handler = MachineHandler(user, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        subnet = factory.make_Subnet()
        params = {
            "system_id": node.system_id,
            "interface_id": interface.id,
            "link_id": factory.make_StaticIPAddress(interface=interface).id,
            "subnet": subnet.id,
            "mode": factory.pick_enum(INTERFACE_LINK_TYPE),
            "ip_address": factory.make_ip_address(),
        }
        self.assertRaises(HandlerPermissionError, handler.link_subnet, params)

    def test_unlink_subnet(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = MachineHandler(user, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        link_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="", interface=interface
        )
        handler.unlink_subnet(
            {
                "system_id": node.system_id,
                "interface_id": interface.id,
                "link_id": link_ip.id,
            }
        )
        self.assertIsNone(reload_object(link_ip))

    def test_unlink_subnet_locked_raises_permission_error(self):
        user = factory.make_admin()
        node = factory.make_Node(locked=True)
        handler = MachineHandler(user, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        link_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="", interface=interface
        )
        params = {
            "system_id": node.system_id,
            "interface_id": interface.id,
            "link_id": link_ip.id,
        }
        self.assertRaises(
            HandlerPermissionError, handler.unlink_subnet, params
        )

    def test_get_grouped_storages_parses_blockdevices(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        size = random.randint(MIN_BLOCK_DEVICE_SIZE, 1000**3)
        ssd = factory.make_PhysicalBlockDevice(node=node, tags=["ssd"])
        hdd = factory.make_PhysicalBlockDevice(
            node=node, tags=["hdd"], size=size
        )
        rotary = factory.make_PhysicalBlockDevice(
            node=node, tags=["rotary"], size=size
        )
        handler = MachineHandler(user, {}, None)
        self.assertEqual(
            handler.get_grouped_storages([ssd, hdd, rotary]),
            [
                {
                    "count": 1,
                    "size": ssd.size,
                    "disk_type": "ssd",
                },
                {
                    "count": 2,
                    "size": hdd.size,
                    "disk_type": "hdd",
                },
            ],
        )

    def test_scriptresult_cache_allows_duplicate_with_diff_params(self):
        user = factory.make_User()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(with_boot_disk=False)
        bds = [
            factory.make_PhysicalBlockDevice(node=node, bootable=True)
            for _ in range(2)
        ]
        ifaces = [factory.make_Interface(node=node) for _ in range(2)]
        testing_script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.TESTING
        )
        node.current_testing_script_set = testing_script_set
        node.save()
        bd_script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            hardware_type=HARDWARE_TYPE.STORAGE,
            parameters={"storage": {"type": "storage"}},
        )
        iface_script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            hardware_type=HARDWARE_TYPE.NETWORK,
            parameters={"interface": {"type": "interface"}},
        )
        factory.make_ScriptResult(
            script_set=testing_script_set,
            script=bd_script,
            status=SCRIPT_STATUS.PASSED,
            physical_blockdevice=bds[0],
        )
        factory.make_ScriptResult(
            script_set=testing_script_set,
            script=bd_script,
            status=SCRIPT_STATUS.FAILED,
            physical_blockdevice=bds[1],
        )
        factory.make_ScriptResult(
            script_set=testing_script_set,
            script=iface_script,
            status=SCRIPT_STATUS.PASSED,
            interface=ifaces[0],
        )
        factory.make_ScriptResult(
            script_set=testing_script_set,
            script=iface_script,
            status=SCRIPT_STATUS.FAILED,
            interface=ifaces[1],
        )
        observed = handler.get({"system_id": node.system_id})
        self.assertEqual(
            {
                "status": SCRIPT_STATUS.FAILED,
                "pending": 0,
                "running": 0,
                "passed": 2,
                "failed": 2,
            },
            observed["testing_status"],
        )
        self.assertDictEqual(
            {
                "status": SCRIPT_STATUS.FAILED,
                "pending": 0,
                "running": 0,
                "passed": 1,
                "failed": 1,
            },
            observed["storage_test_status"],
        )
        self.assertEqual(
            {
                "status": SCRIPT_STATUS.FAILED,
                "pending": 0,
                "running": 0,
                "passed": 1,
                "failed": 1,
            },
            observed["network_test_status"],
        )


class TestMachineHandlerCheckPower(MAASTransactionServerTestCase):
    @wait_for_reactor
    @inlineCallbacks
    def test_retrieves_and_updates_power_state(self):
        user = yield deferToDatabase(transactional(factory.make_User))
        machine_handler = MachineHandler(user, {}, None)
        node = yield deferToDatabase(
            transactional(factory.make_Node), power_state=POWER_STATE.OFF
        )
        mock_power_query = self.patch(Node, "power_query")
        mock_power_query.return_value = POWER_STATE.ON
        power_state = yield machine_handler.check_power(
            {"system_id": node.system_id}
        )
        self.assertEqual(power_state, POWER_STATE.ON)

    @wait_for_reactor
    @inlineCallbacks
    def test_raises_failure_for_UnknownPowerType(self):
        user = yield deferToDatabase(transactional(factory.make_User))
        machine_handler = MachineHandler(user, {}, None)
        node = yield deferToDatabase(transactional(factory.make_Node))
        mock_power_query = self.patch(Node, "power_query")
        mock_power_query.side_effect = UnknownPowerType()
        power_state = yield machine_handler.check_power(
            {"system_id": node.system_id}
        )
        self.assertEqual(power_state, POWER_STATE.UNKNOWN)

    @wait_for_reactor
    @inlineCallbacks
    def test_raises_failure_for_NotImplementedError(self):
        user = yield deferToDatabase(transactional(factory.make_User))
        machine_handler = MachineHandler(user, {}, None)
        node = yield deferToDatabase(transactional(factory.make_Node))
        mock_power_query = self.patch(Node, "power_query")
        mock_power_query.side_effect = NotImplementedError()
        power_state = yield machine_handler.check_power(
            {"system_id": node.system_id}
        )
        self.assertEqual(power_state, POWER_STATE.UNKNOWN)

    @wait_for_reactor
    @inlineCallbacks
    def test_logs_other_errors(self):
        user = yield deferToDatabase(transactional(factory.make_User))
        machine_handler = MachineHandler(user, {}, None)
        node = yield deferToDatabase(transactional(factory.make_Node))
        mock_power_query = self.patch(Node, "power_query")
        mock_power_query.side_effect = factory.make_exception("Error")
        mock_log_err = self.patch(machine_module.log, "err")
        power_state = yield machine_handler.check_power(
            {"system_id": node.system_id}
        )
        self.assertEqual(power_state, POWER_STATE.ERROR)
        mock_log_err.assert_called_once_with(
            ANY, "Failed to update power state of machine."
        )


class TestMachineHandlerMountSpecial(MAASServerTestCase):
    """Tests for MachineHandler.mount_special."""

    def test_fstype_and_mount_point_is_required_but_options_is_not(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        machine = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=user)
        params = {"system_id": machine.system_id}
        error = self.assertRaises(
            HandlerValidationError, handler.mount_special, params
        )
        self.assertEqual(
            dict(error),
            {
                "fstype": ["This field is required."],
                "mount_point": ["This field is required."],
            },
        )

    def test_fstype_must_be_a_non_storage_type(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        machine = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=user)
        for fstype in Filesystem.TYPES_REQUIRING_STORAGE:
            params = {
                "system_id": machine.system_id,
                "fstype": fstype,
                "mount_point": factory.make_absolute_path(),
            }
            error = self.assertRaises(
                HandlerValidationError, handler.mount_special, params
            )
            self.assertEqual(
                dict(error)["fstype"],
                [
                    f"Select a valid choice. {fstype} is not one of the available choices."
                ],
                f"using fstype {fstype}",
            )

    def test_mount_point_must_be_absolute(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        machine = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=user)
        params = {
            "system_id": machine.system_id,
            "fstype": FILESYSTEM_TYPE.RAMFS,
            "mount_point": factory.make_name("path"),
        }
        error = self.assertRaises(
            HandlerValidationError, handler.mount_special, params
        )
        self.assertEqual(
            dict(error)[
                "mount_point"
            ],  # XXX: Wow, what a lame error from AbsolutePathField!
            ["Enter a valid value."],
        )

    def test_locked_raises_permission_error(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        machine = factory.make_Node(locked=True, owner=user)
        params = {
            "system_id": machine.system_id,
            "fstype": FILESYSTEM_TYPE.RAMFS,
            "mount_point": factory.make_absolute_path(),
        }
        self.assertRaises(
            HandlerPermissionError, handler.mount_special, params
        )


class TestMachineHandlerMountSpecialScenarios(MAASServerTestCase):
    """Scenario tests for MachineHandler.mount_special."""

    scenarios = [
        (displayname, {"fstype": name})
        for name, displayname in FILESYSTEM_FORMAT_TYPE_CHOICES
        if name not in Filesystem.TYPES_REQUIRING_STORAGE
    ]

    def assertCanMountFilesystem(self, user, machine):
        handler = MachineHandler(user, {}, None)
        mount_point = factory.make_absolute_path()
        mount_options = factory.make_name("options")
        params = {
            "system_id": machine.system_id,
            "fstype": self.fstype,
            "mount_point": mount_point,
            "mount_options": mount_options,
        }
        self.assertIsNone(handler.mount_special(params))
        special_fss = list(machine.current_config.special_filesystems)
        self.assertEqual(len(special_fss), 1)
        fs = special_fss[0]
        self.assertEqual(fs.fstype, self.fstype)
        self.assertEqual(fs.mount_point, mount_point)
        self.assertEqual(fs.mount_options, mount_options)
        self.assertEqual(fs.node_config, machine.current_config)

    def test_user_mounts_non_storage_filesystem_on_allocated_machine(self):
        user = factory.make_User()
        self.assertCanMountFilesystem(
            user, factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=user)
        )

    def test_admin_mounts_non_storage_filesystem_on_allocated_machine(self):
        admin = factory.make_admin()
        self.assertCanMountFilesystem(
            admin, factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=admin)
        )

    def test_admin_mounts_non_storage_filesystem_on_ready_machine(self):
        admin = factory.make_admin()
        self.assertCanMountFilesystem(
            admin, factory.make_Node(status=NODE_STATUS.READY)
        )

    def test_admin_cannot_mount_on_non_ready_or_allocated_machine(self):
        admin = factory.make_admin()
        handler = MachineHandler(admin, {}, None)
        statuses = {name for name, _ in NODE_STATUS_CHOICES}
        statuses -= {NODE_STATUS.READY, NODE_STATUS.ALLOCATED}
        status_iter = iter(statuses)
        machine = factory.make_Node(status=next(status_iter))
        self.patch(
            MachineHandler, "_get_node_or_permission_error"
        ).return_value = machine
        err_msg_regex = re.escape(
            "Cannot mount the filesystem because the "
            "machine is not Allocated or Ready."
        )
        for status in status_iter:
            machine.status = status
            params = {
                "system_id": machine.system_id,
                "fstype": self.fstype,
                "mount_point": factory.make_absolute_path(),
                "mount_options": factory.make_name("options"),
            }
            with self.assertRaisesRegex(
                NodeStateViolation,
                err_msg_regex,
                msg=f"using status {status} on {self.fstype}",
            ):
                handler.mount_special(params)


class TestMachineHandlerUnmountSpecial(MAASServerTestCase):
    """Tests for MachineHandler.unmount_special."""

    def test_mount_point_is_required(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        machine = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=user)
        params = {"system_id": machine.system_id}
        error = self.assertRaises(
            HandlerValidationError, handler.unmount_special, params
        )
        self.assertEqual(
            {"mount_point": ["This field is required."]}, dict(error)
        )

    def test_mount_point_must_be_absolute(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        machine = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=user)
        params = {
            "system_id": machine.system_id,
            "fstype": FILESYSTEM_TYPE.RAMFS,
            "mount_point": factory.make_name("path"),
        }
        error = self.assertRaises(
            HandlerValidationError, handler.unmount_special, params
        )
        # XXX: Wow, what a lame error from AbsolutePathField!
        self.assertEqual(dict(error)["mount_point"], ["Enter a valid value."])


class TestMachineHandlerUnmountSpecialScenarios(MAASServerTestCase):
    """Scenario tests for MachineHandler.unmount_special."""

    scenarios = [
        (displayname, {"fstype": name})
        for name, displayname in FILESYSTEM_FORMAT_TYPE_CHOICES
        if name not in Filesystem.TYPES_REQUIRING_STORAGE
    ]

    def assertCanUnmountFilesystem(self, user, machine):
        handler = MachineHandler(user, {}, None)
        filesystem = factory.make_Filesystem(
            node_config=machine.current_config,
            fstype=self.fstype,
            mount_point=factory.make_absolute_path(),
        )
        params = {
            "system_id": machine.system_id,
            "mount_point": filesystem.mount_point,
        }
        self.assertIsNone(handler.unmount_special(params))
        self.assertFalse(machine.current_config.special_filesystems.exists())

    def test_user_unmounts_non_storage_filesystem_on_allocated_machine(self):
        user = factory.make_User()
        self.assertCanUnmountFilesystem(
            user, factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=user)
        )

    def test_admin_unmounts_non_storage_filesystem_on_allocated_machine(self):
        admin = factory.make_admin()
        self.assertCanUnmountFilesystem(
            admin, factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=admin)
        )

    def test_admin_unmounts_non_storage_filesystem_on_ready_machine(self):
        admin = factory.make_admin()
        self.assertCanUnmountFilesystem(
            admin, factory.make_Node(status=NODE_STATUS.READY)
        )

    def test_admin_cannot_unmount_on_non_ready_or_allocated_machine(self):
        admin = factory.make_admin()
        handler = MachineHandler(admin, {}, None)
        statuses = {name for name, _ in NODE_STATUS_CHOICES}
        statuses -= {NODE_STATUS.READY, NODE_STATUS.ALLOCATED}
        status_iter = iter(statuses)
        machine = factory.make_Node(status=next(status_iter))
        self.patch(
            MachineHandler, "_get_node_or_permission_error"
        ).return_value = machine
        err_msg_regex = re.escape(
            "Cannot unmount the filesystem because the machine is not Allocated or Ready."
        )
        for status in status_iter:
            machine.status = status
            filesystem = factory.make_Filesystem(
                node_config=machine.current_config,
                fstype=self.fstype,
                mount_point=factory.make_absolute_path(),
            )
            params = {
                "system_id": machine.system_id,
                "mount_point": filesystem.mount_point,
            }
            with self.assertRaisesRegex(
                NodeStateViolation,
                err_msg_regex,
                msg=f"using status {status} on {self.fstype}",
            ):
                handler.unmount_special(params)

    def test_locked_raises_permission_error(self):
        admin = factory.make_admin()
        node = factory.make_Node(locked=True, owner=admin)
        filesystem = factory.make_Filesystem(
            node_config=node.current_config,
            fstype=self.fstype,
            mount_point=factory.make_absolute_path(),
        )
        handler = MachineHandler(admin, {}, None)
        params = {
            "system_id": node.system_id,
            "mount_point": filesystem.mount_point,
        }
        self.assertRaises(
            HandlerPermissionError, handler.unmount_special, params
        )


class TestMachineHandlerUpdateFilesystem(MAASServerTestCase):
    def test_locked_raises_permission_error(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        node = factory.make_Node(locked=True)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        fs = factory.make_Filesystem(block_device=block_device)
        params = {
            "system_id": node.system_id,
            "block_id": block_device.id,
            "fstype": fs.fstype,
            "mount_point": None,
            "mount_options": None,
        }
        self.assertRaises(
            HandlerPermissionError, handler.update_filesystem, params
        )

    def test_unmount_blockdevice_filesystem(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED,
        )
        block_device = factory.make_PhysicalBlockDevice(node=node)
        fs = factory.make_Filesystem(block_device=block_device)
        handler.update_filesystem(
            {
                "system_id": node.system_id,
                "block_id": block_device.id,
                "fstype": fs.fstype,
                "mount_point": None,
                "mount_options": None,
            }
        )
        efs = block_device.get_effective_filesystem()
        self.assertIsNone(efs.mount_point)
        self.assertIsNone(efs.mount_options)

    def test_unmount_partition_filesystem(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED,
        )
        partition = factory.make_Partition(node=node)
        fs = factory.make_Filesystem(partition=partition)
        handler.update_filesystem(
            {
                "system_id": node.system_id,
                "block_id": partition.partition_table.block_device.id,
                "partition_id": partition.id,
                "fstype": fs.fstype,
                "mount_point": None,
                "mount_options": None,
            }
        )
        efs = partition.get_effective_filesystem()
        self.assertIsNone(efs.mount_point)
        self.assertIsNone(efs.mount_options)

    def test_mount_blockdevice_filesystem(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED,
        )
        block_device = factory.make_PhysicalBlockDevice(node=node)
        fs = factory.make_Filesystem(block_device=block_device)
        mount_point = factory.make_absolute_path()
        mount_options = factory.make_name("options")
        handler.update_filesystem(
            {
                "system_id": node.system_id,
                "block_id": block_device.id,
                "fstype": fs.fstype,
                "mount_point": mount_point,
                "mount_options": mount_options,
            }
        )
        efs = block_device.get_effective_filesystem()
        self.assertEqual(efs.mount_point, mount_point)
        self.assertEqual(efs.mount_options, mount_options)

    def test_mount_partition_filesystem(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED,
        )
        partition = factory.make_Partition(node=node)
        fs = factory.make_Filesystem(partition=partition)
        mount_point = factory.make_absolute_path()
        mount_options = factory.make_name("options")
        handler.update_filesystem(
            {
                "system_id": node.system_id,
                "block_id": partition.partition_table.block_device.id,
                "partition_id": partition.id,
                "fstype": fs.fstype,
                "mount_point": mount_point,
                "mount_options": mount_options,
            }
        )
        efs = partition.get_effective_filesystem()
        self.assertEqual(efs.mount_point, mount_point)
        self.assertEqual(efs.mount_options, mount_options)

    def test_change_blockdevice_filesystem(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED,
        )
        block_device = factory.make_PhysicalBlockDevice(node=node)
        fs = factory.make_Filesystem(block_device=block_device)
        new_fstype = factory.pick_filesystem_type(but_not={fs.fstype})
        handler.update_filesystem(
            {
                "system_id": node.system_id,
                "block_id": block_device.id,
                "fstype": new_fstype,
                "mount_point": None,
            }
        )
        self.assertEqual(
            new_fstype, block_device.get_effective_filesystem().fstype
        )

    def test_change_partition_filesystem(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED,
        )
        partition = factory.make_Partition(node=node)
        fs = factory.make_Filesystem(partition=partition)
        new_fstype = factory.pick_filesystem_type(but_not={fs.fstype})
        handler.update_filesystem(
            {
                "system_id": node.system_id,
                "block_id": partition.partition_table.block_device.id,
                "partition_id": partition.id,
                "fstype": new_fstype,
                "mount_point": None,
            }
        )
        self.assertEqual(
            new_fstype, partition.get_effective_filesystem().fstype
        )

    def test_new_blockdevice_filesystem(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED,
        )
        block_device = factory.make_PhysicalBlockDevice(node=node)
        fstype = factory.pick_filesystem_type()
        handler.update_filesystem(
            {
                "system_id": node.system_id,
                "block_id": block_device.id,
                "fstype": fstype,
                "mount_point": None,
            }
        )
        self.assertEqual(
            fstype, block_device.get_effective_filesystem().fstype
        )

    def test_new_partition_filesystem(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED,
        )
        partition = factory.make_Partition(node=node)
        fstype = factory.pick_filesystem_type()
        handler.update_filesystem(
            {
                "system_id": node.system_id,
                "block_id": partition.partition_table.block_device.id,
                "partition_id": partition.id,
                "fstype": fstype,
                "mount_point": None,
            }
        )
        self.assertEqual(fstype, partition.get_effective_filesystem().fstype)

    def test_delete_blockdevice_filesystem(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True, architecture=architecture, status=NODE_STATUS.READY
        )
        block_device = factory.make_PhysicalBlockDevice(node=node)
        factory.make_Filesystem(block_device=block_device)
        handler.update_filesystem(
            {
                "system_id": node.system_id,
                "block_id": block_device.id,
                "fstype": "",
                "mount_point": None,
            }
        )
        self.assertIsNone(block_device.get_effective_filesystem())

    def test_delete_partition_filesystem(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True, architecture=architecture, status=NODE_STATUS.READY
        )
        partition = factory.make_Partition(node=node)
        factory.make_Filesystem(partition=partition)
        handler.update_filesystem(
            {
                "system_id": node.system_id,
                "block_id": partition.partition_table.block_device.id,
                "partition_id": partition.id,
                "fstype": "",
                "mount_point": None,
            }
        )
        self.assertIsNone(partition.get_effective_filesystem())

    def test_sets_tags(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True, architecture=architecture, status=NODE_STATUS.READY
        )
        blockdevice = factory.make_BlockDevice(node=node, tags=None)
        tag1 = factory.make_name()
        tag2 = factory.make_name()
        handler.update_filesystem(
            {
                "system_id": node.system_id,
                "block_id": blockdevice.id,
                "tags": [{"text": tag1}, {"text": tag2}],
            }
        )
        blockdevice = reload_object(blockdevice)
        self.assertEqual(blockdevice.tags, [tag1, tag2])

    def test_skips_updating_tags_if_tags_match(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True, architecture=architecture, status=NODE_STATUS.READY
        )
        tag1 = factory.make_name()
        tag2 = factory.make_name()
        blockdevice = factory.make_BlockDevice(node=node, tags=[tag1, tag2])
        handler.update_filesystem(
            {
                "system_id": node.system_id,
                "block_id": blockdevice.id,
                "tags": [
                    # Just change the order. The tags are backed by an arary.
                    {"text": tag2},
                    {"text": tag1},
                ],
            }
        )
        blockdevice = reload_object(blockdevice)
        self.assertEqual(blockdevice.tags, [tag1, tag2])

    def test_skips_updating_tags_if_tags_missing_from_parameters(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True, architecture=architecture, status=NODE_STATUS.READY
        )
        tag1 = factory.make_name()
        tag2 = factory.make_name()
        blockdevice = factory.make_BlockDevice(node=node, tags=[tag1, tag2])
        handler.update_filesystem(
            {"system_id": node.system_id, "block_id": blockdevice.id}
        )
        blockdevice = reload_object(blockdevice)
        self.assertEqual(blockdevice.tags, [tag1, tag2])

    def test_skips_updating_tags_if_blockdevice_id_missing(self):
        user = factory.make_admin()
        handler = MachineHandler(user, {}, None)
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True, architecture=architecture, status=NODE_STATUS.READY
        )
        tag1 = factory.make_name()
        tag2 = factory.make_name()
        blockdevice = factory.make_BlockDevice(node=node, tags=[])
        handler.update_filesystem(
            {
                "system_id": node.system_id,
                "tags": [{"text": tag1}, {"text": tag2}],
            }
        )
        blockdevice = reload_object(blockdevice)
        self.assertEqual(blockdevice.tags, [])


class TestMachineHandlerSuppressScriptResult(MAASServerTestCase):
    def create_script_results(self, nodes, count=5):
        script_results = []
        for node in nodes:
            script = factory.make_Script()
            for _ in range(count):
                script_set = factory.make_ScriptSet(
                    result_type=script.script_type, node=node
                )
                factory.make_ScriptResult(script=script, script_set=script_set)

            script_set = factory.make_ScriptSet(
                result_type=script.script_type, node=node
            )
            script_result = factory.make_ScriptResult(
                script=script,
                script_set=script_set,
                status=random.choice(
                    list(SCRIPT_STATUS_FAILED.union({SCRIPT_STATUS.PASSED}))
                ),
            )
            if script.script_type == SCRIPT_TYPE.TESTING and (
                script_result.status in SCRIPT_STATUS_FAILED
            ):
                script_results.append(script_result)
        return script_results

    def test_set_script_result_suppressed(self):
        owner = factory.make_admin()
        node = factory.make_Node(owner=owner)
        handler = MachineHandler(owner, {}, None)
        hardware_type = factory.pick_choice(HARDWARE_TYPE_CHOICES)
        script_set = factory.make_ScriptSet(node=node)
        script = factory.make_Script(hardware_type=hardware_type)
        script_result = factory.make_ScriptResult(script_set, script=script)

        script_results = []
        for _ in range(3):
            script_results.append(
                factory.make_ScriptResult(script_set=script_set)
            )

        handler.set_script_result_suppressed(
            {
                "system_id": node.system_id,
                "script_result_ids": [
                    script_result.id for script_result in script_results
                ],
            }
        )
        script_result = reload_object(script_result)
        self.assertFalse(script_result.suppressed)
        for script_result in script_results:
            script_result = reload_object(script_result)
            self.assertTrue(script_result.suppressed)

    def test_set_script_result_suppressed_raises_permission_error(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = MachineHandler(owner, {}, None)
        script_set = factory.make_ScriptSet(node=node)
        script_results = []
        for _ in range(3):
            script_results.append(
                factory.make_ScriptResult(script_set=script_set)
            )
        params = {
            "system_id": node.system_id,
            "script_result_ids": [
                script_result.id for script_result in script_results
            ],
        }

        self.assertRaises(
            HandlerPermissionError,
            handler.set_script_result_suppressed,
            params,
        )

    def test_set_script_result_unsuppressed(self):
        owner = factory.make_admin()
        node = factory.make_Node(owner=owner)
        handler = MachineHandler(owner, {}, None)
        hardware_type = factory.pick_choice(HARDWARE_TYPE_CHOICES)
        script_set = factory.make_ScriptSet(node=node)
        script = factory.make_Script(hardware_type=hardware_type)
        script_result = factory.make_ScriptResult(
            script_set, script=script, suppressed=True
        )

        script_results = []
        for _ in range(3):
            script_results.append(
                factory.make_ScriptResult(script_set=script_set)
            )

        handler.set_script_result_unsuppressed(
            {
                "system_id": node.system_id,
                "script_result_ids": [
                    script_result.id for script_result in script_results
                ],
            }
        )
        script_result = reload_object(script_result)
        self.assertTrue(script_result.suppressed)
        for script_result in script_results:
            script_result = reload_object(script_result)
            self.assertFalse(script_result.suppressed)

    def test_set_script_result_unsuppressed_raises_permission_error(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = MachineHandler(owner, {}, None)
        script_set = factory.make_ScriptSet(node=node)
        script_results = []
        for _ in range(3):
            script_results.append(
                factory.make_ScriptResult(script_set=script_set)
            )
        params = {
            "system_id": node.system_id,
            "script_result_ids": [
                script_result.id for script_result in script_results
            ],
        }

        self.assertRaises(
            HandlerPermissionError,
            handler.set_script_result_unsuppressed,
            params,
        )

    def test_get_latest_failed_testing_script_results(self):
        owner = factory.make_User()
        handler = MachineHandler(owner, {}, None)
        node_result_handler = NodeResultHandler(owner, {}, None)
        nodes = [factory.make_Node(owner=owner) for _ in range(10)]

        script_results = self.create_script_results(nodes)

        requests = [
            {"system_ids": [node.system_id for node in nodes]},
            {"filter": {"owner": owner.username}},
        ]

        for request in requests:
            actual = handler.get_latest_failed_testing_script_results(request)
            expected = {}
            for script_result in script_results:
                if script_result.script_set.node.system_id not in expected:
                    expected[script_result.script_set.node.system_id] = []
                mapping = node_result_handler.dehydrate(
                    script_result, {}, for_list=True
                )
                mapping["id"] = script_result.id
                expected[script_result.script_set.node.system_id].append(
                    mapping
                )
            self.assertEqual(actual, expected)

    def test_get_latest_failed_testing_script_results_num_queries(self):
        # Prevent RBAC from making a query.
        self.useFixture(RBACForceOffFixture())
        owner = factory.make_User()
        handler = MachineHandler(owner, {}, None)
        nodes = []
        for idx in range(10):
            node = factory.make_Node(owner=owner)
            nodes.append(node)
            factory.make_ScriptResult(
                status=random.choice(list(SCRIPT_STATUS_FAILED)),
                script_set=factory.make_ScriptSet(
                    node=node, result_type=RESULT_TYPE.TESTING
                ),
            )

        queries_one, _ = count_queries(
            handler.get_latest_failed_testing_script_results,
            {"system_ids": [nodes[0].system_id]},
        )
        queries_total, _ = count_queries(
            handler.get_latest_failed_testing_script_results,
            {"system_ids": [node.system_id for node in nodes]},
        )
        # This check is to notify the developer that a change was made that
        # affects the number of queries performed when doing a node listing.
        # It is important to keep this number as low as possible. A larger
        # number means regiond has to do more work slowing down its process
        # and slowing down the client waiting for the response.
        self.assertEqual(
            queries_one,
            4,
            "Number of queries has changed; make sure this is expected.",
        )
        self.assertEqual(
            queries_total,
            4,
            "Number of queries has changed; make sure this is expected.",
        )


class TestMachineHandlerWorkloadAnnotations(MAASServerTestCase):
    def test_set_workload_annotations(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        handler = MachineHandler(user, {}, None)
        workload_annotations = {"data1": "value 1"}
        self.assertEqual(
            workload_annotations,
            handler.set_workload_annotations(
                {
                    "system_id": node.system_id,
                    "workload_annotations": workload_annotations,
                }
            ),
        )

    def test_set_workload_annotations_invalid_char(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        handler = MachineHandler(user, {}, None)
        workload_annotations = {"data 1": "value 1"}
        error = self.assertRaises(
            HandlerValidationError,
            handler.set_workload_annotations,
            {
                "system_id": node.system_id,
                "workload_annotations": workload_annotations,
            },
        )
        self.assertEqual(error.message, "Invalid character in key name")

    def test_set_workload_annotations_overwrite(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        handler = MachineHandler(user, {}, None)
        workload_annotations = {"data1": "value 1"}
        self.assertEqual(
            workload_annotations,
            handler.set_workload_annotations(
                {
                    "system_id": node.system_id,
                    "workload_annotations": workload_annotations,
                }
            ),
        )
        workload_annotations = {"data1": "value 2"}
        self.assertEqual(
            workload_annotations,
            handler.set_workload_annotations(
                {
                    "system_id": node.system_id,
                    "workload_annotations": workload_annotations,
                }
            ),
        )

    def test_set_workload_annotations_empty(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        handler = MachineHandler(user, {}, None)
        workload_annotations = {"data1": "value 1"}
        self.assertEqual(
            workload_annotations,
            handler.set_workload_annotations(
                {
                    "system_id": node.system_id,
                    "workload_annotations": workload_annotations,
                }
            ),
        )
        workload_annotations = {"data1": ""}
        self.assertEqual(
            {},
            handler.set_workload_annotations(
                {
                    "system_id": node.system_id,
                    "workload_annotations": workload_annotations,
                }
            ),
        )

    def test_get_workload_annotations(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        handler = MachineHandler(user, {}, None)
        workload_annotations = {"data1": "value 1"}
        self.assertEqual(
            workload_annotations,
            handler.set_workload_annotations(
                {
                    "system_id": node.system_id,
                    "workload_annotations": workload_annotations,
                }
            ),
        )
        self.assertEqual(
            workload_annotations,
            handler.get_workload_annotations(
                {
                    "system_id": node.system_id,
                }
            ),
        )


class TestMachineHandlerNewSchema(MAASServerTestCase):
    def test_filter_bulk_action(self):
        logger_twisted = self.useFixture(TwistedLoggerFixture())
        user = factory.make_admin()
        zone1 = factory.make_Zone()
        zone2 = factory.make_Zone()
        zone1_machines = [
            factory.make_Machine(status=NODE_STATUS.READY, zone=zone1)
            for _ in range(2)
        ]
        # You can't acquire a deployed machine, check it is reported as failed
        deployed_zone1_machine = factory.make_Machine(
            status=NODE_STATUS.DEPLOYED, zone=zone1
        )
        zone1_machines.append(deployed_zone1_machine)
        zone2_machines = [
            factory.make_Machine(status=NODE_STATUS.READY, zone=zone2)
            for _ in range(2)
        ]
        handler = MachineHandler(user, {}, None)
        params = {
            "action": "acquire",
            "extra": {},
            "filter": {"zone": zone1},
        }
        response = handler.action(params)
        self.assertEqual(
            response,
            {
                "success_count": 2,
                "failed_system_ids": [deployed_zone1_machine.system_id],
                "failure_details": {
                    "acquire action is not available for this node.": [
                        deployed_zone1_machine.system_id
                    ]
                },
            },
        )
        self.assertIn(
            f"Bulk action (acquire) for {deployed_zone1_machine.system_id} failed: acquire action is not available for this node",
            logger_twisted.output,
        )
        # Skip the deployed zone1 machine
        for machine in zone1_machines[:-1]:
            machine.refresh_from_db()
            self.assertEqual(machine.status, NODE_STATUS.ALLOCATED)
        for machine in zone2_machines:
            machine.refresh_from_db()
            self.assertEqual(machine.status, NODE_STATUS.READY)

    def test_filter_groups(self):
        self.maxDiff = None
        user = factory.make_User()
        handler = MachineHandler(user, {}, None)
        self.assertCountEqual(
            [
                {
                    "key": "arch",
                    "label": "Architecture",
                    "dynamic": False,
                    "type": "list[str]",
                    "for_grouping": True,
                },
                {
                    "key": "tags",
                    "label": "Tags",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "not_tags",
                    "label": "Not having tags",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "fabrics",
                    "label": "Attached to fabrics",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "not_fabrics",
                    "label": "Not attached to fabrics",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "fabric_classes",
                    "label": "Attached to fabric with specified classes",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "not_fabric_classes",
                    "label": "Not attached to fabric with specified classes",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "subnets",
                    "label": "Attached to subnets",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "not_subnets",
                    "label": "Not attached to subnets",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "link_speed",
                    "label": "Link speed",
                    "dynamic": True,
                    "type": "list[float]",
                    "for_grouping": False,
                },
                {
                    "key": "vlans",
                    "label": "Attached to VLANs",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "not_vlans",
                    "label": "Not attached to VLANs",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "zone",
                    "label": "Physical zone",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": True,
                },
                {
                    "key": "not_in_zone",
                    "label": "Not in zone",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "pool",
                    "label": "Resource pool",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": True,
                },
                {
                    "key": "not_in_pool",
                    "label": "Not in resource pool",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "deployment_target",
                    "label": "Deployment target",
                    "dynamic": False,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "not_deployment_target",
                    "label": "Deployment target",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "storage",
                    "label": "Storage",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "interfaces",
                    "label": "Interfaces",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "devices",
                    "label": "Devices",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "cpu_count",
                    "label": "CPU count",
                    "dynamic": True,
                    "type": "list[float]",
                    "for_grouping": False,
                },
                {
                    "key": "mem",
                    "label": "Memory",
                    "dynamic": True,
                    "type": "list[float]",
                    "for_grouping": False,
                },
                {
                    "key": "pod",
                    "label": "The name of the desired pod",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": True,
                },
                {
                    "key": "not_pod",
                    "label": "The name of the undesired pod",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "pod_type",
                    "label": "The power_type of the desired pod",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": True,
                },
                {
                    "key": "not_pod_type",
                    "label": "The power_type of the undesired pod",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "mac_address",
                    "label": "MAC addresses to filter on",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "domain",
                    "label": "Domain names to filter on",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": True,
                },
                {
                    "key": "agent_name",
                    "label": "Only include nodes with events matching the agent name",
                    "dynamic": True,
                    "type": "list[str]",
                    "for_grouping": False,
                },
                {
                    "key": "status",
                    "label": "Only includes nodes with the specified status",
                    "dynamic": False,
                    "type": "list[str]",
                    "for_grouping": True,
                },
                {
                    "key": "owner",
                    "label": "Owner",
                    "dynamic": True,
                    "for_grouping": True,
                    "type": "list[str]",
                },
                {
                    "key": "power_state",
                    "label": "Power State",
                    "dynamic": False,
                    "for_grouping": True,
                    "type": "list[str]",
                },
                {
                    "key": "not_arch",
                    "label": "Architecture",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "cpu_speed",
                    "label": "CPU speed",
                    "type": "list[float]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_owner",
                    "label": "Owner",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_power_state",
                    "label": "Power State",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_domain",
                    "label": "Domain names to ignore",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_agent_name",
                    "label": "Excludes nodes with events matching the agent name",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_status",
                    "label": "Exclude nodes with the specified status",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "osystem",
                    "label": "The OS of the desired node",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_osystem",
                    "label": "OS to ignore",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "distro_series",
                    "label": "The OS distribution of the desired node",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_distro_series",
                    "label": "OS distribution to ignore",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "ip_addresses",
                    "label": "Node's IP address",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_ip_addresses",
                    "label": "IP address to ignore",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "spaces",
                    "label": "Node's spaces",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "workloads",
                    "label": "Node's workload annotations",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_mac_address",
                    "label": "MAC addresses to filter on",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_spaces",
                    "label": "Node's spaces",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_workloads",
                    "label": "Node's workload annotations",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_link_speed",
                    "label": "Link speed",
                    "type": "list[float]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_cpu_count",
                    "label": "CPU count",
                    "type": "list[float]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_cpu_speed",
                    "label": "CPU speed",
                    "type": "list[float]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_mem",
                    "label": "Memory",
                    "type": "list[float]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "physical_disk_count",
                    "label": "Physical disk Count",
                    "type": "list[int]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_physical_disk_count",
                    "label": "Physical disk Count",
                    "type": "list[int]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "total_storage",
                    "label": "Total storage",
                    "type": "list[float]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_total_storage",
                    "label": "Total storage",
                    "type": "list[float]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "pxe_mac",
                    "label": "Boot interface MAC address",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_pxe_mac",
                    "label": "Boot interface MAC address",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "fabric_name",
                    "label": "Boot interface Fabric",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_fabric_name",
                    "label": "Boot interface Fabric",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "fqdn",
                    "label": "Node FQDN",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "not_fqdn",
                    "label": "Node FQDN",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "simple_status",
                    "label": "Only includes nodes with the specified simplified status",
                    "type": "list[str]",
                    "dynamic": False,
                    "for_grouping": False,
                },
                {
                    "key": "not_simple_status",
                    "label": "Exclude nodes with the specified simplified status",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": False,
                },
                {
                    "key": "parent",
                    "label": "Parent node",
                    "type": "list[str]",
                    "dynamic": True,
                    "for_grouping": True,
                },
            ],
            handler.filter_groups({}),
        )

    def test_filter_options(self):
        user = factory.make_User()
        handler = MachineHandler(user, {}, None)
        factory.make_RegionController()
        architectures = [
            "amd64/generic",
            "arm64/generic",
            "ppc64el/generic",
            "s390x/generic",
        ]
        [
            factory.make_usable_boot_resource(architecture=arch)
            for arch in architectures
        ]
        machines = [
            factory.make_Machine_with_Interface_on_Subnet(
                architecture=architectures[i % len(architectures)],
                owner=user,
                bmc=factory.make_Pod(pod_type=random.choice(["lxd", "virsh"])),
            )
            for i in range(5)
        ]
        for i in range(5):
            factory.make_Machine(
                architecture=architectures[i % len(architectures)],
                owner=user,
                parent=machines[i],
            )

        def _assert_value_in(value, field_name):
            self.assertIn(
                value,
                [
                    option["key"]
                    for option in handler.filter_options(
                        {"group_key": field_name}
                    )
                ],
                field_name,
            )

        def _assert_subset(subset, field_name):
            self.assertLessEqual(
                subset,
                {
                    option["key"]
                    for option in handler.filter_options(
                        {"group_key": field_name}
                    )
                },
                field_name,
            )

        for machine in machines:
            machine.tags.add(factory.make_Tag())

            _assert_value_in(machine.hostname, "parent")
            _assert_value_in(machine.architecture, "arch")
            _assert_value_in(machine.owner.username, "owner")
            _assert_value_in(machine.power_state, "power_state")
            _assert_value_in(machine.power_state, "not_power_state")
            _assert_subset(set(machine.tag_names()), "tags")
            _assert_subset(set(machine.tag_names()), "not_tags")
            _assert_subset(
                set(
                    iface.vlan.fabric.name
                    for iface in machine.current_config.interface_set.all()
                ),
                "fabrics",
            )
            _assert_subset(
                set(
                    iface.vlan.fabric.name
                    for iface in machine.current_config.interface_set.all()
                ),
                "not_fabrics",
            )
            _assert_subset(
                set(
                    iface.vlan.fabric.class_type
                    for iface in machine.current_config.interface_set.all()
                    if iface.vlan.fabric.class_type
                ),
                "fabric_classes",
            )
            _assert_subset(
                set(
                    iface.vlan.fabric.class_type
                    for iface in machine.current_config.interface_set.all()
                    if iface.vlan.fabric.class_type
                ),
                "not_fabric_classes",
            )
            _assert_subset(
                set(
                    link["subnet"].id
                    for iface in machine.current_config.interface_set.all()
                    for link in iface.get_links()
                ),
                "subnets",
            )
            _assert_subset(
                set(
                    link["subnet"].id
                    for iface in machine.current_config.interface_set.all()
                    for link in iface.get_links()
                ),
                "not_subnets",
            )
            _assert_subset(
                set(
                    iface.link_speed
                    for iface in machine.current_config.interface_set.all()
                ),
                "link_speed",
            )
            _assert_subset(
                set(
                    iface.vlan.name
                    for iface in machine.current_config.interface_set.all()
                ),
                "vlans",
            )
            _assert_subset(
                set(
                    iface.vlan.name
                    for iface in machine.current_config.interface_set.all()
                ),
                "not_vlans",
            )
            _assert_value_in(machine.zone.name, "zone")
            _assert_value_in(machine.zone.name, "not_in_zone")
            _assert_value_in(machine.pool.name, "pool")
            _assert_value_in(machine.pool.name, "not_in_pool")
            _assert_value_in(machine.cpu_count, "cpu_count")
            _assert_value_in(machine.memory, "mem")
            _assert_value_in(machine.hostname, "hostname")
            _assert_value_in(
                NODE_STATUS_SHORT_LABEL_CHOICES[machine.status][0], "status"
            )
            _assert_value_in(
                NODE_STATUS_SHORT_LABEL_CHOICES[machine.status][0],
                "not_status",
            )
            simple_status_rev_map = map_enum_reverse(SIMPLIFIED_NODE_STATUS)
            _assert_value_in(
                simple_status_rev_map[machine.simplified_status].lower(),
                "simple_status",
            )
            _assert_value_in(
                simple_status_rev_map[machine.simplified_status].lower(),
                "not_simple_status",
            )
            _assert_subset(
                set(
                    iface.mac_address
                    for iface in machine.current_config.interface_set.all()
                ),
                "mac_address",
            )
            _assert_value_in(machine.domain.name, "domain")
            _assert_value_in(machine.agent_name, "agent_name")
            if machine.bmc.power_type == "lxd":
                _assert_value_in(machine.bmc.power_type, "pod_type")
                _assert_value_in(machine.bmc.power_type, "not_pod_type")
                _assert_value_in(machine.bmc.name, "pod")
                _assert_value_in(machine.bmc.name, "not_pod")

    def test_filter_options_labels(self):
        user = factory.make_User()
        handler = MachineHandler(user, {}, None)
        result = handler.filter_options({"group_key": "status"})
        self.assertCountEqual(
            [v["label"] for v in result],
            [choice[1] for choice in NODE_STATUS_CHOICES],
        )

    def test_filter_options_simple_status(self):
        user = factory.make_User()
        handler = MachineHandler(user, {}, None)
        result = handler.filter_options({"group_key": "simple_status"})
        self.assertCountEqual(
            [v["label"] for v in result],
            [choice[1] for choice in SIMPLIFIED_NODE_STATUS_CHOICES],
        )

    def test_filter_options_interfaces_unique_values(self):
        user = factory.make_User()
        tags = [factory.make_name("tag") for _ in range(3)]
        nodes = [factory.make_Machine() for _ in range(3)]
        ifaces = [factory.make_Interface(tags=tags) for _ in range(3)]
        for node, iface in zip(nodes, ifaces):
            node.current_config.interface_set.add(iface)
        handler = MachineHandler(user, {}, None)
        result = handler.filter_options({"group_key": "interfaces"})
        self.assertEqual(len(result), len(ifaces) + len(tags) + 1)

    def test_filter_options_deployment_target(self):
        user = factory.make_User()
        handler = MachineHandler(user, {}, None)
        result = handler.filter_options({"group_key": "deployment_target"})
        key_values = list(map(lambda item: item["key"], result))
        assert len(key_values) == 2
        assert "memory" in key_values
        assert "disk" in key_values

    def test_unsubscribe_raises_validation_error_with_no_pk(self):
        admin = factory.make_admin()
        handler = MachineHandler(admin, {}, None)
        self.assertRaises(HandlerValidationError, handler.unsubscribe, {})

    def test_count_endpoint_no_filter(self):
        owner = factory.make_User()
        nodes = [factory.make_Node(owner=owner) for _ in range(3)]
        handler = MachineHandler(owner, {}, None)
        self.assertEqual(len(nodes), handler.count({})["count"])

    def test_count_endpoint_filter(self):
        owner = factory.make_User()
        zone = factory.make_Zone()
        nodes_without_zone = [factory.make_Node() for _ in range(2)]
        nodes_in_zone = [factory.make_Node(zone=zone) for _ in range(2)]
        handler = MachineHandler(owner, {}, None)
        self.assertEqual(
            len(nodes_without_zone) + len(nodes_in_zone),
            handler.count({})["count"],
        )
        self.assertEqual(
            len(nodes_in_zone),
            handler.count({"filter": {"zone": zone.name}})["count"],
        )

    def test_count_endpoint_filter_simple_status(self):
        owner = factory.make_User()
        statuses = [NODE_STATUS.ALLOCATED, NODE_STATUS.FAILED_COMMISSIONING]
        nodes = [
            factory.make_Machine(
                owner=owner,
                status=statuses[idx],
                hostname=f"node{idx}-{factory.make_string(10)}",
            )
            for idx in range(2)
        ]
        handler = MachineHandler(owner, {}, None)
        self.assertEqual(
            len(nodes),
            handler.count({})["count"],
        )
        self.assertEqual(
            1,
            handler.count({"filter": {"simple_status": "allocated"}})["count"],
        )
