# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.device`"""

__all__ = []

from maasserver.enum import (
    IPADDRESS_TYPE,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
)
from maasserver.exceptions import NodeActionError
from maasserver.fields import MAC
from maasserver.forms import (
    DeviceForm,
    DeviceWithMACsForm,
)
from maasserver.models import interface as interface_module
from maasserver.models.interface import Interface
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
from maasserver.websockets.handlers.device import (
    DEVICE_IP_ASSIGNMENT,
    DeviceHandler,
)
from maasserver.websockets.handlers.timestampedmodel import dehydrate_datetime
from maastesting.djangotestcase import count_queries
from testtools import ExpectedException
from testtools.matchers import (
    Equals,
    Is,
)


class TestDeviceHandler(MAASServerTestCase):

    def setUp(self):
        super(TestDeviceHandler, self).setUp()
        # Prevent actual, real-world, updates to host maps.
        self.patch_autospec(interface_module, "update_host_maps")

    def dehydrate_ip_assignment(self, device):
        boot_interface = device.get_boot_interface()
        if boot_interface is None:
            return ""
        ip_address = boot_interface.ip_addresses.exclude(
            alloc_type=IPADDRESS_TYPE.DISCOVERED).first()
        if ip_address is not None:
            if ip_address.alloc_type == IPADDRESS_TYPE.DHCP:
                return DEVICE_IP_ASSIGNMENT.DYNAMIC
            elif ip_address.subnet is None:
                return DEVICE_IP_ASSIGNMENT.EXTERNAL
            else:
                return DEVICE_IP_ASSIGNMENT.STATIC
        return DEVICE_IP_ASSIGNMENT.DYNAMIC

    def dehydrate_ip_address(self, device):
        """Return the IP address for the device."""
        boot_interface = device.get_boot_interface()
        if boot_interface is None:
            return None
        static_ip = boot_interface.ip_addresses.exclude(
            alloc_type=IPADDRESS_TYPE.DISCOVERED).first()
        if static_ip is not None:
            ip = static_ip.get_ip()
            if ip:
                return "%s" % ip
        return None

    def dehydrate_device(self, node, user, for_list=False):
        boot_interface = node.get_boot_interface()
        data = {
            "actions": list(compile_node_actions(node, user).keys()),
            "created": dehydrate_datetime(node.created),
            "extra_macs": [
                "%s" % mac_address.mac_address
                for mac_address in node.get_extra_macs()
                ],
            "fqdn": node.fqdn,
            "hostname": node.hostname,
            "primary_mac": (
                "" if boot_interface is None else
                "%s" % boot_interface.mac_address),
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
            for key in list(data):
                if key not in allowed_fields:
                    del data[key]
        return data

    def make_device_with_ip_address(
            self, nodegroup=None, ip_assignment=None, owner=None):
        """The `DEVICE_IP_ASSIGNMENT` is based on what data exists in the model
        for a device. This will setup the model to make sure the device will
        match `ip_assignment`."""
        if nodegroup is None:
            nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        if ip_assignment is None:
            ip_assignment = factory.pick_enum(DEVICE_IP_ASSIGNMENT)
        if owner is None:
            owner = factory.make_User()
        device = factory.make_Node(
            nodegroup=nodegroup, installable=False,
            interface=True, owner=owner)
        interface = device.get_boot_interface()
        if ip_assignment == DEVICE_IP_ASSIGNMENT.EXTERNAL:
            subnet = factory.make_Subnet()
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.USER_RESERVED,
                ip=factory.pick_ip_in_network(subnet.get_ipnetwork()),
                subnet=subnet, user=owner)
        elif ip_assignment == DEVICE_IP_ASSIGNMENT.DYNAMIC:
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.DHCP, ip="", interface=interface)
        else:
            subnet = factory.make_Subnet(vlan=interface.vlan)
            factory.make_NodeGroupInterface(
                nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
                subnet=subnet)
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, ip="",
                interface=interface, subnet=subnet)
            interface.claim_static_ips()
        return device

    def make_devices(self, nodegroup, number, owner=None):
        """Create `number` of new devices."""
        for counter in range(number):
            self.make_device_with_ip_address(nodegroup=nodegroup, owner=owner)

    def test_get(self):
        owner = factory.make_User()
        handler = DeviceHandler(owner, {})
        device = self.make_device_with_ip_address(owner=owner)
        self.assertEqual(
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
        # Create a device with parent.
        node = factory.make_Node(owner=owner)
        device_with_parent = self.make_device_with_ip_address(owner=owner)
        device_with_parent.parent = node
        device_with_parent.save()
        self.assertItemsEqual(
            [self.dehydrate_device(device, owner, for_list=True)],
            handler.list({}))

    def test_list_ignores_devices_with_parents(self):
        owner = factory.make_User()
        handler = DeviceHandler(owner, {})
        device = self.make_device_with_ip_address(owner=owner)
        # Create a node.
        factory.make_Node(owner=owner)
        self.assertItemsEqual(
            [self.dehydrate_device(device, owner, for_list=True)],
            handler.list({}))

    def test_list_num_queries_is_independent_of_num_devices(self):
        owner = factory.make_User()
        handler = DeviceHandler(owner, {})
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        self.make_devices(nodegroup, 10, owner=owner)
        query_10_count, _ = count_queries(handler.list, {})
        self.make_devices(nodegroup, 10, owner=owner)
        query_20_count, _ = count_queries(handler.list, {})

        # This check is to notify the developer that a change was made that
        # affects the number of queries performed when doing a node listing.
        # It is important to keep this number as low as possible. A larger
        # number means regiond has to do more work slowing down its process
        # and slowing down the client waiting for the response.
        self.assertEqual(
            query_10_count, 7,
            "Number of queries has changed; make sure this is expected.")
        self.assertEqual(
            query_10_count, query_20_count,
            "Number of queries is not independent to the number of nodes.")

    def test_list_returns_devices_only_viewable_by_user(self):
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
        self.assertEqual(
            device.system_id,
            handler.get_object({"system_id": device.system_id}).system_id)

    def test_get_object_returns_node_if_owner(self):
        owner = factory.make_User()
        device = self.make_device_with_ip_address(owner=owner)
        handler = DeviceHandler(owner, {})
        self.assertEqual(
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
        error = self.assertRaises(
            HandlerValidationError, handler.create, params)
        self.assertThat(error.message_dict, Equals(
            {'mac_addresses': ['This field is required.']}))

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

    def test_create_creates_device_with_static_ip_assignment_implicit(self):
        user = factory.make_User()
        handler = DeviceHandler(user, {})
        mac = factory.make_mac_address()
        hostname = factory.make_name("hostname")
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        nodegroup_interface = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
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
        static_interface = Interface.objects.get(mac_address=MAC(mac))
        subnet = static_interface.ip_addresses.first().subnet
        linked_ngi = subnet.nodegroupinterface_set.first()
        self.expectThat(
            linked_ngi, Equals(nodegroup_interface),
            "Link between Interface and NodeGroupInterface was not created.")
        ip_address = created_device["ip_address"]
        self.expectThat(
            StaticIPAddress.objects.filter(ip=ip_address).count(),
            Equals(1), "StaticIPAddress was not created.")

    def test_create_creates_device_with_static_ip_assignment_explicit(self):
        user = factory.make_User()
        handler = DeviceHandler(user, {})
        mac = factory.make_mac_address()
        hostname = factory.make_name("hostname")
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        nodegroup_interface = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        ip_address = nodegroup_interface.static_ip_range_low
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
        static_interface = Interface.objects.get(mac_address=MAC(mac))
        subnet = static_interface.ip_addresses.first().subnet
        linked_ngi = subnet.nodegroupinterface_set.first()
        self.expectThat(
            linked_ngi, Equals(nodegroup_interface),
            "Link between Interface and NodeGroupInterface was not created.")
        self.expectThat(
            StaticIPAddress.objects.filter(ip=ip_address).count(),
            Equals(1), "StaticIPAddress was not created.")

    def test_create_creates_device_with_static_and_external_ip(self):
        user = factory.make_User()
        handler = DeviceHandler(user, {})
        hostname = factory.make_name("hostname")
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        nodegroup_interface = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        mac_static = factory.make_mac_address()
        static_ip_address = nodegroup_interface.static_ip_range_low
        mac_external = factory.make_mac_address()
        external_ip_address = factory.make_ipv4_address()
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
        static_interface = Interface.objects.get(mac_address=MAC(mac_static))
        subnet = static_interface.ip_addresses.first().subnet
        linked_ngi = subnet.nodegroupinterface_set.first()
        self.expectThat(
            linked_ngi, Equals(nodegroup_interface),
            "Link between Interface and NodeGroupInterface was not created.")
        self.expectThat(
            StaticIPAddress.objects.filter(ip=static_ip_address).count(),
            Equals(1), "Static StaticIPAddress was not created.")
        self.expectThat(
            StaticIPAddress.objects.filter(ip=external_ip_address).count(),
            Equals(1), "External StaticIPAddress was not created.")

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
