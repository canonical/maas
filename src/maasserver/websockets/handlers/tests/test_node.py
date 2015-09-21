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
from lxml import etree
from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
)
from maasserver.exceptions import NodeActionError
from maasserver.forms import AdminNodeWithMACAddressesForm
from maasserver.models import interface as interface_module
from maasserver.models.config import Config
from maasserver.models.event import Event
from maasserver.models.nodeprobeddetails import get_single_probed_details
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
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
from maasserver.utils.converters import XMLToYAML
from maasserver.utils.orm import transactional
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
from metadataserver.models import NodeResult
from metadataserver.models.commissioningscript import (
    LIST_MODALIASES_OUTPUT_NAME,
    LLDP_OUTPUT_NAME,
)
from mock import sentinel
from provisioningserver.power.poweraction import PowerActionFail
from provisioningserver.rpc.cluster import PowerQuery
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.tags import merge_details_cleanly
from provisioningserver.utils.twisted import asynchronous
from testtools import ExpectedException
from testtools.matchers import Equals
from twisted.internet.defer import CancelledError
from twisted.internet.threads import deferToThread


class TestNodeHandler(MAASServerTestCase):

    def dehydrate_blockdevice(self, blockdevice):
        # model and serial are currently only avalible on physical block
        # devices
        if isinstance(blockdevice, PhysicalBlockDevice):
            model = blockdevice.model
            serial = blockdevice.serial
        else:
            serial = model = ""
        partition_table = blockdevice.get_partitiontable()
        if partition_table is not None:
            partition_table_type = partition_table.table_type
        else:
            partition_table_type = ""
        return {
            "id": blockdevice.id,
            "name": blockdevice.name,
            "tags": blockdevice.tags,
            "type": blockdevice.type,
            "path": blockdevice.path,
            "size": blockdevice.size,
            "size_gb": "%3.1f" % (blockdevice.size / (1000 ** 3)),
            "block_size": blockdevice.block_size,
            "model": model,
            "serial": serial,
            "partition_table_type": partition_table_type,
            "filesystem": self.dehydrate_filesystem(
                blockdevice.filesystem),
            "partitions": self.dehydrate_partitions(
                blockdevice.get_partitiontable()),
        }

    def dehydrate_partitions(self, partition_table):
        if partition_table is None:
            return None
        return [
            {
                "filesystem": self.dehydrate_filesystem(
                    partition.filesystem),
                "path": partition.path,
                "type": partition.type,
                "id": partition.id,
                "size": partition.size,
                "size_gb": "%3.1f" % (partition.size / (1000 ** 3)),
            }
            for partition in partition_table.partitions.all()
        ]

    def dehydrate_filesystem(self, filesystem):
        if filesystem is None:
            return None
        return {
            "label": filesystem.label,
            "mount_point": filesystem.mount_point,
            "fstype": filesystem.fstype,
            }

    def dehydrate_event(self, event):
        return {
            "id": event.id,
            "type": {
                "id": event.type.id,
                "name": event.type.name,
                "description": event.type.description,
                "level": dehydrate_event_type_level(event.type.level),
            },
            "description": event.description,
            "created": dehydrate_datetime(event.created),
        }

    def dehydrate_node_result(self, result):
        return {
            "id": result.id,
            "result": result.script_result,
            "name": result.name,
            "data": result.data,
            "line_count": len(result.data.splitlines()),
            "created": dehydrate_datetime(result.created),
        }

    def dehydrate_interface(self, interface, node):
        ip_addresses = []
        subnets = set()
        for ip_address in interface.ip_addresses.all():
            if ip_address.subnet is not None:
                subnets.add(ip_address.subnet)
            if ip_address.ip:
                if ip_address.alloc_type != IPADDRESS_TYPE.DISCOVERED:
                    ip_addresses.append({
                        "type": "static",
                        "alloc_type": ip_address.alloc_type,
                        "ip_address": "%s" % ip_address.ip,
                    })
                else:
                    ip_addresses.append({
                        "type": "dynamic",
                        "ip_address": "%s" % ip_address.ip,
                    })
        networks = [
            {
                "id": subnet.id,
                "name": subnet.name,
                "cidr": "%s" % subnet.get_ipnetwork(),
                "vlan": subnet.vlan.vid,
            }
            for subnet in subnets
        ]
        return {
            "id": interface.id,
            "is_pxe": interface == node.boot_interface,
            "mac_address": "%s" % interface.mac_address,
            "ip_addresses": ip_addresses,
            "networks": networks,
        }

    def dehydrate_interfaces(self, node):
        return sorted([
            self.dehydrate_interface(mac_address, node)
            for mac_address in node.interface_set.all().order_by('id')
        ], key=itemgetter('is_pxe'), reverse=True)

    def get_all_storage_tags(self, blockdevices):
        tags = set()
        for blockdevice in blockdevices:
            tags = tags.union(blockdevice.tags)
        return list(tags)

    def dehydrate_node(
            self, node, user, for_list=False, include_summary=False):
        boot_interface = node.get_boot_interface()
        pxe_mac_vendor = node.get_pxe_mac_vendor()
        blockdevices = [
            blockdevice.actual_instance
            for blockdevice in node.blockdevice_set.all()
            ]
        physical_blockdevices = [
            blockdevice for blockdevice in blockdevices
            if isinstance(blockdevice, PhysicalBlockDevice)
            ]
        power_parameters = (
            None if node.power_parameters == "" else node.power_parameters)
        events = (
            Event.objects.filter(node=node)
            .exclude(type__level=logging.DEBUG)
            .select_related("type")
            .order_by('-id')[:50])
        driver = get_third_party_driver(node)
        data = {
            "actions": compile_node_actions(node, user).keys(),
            "architecture": node.architecture,
            "boot_type": node.boot_type,
            "boot_disk": node.boot_disk,
            "bios_boot_method": node.bios_boot_method,
            "commissioning_results": [
                self.dehydrate_node_result(result)
                for result in NodeResult.objects.filter(
                    node=node, result_type=RESULT_TYPE.COMMISSIONING)
            ],
            "cpu_count": node.cpu_count,
            "created": dehydrate_datetime(node.created),
            "devices": sorted([
                {
                    "fqdn": device.fqdn,
                    "interfaces": self.dehydrate_interfaces(device),
                }
                for device in node.children.all().order_by('id')
            ], key=itemgetter('fqdn')),
            "disable_ipv4": node.disable_ipv4,
            "physical_disk_count": len(physical_blockdevices),
            "disks": [
                self.dehydrate_blockdevice(blockdevice)
                for blockdevice in blockdevices
            ],
            "distro_series": node.get_distro_series(),
            "error": node.error,
            "error_description": node.error_description,
            "events": [
                self.dehydrate_event(event)
                for event in events
            ],
            "extra_macs": [
                "%s" % mac_address
                for mac_address in node.get_extra_macs()
            ],
            "fqdn": node.fqdn,
            "hwe_kernel": node.hwe_kernel,
            "hostname": node.hostname,
            "id": node.id,
            "installation_results": [
                self.dehydrate_node_result(result)
                for result in NodeResult.objects.filter(
                    node=node, result_type=RESULT_TYPE.INSTALLATION)
            ],
            "interfaces": self.dehydrate_interfaces(node),
            "license_key": node.license_key,
            "memory": node.display_memory(),
            "min_hwe_kernel": node.min_hwe_kernel,
            "nodegroup": {
                "id": node.nodegroup.id,
                "uuid": node.nodegroup.uuid,
                "name": node.nodegroup.name,
                "cluster_name": node.nodegroup.cluster_name,
            },
            "osystem": node.get_osystem(),
            "owner": "" if node.owner is None else node.owner.username,
            "power_parameters": power_parameters,
            "power_state": node.power_state,
            "power_type": node.power_type,
            "pxe_mac": (
                "" if boot_interface is None else
                "%s" % boot_interface.mac_address),
            "pxe_mac_vendor": "" if pxe_mac_vendor is None else pxe_mac_vendor,
            "routers": [
                "%s" % router
                for router in node.routers
            ],
            "status": node.display_status(),
            "storage": "%3.1f" % (sum([
                blockdevice.size
                for blockdevice in physical_blockdevices
            ]) / (1000 ** 3)),
            "storage_tags": self.get_all_storage_tags(blockdevices),
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
            "zone": {
                "id": node.zone.id,
                "name": node.zone.name,
            },
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
                "networks",
                "physical_disk_count",
                "storage",
                "storage_tags",
            ]
            for key in data.keys():
                if key not in allowed_fields:
                    del data[key]
        if include_summary:
            probed_details = merge_details_cleanly(
                get_single_probed_details(node.system_id))
            data['summary_xml'] = etree.tostring(
                probed_details, encoding=unicode, pretty_print=True)
            data['summary_yaml'] = XMLToYAML(
                etree.tostring(
                    probed_details, encoding=unicode,
                    pretty_print=True)).convert()
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

        # LINK_UP interface with no subnet.
        nic1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        nic1_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip="",
            subnet=None, interface=nic1)
        nic1_ip.subnet = None
        nic1_ip.save()

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
            self.dehydrate_node(node, user, include_summary=True),
            handler.get({"system_id": node.system_id}))

    def test_list(self):
        user = factory.make_User()
        handler = NodeHandler(user, {})
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=user)
        factory.make_PhysicalBlockDevice(node)
        self.assertItemsEqual(
            [self.dehydrate_node(node, user, for_list=True)],
            handler.list({}))

    def test_list_ignores_devices(self):
        owner = factory.make_User()
        handler = NodeHandler(owner, {})
        # Create a device.
        factory.make_Node(owner=owner, installable=False)
        node = factory.make_Node(owner=owner)
        self.assertItemsEqual(
            [self.dehydrate_node(node, owner, for_list=True)],
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
            query_10_count, 9,
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
            self.dehydrate_node(node, user, for_list=True),
            self.dehydrate_node(ownered_node, user, for_list=True),
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
        node_data = self.dehydrate_node(node, user)
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
        node_data = self.dehydrate_node(node, user)
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
        node_data = self.dehydrate_node(node, user)
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
        node_data = self.dehydrate_node(node, user)
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
        node_data = self.dehydrate_node(node, user)
        node_data["tags"].append(tag_name)
        updated_node = handler.update(node_data)
        self.assertItemsEqual([tag_name], updated_node["tags"])

    def test_update_raise_HandlerError_if_tag_has_definition(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        tag = factory.make_Tag()
        node_data = self.dehydrate_node(node, user)
        node_data["tags"].append(tag.name)
        self.assertRaises(HandlerError, handler.update, node_data)

    def test_update_updates_tags_on_physical_block_device_for_node(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        architecture = make_usable_architecture(self)
        node = factory.make_Node(interface=True, architecture=architecture)
        factory.make_PhysicalBlockDevice(node=node)
        blockdevice_tags = [
            factory.make_name("tag")
            for _ in range(3)
            ]
        node_data = self.dehydrate_node(node, user)
        node_data["disks"][0]["tags"] = blockdevice_tags
        updated_node = handler.update(node_data)
        self.assertItemsEqual(
            blockdevice_tags, updated_node["disks"][0]["tags"])

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


class TestNodeHandlerCheckPower(MAASTransactionServerTestCase):

    @asynchronous
    def make_node(self, power_type="ipmi"):
        """Makes a node that is committed in the database."""
        return deferToThread(
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
