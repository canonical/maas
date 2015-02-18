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

from django.core.urlresolvers import reverse
from maasserver.enum import NODE_STATUS
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import human_readable_bytes
from maasserver.websockets.handlers.node import NodeHandler
from maastesting.djangotestcase import count_queries


class TestNodeHandler(MAASServerTestCase):

    def dehydrate_physicalblockdevice(self, blockdevice):
        return {
            "name": blockdevice.name,
            "tags": blockdevice.tags,
            "path": blockdevice.path,
            "size": blockdevice.size,
            "block_size": blockdevice.block_size,
            "model": blockdevice.model,
            "serial": blockdevice.serial,
            }

    def get_all_disk_tags(self, physicalblockdevices):
        tags = set()
        for blockdevice in physicalblockdevices:
            tags = tags.union(blockdevice.tags)
        return list(tags)

    def dehydrate_node(self, node, for_list=False):
        pxe_mac = node.get_pxe_mac()
        pxe_mac_vendor = node.get_pxe_mac_vendor()
        physicalblockdevices = list(
            node.physicalblockdevice_set.all().order_by('name'))
        data = {
            "architecture": node.architecture,
            "boot_type": node.boot_type,
            "cpu_count": node.cpu_count,
            "created": "%s" % node.created,
            "disable_ipv4": node.disable_ipv4,
            "disks": len(physicalblockdevices),
            "disk_tags": self.get_all_disk_tags(physicalblockdevices),
            "distro_series": node.distro_series,
            "error": node.error,
            "error_description": node.error_description,
            "extra_macs": [
                "%s" % mac_address.mac_address
                for mac_address in node.get_extra_macs()
                ],
            "fqdn": node.fqdn,
            "hostname": node.hostname,
            "ip_addresses": list(node.ip_addresses()),
            "license_key": node.license_key,
            "memory": node.memory,
            "nodegroup": node.nodegroup.name,
            "osystem": node.osystem,
            "owner": "" if node.owner is None else node.owner.username,
            "physical_disks": [
                self.dehydrate_physicalblockdevice(blockdevice)
                for blockdevice in physicalblockdevices
                ],
            "power_parameters": node.power_parameters,
            "power_state": node.power_state,
            "power_type": node.power_type,
            "pxe_mac": "" if pxe_mac is None else "%s" % pxe_mac.mac_address,
            "pxe_mac_vendor": "" if pxe_mac_vendor is None else pxe_mac_vendor,
            "routers": [
                "%s" % router
                for router in node.routers
                ],
            "status": node.display_status(),
            "storage": human_readable_bytes(sum([
                blockdevice.size
                for blockdevice in physicalblockdevices
                ]), include_suffix=False),
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
        return data

    def make_nodes(self, nodegroup, number):
        """Create `number` of new nodes."""
        for counter in range(number):
            node = factory.make_Node(
                nodegroup=nodegroup, mac=True, status=NODE_STATUS.READY)
            factory.make_PhysicalBlockDevice(node)

    def test_get(self):
        handler = NodeHandler(factory.make_User())
        node = factory.make_Node(status=NODE_STATUS.READY)
        factory.make_PhysicalBlockDevice(node)
        self.assertEquals(
            self.dehydrate_node(node),
            handler.get({"system_id": node.system_id}))

    def test_list(self):
        handler = NodeHandler(factory.make_User())
        node = factory.make_Node()
        factory.make_PhysicalBlockDevice(node)
        self.assertItemsEqual(
            [self.dehydrate_node(node, for_list=True)],
            handler.list({}))

    def test_list_ignores_devices(self):
        owner = factory.make_User()
        handler = NodeHandler(owner)
        # Create a device.
        factory.make_Node(owner=owner, installable=False)
        node = factory.make_Node(owner=owner)
        self.assertItemsEqual(
            [self.dehydrate_node(node, for_list=True)],
            handler.list({}))

    def test_list_num_queries_is_independent_of_num_nodes(self):
        handler = NodeHandler(factory.make_User())
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
        handler = NodeHandler(user)
        self.assertItemsEqual([
            self.dehydrate_node(node, for_list=True),
            self.dehydrate_node(ownered_node, for_list=True),
            ], handler.list({}))

    def test_get_object_returns_node_if_super_user(self):
        user = factory.make_admin()
        node = factory.make_Node()
        handler = NodeHandler(user)
        self.assertEquals(
            node, handler.get_object({"system_id": node.system_id}))

    def test_get_object_returns_node_if_owner(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        handler = NodeHandler(user)
        self.assertEquals(
            node, handler.get_object({"system_id": node.system_id}))

    def test_get_object_returns_node_if_owner_empty(self):
        user = factory.make_User()
        node = factory.make_Node()
        handler = NodeHandler(user)
        self.assertEquals(
            node, handler.get_object({"system_id": node.system_id}))

    def test_get_object_returns_None_if_owner_by_another_user(self):
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        handler = NodeHandler(user)
        self.assertIsNone(handler.get_object({"system_id": node.system_id}))
