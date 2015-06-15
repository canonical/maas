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

import re

from maasserver.clusterrpc import dhcp as dhcp_module
from maasserver.dns import config as dns_config
from maasserver.exceptions import NodeActionError
from maasserver.fields import MAC
from maasserver.forms import (
    DeviceForm,
    DeviceWithMACsForm,
)
from maasserver.models.macaddress import MACAddress
from maasserver.models.node import Node
from maasserver.models.nodegroup import NodeGroup
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.node_action import compile_node_actions
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import (
    HandlerDoesNotExistError,
    HandlerError,
    HandlerValidationError,
)
from maasserver.websockets.handlers import device as device_module
from maasserver.websockets.handlers.device import (
    DEVICE_IP_ASSIGNMENT,
    DeviceHandler,
)
from maasserver.websockets.handlers.timestampedmodel import dehydrate_datetime
from maastesting.djangotestcase import count_queries
from maastesting.matchers import MockCalledOnceWith
from testtools import ExpectedException
from testtools.matchers import (
    Equals,
    Is,
)
from twisted.python.failure import Failure


class TestDeviceHandler(MAASServerTestCase):

    def dehydrate_ip_assignment(self, device):
        mac = device.get_primary_mac()
        if mac is None:
            return ""
        num_ip_address = mac.ip_addresses.count()
        if mac.cluster_interface is None and num_ip_address > 0:
            return DEVICE_IP_ASSIGNMENT.EXTERNAL
        elif mac.cluster_interface is not None and num_ip_address > 0:
            return DEVICE_IP_ASSIGNMENT.STATIC
        else:
            return DEVICE_IP_ASSIGNMENT.DYNAMIC

    def dehydrate_ip_address(self, device):
        """Return the IP address for the device."""
        primary_mac = device.get_primary_mac()
        if primary_mac is None:
            return None
        static_ips = list(primary_mac.ip_addresses.all())
        if len(static_ips) > 0:
            return "%s" % static_ips[0].ip
        for lease in device.nodegroup.dhcplease_set.all():
            if lease.mac == primary_mac.mac_address:
                return "%s" % lease.ip
        return None

    def dehydrate_device(self, node, user, for_list=False):
        primary_mac = node.get_primary_mac()
        data = {
            "actions": compile_node_actions(node, user).keys(),
            "created": dehydrate_datetime(node.created),
            "extra_macs": [
                "%s" % mac_address.mac_address
                for mac_address in node.get_extra_macs()
                ],
            "fqdn": node.fqdn,
            "hostname": node.hostname,
            "primary_mac": (
                "" if primary_mac is None else "%s" % primary_mac.mac_address),
            "parent": (
                node.parent.system_id if node.parent is not None else None),
            "ip_address": self.dehydrate_ip_address(node),
            "ip_assignment": self.dehydrate_ip_assignment(node),
            "nodegroup": {
                "id": node.nodegroup.id,
                "uuid": node.nodegroup.uuid,
                "name": node.nodegroup.name,
                "cluster_name": node.nodegroup.cluster_name,
                },
            "owner": "" if node.owner is None else node.owner.username,
            "swap_size": node.swap_size,
            "system_id": node.system_id,
            "tags": [
                tag.name
                for tag in node.tags.all()
                ],
            "updated": dehydrate_datetime(node.updated),
            "zone": {
                "id": node.zone.id,
                "name": node.zone.name,
                },
            }
        if for_list:
            allowed_fields = DeviceHandler.Meta.list_fields + [
                "actions",
                "fqdn",
                "extra_macs",
                "tags",
                "primary_mac",
                "ip_address",
                "ip_assignment",
                ]
            for key in data.keys():
                if key not in allowed_fields:
                    del data[key]
        return data

    def make_device_with_ip_address(
            self, nodegroup=None, ip_assignment=None, owner=None):
        """The `DEVICE_IP_ASSIGNMENT` is based on what data exists in the model
        for a device. This will setup the model to make sure the device will
        match `ip_assignment`."""
        if nodegroup is None:
            nodegroup = factory.make_NodeGroup()
        if ip_assignment is None:
            ip_assignment = factory.pick_enum(DEVICE_IP_ASSIGNMENT)
        if owner is None:
            owner = factory.make_User()
        device = factory.make_Node(
            nodegroup=nodegroup, installable=False, mac=True, owner=owner)
        primary_mac = device.get_primary_mac()
        if ip_assignment == DEVICE_IP_ASSIGNMENT.EXTERNAL:
            primary_mac.set_static_ip(
                factory.make_ipv4_address(), owner)
        elif ip_assignment == DEVICE_IP_ASSIGNMENT.DYNAMIC:
            factory.make_DHCPLease(
                nodegroup, ip=factory.make_ipv4_address(),
                mac=primary_mac.mac_address)
        else:
            interface = factory.make_NodeGroupInterface(nodegroup)
            primary_mac.cluster_interface = interface
            primary_mac.save()
            primary_mac.claim_static_ips(update_host_maps=False)
        return device

    def make_devices(self, nodegroup, number, owner=None):
        """Create `number` of new devices."""
        for counter in range(number):
            self.make_device_with_ip_address(nodegroup=nodegroup, owner=owner)

    def test_get(self):
        owner = factory.make_User()
        handler = DeviceHandler(owner, {})
        device = self.make_device_with_ip_address(owner=owner)
        self.assertEquals(
            self.dehydrate_device(device, owner),
            handler.get({"system_id": device.system_id}))

    def test_list(self):
        owner = factory.make_User()
        handler = DeviceHandler(owner, {})
        device = self.make_device_with_ip_address(owner=owner)
        self.assertItemsEqual(
            [self.dehydrate_device(device, owner, for_list=True)],
            handler.list({}))

    def test_list_ignores_nodes(self):
        owner = factory.make_User()
        handler = DeviceHandler(owner, {})
        device = self.make_device_with_ip_address(owner=owner)
        # Create a node.
        factory.make_Node(owner=owner)
        self.assertItemsEqual(
            [self.dehydrate_device(device, owner, for_list=True)],
            handler.list({}))

    def test_list_num_queries_is_independent_of_num_devices(self):
        self.patch(Node, "update_host_maps")
        owner = factory.make_User()
        handler = DeviceHandler(owner, {})
        nodegroup = factory.make_NodeGroup()
        self.make_devices(nodegroup, 10, owner=owner)
        query_10_count, _ = count_queries(handler.list, {})
        self.make_devices(nodegroup, 10, owner=owner)
        query_20_count, _ = count_queries(handler.list, {})

        # This check is to notify the developer that a change was made that
        # affects the number of queries performed when doing a node listing.
        # It is important to keep this number as low as possible. A larger
        # number means regiond has to do more work slowing down its process
        # and slowing down the client waiting for the response.
        self.assertEquals(
            query_10_count, 8,
            "Number of queries has changed, make sure this is expected.")
        self.assertEquals(
            query_10_count, query_20_count,
            "Number of queries is not independent to the number of nodes.")

    def test_list_returns_devices_only_viewable_by_user(self):
        self.patch(Node, "update_host_maps")
        user = factory.make_User()
        # Create another user.
        factory.make_User()
        device = self.make_device_with_ip_address(owner=user)
        # Create another device not ownered by user.
        self.make_device_with_ip_address()
        handler = DeviceHandler(user, {})
        self.assertItemsEqual([
            self.dehydrate_device(device, user, for_list=True),
            ], handler.list({}))

    def test_get_object_returns_device_if_super_user(self):
        admin = factory.make_admin()
        owner = factory.make_User()
        device = self.make_device_with_ip_address(owner=owner)
        handler = DeviceHandler(admin, {})
        self.assertEquals(
            device.system_id,
            handler.get_object({"system_id": device.system_id}).system_id)

    def test_get_object_returns_node_if_owner(self):
        owner = factory.make_User()
        device = self.make_device_with_ip_address(owner=owner)
        handler = DeviceHandler(owner, {})
        self.assertEquals(
            device.system_id,
            handler.get_object({"system_id": device.system_id}).system_id)

    def test_get_object_raises_exception_if_owner_by_another_user(self):
        user = factory.make_User()
        device = self.make_device_with_ip_address()
        handler = DeviceHandler(user, {})
        with ExpectedException(HandlerDoesNotExistError):
            handler.get_object({"system_id": device.system_id})

    def test_get_form_class_returns_DeviceWithMACsForm_for_create(self):
        user = factory.make_User()
        handler = DeviceHandler(user, {})
        self.assertIs(DeviceWithMACsForm, handler.get_form_class("create"))

    def test_get_form_class_returns_DeviceForm_for_update(self):
        user = factory.make_User()
        handler = DeviceHandler(user, {})
        self.assertIs(DeviceForm, handler.get_form_class("update"))

    def test_get_form_class_raises_error_for_unknown_action(self):
        user = factory.make_User()
        handler = DeviceHandler(user, {})
        self.assertRaises(
            HandlerError,
            handler.get_form_class, factory.make_name())

    def test_create_raises_validation_error_for_missing_macs(self):
        user = factory.make_User()
        handler = DeviceHandler(user, {})
        params = {
            "hostname": factory.make_name("hostname"),
            }
        with ExpectedException(
                HandlerValidationError,
                re.escape("{u'mac_addresses': [u'This field is required.']}")):
            handler.create(params)

    def test_create_creates_device_with_dynamic_ip_assignment(self):
        user = factory.make_User()
        handler = DeviceHandler(user, {})
        mac = factory.make_mac_address()
        hostname = factory.make_name("hostname")
        created_device = handler.create({
            "hostname": hostname,
            "primary_mac": mac,
            "interfaces": [{
                "mac": mac,
                "ip_assignment": DEVICE_IP_ASSIGNMENT.DYNAMIC,
            }],
        })
        self.expectThat(created_device["hostname"], Equals(hostname))
        self.expectThat(created_device["primary_mac"], Equals(mac))
        self.expectThat(created_device["extra_macs"], Equals([]))
        self.expectThat(
            created_device["ip_assignment"],
            Equals(DEVICE_IP_ASSIGNMENT.DYNAMIC))
        self.expectThat(created_device["ip_address"], Is(None))
        self.expectThat(created_device["owner"], Equals(user.username))

    def test_create_creates_device_with_external_ip_assignment(self):
        user = factory.make_User()
        handler = DeviceHandler(user, {})
        mac = factory.make_mac_address()
        hostname = factory.make_name("hostname")
        ip_address = factory.make_ipv4_address()
        self.patch(dhcp_module, "update_host_maps").return_value = []
        created_device = handler.create({
            "hostname": hostname,
            "primary_mac": mac,
            "interfaces": [{
                "mac": mac,
                "ip_assignment": DEVICE_IP_ASSIGNMENT.EXTERNAL,
                "ip_address": ip_address,
            }],
        })
        self.expectThat(
            created_device["ip_assignment"],
            Equals(DEVICE_IP_ASSIGNMENT.EXTERNAL))
        self.expectThat(created_device["ip_address"], Equals(ip_address))
        self.expectThat(
            StaticIPAddress.objects.filter(ip=ip_address).count(),
            Equals(1), "StaticIPAddress was not created.")

    def test_create_with_external_ip_calls_dns_update_zones(self):
        user = factory.make_User()
        handler = DeviceHandler(user, {})
        mac = factory.make_mac_address()
        hostname = factory.make_name("hostname")
        ip_address = factory.make_ipv4_address()
        self.patch(dhcp_module, "update_host_maps").return_value = []
        mock_dns_update_zones = self.patch(dns_config.dns_update_zones)
        handler.create({
            "hostname": hostname,
            "primary_mac": mac,
            "interfaces": [{
                "mac": mac,
                "ip_assignment": DEVICE_IP_ASSIGNMENT.EXTERNAL,
                "ip_address": ip_address,
            }],
        })
        self.assertThat(
            mock_dns_update_zones,
            MockCalledOnceWith([NodeGroup.objects.ensure_master()]))

    def test_create_raises_failure_external_ip_update_hostmaps_fails(self):
        user = factory.make_User()
        handler = DeviceHandler(user, {})
        mac = factory.make_mac_address()
        hostname = factory.make_name("hostname")
        ip_address = factory.make_ipv4_address()
        mock_update_host_maps = self.patch(dhcp_module, "update_host_maps")
        mock_update_host_maps.return_value = [
            Failure(factory.make_exception()),
            ]
        self.assertRaises(HandlerError, handler.create, {
            "hostname": hostname,
            "primary_mac": mac,
            "interfaces": [{
                "mac": mac,
                "ip_assignment": DEVICE_IP_ASSIGNMENT.EXTERNAL,
                "ip_address": ip_address,
            }],
        })
        self.expectThat(
            Node.objects.filter(hostname=hostname).count(),
            Equals(0), "Created Node was not deleted.")
        self.expectThat(
            MACAddress.objects.filter(mac_address=MAC(mac)).count(),
            Equals(0), "Created MACAddress was not deleted.")
        self.expectThat(
            StaticIPAddress.objects.filter(ip=ip_address).count(),
            Equals(0), "Created StaticIPAddress was not deleted.")

    def test_create_creates_device_with_static_ip_assignment_implicit(self):
        self.patch(Node, "update_host_maps")
        user = factory.make_User()
        handler = DeviceHandler(user, {})
        mac = factory.make_mac_address()
        hostname = factory.make_name("hostname")
        nodegroup = factory.make_NodeGroup()
        nodegroup_interface = factory.make_NodeGroupInterface(nodegroup)
        self.patch(dhcp_module, "update_host_maps").return_value = []
        created_device = handler.create({
            "hostname": hostname,
            "primary_mac": mac,
            "interfaces": [{
                "mac": mac,
                "ip_assignment": DEVICE_IP_ASSIGNMENT.STATIC,
                "interface": nodegroup_interface.id,
            }],
        })
        self.expectThat(
            created_device["ip_assignment"],
            Equals(DEVICE_IP_ASSIGNMENT.STATIC))
        self.expectThat(
            MACAddress.objects.get(mac_address=MAC(mac)).cluster_interface,
            Equals(nodegroup_interface),
            "Link between MACAddress and NodeGroupInterface was not created.")
        ip_address = created_device["ip_address"]
        self.expectThat(
            StaticIPAddress.objects.filter(ip=ip_address).count(),
            Equals(1), "StaticIPAddress was not created.")

    def test_create_creates_device_with_static_ip_assignment_explicit(self):
        self.patch(Node, "update_host_maps")
        user = factory.make_User()
        handler = DeviceHandler(user, {})
        mac = factory.make_mac_address()
        hostname = factory.make_name("hostname")
        nodegroup = factory.make_NodeGroup()
        nodegroup_interface = factory.make_NodeGroupInterface(nodegroup)
        ip_address = nodegroup_interface.static_ip_range_low
        self.patch(dhcp_module, "update_host_maps").return_value = []
        created_device = handler.create({
            "hostname": hostname,
            "primary_mac": mac,
            "interfaces": [{
                "mac": mac,
                "ip_assignment": DEVICE_IP_ASSIGNMENT.STATIC,
                "interface": nodegroup_interface.id,
                "ip_address": ip_address,
            }],
        })
        self.expectThat(
            created_device["ip_assignment"],
            Equals(DEVICE_IP_ASSIGNMENT.STATIC))
        self.expectThat(created_device["ip_address"], Equals(ip_address))
        self.expectThat(
            MACAddress.objects.get(mac_address=MAC(mac)).cluster_interface,
            Equals(nodegroup_interface),
            "Link between MACAddress and NodeGroupInterface was not created.")
        self.expectThat(
            StaticIPAddress.objects.filter(ip=ip_address).count(),
            Equals(1), "StaticIPAddress was not created.")

    def test_create_with_static_ip_calls_dns_update_zones(self):
        self.patch(device_module.update_host_maps).return_value = []
        # self.patch(Node.update_host_maps).return_value = []
        user = factory.make_User()
        handler = DeviceHandler(user, {})
        mac = factory.make_mac_address()
        hostname = factory.make_name("hostname")
        nodegroup = factory.make_NodeGroup()
        nodegroup_interface = factory.make_NodeGroupInterface(nodegroup)
        mock_dns_update_zones = self.patch(dns_config.dns_update_zones)
        handler.create({
            "hostname": hostname,
            "primary_mac": mac,
            "interfaces": [{
                "mac": mac,
                "ip_assignment": DEVICE_IP_ASSIGNMENT.STATIC,
                "interface": nodegroup_interface.id,
            }],
        })
        self.assertThat(
            mock_dns_update_zones,
            MockCalledOnceWith([NodeGroup.objects.ensure_master()]))

    def test_create_raises_failure_static_ip_update_hostmaps_fails(self):
        self.patch(Node, "update_host_maps")
        mock_update_host_maps = self.patch(dhcp_module, "update_host_maps")
        user = factory.make_User()
        handler = DeviceHandler(user, {})
        mac = factory.make_mac_address()
        hostname = factory.make_name("hostname")
        nodegroup = factory.make_NodeGroup()
        nodegroup_interface = factory.make_NodeGroupInterface(nodegroup)
        ip_address = nodegroup_interface.static_ip_range_low
        mock_update_host_maps.return_value = [
            Failure(factory.make_exception()),
            ]
        self.assertRaises(HandlerError, handler.create, {
            "hostname": hostname,
            "primary_mac": mac,
            "interfaces": [{
                "mac": mac,
                "ip_assignment": DEVICE_IP_ASSIGNMENT.STATIC,
                "interface": nodegroup_interface.id,
                "ip_address": ip_address,
            }],
        })
        self.expectThat(
            Node.objects.filter(hostname=hostname).count(),
            Equals(0), "Created Node was not deleted.")
        self.expectThat(
            MACAddress.objects.filter(mac_address=MAC(mac)).count(),
            Equals(0), "Created MACAddress was not deleted.")
        self.expectThat(
            StaticIPAddress.objects.filter(ip=ip_address).count(),
            Equals(0), "Created StaticIPAddress was not deleted.")

    def test_create_creates_device_with_static_and_external_ip(self):
        self.patch(Node, "update_host_maps")
        user = factory.make_User()
        handler = DeviceHandler(user, {})
        hostname = factory.make_name("hostname")
        nodegroup = factory.make_NodeGroup()
        nodegroup_interface = factory.make_NodeGroupInterface(nodegroup)
        mac_static = factory.make_mac_address()
        static_ip_address = nodegroup_interface.static_ip_range_low
        mac_external = factory.make_mac_address()
        external_ip_address = factory.make_ipv4_address()
        self.patch(dhcp_module, "update_host_maps").return_value = []
        created_device = handler.create({
            "hostname": hostname,
            "primary_mac": mac_static,
            "extra_macs": [
                mac_external
            ],
            "interfaces": [
                {
                    "mac": mac_static,
                    "ip_assignment": DEVICE_IP_ASSIGNMENT.STATIC,
                    "interface": nodegroup_interface.id,
                    "ip_address": static_ip_address,
                },
                {
                    "mac": mac_external,
                    "ip_assignment": DEVICE_IP_ASSIGNMENT.EXTERNAL,
                    "ip_address": external_ip_address,
                },
            ],
        })
        self.expectThat(
            created_device["primary_mac"],
            Equals(mac_static))
        self.expectThat(
            created_device["extra_macs"],
            Equals([mac_external]))
        self.expectThat(
            created_device["ip_assignment"],
            Equals(DEVICE_IP_ASSIGNMENT.STATIC))
        self.expectThat(
            created_device["ip_address"], Equals(static_ip_address))
        self.expectThat(
            MACAddress.objects.get(
                mac_address=MAC(mac_static)).cluster_interface,
            Equals(nodegroup_interface),
            "Link between MACAddress and NodeGroupInterface was not created.")
        self.expectThat(
            StaticIPAddress.objects.filter(ip=static_ip_address).count(),
            Equals(1), "Static StaticIPAddress was not created.")
        self.expectThat(
            StaticIPAddress.objects.filter(ip=external_ip_address).count(),
            Equals(1), "External StaticIPAddress was not created.")

    def test_create_deletes_device_and_ips_when_only_one_errors(self):
        self.patch(Node, "update_host_maps")
        self.patch(dhcp_module, "update_host_maps").side_effect = [
            [], [Failure(factory.make_exception())],
        ]
        user = factory.make_User()
        handler = DeviceHandler(user, {})
        hostname = factory.make_name("hostname")
        nodegroup = factory.make_NodeGroup()
        nodegroup_interface = factory.make_NodeGroupInterface(nodegroup)
        mac_static = factory.make_mac_address()
        static_ip_address = nodegroup_interface.static_ip_range_low
        mac_external = factory.make_mac_address()
        external_ip_address = factory.make_ipv4_address()
        self.assertRaises(HandlerError, handler.create, {
            "hostname": hostname,
            "primary_mac": mac_static,
            "extra_macs": [
                mac_external
            ],
            "interfaces": [
                {
                    "mac": mac_static,
                    "ip_assignment": DEVICE_IP_ASSIGNMENT.STATIC,
                    "interface": nodegroup_interface.id,
                    "ip_address": static_ip_address,
                },
                {
                    "mac": mac_external,
                    "ip_assignment": DEVICE_IP_ASSIGNMENT.EXTERNAL,
                    "ip_address": external_ip_address,
                },
            ],
        })
        self.expectThat(
            Node.objects.filter(hostname=hostname).count(),
            Equals(0), "Created Node was not deleted.")
        self.expectThat(
            MACAddress.objects.filter(mac_address=MAC(mac_static)).count(),
            Equals(0),
            "Created MACAddress for static ip address was not deleted.")
        self.expectThat(
            MACAddress.objects.filter(mac_address=MAC(mac_external)).count(),
            Equals(0),
            "Created MACAddress for external ip address was not deleted.")
        self.expectThat(
            StaticIPAddress.objects.filter(ip=static_ip_address).count(),
            Equals(0),
            "Created StaticIPAddress for static ip address was not deleted.")
        self.expectThat(
            StaticIPAddress.objects.filter(ip=external_ip_address).count(),
            Equals(0),
            "Created StaticIPAddress for external ip address was not deleted.")

    def test_missing_action_raises_error(self):
        user = factory.make_User()
        device = self.make_device_with_ip_address(owner=user)
        handler = DeviceHandler(user, {})
        with ExpectedException(NodeActionError):
            handler.action({"system_id": device.system_id})

    def test_invalid_action_raises_error(self):
        user = factory.make_User()
        device = self.make_device_with_ip_address(owner=user)
        handler = DeviceHandler(user, {})
        self.assertRaises(
            NodeActionError,
            handler.action,
            {"system_id": device.system_id, "action": "unknown"})

    def test_not_available_action_raises_error(self):
        user = factory.make_User()
        device = self.make_device_with_ip_address(owner=user)
        handler = DeviceHandler(user, {})
        self.assertRaises(
            NodeActionError,
            handler.action,
            {"system_id": device.system_id, "action": "unknown"})

    def test_action_performs_action(self):
        user = factory.make_User()
        device = factory.make_Node(owner=user, installable=False)
        handler = DeviceHandler(user, {})
        handler.action({"system_id": device.system_id, "action": "delete"})
        self.assertIsNone(reload_object(device))

    def test_action_performs_action_passing_extra(self):
        user = factory.make_User()
        device = self.make_device_with_ip_address(owner=user)
        zone = factory.make_Zone()
        handler = DeviceHandler(user, {})
        handler.action({
            "system_id": device.system_id,
            "action": "set-zone",
            "extra": {
                "zone_id": zone.id,
            }})
        device = reload_object(device)
        self.expectThat(device.zone, Equals(zone))
