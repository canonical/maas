# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.node`"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = []

import logging
from operator import itemgetter
import random
import re

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from lxml import etree
from maasserver.enum import (
    BOND_MODE,
    CACHE_MODE_TYPE,
    FILESYSTEM_FORMAT_TYPE_CHOICES,
    FILESYSTEM_FORMAT_TYPE_CHOICES_DICT,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
)
from maasserver.exceptions import NodeActionError
from maasserver.forms import AdminNodeWithMACAddressesForm
from maasserver.models import interface as interface_module
from maasserver.models.blockdevice import BlockDevice
from maasserver.models.cacheset import CacheSet
from maasserver.models.config import Config
from maasserver.models.filesystemgroup import (
    Bcache,
    RAID,
    VolumeGroup,
)
from maasserver.models.interface import Interface
from maasserver.models.node import Node
from maasserver.models.nodeprobeddetails import get_single_probed_details
from maasserver.models.partition import (
    Partition,
    PARTITION_ALIGNMENT_SIZE,
)
from maasserver.node_action import compile_node_actions
from maasserver.rpc.testing.fixtures import MockLiveRegionToClusterRPCFixture
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.third_party_drivers import get_third_party_driver
from maasserver.utils.converters import (
    human_readable_bytes,
    round_size_to_nearest_block,
    XMLToYAML,
)
from maasserver.utils.orm import (
    get_one,
    transactional,
)
from maasserver.utils.osystems import make_hwe_kernel_ui_text
from maasserver.utils.threads import deferToDatabase
from maasserver.websockets.base import (
    HandlerDoesNotExistError,
    HandlerError,
    HandlerPermissionError,
    HandlerValidationError,
)
from maasserver.websockets.handlers import node as node_module
from maasserver.websockets.handlers.event import dehydrate_event_type_level
from maasserver.websockets.handlers.node import (
    Node as node_model,
    NodeHandler,
)
from maasserver.websockets.handlers.timestampedmodel import dehydrate_datetime
from maastesting.djangotestcase import count_queries
from maastesting.matchers import MockCalledOnceWith
from maastesting.twisted import (
    always_fail_with,
    always_succeed_with,
)
from metadataserver.enum import RESULT_TYPE
from metadataserver.models.commissioningscript import (
    LIST_MODALIASES_OUTPUT_NAME,
    LLDP_OUTPUT_NAME,
)
from mock import (
    ANY,
    sentinel,
)
from netaddr import IPAddress
from provisioningserver.power.poweraction import PowerActionFail
from provisioningserver.rpc.cluster import PowerQuery
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.tags import merge_details_cleanly
from provisioningserver.utils.twisted import asynchronous
from testtools import ExpectedException
from testtools.matchers import Equals
from twisted.internet.defer import CancelledError


