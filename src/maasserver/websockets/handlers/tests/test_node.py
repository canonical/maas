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
import re

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from lxml import etree
from maasserver.enum import NODE_STATUS
from maasserver.exceptions import NodeActionError
from maasserver.forms import (
    AdminNodeForm,
    AdminNodeWithMACAddressesForm,
    )
from maasserver.models.event import Event
from maasserver.models.nodeprobeddetails import get_single_probed_details
from maasserver.node_action import compile_node_actions
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.osystems import make_osystem_with_releases
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import XMLToYAML
from maasserver.websockets.base import (
    HandlerDoesNotExistError,
    HandlerError,
    HandlerPermissionError,
    HandlerValidationError,
    )
from maasserver.websockets.handlers.node import NodeHandler
from maastesting.djangotestcase import count_queries
from metadataserver.enum import RESULT_TYPE
from metadataserver.models import NodeResult
from metadataserver.models.commissioningscript import LLDP_OUTPUT_NAME
from provisioningserver.tags import merge_details_cleanly
from testtools import ExpectedException
from testtools.matchers import Equals


class TestNodeHandler(MAASServerTestCase):

    def dehydrate_physicalblockdevice(self, blockdevice):
        return {
            "name": blockdevice.name,
            "tags": blockdevice.tags,
            "path": blockdevice.path,
            "size": blockdevice.size,
            "size_gb": "%3.1f" % (blockdevice.size / (1000 ** 3)),
            "block_size": blockdevice.block_size,
            "model": blockdevice.model,
            "serial": blockdevice.serial,
            }

    def dehydrate_event(self, event):
        return {
            "id": event.id,
            "type": {
                "id": event.type.id,
                "name": event.type.name,
                "description": event.type.description,
                "level": event.type.level,
                },
            "description": event.description,
            "created": event.created.strftime('%a, %d %b. %Y %H:%M:%S'),
            }

    def dehydrate_node_result(self, result):
        return {
            "id": result.id,
            "result": result.script_result,
            "name": result.name,
            "data": result.data,
            "line_count": len(result.data.splitlines()),
            "created": result.created.strftime('%a, %d %b. %Y %H:%M:%S'),
            }

    def dehydrate_interface(self, mac_address, node):
        ip_addresses = [
            {
                "type": "static",
                "alloc_type": ip_address.alloc_type,
                "ip_address": "%s" % ip_address.ip,
            }
            for ip_address in mac_address.ip_addresses.all()
            ]
        static_addresses = [
            ip_address["ip_address"]
            for ip_address in ip_addresses
            ]
        ip_addresses += [
            {
                "type": "dynamic",
                "ip_address": lease.ip,
            }
            for lease in node.nodegroup.dhcplease_set.all()
            if (lease.mac == mac_address.mac_address and
                lease.ip not in static_addresses)
            ]
        networks = [
            {
                "id": network.id,
                "name": network.name,
                "ip": network.ip,
                "cidr": "%s" % network.get_network().cidr,
                "vlan": network.vlan_tag,
            }
            for network in mac_address.networks.all()
            ]
        return {
            "id": mac_address.id,
            "is_pxe": mac_address == node.pxe_mac,
            "mac_address": "%s" % mac_address.mac_address,
            "ip_addresses": ip_addresses,
            "networks": networks,
        }

    def dehydrate_interfaces(self, node):
        return sorted([
            self.dehydrate_interface(mac_address, node)
            for mac_address in node.macaddress_set.all().order_by('id')
            ], key=itemgetter('is_pxe'), reverse=True)

    def get_all_disk_tags(self, physicalblockdevices):
        tags = set()
        for blockdevice in physicalblockdevices:
            tags = tags.union(blockdevice.tags)
        return list(tags)

    def dehydrate_node(
            self, node, user, for_list=False, include_summary=False):
        pxe_mac = node.get_pxe_mac()
        pxe_mac_vendor = node.get_pxe_mac_vendor()
        physicalblockdevices = list(
            node.physicalblockdevice_set.all().order_by('name'))
        power_parameters = (
            None if node.power_parameters == "" else node.power_parameters)
        events = (
            Event.objects.filter(node=node)
            .exclude(type__level=logging.DEBUG)
            .select_related("type")
            .order_by('-id')[:50])
        data = {
            "actions": compile_node_actions(node, user).keys(),
            "architecture": node.architecture,
            "boot_type": node.boot_type,
            "commissioning_results": [
                self.dehydrate_node_result(result)
                for result in NodeResult.objects.filter(
                    node=node, result_type=RESULT_TYPE.COMMISSIONING)
                ],
            "cpu_count": node.cpu_count,
            "created": "%s" % node.created,
            "disable_ipv4": node.disable_ipv4,
            "disks": len(physicalblockdevices),
            "disk_tags": self.get_all_disk_tags(physicalblockdevices),
            "distro_series": node.get_distro_series(),
            "error": node.error,
            "error_description": node.error_description,
            "events": [
                self.dehydrate_event(event)
                for event in events
                ],
            "events_total": Event.objects.filter(node=node).count(),
            "extra_macs": [
                "%s" % mac_address.mac_address
                for mac_address in node.get_extra_macs()
                ],
            "fqdn": node.fqdn,
            "hostname": node.hostname,
            "installation_results": [
                self.dehydrate_node_result(result)
                for result in NodeResult.objects.filter(
                    node=node, result_type=RESULT_TYPE.INSTALLATION)
                ],
            "interfaces": self.dehydrate_interfaces(node),
            "license_key": node.license_key,
            "memory": node.display_memory(),
            "nodegroup": {
                "id": node.nodegroup.id,
                "uuid": node.nodegroup.uuid,
                "name": node.nodegroup.name,
                "cluster_name": node.nodegroup.cluster_name,
                },
            "osystem": node.get_osystem(),
            "owner": "" if node.owner is None else node.owner.username,
            "physical_disks": [
                self.dehydrate_physicalblockdevice(blockdevice)
                for blockdevice in physicalblockdevices
                ],
            "power_parameters": power_parameters,
            "power_state": node.power_state,
            "power_type": node.power_type,
            "pxe_mac": "" if pxe_mac is None else "%s" % pxe_mac.mac_address,
            "pxe_mac_vendor": "" if pxe_mac_vendor is None else pxe_mac_vendor,
            "routers": [
                "%s" % router
                for router in node.routers
                ],
            "status": node.display_status(),
            "storage": "%3.1f" % (sum([
                blockdevice.size
                for blockdevice in physicalblockdevices
                ]) / (1000 ** 3)),
            "swap_size": node.swap_size,
            "system_id": node.system_id,
            "tags": [
                tag.name
                for tag in node.tags.all()
                ],
            "updated": "%s" % node.updated,
            "url": reverse('node-view', args=[node.system_id]),
            "zone": {
                "id": node.zone.id,
                "name": node.zone.name,
                "url": reverse('zone-view', args=[node.zone.name]),
                },
            }
        if for_list:
            allowed_fields = NodeHandler.Meta.list_fields + [
                "actions",
                "url",
                "fqdn",
                "status",
                "pxe_mac",
                "pxe_mac_vendor",
                "extra_macs",
                "tags",
                "disks",
                "disk_tags",
                "storage",
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
                nodegroup=nodegroup, mac=True, status=NODE_STATUS.READY)
            factory.make_PhysicalBlockDevice(node)

    def test_get(self):
        user = factory.make_User()
        handler = NodeHandler(user, {})
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        node.owner = user
        node.save()
        for _ in range(100):
            factory.make_Event(node=node)
        lldp_data = "<foo>bar</foo>".encode("utf-8")
        factory.make_NodeResult_for_commissioning(
            node=node, name=LLDP_OUTPUT_NAME, script_result=0, data=lldp_data)
        factory.make_PhysicalBlockDevice(node)

        mac_address = node.macaddress_set.all()[0]
        factory.make_StaticIPAddress(mac=mac_address)
        factory.make_DHCPLease(
            nodegroup=node.nodegroup, mac=mac_address.mac_address)

        pxe_mac_address = factory.make_MACAddress(node=node)
        node.pxe_mac = pxe_mac_address
        node.save()

        network = factory.make_Network()
        pxe_mac_address.networks.add(network)
        pxe_mac_address.save()

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
            query_10_count, 7,
            "Number of queries has changed, make sure this is expected.")
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
            AdminNodeForm,
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

    def test_update_raise_permissions_error_for_non_admin(self):
        user = factory.make_User()
        handler = NodeHandler(user, {})
        self.assertRaises(
            HandlerPermissionError,
            handler.update, {})

    def test_update_raises_validation_error_for_invalid_architecture(self):
        user = factory.make_admin()
        handler = NodeHandler(user, {})
        node = factory.make_Node(mac=True)
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
        node = factory.make_Node(mac=True)
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
        user = factory.make_User()
        factory.make_SSHKey(user)
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=user)
        handler = NodeHandler(user, {})
        self.assertEquals(
            handler.action({"system_id": node.system_id, "action": "deploy"}),
            "This node has been asked to deploy.")

    def test_action_performs_action_passing_extra(self):
        user = factory.make_User()
        factory.make_SSHKey(user)
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=user)
        osystem = make_osystem_with_releases(self)
        handler = NodeHandler(user, {})
        self.expectThat(
            handler.action({
                "system_id": node.system_id,
                "action": "deploy",
                "extra": {
                    "osystem": osystem["name"],
                    "distro_series": osystem["releases"][0]["name"],
                }}),
            Equals("This node has been asked to deploy."))
        node = reload_object(node)
        self.expectThat(node.osystem, Equals(osystem["name"]))
        self.expectThat(
            node.distro_series, Equals(osystem["releases"][0]["name"]))
