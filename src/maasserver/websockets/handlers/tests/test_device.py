# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.device`"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django.core.urlresolvers import reverse
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.handlers.device import DeviceHandler
from maastesting.djangotestcase import count_queries


class TestDeviceHandler(MAASServerTestCase):

    def dehydrate_device(self, node, for_list=False):
        pxe_mac = node.get_pxe_mac()
        pxe_mac_vendor = node.get_pxe_mac_vendor()
        data = {
            "created": "%s" % node.created,
            "extra_macs": [
                "%s" % mac_address.mac_address
                for mac_address in node.get_extra_macs()
                ],
            "fqdn": node.fqdn,
            "hostname": node.hostname,
            "pxe_mac": "" if pxe_mac is None else "%s" % pxe_mac.mac_address,
            "pxe_mac_vendor": "" if pxe_mac_vendor is None else pxe_mac_vendor,
            "parent": (
                node.parent.system_id if node.parent is not None else None),
            "ip_addresses": list(node.ip_addresses()),
            "nodegroup": node.nodegroup.name,
            "owner": "" if node.owner is None else node.owner.username,
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
            allowed_fields = DeviceHandler.Meta.list_fields + [
                "url",
                "fqdn",
                "status",
                "extra_macs",
                "tags",
                "pxe_mac",
                "pxe_mac_vendor",
                ]
            for key in data.keys():
                if key not in allowed_fields:
                    del data[key]
        return data

    def make_devices(self, nodegroup, number):
        """Create `number` of new devices."""
        for counter in range(number):
            factory.make_Node(
                nodegroup=nodegroup, installable=False, mac=True)

    def test_get(self):
        owner = factory.make_User()
        handler = DeviceHandler(owner)
        device = factory.make_Node(owner=owner, installable=False)
        self.assertEquals(
            self.dehydrate_device(device),
            handler.get({"system_id": device.system_id}))

    def test_list(self):
        owner = factory.make_User()
        handler = DeviceHandler(owner)
        device = factory.make_Node(owner=owner, installable=False)
        self.assertItemsEqual(
            [self.dehydrate_device(device, for_list=True)],
            handler.list({}))

    def test_list_ignores_nodes(self):
        owner = factory.make_User()
        handler = DeviceHandler(owner)
        device = factory.make_Node(owner=owner, installable=False)
        # Create a node.
        factory.make_Node(owner=owner)
        self.assertItemsEqual(
            [self.dehydrate_device(device, for_list=True)],
            handler.list({}))

    def test_list_num_queries_is_independent_of_num_devices(self):
        owner = factory.make_User()
        handler = DeviceHandler(owner)
        factory.make_Node(owner=owner, installable=False)
        nodegroup = factory.make_NodeGroup()
        self.make_devices(nodegroup, 10)
        query_10_count, _ = count_queries(handler.list, {})
        self.make_devices(nodegroup, 10)
        query_20_count, _ = count_queries(handler.list, {})

        # This check is to notify the developer that a change was made that
        # affects the number of queries performed when doing a node listing.
        # It is important to keep this number as low as possible. A larger
        # number means regiond has to do more work slowing down its process
        # and slowing down the client waiting for the response.
        self.assertEquals(
            query_10_count, 5,
            "Number of queries has changed, make sure this is expected.")
        self.assertEquals(
            query_10_count, query_20_count,
            "Number of queries is not independent to the number of nodes.")

    def test_list_returns_devices_only_viewable_by_user(self):
        user = factory.make_User()
        # Create another user.
        factory.make_User()
        handler = DeviceHandler(user)
        device = factory.make_Node(owner=user, installable=False)
        # Create another device.
        factory.make_Node(
            owner=factory.make_User(), installable=False)
        handler = DeviceHandler(user)
        self.assertItemsEqual([
            self.dehydrate_device(device, for_list=True),
            ], handler.list({}))

    def test_get_object_returns_device_if_super_user(self):
        admin = factory.make_admin()
        owner = factory.make_User()
        device = factory.make_Node(owner=owner, installable=False)
        handler = DeviceHandler(admin)
        self.assertEquals(
            device.system_id,
            handler.get_object({"system_id": device.system_id}).system_id)

    def test_get_object_returns_node_if_owner(self):
        owner = factory.make_User()
        device = factory.make_Node(owner=owner, installable=False)
        handler = DeviceHandler(owner)
        self.assertEquals(
            device.system_id,
            handler.get_object({"system_id": device.system_id}).system_id)

    def test_get_object_returns_None_if_owner_by_another_user(self):
        user = factory.make_User()
        device = factory.make_Node(owner=factory.make_User())
        handler = DeviceHandler(user)
        self.assertIsNone(handler.get_object({"system_id": device.system_id}))