class TestNodeHandler(MAASServerTestCase):

    def dehydrate_node(
            self, node, handler, for_list=False, include_summary=False):
        boot_interface = node.get_boot_interface()
        pxe_mac_vendor = node.get_pxe_mac_vendor()
        blockdevices = [
            blockdevice.actual_instance
            for blockdevice in node.blockdevice_set.all()
            ]
        driver = get_third_party_driver(node)
        disks = [
            handler.dehydrate_blockdevice(blockdevice, node)
            for blockdevice in blockdevices
        ]
        disks = disks + [
            handler.dehydrate_volume_group(volume_group)
            for volume_group in VolumeGroup.objects.filter_by_node(node)
        ] + [
            handler.dehydrate_cache_set(cache_set)
            for cache_set in CacheSet.objects.get_cache_sets_for_node(node)
        ]
        disks = sorted(disks, key=itemgetter("name"))
        subnets = handler.get_all_subnets(node)
        data = {
            "actions": compile_node_actions(node, handler.user).keys(),
            "architecture": node.architecture,
            "boot_type": node.boot_type,
            "boot_disk": node.boot_disk,
            "bios_boot_method": node.bios_boot_method,
            "commissioning_results": handler.dehydrate_node_results(
                node, RESULT_TYPE.COMMISSIONING),
            "cpu_count": node.cpu_count,
            "created": dehydrate_datetime(node.created),
            "devices": sorted([
                {
                    "fqdn": device.fqdn,
                    "interfaces": [
                        handler.dehydrate_interface(interface, device)
                        for interface in device.interface_set.all().order_by(
                            'id')
                    ],
                }
                for device in node.children.all().order_by('id')
            ], key=itemgetter('fqdn')),
            "disable_ipv4": node.disable_ipv4,
            "physical_disk_count": node.physicalblockdevice_set.count(),
            "disks": disks,
            "supported_filesystems": [
                {'key': key, 'ui': ui}
                for key, ui in FILESYSTEM_FORMAT_TYPE_CHOICES],
            "distro_series": node.get_distro_series(),
            "error": node.error,
            "error_description": node.error_description,
            "events": handler.dehydrate_events(node),
            "extra_macs": [
                "%s" % mac_address
                for mac_address in node.get_extra_macs()
            ],
            "fqdn": node.fqdn,
            "hwe_kernel": make_hwe_kernel_ui_text(node.hwe_kernel),
            "hostname": node.hostname,
            "id": node.id,
            "installation_results": handler.dehydrate_node_results(
                node, RESULT_TYPE.INSTALLATION),
            "interfaces": [
                handler.dehydrate_interface(interface, node)
                for interface in node.interface_set.all().order_by('name')
            ],
            "on_network": node.on_network(),
            "license_key": node.license_key,
            "memory": node.display_memory(),
            "min_hwe_kernel": node.min_hwe_kernel,
            "nodegroup": handler.dehydrate_nodegroup(node.nodegroup),
            "osystem": node.get_osystem(),
            "owner": handler.dehydrate_owner(node.owner),
            "power_parameters": handler.dehydrate_power_parameters(
                node.power_parameters),
            "power_state": node.power_state,
            "power_type": node.power_type,
            "pxe_mac": (
                "" if boot_interface is None else
                "%s" % boot_interface.mac_address),
            "pxe_mac_vendor": "" if pxe_mac_vendor is None else pxe_mac_vendor,
            "routers": handler.dehydrate_routers(node.routers),
            "show_os_info": handler.dehydrate_show_os_info(node),
            "status": node.display_status(),
            "storage": "%3.1f" % (sum([
                blockdevice.size
                for blockdevice in node.physicalblockdevice_set.all()
            ]) / (1000 ** 3)),
            "storage_tags": handler.get_all_storage_tags(blockdevices),
            "subnets": [subnet.cidr for subnet in subnets],
            "fabrics": handler.get_all_fabric_names(node, subnets),
            "spaces": handler.get_all_space_names(subnets),
            "swap_size": node.swap_size,
            "system_id": node.system_id,
            "tags": [
                tag.name
                for tag in node.tags.all()
            ],
            "third_party_driver": {
                "module": driver["module"] if "module" in driver else "",
                "comment": driver["comment"] if "comment" in driver else "",
            },
            "updated": dehydrate_datetime(node.updated),
            "zone": handler.dehydrate_zone(node.zone),
        }
        if for_list:
            allowed_fields = NodeHandler.Meta.list_fields + [
                "actions",
                "fqdn",
                "status",
                "pxe_mac",
                "pxe_mac_vendor",
                "extra_macs",
                "tags",
                "subnets",
                "fabrics",
                "spaces",
                "physical_disk_count",
                "storage",
                "storage_tags",
            ]
            for key in data.keys():
                if key not in allowed_fields:
                    del data[key]
        if include_summary:
            data = handler.dehydrate_summary_output(node, data)
        return data

    def make_nodes(self, nodegroup, number):
        """Create `number` of new nodes."""
        for counter in range(number):
            node = factory.make_Node(
                nodegroup=nodegroup, interface=True, status=NODE_STATUS.READY)
            factory.make_PhysicalBlockDevice(node)
            # Make some devices.
            for _ in range(3):
                factory.make_Node(
                    installable=False, parent=node, interface=True)

    def test_dehydrate_owner_empty_when_None(self):
        owner = factory.make_User()
        handler = NodeHandler(owner, {})
        self.assertEquals("", handler.dehydrate_owner(None))

    def test_dehydrate_owner_username(self):
        owner = factory.make_User()
        handler = NodeHandler(owner, {})
        self.assertEquals(owner.username, handler.dehydrate_owner(owner))

    def test_dehydrate_zone(self):
        owner = factory.make_User()
        handler = NodeHandler(owner, {})
        zone = factory.make_Zone()
        self.assertEquals({
            "id": zone.id,
            "name": zone.name,
            }, handler.dehydrate_zone(zone))

    def test_dehydrate_nodegroup_returns_None_when_None(self):
        owner = factory.make_User()
        handler = NodeHandler(owner, {})
        self.assertIsNone(handler.dehydrate_nodegroup(None))

    def test_dehydrate_nodegroup(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = NodeHandler(owner, {})
        self.assertEquals({
            "id": node.nodegroup.id,
            "uuid": node.nodegroup.uuid,
            "name": node.nodegroup.name,
            "cluster_name": node.nodegroup.cluster_name,
            }, handler.dehydrate_nodegroup(node.nodegroup))

    def test_dehydrate_routers_returns_empty_list_when_None(self):
        owner = factory.make_User()
        handler = NodeHandler(owner, {})
        self.assertEquals([], handler.dehydrate_routers(None))

    def test_dehydrate_routers_returns_list_of_strings(self):
        owner = factory.make_User()
        handler = NodeHandler(owner, {})
        routers = [
            IPAddress(factory.make_ipv4_address())
            for _ in range(3)
        ]
        expected = [
            "%s" % router
            for router in routers
        ]
        self.assertEquals(expected, handler.dehydrate_routers(routers))

    def test_dehydrate_power_parameters_returns_None_when_empty(self):
        owner = factory.make_User()
        handler = NodeHandler(owner, {})
        self.assertIsNone(handler.dehydrate_power_parameters(''))

    def test_dehydrate_power_parameters_returns_params(self):
        owner = factory.make_User()
        handler = NodeHandler(owner, {})
        params = {
            factory.make_name("key"): factory.make_name("value")
            for _ in range(3)
        }
        self.assertEquals(params, handler.dehydrate_power_parameters(params))

    def test_dehydrate_show_os_info_returns_true(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner, status=NODE_STATUS.DEPLOYED)
        handler = NodeHandler(owner, {})
        self.assertTrue(handler.dehydrate_show_os_info(node))

    def test_dehydrate_show_os_info_returns_false(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner, status=NODE_STATUS.READY)
        handler = NodeHandler(owner, {})
        self.assertFalse(handler.dehydrate_show_os_info(node))

    def test_dehydrate_device(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = NodeHandler(owner, {})
        device = factory.make_Node(installable=False, parent=node)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device)
        self.assertEquals({
            "fqdn": device.fqdn,
            "interfaces": [handler.dehydrate_interface(interface, device)],
            }, handler.dehydrate_device(device))

    def test_dehydrate_block_device_with_PhysicalBlockDevice_with_ptable(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = NodeHandler(owner, {})
        blockdevice = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(block_device=blockdevice)
        is_boot = blockdevice.id == node.get_boot_disk().id
        self.assertEquals({
            "id": blockdevice.id,
            "is_boot": is_boot,
            "name": blockdevice.get_name(),
            "tags": blockdevice.tags,
            "type": blockdevice.type,
            "path": blockdevice.path,
            "size": blockdevice.size,
            "size_human": human_readable_bytes(blockdevice.size),
            "used_size": blockdevice.used_size,
            "used_size_human": human_readable_bytes(blockdevice.used_size),
            "available_size": blockdevice.available_size,
            "available_size_human": human_readable_bytes(
                blockdevice.available_size),
            "block_size": blockdevice.block_size,
            "model": blockdevice.model,
            "serial": blockdevice.serial,
            "partition_table_type": partition_table.table_type,
            "used_for": blockdevice.used_for,
            "filesystem": handler.dehydrate_filesystem(
                blockdevice.get_effective_filesystem()),
            "partitions": handler.dehydrate_partitions(
                blockdevice.get_partitiontable()),
            }, handler.dehydrate_blockdevice(blockdevice, node))

    def test_dehydrate_block_device_with_PhysicalBlockDevice_wo_ptable(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = NodeHandler(owner, {})
        blockdevice = factory.make_PhysicalBlockDevice(node=node)
        is_boot = blockdevice.id == node.get_boot_disk().id
        self.assertEquals({
            "id": blockdevice.id,
            "is_boot": is_boot,
            "name": blockdevice.get_name(),
            "tags": blockdevice.tags,
            "type": blockdevice.type,
            "path": blockdevice.path,
            "size": blockdevice.size,
            "size_human": human_readable_bytes(blockdevice.size),
            "used_size": blockdevice.used_size,
            "used_size_human": human_readable_bytes(blockdevice.used_size),
            "available_size": blockdevice.available_size,
            "available_size_human": human_readable_bytes(
                blockdevice.available_size),
            "block_size": blockdevice.block_size,
            "model": blockdevice.model,
            "serial": blockdevice.serial,
            "partition_table_type": "",
            "used_for": blockdevice.used_for,
            "filesystem": handler.dehydrate_filesystem(
                blockdevice.get_effective_filesystem()),
            "partitions": handler.dehydrate_partitions(
                blockdevice.get_partitiontable()),
            }, handler.dehydrate_blockdevice(blockdevice, node))

    def test_dehydrate_block_device_with_VirtualBlockDevice(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = NodeHandler(owner, {})
        blockdevice = factory.make_VirtualBlockDevice(node=node)
        self.assertEquals({
            "id": blockdevice.id,
            "is_boot": False,
            "name": blockdevice.get_name(),
            "tags": blockdevice.tags,
            "type": blockdevice.type,
            "path": blockdevice.path,
            "size": blockdevice.size,
            "size_human": human_readable_bytes(blockdevice.size),
            "used_size": blockdevice.used_size,
            "used_size_human": human_readable_bytes(blockdevice.used_size),
            "available_size": blockdevice.available_size,
            "available_size_human": human_readable_bytes(
                blockdevice.available_size),
            "block_size": blockdevice.block_size,
            "model": "",
            "serial": "",
            "partition_table_type": "",
            "used_for": blockdevice.used_for,
            "filesystem": handler.dehydrate_filesystem(
                blockdevice.get_effective_filesystem()),
            "partitions": handler.dehydrate_partitions(
                blockdevice.get_partitiontable()),
            "parent": {
                "id": blockdevice.filesystem_group.id,
                "type": blockdevice.filesystem_group.group_type,
                "uuid": blockdevice.filesystem_group.uuid,
                },
            }, handler.dehydrate_blockdevice(blockdevice, node))

    def test_dehydrate_volume_group(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = NodeHandler(owner, {})
        volume_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, node=node)
        self.assertEquals({
            "id": volume_group.id,
            "name": volume_group.name,
            "tags": [],
            "type": volume_group.group_type,
            "path": "",
            "size": volume_group.get_size(),
            "size_human": human_readable_bytes(volume_group.get_size()),
            "used_size": volume_group.get_lvm_allocated_size(),
            "used_size_human": human_readable_bytes(
                volume_group.get_lvm_allocated_size()),
            "available_size": volume_group.get_lvm_free_space(),
            "available_size_human": human_readable_bytes(
                volume_group.get_lvm_free_space()),
            "block_size": volume_group.get_virtual_block_device_block_size(),
            "model": "",
            "serial": "",
            "partition_table_type": "",
            "used_for": "volume group",
            "filesystem": None,
            "partitions": None,
            }, handler.dehydrate_volume_group(volume_group))

    def test_dehydrate_cache_set(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = NodeHandler(owner, {})
        cache_set = factory.make_CacheSet(node=node)
        backings = []
        for _ in range(3):
            backing = factory.make_PhysicalBlockDevice(node=node)
            fs = factory.make_Filesystem(
                block_device=backing, fstype=FILESYSTEM_TYPE.BCACHE_BACKING)
            backings.append(
                factory.make_FilesystemGroup(
                    group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
                    filesystems=[fs], cache_set=cache_set))
        self.assertEquals({
            "id": cache_set.id,
            "name": cache_set.name,
            "tags": [],
            "type": "cache-set",
            "path": "",
            "size": cache_set.get_device().size,
            "size_human": human_readable_bytes(
                cache_set.get_device().size),
            "used_size": cache_set.get_device().get_used_size(),
            "used_size_human": human_readable_bytes(
                cache_set.get_device().get_used_size()),
            "available_size": cache_set.get_device().get_available_size(),
            "available_size_human": human_readable_bytes(
                cache_set.get_device().get_available_size()),
            "block_size": cache_set.get_device().get_block_size(),
            "model": "",
            "serial": "",
            "partition_table_type": "",
            "used_for": ", ".join(sorted([
                backing_device.name
                for backing_device in backings
                ])),
            "filesystem": None,
            "partitions": None,
            }, handler.dehydrate_cache_set(cache_set))

    def test_dehydrate_partitions_returns_None(self):
        owner = factory.make_User()
        handler = NodeHandler(owner, {})
        self.assertIsNone(handler.dehydrate_partitions(None))

    def test_dehydrate_partitions_returns_list_of_partitions(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = NodeHandler(owner, {})
        blockdevice = factory.make_PhysicalBlockDevice(
            node=node, size=10 * 1024 ** 3, block_size=512)
        partition_table = factory.make_PartitionTable(block_device=blockdevice)
        partitions = [
            factory.make_Partition(
                partition_table=partition_table, size=1 * 1024 ** 3)
            for _ in range(3)
        ]
        expected = []
        for partition in partitions:
            expected.append({
                "filesystem": handler.dehydrate_filesystem(
                    partition.get_effective_filesystem()),
                "name": partition.get_name(),
                "path": partition.path,
                "type": partition.type,
                "id": partition.id,
                "size": partition.size,
                "size_human": human_readable_bytes(partition.size),
                "used_for": partition.used_for,
            })
        self.assertEquals(
            expected, handler.dehydrate_partitions(partition_table))

    def test_dehydrate_filesystem_returns_None(self):
        owner = factory.make_User()
        handler = NodeHandler(owner, {})
        self.assertIsNone(handler.dehydrate_filesystem(None))

    def test_dehydrate_filesystem(self):
        owner = factory.make_User()
        handler = NodeHandler(owner, {})
        filesystem = factory.make_Filesystem()
        self.assertEquals({
            "label": filesystem.label,
            "mount_point": filesystem.mount_point,
            "fstype": filesystem.fstype,
            "is_format_fstype": (
                filesystem.fstype in FILESYSTEM_FORMAT_TYPE_CHOICES_DICT),
            }, handler.dehydrate_filesystem(filesystem))

    def test_dehydrate_interface_for_ready_node(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner, status=NODE_STATUS.READY)
        handler = NodeHandler(owner, {})
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=factory.make_Subnet(), interface=interface)
        expected_links = interface.get_links()
        for link in expected_links:
            link["subnet_id"] = link.pop("subnet").id
        self.assertEquals({
            "id": interface.id,
            "type": interface.type,
            "name": interface.get_name(),
            "enabled": interface.is_enabled(),
            "is_boot": interface == node.boot_interface,
            "mac_address": "%s" % interface.mac_address,
            "vlan_id": interface.vlan_id,
            "parents": [
                nic.id
                for nic in interface.parents.all()
            ],
            "children": [
                nic.child.id
                for nic in interface.children_relationships.all()
            ],
            "links": expected_links,
            }, handler.dehydrate_interface(interface, node))

    def test_dehydrate_interface_for_commissioning_node(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner, status=NODE_STATUS.COMMISSIONING)
        handler = NodeHandler(owner, {})
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=factory.make_Subnet(), interface=interface)
        expected_links = interface.get_links()
        for link in expected_links:
            link["subnet_id"] = link.pop("subnet").id
        discovered_subnet = factory.make_Subnet()
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            ip=factory.pick_ip_in_network(discovered_subnet.get_ipnetwork()),
            subnet=discovered_subnet, interface=interface)
        expected_discovered = interface.get_discovered()
        for discovered in expected_discovered:
            discovered["subnet_id"] = discovered.pop("subnet").id
        self.assertEquals({
            "id": interface.id,
            "type": interface.type,
            "name": interface.get_name(),
            "enabled": interface.is_enabled(),
            "is_boot": interface == node.boot_interface,
            "mac_address": "%s" % interface.mac_address,
            "vlan_id": interface.vlan_id,
            "parents": [
                nic.id
                for nic in interface.parents.all()
            ],
            "children": [
                nic.child.id
                for nic in interface.children_relationships.all()
            ],
            "links": expected_links,
            "discovered": expected_discovered,
        }, handler.dehydrate_interface(interface, node))

    def test_dehydrate_summary_output_returns_None(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = NodeHandler(owner, {})
        observed = handler.dehydrate_summary_output(node, {})
        self.assertEquals({
            "summary_xml": None,
            "summary_yaml": None,
            }, observed)

    def test_dehydrate_summary_output_returns_data(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = NodeHandler(owner, {})
        lldp_data = "<foo>bar</foo>".encode("utf-8")
        factory.make_NodeResult_for_commissioning(
            node=node, name=LLDP_OUTPUT_NAME, script_result=0, data=lldp_data)
        observed = handler.dehydrate_summary_output(node, {})
        probed_details = merge_details_cleanly(
            get_single_probed_details(node.system_id))
        self.assertEquals({
            "summary_xml": etree.tostring(
                probed_details, encoding=unicode, pretty_print=True),
            "summary_yaml": XMLToYAML(
                etree.tostring(
                    probed_details, encoding=unicode,
                    pretty_print=True)).convert(),
            }, observed)

    def test_dehydrate_node_results(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = NodeHandler(owner, {})
        lldp_data = "<foo>bar</foo>".encode("utf-8")
        result = factory.make_NodeResult_for_commissioning(
            node=node, name=LLDP_OUTPUT_NAME, script_result=0, data=lldp_data)
        self.assertEquals([{
            "id": result.id,
            "result": result.script_result,
            "name": result.name,
            "data": result.data,
            "line_count": 1,
            "created": dehydrate_datetime(result.created),
            }],
            handler.dehydrate_node_results(node, RESULT_TYPE.COMMISSIONING))

    def test_dehydrate_events_only_includes_lastest_50(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = NodeHandler(owner, {})
        event_type = factory.make_EventType(level=logging.INFO)
        events = [
            factory.make_Event(node=node, type=event_type)
            for _ in range(100)
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
        self.assertEquals(expected, handler.dehydrate_events(node))

    def test_dehydrate_events_doesnt_include_debug(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        handler = NodeHandler(owner, {})
        event_type = factory.make_EventType(level=logging.DEBUG)
        for _ in range(5):
            factory.make_Event(node=node, type=event_type)
        self.assertEquals([], handler.dehydrate_events(node))

    def make_node_with_subnets(self):
        user = factory.make_User()
        handler = NodeHandler(user, {})
        space1 = factory.make_Space()
        fabric1 = factory.make_Fabric(name=factory.make_name("fabric"))
        vlan1 = factory.make_VLAN(fabric=fabric1)
        subnet1 = factory.make_Subnet(space=space1, vlan=vlan1)
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet1, vlan=vlan1)
        node.save()

        # Bond interface with a VLAN on top. With the bond set to STATIC
        # and the VLAN set to AUTO.
        fabric2 = factory.make_Fabric(name=factory.make_name("fabric"))
        vlan2 = factory.make_VLAN(fabric=fabric2)
        space2 = factory.make_Space()
        bond_subnet = factory.make_Subnet(space=space1, vlan=vlan1)
        vlan_subnet = factory.make_Subnet(space=space2, vlan=vlan2)
        nic1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan1)
        nic2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan2)
        bond = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[nic1, nic2], vlan=vlan1)
        vlan_int = factory.make_Interface(
            INTERFACE_TYPE.VLAN, vlan=vlan2, parents=[bond])
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(bond_subnet.get_ipnetwork()),
            subnet=bond_subnet, interface=bond)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip="",
            subnet=vlan_subnet, interface=vlan_int)

        # LINK_UP interface with no subnet.
        fabric3 = factory.make_Fabric(name=factory.make_name("fabric"))
        vlan3 = factory.make_VLAN(fabric=fabric3)
        nic3 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan3, node=node)
        nic3_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip="",
            subnet=None, interface=nic3)
        nic3_ip.subnet = None
        nic3_ip.save()

        self.patch_autospec(interface_module, "update_host_maps")
        boot_interface = node.get_boot_interface()
        boot_interface.claim_static_ips()
        node.boot_interface = boot_interface
        node.save()

        subnets = [subnet1, bond_subnet, vlan_subnet]
        fabrics = [fabric1, fabric2, fabric3]
        spaces = [space1, space2]
        return (handler, node, subnets, fabrics, spaces)

    def test_get_all_subnets(self):
        (handler, node, subnets, _, _) = self.make_node_with_subnets()
        self.assertItemsEqual(subnets, handler.get_all_subnets(node))

    def test_get_all_fabric_names(self):
        (handler, node, _, fabrics, _) = self.make_node_with_subnets()
        fabric_names = [fabric.name for fabric in fabrics]
        node_subnets = handler.get_all_subnets(node)
        self.assertItemsEqual(
            fabric_names, handler.get_all_fabric_names(node, node_subnets))

    def test_get_all_space_names(self):
        (handler, node, _, _, spaces) = self.make_node_with_subnets()
        space_names = [space.name for space in spaces]
        node_subnets = handler.get_all_subnets(node)
        self.assertItemsEqual(
            space_names, handler.get_all_space_names(node_subnets))

    def test_get(self):
        user = factory.make_User()
        handler = NodeHandler(user, {})
        node = factory.make_Node_with_Interface_on_Subnet()
        factory.make_FilesystemGroup(node=node)
        node.owner = user
        node.save()
        for _ in range(100):
            factory.make_Event(node=node)
        lldp_data = "<foo>bar</foo>".encode("utf-8")
        factory.make_NodeResult_for_commissioning(
            node=node, name=LLDP_OUTPUT_NAME, script_result=0, data=lldp_data)
        factory.make_PhysicalBlockDevice(node)

        Config.objects.set_config(
            name='enable_third_party_drivers', value=True)
        data = "pci:v00001590d00000047sv00001590sd00000047bc*sc*i*"
        factory.make_NodeResult_for_commissioning(
            node=node, name=LIST_MODALIASES_OUTPUT_NAME, script_result=0,
            data=data.encode("utf-8"))

        # Bond interface with a VLAN on top. With the bond set to STATIC
        # and the VLAN set to AUTO.
        bond_subnet = factory.make_Subnet()
        vlan_subnet = factory.make_Subnet()
        nic1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        nic2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        bond = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[nic1, nic2])
        vlan = factory.make_Interface(INTERFACE_TYPE.VLAN, parents=[bond])
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(bond_subnet.get_ipnetwork()),
            subnet=bond_subnet, interface=bond)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip="",
            subnet=vlan_subnet, interface=vlan)

        # LINK_UP interface with no subnet.
        nic3 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        nic3_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip="",
            subnet=None, interface=nic3)
        nic3_ip.subnet = None
        nic3_ip.save()

        # Make some devices.
        for _ in range(3):
            factory.make_Node(
                installable=False, parent=node, interface=True)

        self.patch_autospec(interface_module, "update_host_maps")
        boot_interface = node.get_boot_interface()
        boot_interface.claim_static_ips()
        node.boot_interface = boot_interface
        node.save()

        self.assertEquals(
            self.dehydrate_node(node, handler, include_summary=True),
            handler.get({"system_id": node.system_id}))

    def test_list(self):
        user = factory.make_User()
        handler = NodeHandler(user, {})
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=user)
        factory.make_PhysicalBlockDevice(node)
        self.assertItemsEqual(
            [self.dehydrate_node(node, handler, for_list=True)],
            handler.list({}))

    def test_list_ignores_devices(self):
        owner = factory.make_User()
        handler = NodeHandler(owner, {})
        # Create a device.
        factory.make_Node(owner=owner, installable=False)
        node = factory.make_Node(owner=owner)
        self.assertItemsEqual(
            [self.dehydrate_node(node, handler, for_list=True)],
            handler.list({}))

    def test_list_num_queries_is_independent_of_num_nodes(self):
        user = factory.make_User()
        user_ssh_prefetch = User.objects.filter(
            id=user.id).prefetch_related('sshkey_set').first()
        handler = NodeHandler(user_ssh_prefetch, {})
        nodegroup = factory.make_NodeGroup()
        self.make_nodes(nodegroup, 10)
        query_10_count, _ = count_queries(handler.list, {})
        self.make_nodes(nodegroup, 10)
        query_20_count, _ = count_queries(handler.list, {})

        # This check is to notify the developer that a change was made that
        # affects the number of queries performed when doing a node listing.
        # It is important to keep this number as low as possible. A larger
        # number means regiond has to do more work slowing down its process
        # and slowing down the client waiting for the response.
        self.assertEquals(
            query_10_count, 11,
            "Number of queries has changed; make sure this is expected.")
        self.assertEquals(
            query_10_count, query_20_count,
            "Number of queries is not independent to the number of nodes.")

    def test_list_returns_nodes_only_viewable_by_user(self):
        user = factory.make_User()
        other_user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.READY)
        ownered_node = factory.make_Node(
            owner=user, status=NODE_STATUS.ALLOCATED)
        factory.make_Node(
            owner=other_user, status=NODE_STATUS.ALLOCATED)
        handler = NodeHandler(user, {})
        self.assertItemsEqual([
            self.dehydrate_node(node, handler, for_list=True),
            self.dehydrate_node(ownered_node, handler, for_list=True),
        ], handler.list({}))

    def test_get_object_returns_node_if_super_user(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = NodeHandler(user, {})
        self.assertEquals(
            node, handler.get_object({"system_id": node.system_id}))

    def test_get_object_returns_node_if_owner(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        handler = NodeHandler(user, {})
        self.assertEquals(
            node, handler.get_object({"system_id": node.system_id}))

    def test_get_object_returns_node_if_owner_empty(self):
        user = factory.make_User()
        node = factory.make_Node()
        handler = NodeHandler(user, {})
        self.assertEquals(
            node, handler.get_object({"system_id": node.system_id}))

    def test_get_object_raises_error_if_owner_by_another_user(self):
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        handler = NodeHandler(user, {})
        self.assertRaises(
            HandlerDoesNotExistError,
            handler.get_object, {"system_id": node.system_id})

    def test_get_form_class_for_create(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        self.assertEquals(
            AdminNodeWithMACAddressesForm,
            handler.get_form_class("create"))

    def test_get_form_class_for_update(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        self.assertEquals(
            AdminNodeWithMACAddressesForm,
            handler.get_form_class("update"))

    def test_get_form_class_raises_error_for_unknown_action(self):
        user = factory.make_User()
        handler = NodeHandler(user, {})
        self.assertRaises(
            HandlerError,
            handler.get_form_class, factory.make_name())

    def test_create_raise_permissions_error_for_non_admin(self):
        user = factory.make_User()
        handler = NodeHandler(user, {})
        self.assertRaises(
            HandlerPermissionError,
            handler.create, {})

    def test_create_raises_validation_error_for_missing_pxe_mac(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        nodegroup = factory.make_NodeGroup()
        zone = factory.make_Zone()
        params = {
            "architecture": make_usable_architecture(self),
            "zone": {
                "name": zone.name,
            },
            "nodegroup": {
                "uuid": nodegroup.uuid,
            },
        }
        with ExpectedException(
                HandlerValidationError,
                re.escape("{u'mac_addresses': [u'This field is required.']}")):
            handler.create(params)

    def test_create_raises_validation_error_for_missing_architecture(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        nodegroup = factory.make_NodeGroup()
        zone = factory.make_Zone()
        params = {
            "pxe_mac": factory.make_mac_address(),
            "zone": {
                "name": zone.name,
            },
            "nodegroup": {
                "uuid": nodegroup.uuid,
            },
        }
        with ExpectedException(
                HandlerValidationError,
                re.escape(
                    "{u'architecture': [u'Architecture must be "
                    "defined for installable nodes.']}")):
            handler.create(params)

    def test_create_creates_node(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        nodegroup = factory.make_NodeGroup()
        zone = factory.make_Zone()
        mac = factory.make_mac_address()
        hostname = factory.make_name("hostname")
        architecture = make_usable_architecture(self)

        self.patch(node_model, "start_commissioning")

        created_node = handler.create({
            "hostname": hostname,
            "pxe_mac": mac,
            "architecture": architecture,
            "zone": {
                "name": zone.name,
            },
            "nodegroup": {
                "uuid": nodegroup.uuid,
            },
            "power_type": "ether_wake",
            "power_parameters": {
                "mac_address": mac,
            },
        })
        self.expectThat(created_node["hostname"], Equals(hostname))
        self.expectThat(created_node["pxe_mac"], Equals(mac))
        self.expectThat(created_node["extra_macs"], Equals([]))
        self.expectThat(created_node["architecture"], Equals(architecture))
        self.expectThat(created_node["zone"]["id"], Equals(zone.id))
        self.expectThat(created_node["nodegroup"]["id"], Equals(nodegroup.id))
        self.expectThat(created_node["power_type"], Equals("ether_wake"))
        self.expectThat(created_node["power_parameters"], Equals({
            "mac_address": mac,
        }))

    def test_create_starts_auto_commissioning(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        nodegroup = factory.make_NodeGroup()
        zone = factory.make_Zone()
        mac = factory.make_mac_address()
        hostname = factory.make_name("hostname")
        architecture = make_usable_architecture(self)

        mock_start_commissioning = self.patch(node_model,
                                              "start_commissioning")

        handler.create({
            "hostname": hostname,
            "pxe_mac": mac,
            "architecture": architecture,
            "zone": {
                "name": zone.name,
            },
            "nodegroup": {
                "uuid": nodegroup.uuid,
            },
            "power_type": "ether_wake",
            "power_parameters": {
                "mac_address": mac,
            },
        })
        self.assertThat(mock_start_commissioning, MockCalledOnceWith(user))

    def test_update_raise_permissions_error_for_non_admin(self):
        user = factory.make_User()
        handler = NodeHandler(user, {})
        self.assertRaises(
            HandlerPermissionError,
            handler.update, {})

    def test_update_raises_validation_error_for_invalid_architecture(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        node = factory.make_Node(interface=True)
        node_data = self.dehydrate_node(node, handler)
        arch = factory.make_name("arch")
        node_data["architecture"] = arch
        with ExpectedException(
                HandlerValidationError,
                re.escape(
                    "{u'architecture': [u\"'%s' is not a valid architecture.  "
                    "It should be one of: ''.\"]}" % arch)):
            handler.update(node_data)

    def test_update_updates_node(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        node = factory.make_Node(interface=True)
        node_data = self.dehydrate_node(node, handler)
        new_nodegroup = factory.make_NodeGroup()
        new_zone = factory.make_Zone()
        new_hostname = factory.make_name("hostname")
        new_architecture = make_usable_architecture(self)
        node_data["hostname"] = new_hostname
        node_data["architecture"] = new_architecture
        node_data["zone"] = {
            "name": new_zone.name,
        }
        node_data["nodegroup"] = {
            "uuid": new_nodegroup.uuid,
        }
        node_data["power_type"] = "ether_wake"
        power_mac = factory.make_mac_address()
        node_data["power_parameters"] = {
            "mac_address": power_mac,
        }
        updated_node = handler.update(node_data)
        self.expectThat(updated_node["hostname"], Equals(new_hostname))
        self.expectThat(updated_node["architecture"], Equals(new_architecture))
        self.expectThat(updated_node["zone"]["id"], Equals(new_zone.id))
        self.expectThat(
            updated_node["nodegroup"]["id"], Equals(new_nodegroup.id))
        self.expectThat(updated_node["power_type"], Equals("ether_wake"))
        self.expectThat(updated_node["power_parameters"], Equals({
            "mac_address": power_mac,
        }))

    def test_update_adds_tags_to_node(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        tags = [
            factory.make_Tag(definition='').name
            for _ in range(3)
            ]
        node_data = self.dehydrate_node(node, handler)
        node_data["tags"] = tags
        updated_node = handler.update(node_data)
        self.assertItemsEqual(tags, updated_node["tags"])

    def test_update_removes_tag_from_node(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        tags = []
        for _ in range(3):
            tag = factory.make_Tag(definition='')
            tag.node_set.add(node)
            tag.save()
            tags.append(tag.name)
        node_data = self.dehydrate_node(node, handler)
        removed_tag = tags.pop()
        node_data["tags"].remove(removed_tag)
        updated_node = handler.update(node_data)
        self.assertItemsEqual(tags, updated_node["tags"])

    def test_update_creates_tag_for_node(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        tag_name = factory.make_name("tag")
        node_data = self.dehydrate_node(node, handler)
        node_data["tags"].append(tag_name)
        updated_node = handler.update(node_data)
        self.assertItemsEqual([tag_name], updated_node["tags"])

    def test_unmount_blockdevice_filesystem(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        fs = factory.make_Filesystem(block_device=block_device)
        handler.update_filesystem({
            'system_id': node.system_id,
            'block_id': block_device.id,
            'fstype': fs.fstype,
            'mount_point': None
            })
        self.assertEquals(
            None, block_device.get_effective_filesystem().mount_point)

    def test_unmount_partition_filesystem(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED)
        partition = factory.make_Partition(node=node)
        fs = factory.make_Filesystem(partition=partition)
        handler.update_filesystem({
            'system_id': node.system_id,
            'block_id': partition.partition_table.block_device.id,
            'partition_id': partition.id,
            'fstype': fs.fstype,
            'mount_point': None
            })
        self.assertEquals(
            None, partition.get_effective_filesystem().mount_point)

    def test_mount_blockdevice_filesystem(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        fs = factory.make_Filesystem(block_device=block_device)
        handler.update_filesystem({
            'system_id': node.system_id,
            'block_id': block_device.id,
            'fstype': fs.fstype,
            'mount_point': '/mnt'
            })
        self.assertEquals(
            '/mnt', block_device.get_effective_filesystem().mount_point)

    def test_mount_partition_filesystem(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED)
        partition = factory.make_Partition(node=node)
        fs = factory.make_Filesystem(partition=partition)
        handler.update_filesystem({
            'system_id': node.system_id,
            'block_id': partition.partition_table.block_device.id,
            'partition_id': partition.id,
            'fstype': fs.fstype,
            'mount_point': '/mnt'
            })
        self.assertEquals(
            '/mnt', partition.get_effective_filesystem().mount_point)

    def test_change_blockdevice_filesystem(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        fs = factory.make_Filesystem(block_device=block_device)
        new_fstype = factory.pick_choice(
            FILESYSTEM_FORMAT_TYPE_CHOICES,
            (fs.fstype))
        handler.update_filesystem({
            'system_id': node.system_id,
            'block_id': block_device.id,
            'fstype': new_fstype,
            'mount_point': None
            })
        self.assertEquals(
            new_fstype, block_device.get_effective_filesystem().fstype)

    def test_change_partition_filesystem(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED)
        partition = factory.make_Partition(node=node)
        fs = factory.make_Filesystem(partition=partition)
        new_fstype = factory.pick_choice(
            FILESYSTEM_FORMAT_TYPE_CHOICES,
            (fs.fstype))
        handler.update_filesystem({
            'system_id': node.system_id,
            'block_id': partition.partition_table.block_device.id,
            'partition_id': partition.id,
            'fstype': new_fstype,
            'mount_point': None
            })
        self.assertEquals(
            new_fstype, partition.get_effective_filesystem().fstype)

    def test_new_blockdevice_filesystem(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        fstype = factory.pick_choice(FILESYSTEM_FORMAT_TYPE_CHOICES)
        handler.update_filesystem({
            'system_id': node.system_id,
            'block_id': block_device.id,
            'fstype': fstype,
            'mount_point': None
            })
        self.assertEquals(
            fstype, block_device.get_effective_filesystem().fstype)

    def test_new_partition_filesystem(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED)
        partition = factory.make_Partition(node=node)
        fstype = factory.pick_choice(FILESYSTEM_FORMAT_TYPE_CHOICES)
        handler.update_filesystem({
            'system_id': node.system_id,
            'block_id': partition.partition_table.block_device.id,
            'partition_id': partition.id,
            'fstype': fstype,
            'mount_point': None
            })
        self.assertEquals(
            fstype, partition.get_effective_filesystem().fstype)

    def test_delete_blockdevice_filesystem(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.READY)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        factory.make_Filesystem(block_device=block_device)
        handler.update_filesystem({
            'system_id': node.system_id,
            'block_id': block_device.id,
            'fstype': '',
            'mount_point': None
            })
        self.assertEquals(
            None, block_device.get_effective_filesystem())

    def test_delete_partition_filesystem(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.READY)
        partition = factory.make_Partition(node=node)
        factory.make_Filesystem(partition=partition)
        handler.update_filesystem({
            'system_id': node.system_id,
            'block_id': partition.partition_table.block_device.id,
            'partition_id': partition.id,
            'fstype': '',
            'mount_point': None
            })
        self.assertEquals(
            None, partition.get_effective_filesystem())

    def test_update_disk_for_physical_block_device(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        new_name = factory.make_name("new")
        handler.update_disk({
            'system_id': node.system_id,
            'block_id': block_device.id,
            'name': new_name,
            })
        self.assertEquals(new_name, reload_object(block_device).name)

    def test_update_disk_for_virtual_block_device(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED)
        block_device = factory.make_VirtualBlockDevice(node=node)
        new_name = factory.make_name("new")
        handler.update_disk({
            'system_id': node.system_id,
            'block_id': block_device.id,
            'name': new_name,
            })
        self.assertEquals(new_name, reload_object(block_device).name)

    def test_delete_disk(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        handler.delete_disk({
            'system_id': node.system_id,
            'block_id': block_device.id,
            })
        self.assertIsNone(reload_object(block_device))

    def test_delete_partition(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED)
        partition = factory.make_Partition(node=node)
        handler.delete_partition({
            'system_id': node.system_id,
            'partition_id': partition.id,
            })
        self.assertIsNone(reload_object(partition))

    def test_delete_volume_group(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED)
        volume_group = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.LVM_VG)
        handler.delete_volume_group({
            'system_id': node.system_id,
            'volume_group_id': volume_group.id,
            })
        self.assertIsNone(reload_object(volume_group))

    def test_delete_cache_set(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED)
        cache_set = factory.make_CacheSet(node=node)
        handler.delete_cache_set({
            'system_id': node.system_id,
            'cache_set_id': cache_set.id,
            })
        self.assertIsNone(reload_object(cache_set))

    def test_create_partition(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED)
        partition_table = factory.make_PartitionTable(node=node)
        size = partition_table.block_device.size / 2
        handler.create_partition({
            'system_id': node.system_id,
            'block_id': partition_table.block_device_id,
            'partition_size': size
            })
        self.assertEquals(
            1, Partition.objects.count())
        self.assertEquals(
            human_readable_bytes(
                round_size_to_nearest_block(
                    size, PARTITION_ALIGNMENT_SIZE, False)),
            human_readable_bytes(Partition.objects.first().size))

    def test_create_partition_with_filesystem(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(
            interface=True,
            architecture=architecture,
            status=NODE_STATUS.ALLOCATED)
        partition_table = factory.make_PartitionTable(node=node)
        size = partition_table.block_device.size / 2
        fstype = factory.pick_choice(FILESYSTEM_FORMAT_TYPE_CHOICES)
        mount_point = factory.make_absolute_path()
        handler.create_partition({
            'system_id': node.system_id,
            'block_id': partition_table.block_device_id,
            'partition_size': size,
            'fstype': fstype,
            'mount_point': mount_point,
            })
        self.assertEquals(
            1, Partition.objects.count())
        self.assertEquals(
            human_readable_bytes(
                round_size_to_nearest_block(
                    size, PARTITION_ALIGNMENT_SIZE, False)),
            human_readable_bytes(Partition.objects.first().size))
        self.assertEquals(
            fstype,
            Partition.objects.first().get_effective_filesystem().fstype)
        self.assertEquals(
            mount_point,
            Partition.objects.first().get_effective_filesystem().mount_point)

    def test_create_cache_set_for_partition(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        partition = factory.make_Partition(node=node)
        handler.create_cache_set({
            'system_id': node.system_id,
            'partition_id': partition.id
            })
        cache_set = CacheSet.objects.get_cache_sets_for_node(node).first()
        self.assertIsNotNone(cache_set)
        self.assertEquals(partition, cache_set.get_filesystem().partition)

    def test_create_cache_set_for_block_device(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        handler.create_cache_set({
            'system_id': node.system_id,
            'block_id': block_device.id
            })
        cache_set = CacheSet.objects.get_cache_sets_for_node(node).first()
        self.assertIsNotNone(cache_set)
        self.assertEquals(
            block_device.id, cache_set.get_filesystem().block_device.id)

    def test_create_bcache_for_partition(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        partition = factory.make_Partition(node=node)
        name = factory.make_name("bcache")
        cache_set = factory.make_CacheSet(node=node)
        cache_mode = factory.pick_enum(CACHE_MODE_TYPE)
        handler.create_bcache({
            'system_id': node.system_id,
            'partition_id': partition.id,
            'block_id': partition.partition_table.block_device.id,
            'name': name,
            'cache_set': cache_set.id,
            'cache_mode': cache_mode,
            })
        bcache = Bcache.objects.filter_by_node(node).first()
        self.assertIsNotNone(bcache)
        self.assertEquals(name, bcache.name)
        self.assertEquals(cache_set, bcache.cache_set)
        self.assertEquals(cache_mode, bcache.cache_mode)
        self.assertEquals(
            partition, bcache.get_bcache_backing_filesystem().partition)

    def test_create_bcache_for_partition_with_filesystem(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        partition = factory.make_Partition(node=node)
        name = factory.make_name("bcache")
        cache_set = factory.make_CacheSet(node=node)
        cache_mode = factory.pick_enum(CACHE_MODE_TYPE)
        fstype = factory.pick_choice(FILESYSTEM_FORMAT_TYPE_CHOICES)
        mount_point = factory.make_absolute_path()
        handler.create_bcache({
            'system_id': node.system_id,
            'partition_id': partition.id,
            'block_id': partition.partition_table.block_device.id,
            'name': name,
            'cache_set': cache_set.id,
            'cache_mode': cache_mode,
            'fstype': fstype,
            'mount_point': mount_point,
            })
        bcache = Bcache.objects.filter_by_node(node).first()
        self.assertIsNotNone(bcache)
        self.assertEquals(name, bcache.name)
        self.assertEquals(cache_set, bcache.cache_set)
        self.assertEquals(cache_mode, bcache.cache_mode)
        self.assertEquals(
            partition, bcache.get_bcache_backing_filesystem().partition)
        self.assertEquals(
            fstype,
            bcache.virtual_device.get_effective_filesystem().fstype)
        self.assertEquals(
            mount_point,
            bcache.virtual_device.get_effective_filesystem().mount_point)

    def test_create_bcache_for_block_device(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        name = factory.make_name("bcache")
        cache_set = factory.make_CacheSet(node=node)
        cache_mode = factory.pick_enum(CACHE_MODE_TYPE)
        handler.create_bcache({
            'system_id': node.system_id,
            'block_id': block_device.id,
            'name': name,
            'cache_set': cache_set.id,
            'cache_mode': cache_mode,
            })
        bcache = Bcache.objects.filter_by_node(node).first()
        self.assertIsNotNone(bcache)
        self.assertEquals(name, bcache.name)
        self.assertEquals(cache_set, bcache.cache_set)
        self.assertEquals(cache_mode, bcache.cache_mode)
        self.assertEquals(
            block_device.id,
            bcache.get_bcache_backing_filesystem().block_device.id)

    def test_create_bcache_for_block_device_with_filesystem(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        name = factory.make_name("bcache")
        cache_set = factory.make_CacheSet(node=node)
        cache_mode = factory.pick_enum(CACHE_MODE_TYPE)
        fstype = factory.pick_choice(FILESYSTEM_FORMAT_TYPE_CHOICES)
        mount_point = factory.make_absolute_path()
        handler.create_bcache({
            'system_id': node.system_id,
            'block_id': block_device.id,
            'name': name,
            'cache_set': cache_set.id,
            'cache_mode': cache_mode,
            'fstype': fstype,
            'mount_point': mount_point,
            })
        bcache = Bcache.objects.filter_by_node(node).first()
        self.assertIsNotNone(bcache)
        self.assertEquals(name, bcache.name)
        self.assertEquals(cache_set, bcache.cache_set)
        self.assertEquals(cache_mode, bcache.cache_mode)
        self.assertEquals(
            block_device.id,
            bcache.get_bcache_backing_filesystem().block_device.id)
        self.assertEquals(
            fstype,
            bcache.virtual_device.get_effective_filesystem().fstype)
        self.assertEquals(
            mount_point,
            bcache.virtual_device.get_effective_filesystem().mount_point)

    def test_create_raid(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        disk0 = factory.make_PhysicalBlockDevice(node=node)
        disk1 = factory.make_PhysicalBlockDevice(node=node)
        disk2 = factory.make_PhysicalBlockDevice(node=node)
        spare_disk = factory.make_PhysicalBlockDevice(node=node)
        name = factory.make_name("md")
        handler.create_raid({
            'system_id': node.system_id,
            'name': name,
            'level': 'raid-5',
            'block_devices': [disk0.id, disk1.id, disk2.id],
            'spare_devices': [spare_disk.id],
            })
        raid = RAID.objects.filter_by_node(node).first()
        self.assertIsNotNone(raid)
        self.assertEquals(name, raid.name)
        self.assertEquals("raid-5", raid.group_type)

    def test_create_raid_with_filesystem(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        disk0 = factory.make_PhysicalBlockDevice(node=node)
        disk1 = factory.make_PhysicalBlockDevice(node=node)
        disk2 = factory.make_PhysicalBlockDevice(node=node)
        spare_disk = factory.make_PhysicalBlockDevice(node=node)
        name = factory.make_name("md")
        fstype = factory.pick_choice(FILESYSTEM_FORMAT_TYPE_CHOICES)
        mount_point = factory.make_absolute_path()
        handler.create_raid({
            'system_id': node.system_id,
            'name': name,
            'level': 'raid-5',
            'block_devices': [disk0.id, disk1.id, disk2.id],
            'spare_devices': [spare_disk.id],
            'fstype': fstype,
            'mount_point': mount_point,
            })
        raid = RAID.objects.filter_by_node(node).first()
        self.assertIsNotNone(raid)
        self.assertEquals(name, raid.name)
        self.assertEquals("raid-5", raid.group_type)
        self.assertEquals(
            fstype,
            raid.virtual_device.get_effective_filesystem().fstype)
        self.assertEquals(
            mount_point,
            raid.virtual_device.get_effective_filesystem().mount_point)

    def test_create_volume_group(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        disk = factory.make_PhysicalBlockDevice(node=node)
        partition = factory.make_Partition(node=node)
        name = factory.make_name("vg")
        handler.create_volume_group({
            'system_id': node.system_id,
            'name': name,
            'block_devices': [disk.id],
            'partitions': [partition.id],
            })
        volume_group = VolumeGroup.objects.filter_by_node(node).first()
        self.assertIsNotNone(volume_group)
        self.assertEquals(name, volume_group.name)

    def test_create_logical_volume(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        volume_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, node=node)
        name = factory.make_name("lv")
        size = volume_group.get_lvm_free_space()
        handler.create_logical_volume({
            'system_id': node.system_id,
            'name': name,
            'volume_group_id': volume_group.id,
            'size': size,
            })
        logical_volume = volume_group.virtual_devices.first()
        self.assertIsNotNone(logical_volume)
        self.assertEquals(
            "%s-%s" % (volume_group.name, name), logical_volume.get_name())
        self.assertEquals(size, logical_volume.size)

    def test_create_logical_volume_with_filesystem(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        volume_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, node=node)
        name = factory.make_name("lv")
        size = volume_group.get_lvm_free_space()
        fstype = factory.pick_choice(FILESYSTEM_FORMAT_TYPE_CHOICES)
        mount_point = factory.make_absolute_path()
        handler.create_logical_volume({
            'system_id': node.system_id,
            'name': name,
            'volume_group_id': volume_group.id,
            'size': size,
            'fstype': fstype,
            'mount_point': mount_point,
            })
        logical_volume = volume_group.virtual_devices.first()
        self.assertIsNotNone(logical_volume)
        self.assertEquals(
            "%s-%s" % (volume_group.name, name), logical_volume.get_name())
        self.assertEquals(size, logical_volume.size)
        self.assertEquals(
            fstype,
            logical_volume.get_effective_filesystem().fstype)
        self.assertEquals(
            mount_point,
            logical_volume.get_effective_filesystem().mount_point)

    def test_set_boot_disk(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        boot_disk = factory.make_PhysicalBlockDevice(node=node)
        handler.set_boot_disk({
            'system_id': node.system_id,
            'block_id': boot_disk.id,
            })
        self.assertEquals(boot_disk.id, reload_object(node).get_boot_disk().id)

    def test_set_boot_disk_raises_error_for_none_physical(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        boot_disk = factory.make_VirtualBlockDevice(node=node)
        error = self.assertRaises(HandlerError, handler.set_boot_disk, {
            'system_id': node.system_id,
            'block_id': boot_disk.id,
            })
        self.assertEquals(
            error.message, "Only a physical disk can be set as the boot disk.")

    def test_update_raise_HandlerError_if_tag_has_definition(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        tag = factory.make_Tag()
        node_data = self.dehydrate_node(node, handler)
        node_data["tags"].append(tag.name)
        self.assertRaises(HandlerError, handler.update, node_data)

    def test_update_tags_on_block_device(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        tags = [
            factory.make_name("tag")
            for _ in range(3)
            ]
        handler.update_disk_tags({
            'system_id': node.system_id,
            'block_id': block_device.id,
            'tags': tags
            })
        # Refresh the block_device to check that the values were updated
        block_device = BlockDevice.objects.get(id=block_device.id)
        self.assertItemsEqual(
            tags, block_device.tags)

    def test_missing_action_raises_error(self):
        user = factory.make_User()
        node = factory.make_Node()
        handler = NodeHandler(user, {})
        self.assertRaises(
            NodeActionError,
            handler.action, {"system_id": node.system_id})

    def test_invalid_action_raises_error(self):
        user = factory.make_User()
        node = factory.make_Node()
        handler = NodeHandler(user, {})
        self.assertRaises(
            NodeActionError,
            handler.action, {"system_id": node.system_id, "action": "unknown"})

    def test_not_available_action_raises_error(self):
        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, owner=user)
        handler = NodeHandler(user, {})
        self.assertRaises(
            NodeActionError,
            handler.action, {"system_id": node.system_id, "action": "unknown"})

    def test_action_performs_action(self):
        admin = factory.make_admin()
        factory.make_SSHKey(admin)
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=admin)
        handler = NodeHandler(admin, {})
        handler.action({"system_id": node.system_id, "action": "delete"})
        self.assertIsNone(reload_object(node))

    def test_action_performs_action_passing_extra(self):
        user = factory.make_User()
        factory.make_SSHKey(user)
        self.patch(Node, 'on_network').return_value = True
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=user)
        osystem = make_usable_osystem(self)
        handler = NodeHandler(user, {})
        handler.action({
            "system_id": node.system_id,
            "action": "deploy",
            "extra": {
                "osystem": osystem["name"],
                "distro_series": osystem["releases"][0]["name"],
            }})
        node = reload_object(node)
        self.expectThat(node.osystem, Equals(osystem["name"]))
        self.expectThat(
            node.distro_series, Equals(osystem["releases"][0]["name"]))

    def test_create_physical_creates_interface(self):
        user = factory.make_admin()
        node = factory.make_Node(interface=False)
        handler = NodeHandler(user, {})
        name = factory.make_name("eth")
        mac_address = factory.make_mac_address()
        vlan = factory.make_VLAN()
        handler.create_physical({
            "system_id": node.system_id,
            "name": name,
            "mac_address": mac_address,
            "vlan": vlan.id,
            })
        self.assertEquals(
            1, node.interface_set.count(),
            "Should have one interface on the node.")

    def test_create_physical_creates_link_auto(self):
        user = factory.make_admin()
        node = factory.make_Node(interface=False)
        handler = NodeHandler(user, {})
        name = factory.make_name("eth")
        mac_address = factory.make_mac_address()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        handler.create_physical({
            "system_id": node.system_id,
            "name": name,
            "mac_address": mac_address,
            "vlan": vlan.id,
            "mode": INTERFACE_LINK_TYPE.AUTO,
            "subnet": subnet.id,
            })
        new_interface = node.interface_set.first()
        self.assertIsNotNone(new_interface)
        auto_ip = new_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO, subnet=subnet)
        self.assertIsNotNone(auto_ip)

    def test_create_physical_creates_link_up(self):
        user = factory.make_admin()
        node = factory.make_Node(interface=False)
        handler = NodeHandler(user, {})
        name = factory.make_name("eth")
        mac_address = factory.make_mac_address()
        vlan = factory.make_VLAN()
        handler.create_physical({
            "system_id": node.system_id,
            "name": name,
            "mac_address": mac_address,
            "vlan": vlan.id,
            "mode": INTERFACE_LINK_TYPE.LINK_UP,
            })
        new_interface = node.interface_set.first()
        self.assertIsNotNone(new_interface)
        link_up_ip = new_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=None)
        self.assertIsNotNone(link_up_ip)

    def test_create_physical_creates_link_up_with_subnet(self):
        user = factory.make_admin()
        node = factory.make_Node(interface=False)
        handler = NodeHandler(user, {})
        name = factory.make_name("eth")
        mac_address = factory.make_mac_address()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        handler.create_physical({
            "system_id": node.system_id,
            "name": name,
            "mac_address": mac_address,
            "vlan": vlan.id,
            "mode": INTERFACE_LINK_TYPE.LINK_UP,
            "subnet": subnet.id,
            })
        new_interface = node.interface_set.first()
        self.assertIsNotNone(new_interface)
        link_up_ip = new_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=None, subnet=subnet)
        self.assertIsNotNone(link_up_ip)

    def test_create_vlan_creates_vlan(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = NodeHandler(user, {})
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        new_vlan = factory.make_VLAN()
        handler.create_vlan({
            "system_id": node.system_id,
            "parent": interface.id,
            "vlan": new_vlan.id,
            })
        vlan_interface = get_one(
            Interface.objects.filter(
                node=node, type=INTERFACE_TYPE.VLAN, parents=interface))
        self.assertIsNotNone(vlan_interface)

    def test_create_vlan_creates_link_auto(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = NodeHandler(user, {})
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        new_vlan = factory.make_VLAN()
        new_subnet = factory.make_Subnet(vlan=new_vlan)
        handler.create_vlan({
            "system_id": node.system_id,
            "parent": interface.id,
            "vlan": new_vlan.id,
            "mode": INTERFACE_LINK_TYPE.AUTO,
            "subnet": new_subnet.id,
            })
        vlan_interface = get_one(
            Interface.objects.filter(
                node=node, type=INTERFACE_TYPE.VLAN, parents=interface))
        self.assertIsNotNone(vlan_interface)
        auto_ip = vlan_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO, subnet=new_subnet)
        self.assertIsNotNone(auto_ip)

    def test_create_vlan_creates_link_up(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = NodeHandler(user, {})
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        new_vlan = factory.make_VLAN()
        handler.create_vlan({
            "system_id": node.system_id,
            "parent": interface.id,
            "vlan": new_vlan.id,
            "mode": INTERFACE_LINK_TYPE.LINK_UP,
            })
        vlan_interface = get_one(
            Interface.objects.filter(
                node=node, type=INTERFACE_TYPE.VLAN, parents=interface))
        self.assertIsNotNone(vlan_interface)
        link_up_ip = vlan_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=None)
        self.assertIsNotNone(link_up_ip)

    def test_create_vlan_creates_link_up_with_subnet(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = NodeHandler(user, {})
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        new_vlan = factory.make_VLAN()
        new_subnet = factory.make_Subnet(vlan=new_vlan)
        handler.create_vlan({
            "system_id": node.system_id,
            "parent": interface.id,
            "vlan": new_vlan.id,
            "mode": INTERFACE_LINK_TYPE.LINK_UP,
            "subnet": new_subnet.id,
            })
        vlan_interface = get_one(
            Interface.objects.filter(
                node=node, type=INTERFACE_TYPE.VLAN, parents=interface))
        self.assertIsNotNone(vlan_interface)
        link_up_ip = vlan_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=None, subnet=new_subnet)
        self.assertIsNotNone(link_up_ip)

    def test_create_bond_creates_bond(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = NodeHandler(user, {})
        nic1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        nic2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=nic1.vlan)
        bond_mode = factory.pick_enum(BOND_MODE)
        name = factory.make_name("bond")
        handler.create_bond({
            "system_id": node.system_id,
            "name": name,
            "parents": [nic1.id, nic2.id],
            "mac_address": "%s" % nic1.mac_address,
            "vlan": nic1.vlan.id,
            "bond_mode": bond_mode
            })
        bond_interface = get_one(
            Interface.objects.filter(
                node=node, type=INTERFACE_TYPE.BOND, parents=nic1,
                name=name, vlan=nic1.vlan))
        self.assertIsNotNone(bond_interface)
        self.assertEquals(bond_mode, bond_interface.params["bond_mode"])

    def test_create_bond_raises_ValidationError(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = NodeHandler(user, {})
        nic1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        nic2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=nic1.vlan)
        with ExpectedException(ValidationError):
            handler.create_bond({
                "system_id": node.system_id,
                "parents": [nic1.id, nic2.id],
                })

    def test_update_interface(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = NodeHandler(user, {})
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        new_name = factory.make_name("name")
        new_vlan = factory.make_VLAN()
        handler.update_interface({
            "system_id": node.system_id,
            "interface_id": interface.id,
            "name": new_name,
            "vlan": new_vlan.id,
            })
        interface = reload_object(interface)
        self.assertEquals(new_name, interface.name)
        self.assertEquals(new_vlan, interface.vlan)

    def test_update_interface_raises_ValidationError(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = NodeHandler(user, {})
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        new_name = factory.make_name("name")
        with ExpectedException(ValidationError):
            handler.update_interface({
                "system_id": node.system_id,
                "interface_id": interface.id,
                "name": new_name,
                "vlan": random.randint(1000, 5000),
                })

    def test_delete_interface(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = NodeHandler(user, {})
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        handler.delete_interface({
            "system_id": node.system_id,
            "interface_id": interface.id,
            })
        self.assertIsNone(reload_object(interface))

    def test_link_subnet_calls_update_link_by_id_if_link_id(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = NodeHandler(user, {})
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        subnet = factory.make_Subnet()
        link_id = random.randint(0, 100)
        mode = factory.pick_enum(INTERFACE_LINK_TYPE)
        ip_address = factory.make_ip_address()
        self.patch_autospec(Interface, "update_link_by_id")
        handler.link_subnet({
            "system_id": node.system_id,
            "interface_id": interface.id,
            "link_id": link_id,
            "subnet": subnet.id,
            "mode": mode,
            "ip_address": ip_address,
            })
        self.assertThat(
            Interface.update_link_by_id,
            MockCalledOnceWith(
                ANY, link_id, mode, subnet, ip_address=ip_address))

    def test_link_subnet_calls_link_subnet_if_not_link_id(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = NodeHandler(user, {})
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        subnet = factory.make_Subnet()
        mode = factory.pick_enum(INTERFACE_LINK_TYPE)
        ip_address = factory.make_ip_address()
        self.patch_autospec(Interface, "link_subnet")
        handler.link_subnet({
            "system_id": node.system_id,
            "interface_id": interface.id,
            "subnet": subnet.id,
            "mode": mode,
            "ip_address": ip_address,
            })
        self.assertThat(
            Interface.link_subnet,
            MockCalledOnceWith(
                ANY, mode, subnet, ip_address=ip_address))

    def test_unlink_subnet(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = NodeHandler(user, {})
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        link_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="", interface=interface)
        handler.delete_interface({
            "system_id": node.system_id,
            "interface_id": interface.id,
            "link_id": link_ip.id,
            })
        self.assertIsNone(reload_object(link_ip))


class TestNodeHandlerCheckPower(MAASTransactionServerTestCase):

    @asynchronous
    def make_node(self, power_type="ipmi"):
        """Makes a node that is committed in the database."""
        return deferToDatabase(
            transactional(factory.make_Node), power_type=power_type)

    def make_handler_with_user(self):
        user = factory.make_User()
        return NodeHandler(user, {})

    def call_check_power(self, node):
        params = {"system_id": node.system_id}
        handler = self.make_handler_with_user()
        return handler.check_power(params).wait()

    def prepare_rpc(self, nodegroup, side_effect=None):
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        self.rpc_fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = self.rpc_fixture.makeCluster(nodegroup, PowerQuery)
        if side_effect is None:
            protocol.PowerQuery.side_effect = always_succeed_with({})
        else:
            protocol.PowerQuery.side_effect = side_effect

    def assertCheckPower(self, node, state):
        result_state = self.call_check_power(node)
        self.expectThat(result_state, Equals(state))
        self.expectThat(reload_object(node).power_state, Equals(state))

    def test__raises_HandlerError_when_NoConnectionsAvailable(self):
        node = self.make_node().wait()
        user = factory.make_User()
        handler = NodeHandler(user, {})
        mock_getClientFor = self.patch(node_module, "getClientFor")
        mock_getClientFor.side_effect = NoConnectionsAvailable()
        with ExpectedException(HandlerError):
            handler.check_power({"system_id": node.system_id}).wait()

    def test__sets_power_state_to_unknown_when_no_power_type(self):
        node = self.make_node(power_type="").wait()
        self.prepare_rpc(
            node.nodegroup,
            side_effect=always_succeed_with({"state": "on"}))
        self.assertCheckPower(node, "unknown")

    def test__sets_power_state_to_unknown_when_power_cannot_be_started(self):
        node = self.make_node(power_type="ether_wake").wait()
        self.prepare_rpc(
            node.nodegroup,
            side_effect=always_succeed_with({"state": "on"}))
        self.assertCheckPower(node, "unknown")

    def test__sets_power_state_to_PowerQuery_result(self):
        node = self.make_node().wait()
        power_state = random.choice(["on", "off"])
        self.prepare_rpc(
            node.nodegroup,
            side_effect=always_succeed_with({"state": power_state}))
        self.assertCheckPower(node, power_state)

    def test__sets_power_state_to_error_on_time_out(self):
        node = self.make_node().wait()
        getClientFor = self.patch(node_module, 'getClientFor')
        getClientFor.return_value = sentinel.client
        deferWithTimeout = self.patch(node_module, 'deferWithTimeout')
        deferWithTimeout.side_effect = always_fail_with(CancelledError())
        self.assertCheckPower(node, "error")

    def test__sets_power_state_to_unknown_on_NotImplementedError(self):
        node = self.make_node().wait()
        self.prepare_rpc(node.nodegroup, side_effect=NotImplementedError())
        self.assertCheckPower(node, "unknown")

    def test__sets_power_state_to_error_on_PowerActionFail(self):
        node = self.make_node().wait()
        self.prepare_rpc(node.nodegroup, side_effect=PowerActionFail())
        self.assertCheckPower(node, "error")
