# Copyright 2015-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from operator import itemgetter
from unittest.mock import ANY

from django.http import HttpRequest
from netaddr import IPAddress, IPNetwork
from testtools import ExpectedException
from testtools.matchers import Equals, Is

from maasserver.enum import (
    DEVICE_IP_ASSIGNMENT_TYPE,
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_TYPE,
)
from maasserver.exceptions import NodeActionError
from maasserver.forms import DeviceForm, DeviceWithMACsForm
from maasserver.models import Interface, StaticIPAddress
from maasserver.node_action import compile_node_actions
from maasserver.permissions import NodePermission
from maasserver.testing.factory import factory
from maasserver.testing.fixtures import RBACEnabled, RBACForceOffFixture
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.orm import reload_object, transactional
from maasserver.websockets.base import (
    dehydrate_datetime,
    HandlerDoesNotExistError,
    HandlerError,
    HandlerValidationError,
)
from maasserver.websockets.handlers.device import DeviceHandler
from maasserver.websockets.handlers.node import NODE_TYPE_TO_LINK_TYPE
from maastesting.djangotestcase import count_queries
from maastesting.matchers import MockCalledOnceWith, MockNotCalled


class TestDeviceHandler(MAASTransactionServerTestCase):
    def dehydrate_ip_assignment(self, device, interface):
        if interface is None:
            return ""
        ip_address = interface.ip_addresses.exclude(
            alloc_type=IPADDRESS_TYPE.DISCOVERED
        ).first()
        if ip_address is not None:
            if ip_address.alloc_type == IPADDRESS_TYPE.DHCP:
                return DEVICE_IP_ASSIGNMENT_TYPE.DYNAMIC
            elif ip_address.subnet is None:
                return DEVICE_IP_ASSIGNMENT_TYPE.EXTERNAL
            else:
                return DEVICE_IP_ASSIGNMENT_TYPE.STATIC
        return DEVICE_IP_ASSIGNMENT_TYPE.DYNAMIC

    def dehydrate_ip_address(self, device, interface):
        """Return the IP address for the device."""
        if interface is None:
            return None
        static_ip = interface.ip_addresses.exclude(
            alloc_type=IPADDRESS_TYPE.DISCOVERED
        ).first()
        if static_ip is not None:
            ip = static_ip.get_ip()
            if ip:
                return "%s" % ip
        return None

    def dehydrate_interface(self, interface, obj):
        """Dehydrate a `interface` into a interface definition."""
        # Sort the links by ID that way they show up in the same order in
        # the UI.
        links = sorted(interface.get_links(), key=itemgetter("id"))
        for link in links:
            # Replace the subnet object with the subnet_id. The client will
            # use this information to pull the subnet information from the
            # websocket.
            subnet = link.pop("subnet", None)
            if subnet is not None:
                link["subnet_id"] = subnet.id
        data = {
            "id": interface.id,
            "type": interface.type,
            "name": interface.name,
            "enabled": interface.is_enabled(),
            "tags": interface.tags,
            "is_boot": interface == obj.get_boot_interface(),
            "mac_address": "%s" % interface.mac_address,
            "vlan_id": interface.vlan_id,
            "params": interface.params,
            "parents": [nic.id for nic in interface.parents.all()],
            "children": [
                nic.child.id for nic in interface.children_relationships.all()
            ],
            "links": links,
            "ip_assignment": self.dehydrate_ip_assignment(obj, interface),
            "ip_address": self.dehydrate_ip_address(obj, interface),
            "interface_speed": interface.interface_speed,
            "link_connected": interface.link_connected,
            "link_speed": interface.link_speed,
            "numa_node": None,
            "vendor": interface.vendor,
            "product": interface.product,
            "firmware_version": interface.firmware_version,
            "sriov_max_vf": 0,
        }
        return data

    def dehydrate_device(self, node, user, for_list=False):
        boot_interface = node.get_boot_interface()
        subnets = {
            ip_address.subnet
            for interface in node.current_config.interface_set.all()
            for ip_address in interface.ip_addresses.all()
            if ip_address.subnet is not None
        }
        space_names = {
            subnet.space.name for subnet in subnets if subnet.space is not None
        }
        fabric_names = {
            iface.vlan.fabric.name
            for iface in node.current_config.interface_set.all()
            if iface.vlan is not None
        }
        fabric_names.update({subnet.vlan.fabric.name for subnet in subnets})
        boot_interface = node.get_boot_interface()
        permissions = []
        if user.has_perm(NodePermission.edit, node):
            permissions = ["edit", "delete"]
        data = {
            "actions": list(compile_node_actions(node, user).keys()),
            "created": dehydrate_datetime(node.created),
            "domain": {"id": node.domain.id, "name": node.domain.name},
            "extra_macs": [
                "%s" % mac_address.mac_address
                for mac_address in node.get_extra_macs()
            ],
            "link_speeds": sorted(
                {
                    interface.link_speed
                    for interface in node.current_config.interface_set.all()
                    if interface.link_speed > 0
                }
            ),
            "fqdn": node.fqdn,
            "hostname": node.hostname,
            "description": node.description,
            "node_type_display": node.get_node_type_display(),
            "link_type": NODE_TYPE_TO_LINK_TYPE[node.node_type],
            "id": node.id,
            "primary_mac": (
                ""
                if boot_interface is None
                else "%s" % boot_interface.mac_address
            ),
            "parent": (
                node.parent.system_id if node.parent is not None else None
            ),
            "permissions": permissions,
            "ip_address": self.dehydrate_ip_address(node, boot_interface),
            "ip_assignment": self.dehydrate_ip_assignment(
                node, boot_interface
            ),
            "interfaces": [
                self.dehydrate_interface(interface, node)
                for interface in node.current_config.interface_set.all().order_by(
                    "name"
                )
            ],
            "subnets": [subnet.cidr for subnet in subnets],
            "fabrics": list(fabric_names),
            "spaces": list(space_names),
            "on_network": node.on_network(),
            "owner": "" if node.owner is None else node.owner.username,
            "locked": node.locked,
            "swap_size": node.swap_size,
            "system_id": node.system_id,
            "tags": [tag.id for tag in node.tags.all()],
            "node_type": node.node_type,
            "updated": dehydrate_datetime(node.updated),
            "zone": {"id": node.zone.id, "name": node.zone.name},
            "pool": None,
            "last_applied_storage_layout": node.last_applied_storage_layout,
        }
        if for_list:
            allowed_fields = DeviceHandler.Meta.list_fields + [
                "actions",
                "extra_macs",
                "fabrics",
                "fqdn",
                "installation_status",
                "ip_address",
                "ip_assignment",
                "link_type",
                "permissions",
                "primary_mac",
                "spaces",
                "tags",
                "interface_speed",
                "link_connected",
                "link_speed",
            ]
            for key in list(data):
                if key not in allowed_fields:
                    del data[key]
        return data

    def make_device_with_ip_address(self, ip_assignment=None, owner=None):
        """The `DEVICE_IP_ASSIGNMENT` is based on what data exists in the model
        for a device. This will setup the model to make sure the device will
        match `ip_assignment`."""
        if ip_assignment is None:
            ip_assignment = factory.pick_enum(DEVICE_IP_ASSIGNMENT_TYPE)
        if owner is None:
            owner = factory.make_User()
        device = factory.make_Node(
            node_type=NODE_TYPE.DEVICE, interface=True, owner=owner
        )
        interface = device.get_boot_interface()
        # always attach to a space so queries counts are consistent
        space = factory.make_Space()
        interface.vlan.space = space
        interface.vlan.save()
        if ip_assignment == DEVICE_IP_ASSIGNMENT_TYPE.EXTERNAL:
            subnet = factory.make_Subnet()
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.USER_RESERVED,
                ip=factory.pick_ip_in_network(subnet.get_ipnetwork()),
                subnet=subnet,
                user=owner,
            )
        elif ip_assignment == DEVICE_IP_ASSIGNMENT_TYPE.DYNAMIC:
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.DHCP, ip="", interface=interface
            )
        else:
            subnet = factory.make_Subnet(vlan=interface.vlan)
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=factory.pick_ip_in_Subnet(subnet),
                interface=interface,
                subnet=subnet,
            )
        return device

    def make_devices(self, number, owner=None, ip_assignment=None):
        """Create `number` of new devices."""
        for counter in range(number):
            self.make_device_with_ip_address(
                owner=owner, ip_assignment=ip_assignment
            )

    @transactional
    def test_get(self):
        owner = factory.make_User()
        handler = DeviceHandler(owner, {}, None)
        device = self.make_device_with_ip_address(owner=owner)
        self.assertEqual(
            self.dehydrate_device(device, owner),
            handler.get({"system_id": device.system_id}),
        )

    @transactional
    def test_get_num_queries_is_the_expected_number(self):
        owner = factory.make_User()
        handler = DeviceHandler(owner, {}, None)
        device = self.make_device_with_ip_address(
            owner=owner, ip_assignment=DEVICE_IP_ASSIGNMENT_TYPE.STATIC
        )
        queries, _ = count_queries(
            handler.get, {"system_id": device.system_id}
        )

        # This check is to notify the developer that a change was made that
        # affects the number of queries performed when doing a node get.
        # It is important to keep this number as low as possible. A larger
        # number means regiond has to do more work slowing down its process
        # and slowing down the client waiting for the response.
        self.assertEqual(
            queries,
            20,
            "Number of queries has changed; make sure this is expected.",
        )

    def test_get_no_numa_nodes_for_device(self):
        user = factory.make_User()
        device = factory.make_Device()
        handler = DeviceHandler(user, {}, None)
        result = handler.get({"system_id": device.system_id})
        self.assertNotIn("numa_nodes", result)

    @transactional
    def test_list(self):
        owner = factory.make_User()
        handler = DeviceHandler(owner, {}, None)
        device = self.make_device_with_ip_address(owner=owner)
        list_results = handler.list({})
        self.assertCountEqual(
            [self.dehydrate_device(device, owner, for_list=True)],
            list_results,
        )

    @transactional
    def test_list_ignores_nodes(self):
        owner = factory.make_User()
        handler = DeviceHandler(owner, {}, None)
        device = self.make_device_with_ip_address(owner=owner)
        # Create a device with parent.
        node = factory.make_Node(owner=owner)
        device_with_parent = self.make_device_with_ip_address(owner=owner)
        device_with_parent.parent = node
        device_with_parent.save()
        list_results = handler.list({})
        self.assertCountEqual(
            [self.dehydrate_device(device, owner, for_list=True)],
            list_results,
        )

    @transactional
    def test_list_ignores_devices_with_parents(self):
        owner = factory.make_User()
        handler = DeviceHandler(owner, {}, None)
        device = self.make_device_with_ip_address(owner=owner)
        # Create a node.
        factory.make_Node(owner=owner)
        list_results = handler.list({})
        self.assertCountEqual(
            [self.dehydrate_device(device, owner, for_list=True)],
            list_results,
        )

    @transactional
    def test_list_num_queries_is_the_expected_number(self):
        # Prevent RBAC from making a query.
        self.useFixture(RBACForceOffFixture())

        owner = factory.make_User()
        handler = DeviceHandler(owner, {}, None)
        self.make_devices(
            10, owner=owner, ip_assignment=DEVICE_IP_ASSIGNMENT_TYPE.STATIC
        )
        query_10_count, _ = count_queries(handler.list, {})
        self.make_devices(10, owner=owner)

        # This check is to notify the developer that a change was made that
        # affects the number of queries performed when doing a node listing.
        # It is important to keep this number as low as possible. A larger
        # number means regiond has to do more work slowing down its process
        # and slowing down the client waiting for the response.
        self.assertEqual(
            query_10_count,
            11,
            "Number of queries has changed; make sure this is expected.",
        )

    @transactional
    def test_list_num_queries_is_independent_of_num_devices(self):
        # Prevent RBAC from making a query.
        self.useFixture(RBACForceOffFixture())

        owner = factory.make_User()
        handler = DeviceHandler(owner, {}, None)
        ip_assignment = factory.pick_enum(DEVICE_IP_ASSIGNMENT_TYPE)
        self.make_devices(10, owner=owner, ip_assignment=ip_assignment)
        query_10_count, _ = count_queries(handler.list, {})
        self.make_devices(10, owner=owner, ip_assignment=ip_assignment)
        query_20_count, _ = count_queries(handler.list, {})

        # This check is to notify the developer that a change was made that
        # affects the number of queries performed when doing a node listing.
        # It is important to keep this number as low as possible. A larger
        # number means regiond has to do more work slowing down its process
        # and slowing down the client waiting for the response.
        self.assertEqual(
            query_10_count,
            query_20_count,
            "Number of queries is not independent to the number of nodes.",
        )

    @transactional
    def test_list_returns_devices_only_viewable_by_user(self):
        user = factory.make_User()
        # Create another user.
        factory.make_User()
        device = self.make_device_with_ip_address(owner=user)
        # Create another device not ownered by user.
        self.make_device_with_ip_address()
        handler = DeviceHandler(user, {}, None)
        list_results = handler.list({})
        self.assertCountEqual(
            [self.dehydrate_device(device, user, for_list=True)],
            list_results,
        )

    @transactional
    def test_get_object_returns_device_if_super_user(self):
        admin = factory.make_admin()
        owner = factory.make_User()
        device = self.make_device_with_ip_address(owner=owner)
        handler = DeviceHandler(admin, {}, None)
        self.assertEqual(
            device.system_id,
            handler.get_object({"system_id": device.system_id}).system_id,
        )

    @transactional
    def test_get_object_returns_node_if_owner(self):
        owner = factory.make_User()
        device = self.make_device_with_ip_address(owner=owner)
        handler = DeviceHandler(owner, {}, None)
        self.assertEqual(
            device.system_id,
            handler.get_object({"system_id": device.system_id}).system_id,
        )

    def test_get_object_raises_exception_if_owner_by_another_user(self):
        user = factory.make_User()
        device = self.make_device_with_ip_address()
        handler = DeviceHandler(user, {}, None)
        with ExpectedException(HandlerDoesNotExistError):
            handler.get_object({"system_id": device.system_id})

    @transactional
    def test_get_form_class_returns_DeviceWithMACsForm_for_create(self):
        user = factory.make_User()
        handler = DeviceHandler(user, {}, None)
        self.assertIs(DeviceWithMACsForm, handler.get_form_class("create"))

    @transactional
    def test_get_form_class_returns_DeviceForm_for_update(self):
        user = factory.make_User()
        handler = DeviceHandler(user, {}, None)
        self.assertIs(DeviceForm, handler.get_form_class("update"))

    @transactional
    def test_get_form_class_raises_error_for_unknown_action(self):
        user = factory.make_User()
        handler = DeviceHandler(user, {}, None)
        self.assertRaises(
            HandlerError, handler.get_form_class, factory.make_name()
        )

    @transactional
    def test_create_raises_validation_error_for_missing_macs(self):
        user = factory.make_User()
        handler = DeviceHandler(user, {}, None)
        params = {"hostname": factory.make_name("hostname")}
        error = self.assertRaises(
            HandlerValidationError, handler.create, params
        )
        self.assertEqual(
            {"mac_addresses": ["This field is required."]},
            error.message_dict,
        )

    @transactional
    def test_create_creates_device_with_dynamic_ip_assignment(self):
        user = factory.make_User()
        request = HttpRequest()
        request.user = user
        handler = DeviceHandler(user, {}, request)
        mac = factory.make_mac_address()
        hostname = factory.make_name("hostname")
        description = factory.make_name("description")
        created_device = handler.create(
            {
                "hostname": hostname,
                "description": description,
                "primary_mac": mac,
                "interfaces": [
                    {
                        "mac": mac,
                        "ip_assignment": DEVICE_IP_ASSIGNMENT_TYPE.DYNAMIC,
                    }
                ],
            }
        )
        self.expectThat(created_device["hostname"], Equals(hostname))
        self.expectThat(created_device["description"], Equals(description))
        self.expectThat(created_device["primary_mac"], Equals(mac))
        self.expectThat(created_device["extra_macs"], Equals([]))
        self.expectThat(
            created_device["ip_assignment"],
            Equals(DEVICE_IP_ASSIGNMENT_TYPE.DYNAMIC),
        )
        self.expectThat(created_device["ip_address"], Is(None))
        self.expectThat(created_device["owner"], Equals(user.username))

    @transactional
    def test_create_creates_device_with_parent(self):
        user = factory.make_User()
        request = HttpRequest()
        request.user = user
        handler = DeviceHandler(user, {}, request)
        mac = factory.make_mac_address()
        hostname = factory.make_name("hostname")
        subnet = factory.make_Subnet()
        ip_address = factory.pick_ip_in_Subnet(subnet)
        node = factory.make_Node(owner=user)
        created_device = handler.create(
            {
                "extra_macs": [],
                "hostname": hostname,
                "interfaces": [
                    {
                        "ip_address": ip_address,
                        "ip_assignment": "dynamic",
                        "mac": mac,
                        "subnet": subnet.id,
                    }
                ],
                "parent": node.system_id,
                "primary_mac": mac,
            }
        )
        self.assertEqual(created_device["hostname"], hostname)
        self.assertEqual(created_device["parent"], node.system_id)

    @transactional
    def test_create_creates_device_with_external_ip_assignment(self):
        user = factory.make_User()
        request = HttpRequest()
        request.user = user
        handler = DeviceHandler(user, {}, request)
        mac = factory.make_mac_address()
        hostname = factory.make_name("hostname")
        ip_address = factory.make_ipv4_address()
        created_device = handler.create(
            {
                "hostname": hostname,
                "primary_mac": mac,
                "interfaces": [
                    {
                        "mac": mac,
                        "ip_assignment": DEVICE_IP_ASSIGNMENT_TYPE.EXTERNAL,
                        "ip_address": ip_address,
                    }
                ],
            }
        )
        self.expectThat(
            created_device["ip_assignment"],
            Equals(DEVICE_IP_ASSIGNMENT_TYPE.EXTERNAL),
        )
        self.expectThat(created_device["ip_address"], Equals(ip_address))
        self.expectThat(
            StaticIPAddress.objects.filter(ip=ip_address).count(),
            Equals(1),
            "StaticIPAddress was not created.",
        )

    @transactional
    def test_create_creates_device_with_static_ip_assignment_implicit(self):
        user = factory.make_User()
        request = HttpRequest()
        request.user = user
        handler = DeviceHandler(user, {}, request)
        mac = factory.make_mac_address()
        hostname = factory.make_name("hostname")
        subnet = factory.make_Subnet()
        created_device = handler.create(
            {
                "hostname": hostname,
                "primary_mac": mac,
                "interfaces": [
                    {
                        "mac": mac,
                        "ip_assignment": DEVICE_IP_ASSIGNMENT_TYPE.STATIC,
                        "subnet": subnet.id,
                    }
                ],
            }
        )
        self.expectThat(
            created_device["ip_assignment"],
            Equals(DEVICE_IP_ASSIGNMENT_TYPE.STATIC),
        )
        static_interface = Interface.objects.get(mac_address=mac)
        observed_subnet = static_interface.ip_addresses.first().subnet
        self.expectThat(
            observed_subnet,
            Equals(subnet),
            "Static assignment to the subnet was not created.",
        )
        ip_address = created_device["ip_address"]
        self.expectThat(
            StaticIPAddress.objects.filter(ip=ip_address).count(),
            Equals(1),
            "StaticIPAddress was not created.",
        )

    @transactional
    def test_create_creates_device_with_static_ip_assignment_explicit(self):
        user = factory.make_User()
        request = HttpRequest()
        request.user = user
        handler = DeviceHandler(user, {}, request)
        mac = factory.make_mac_address()
        hostname = factory.make_name("hostname")
        subnet = factory.make_Subnet()
        ip_address = factory.pick_ip_in_Subnet(subnet)
        created_device = handler.create(
            {
                "hostname": hostname,
                "primary_mac": mac,
                "interfaces": [
                    {
                        "mac": mac,
                        "ip_assignment": DEVICE_IP_ASSIGNMENT_TYPE.STATIC,
                        "subnet": subnet.id,
                        "ip_address": ip_address,
                    }
                ],
            }
        )
        self.expectThat(
            created_device["ip_assignment"],
            Equals(DEVICE_IP_ASSIGNMENT_TYPE.STATIC),
        )
        self.expectThat(created_device["ip_address"], Equals(ip_address))
        static_interface = Interface.objects.get(mac_address=mac)
        observed_subnet = static_interface.ip_addresses.first().subnet
        self.expectThat(
            observed_subnet,
            Equals(subnet),
            "Static assignment to the subnet was not created.",
        )
        self.expectThat(
            StaticIPAddress.objects.filter(ip=ip_address).count(),
            Equals(1),
            "StaticIPAddress was not created.",
        )

    @transactional
    def test_create_creates_device_with_static_and_external_ip(self):
        user = factory.make_User()
        request = HttpRequest()
        request.user = user
        handler = DeviceHandler(user, {}, request)
        hostname = factory.make_name("hostname")
        subnet = factory.make_Subnet()
        mac_static = factory.make_mac_address()
        static_ip_address = factory.pick_ip_in_Subnet(subnet)
        mac_external = factory.make_mac_address()
        external_ip_address = factory.make_ipv4_address()
        created_device = handler.create(
            {
                "hostname": hostname,
                "primary_mac": mac_static,
                "extra_macs": [mac_external],
                "interfaces": [
                    {
                        "mac": mac_static,
                        "ip_assignment": DEVICE_IP_ASSIGNMENT_TYPE.STATIC,
                        "subnet": subnet.id,
                        "ip_address": static_ip_address,
                    },
                    {
                        "mac": mac_external,
                        "ip_assignment": DEVICE_IP_ASSIGNMENT_TYPE.EXTERNAL,
                        "ip_address": external_ip_address,
                    },
                ],
            }
        )
        self.expectThat(created_device["primary_mac"], Equals(mac_static))
        self.expectThat(created_device["extra_macs"], Equals([mac_external]))
        self.expectThat(
            created_device["ip_assignment"],
            Equals(DEVICE_IP_ASSIGNMENT_TYPE.STATIC),
        )
        self.expectThat(
            created_device["ip_address"], Equals(static_ip_address)
        )
        static_interface = Interface.objects.get(mac_address=mac_static)
        observed_subnet = static_interface.ip_addresses.first().subnet
        self.expectThat(
            observed_subnet,
            Equals(subnet),
            "Static assignment to the subnet was not created.",
        )
        self.expectThat(
            StaticIPAddress.objects.filter(ip=static_ip_address).count(),
            Equals(1),
            "Static StaticIPAddress was not created.",
        )
        self.expectThat(
            StaticIPAddress.objects.filter(ip=external_ip_address).count(),
            Equals(1),
            "External StaticIPAddress was not created.",
        )

    @transactional
    def test_create_copes_with_mac_addresses_of_different_case(self):
        user = factory.make_User()
        request = HttpRequest()
        request.user = user
        handler = DeviceHandler(user, {}, request)
        mac = factory.make_mac_address()
        created_device = handler.create(
            {
                "hostname": factory.make_name("hostname"),
                "primary_mac": mac.lower(),  # Lowercase.
                "interfaces": [
                    {
                        "mac": mac.upper(),  # Uppercase.
                        "ip_assignment": DEVICE_IP_ASSIGNMENT_TYPE.DYNAMIC,
                    }
                ],
            }
        )
        self.assertEqual(mac, created_device["primary_mac"])

    @transactional
    def test_create_copes_with_mac_addresses_of_different_forms(self):
        user = factory.make_User()
        request = HttpRequest()
        request.user = user
        handler = DeviceHandler(user, {}, request)
        mac = factory.make_mac_address(delimiter=":")
        created_device = handler.create(
            {
                "hostname": factory.make_name("hostname"),
                "primary_mac": mac,  # Colons.
                "interfaces": [
                    {
                        "mac": mac.replace(":", "-"),  # Hyphens.
                        "ip_assignment": DEVICE_IP_ASSIGNMENT_TYPE.DYNAMIC,
                    }
                ],
            }
        )
        self.assertEqual(mac, created_device["primary_mac"])

    @transactional
    def test_create_interface_raises_validation_error_for_missing_macs(self):
        user = factory.make_User()
        handler = DeviceHandler(user, {}, None)
        device = factory.make_Device(owner=user)
        params = {"system_id": device.system_id}
        error = self.assertRaises(
            HandlerValidationError, handler.create_interface, params
        )
        self.assertThat(
            error.message_dict,
            Equals(
                {
                    "mac_address": [
                        "This field is required.",
                        "This field cannot be blank.",
                    ]
                }
            ),
        )

    @transactional
    def test_create_interface_creates_with_dynamic_ip_assignment(self):
        user = factory.make_User()
        request = HttpRequest()
        request.user = user
        handler = DeviceHandler(user, {}, request)
        device = factory.make_Device(owner=user)
        mac = factory.make_mac_address()
        updated_device = handler.create_interface(
            {
                "system_id": device.system_id,
                "mac_address": mac,
                "ip_assignment": DEVICE_IP_ASSIGNMENT_TYPE.DYNAMIC,
            }
        )
        self.expectThat(updated_device["primary_mac"], Equals(mac))
        self.expectThat(
            updated_device["ip_assignment"],
            Equals(DEVICE_IP_ASSIGNMENT_TYPE.DYNAMIC),
        )

    @transactional
    def test_create_interface_creates_with_external_ip_assignment(self):
        user = factory.make_User()
        request = HttpRequest()
        request.user = user
        handler = DeviceHandler(user, {}, request)
        device = factory.make_Device(owner=user)
        mac = factory.make_mac_address()
        ip_address = factory.make_ipv4_address()
        updated_device = handler.create_interface(
            {
                "system_id": device.system_id,
                "mac_address": mac,
                "ip_assignment": DEVICE_IP_ASSIGNMENT_TYPE.EXTERNAL,
                "ip_address": ip_address,
            }
        )
        self.expectThat(updated_device["primary_mac"], Equals(mac))
        self.expectThat(
            updated_device["ip_assignment"],
            Equals(DEVICE_IP_ASSIGNMENT_TYPE.EXTERNAL),
        )
        self.expectThat(
            StaticIPAddress.objects.filter(ip=ip_address).count(),
            Equals(1),
            "StaticIPAddress was not created.",
        )

    @transactional
    def test_create_interface_creates_with_static_ip_assignment_implicit(self):
        user = factory.make_User()
        handler = DeviceHandler(user, {}, None)
        device = factory.make_Device(owner=user)
        mac = factory.make_mac_address()
        subnet = factory.make_Subnet()
        updated_device = handler.create_interface(
            {
                "system_id": device.system_id,
                "mac_address": mac,
                "ip_assignment": DEVICE_IP_ASSIGNMENT_TYPE.STATIC,
                "subnet": subnet.id,
            }
        )
        self.expectThat(updated_device["primary_mac"], Equals(mac))
        self.expectThat(
            updated_device["ip_assignment"],
            Equals(DEVICE_IP_ASSIGNMENT_TYPE.STATIC),
        )
        static_interface = Interface.objects.get(mac_address=mac)
        observed_subnet = static_interface.ip_addresses.first().subnet
        self.expectThat(
            observed_subnet,
            Equals(subnet),
            "Static assignment to the subnet was not created.",
        )

    @transactional
    def test_create_interface_creates_static_ip_assignment_explicit(self):
        user = factory.make_User()
        request = HttpRequest()
        request.user = user
        handler = DeviceHandler(user, {}, request)
        device = factory.make_Device(owner=user)
        mac = factory.make_mac_address()
        subnet = factory.make_Subnet()
        ip_address = factory.pick_ip_in_Subnet(subnet)
        updated_device = handler.create_interface(
            {
                "system_id": device.system_id,
                "mac_address": mac,
                "ip_assignment": DEVICE_IP_ASSIGNMENT_TYPE.STATIC,
                "subnet": subnet.id,
                "ip_address": ip_address,
            }
        )
        self.expectThat(updated_device["primary_mac"], Equals(mac))
        self.expectThat(
            updated_device["ip_assignment"],
            Equals(DEVICE_IP_ASSIGNMENT_TYPE.STATIC),
        )
        self.expectThat(updated_device["ip_address"], Equals(ip_address))
        static_interface = Interface.objects.get(mac_address=mac)
        observed_subnet = static_interface.ip_addresses.first().subnet
        self.expectThat(
            observed_subnet,
            Equals(subnet),
            "Static assignment to the subnet was not created.",
        )
        self.expectThat(
            StaticIPAddress.objects.filter(ip=ip_address).count(),
            Equals(1),
            "StaticIPAddress was not created.",
        )

    @transactional
    def test_missing_action_raises_error(self):
        user = factory.make_User()
        device = self.make_device_with_ip_address(owner=user)
        handler = DeviceHandler(user, {}, None)
        with ExpectedException(NodeActionError):
            handler.action({"system_id": device.system_id})

    @transactional
    def test_invalid_action_raises_error(self):
        user = factory.make_User()
        device = self.make_device_with_ip_address(owner=user)
        handler = DeviceHandler(user, {}, None)
        self.assertRaises(
            NodeActionError,
            handler.action,
            {"system_id": device.system_id, "action": "unknown"},
        )

    @transactional
    def test_not_available_action_raises_error(self):
        user = factory.make_User()
        device = self.make_device_with_ip_address(owner=user)
        handler = DeviceHandler(user, {}, None)
        self.assertRaises(
            NodeActionError,
            handler.action,
            {"system_id": device.system_id, "action": "unknown"},
        )

    @transactional
    def test_action_performs_action(self):
        user = factory.make_admin()
        request = HttpRequest()
        request.user = user
        device = factory.make_Node(owner=user, node_type=NODE_TYPE.DEVICE)
        handler = DeviceHandler(user, {}, request)
        handler.action(
            {
                "request": request,
                "system_id": device.system_id,
                "action": "delete",
            }
        )
        self.assertIsNone(reload_object(device))

    @transactional
    def test_action_performs_action_passing_extra(self):
        user = factory.make_admin()
        request = HttpRequest()
        request.user = user
        device = self.make_device_with_ip_address(owner=user)
        zone = factory.make_Zone()
        handler = DeviceHandler(user, {}, request)
        handler.action(
            {
                "request": request,
                "system_id": device.system_id,
                "action": "set-zone",
                "extra": {"zone_id": zone.id},
            }
        )
        device = reload_object(device)
        self.expectThat(device.zone, Equals(zone))

    @transactional
    def test_create_interface_creates_interface(self):
        user = factory.make_admin()
        node = factory.make_Node(interface=False, node_type=NODE_TYPE.DEVICE)
        handler = DeviceHandler(user, {}, None)
        name = factory.make_name("eth")
        mac_address = factory.make_mac_address()
        handler.create_interface(
            {
                "system_id": node.system_id,
                "name": name,
                "mac_address": mac_address,
                "ip_assignment": DEVICE_IP_ASSIGNMENT_TYPE.DYNAMIC,
            }
        )
        self.assertEqual(
            1,
            node.current_config.interface_set.count(),
            "Should have one interface on the node.",
        )

    @transactional
    def test_create_interface_creates_static(self):
        user = factory.make_admin()
        node = factory.make_Node(interface=False, node_type=NODE_TYPE.DEVICE)
        handler = DeviceHandler(user, {}, None)
        name = factory.make_name("eth")
        mac_address = factory.make_mac_address()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        subnet = factory.make_Subnet(vlan=vlan)
        handler.create_interface(
            {
                "system_id": node.system_id,
                "name": name,
                "mac_address": mac_address,
                "ip_assignment": DEVICE_IP_ASSIGNMENT_TYPE.STATIC,
                "subnet": subnet.id,
            }
        )
        new_interface = node.current_config.interface_set.first()
        self.assertIsNotNone(new_interface)
        auto_ip = new_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet
        )
        self.assertIsNotNone(auto_ip)
        self.assertEqual(1, len(auto_ip))

    @transactional
    def test_create_interface_creates_external(self):
        user = factory.make_admin()
        node = factory.make_Node(interface=False, node_type=NODE_TYPE.DEVICE)
        handler = DeviceHandler(user, {}, None)
        name = factory.make_name("eth")
        mac_address = factory.make_mac_address()
        ip_address = factory.make_ip_address()
        handler.create_interface(
            {
                "system_id": node.system_id,
                "name": name,
                "mac_address": mac_address,
                "ip_assignment": DEVICE_IP_ASSIGNMENT_TYPE.EXTERNAL,
                "ip_address": ip_address,
            }
        )
        new_interface = node.current_config.interface_set.first()
        self.assertIsNotNone(new_interface)
        auto_ip = new_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED
        )
        self.assertIsNotNone(auto_ip)
        self.assertEqual(1, len(auto_ip))

    @transactional
    def test_update_interface_updates_admin(self):
        user = factory.make_admin()
        node = factory.make_Node(interface=False, node_type=NODE_TYPE.DEVICE)
        handler = DeviceHandler(user, {}, None)
        name = factory.make_name("eth")
        mac_address = factory.make_mac_address()
        ip_assignment = factory.pick_enum(DEVICE_IP_ASSIGNMENT_TYPE)
        params = {
            "system_id": node.system_id,
            "name": name,
            "mac_address": mac_address,
            "ip_assignment": ip_assignment,
        }
        if ip_assignment == DEVICE_IP_ASSIGNMENT_TYPE.STATIC:
            subnet = factory.make_Subnet()
            params["subnet"] = subnet.id
            ip_address = str(IPAddress(IPNetwork(subnet.cidr).first))
            params["ip_address"] = ip_address
        elif ip_assignment == DEVICE_IP_ASSIGNMENT_TYPE.EXTERNAL:
            ip_address = factory.make_ip_address()
            params["ip_address"] = ip_address
        handler.create_interface(params)
        interface = node.current_config.interface_set.first()
        self.assertIsNotNone(interface)
        new_name = factory.make_name("eth")
        new_ip_assignment = factory.pick_enum(DEVICE_IP_ASSIGNMENT_TYPE)
        new_params = {
            "system_id": node.system_id,
            "interface_id": interface.id,
            "name": new_name,
            "mac_address": mac_address,
            "ip_assignment": new_ip_assignment,
        }
        if new_ip_assignment == DEVICE_IP_ASSIGNMENT_TYPE.STATIC:
            new_subnet = factory.make_Subnet()
            new_params["subnet"] = new_subnet.id
            new_ip_address = str(IPAddress(IPNetwork(new_subnet.cidr).first))
            new_params["ip_address"] = new_ip_address
        elif new_ip_assignment == DEVICE_IP_ASSIGNMENT_TYPE.EXTERNAL:
            new_ip_address = factory.make_ip_address()
            new_params["ip_address"] = new_ip_address
        handler.update_interface(new_params)
        data = self.dehydrate_device(node, user)["interfaces"]
        self.assertEqual(1, len(data))
        self.assertEqual(data[0]["ip_assignment"], new_ip_assignment)
        if new_ip_assignment != DEVICE_IP_ASSIGNMENT_TYPE.DYNAMIC:
            self.assertEqual(data[0]["ip_address"], new_ip_address)

    @transactional
    def test_update_interface_updates_non_admin(self):
        user = factory.make_User()
        node = factory.make_Node(
            owner=user, interface=False, node_type=NODE_TYPE.DEVICE
        )
        handler = DeviceHandler(user, {}, None)
        name = factory.make_name("eth")
        mac_address = factory.make_mac_address()
        ip_assignment = DEVICE_IP_ASSIGNMENT_TYPE.DYNAMIC
        params = {
            "system_id": node.system_id,
            "name": name,
            "mac_address": mac_address,
            "ip_assignment": ip_assignment,
        }
        handler.create_interface(params)
        interface = node.current_config.interface_set.first()
        self.assertIsNotNone(interface)
        new_mac_address = factory.make_mac_address()
        new_params = {
            "system_id": node.system_id,
            "interface_id": interface.id,
            "name": name,
            "mac_address": new_mac_address,
            "ip_assignment": ip_assignment,
        }
        handler.update_interface(new_params)
        data = self.dehydrate_device(node, user)["interfaces"]
        self.assertEqual(1, len(data))
        self.assertEqual(data[0]["mac_address"], new_mac_address)

    @transactional
    def test_update_does_not_raise_validation_error_for_invalid_arch(self):
        user = factory.make_admin()
        handler = DeviceHandler(user, {}, None)
        node = factory.make_Node(interface=True, node_type=NODE_TYPE.DEVICE)
        node_data = self.dehydrate_device(node, user)
        arch = factory.make_name("arch")
        node_data["architecture"] = arch
        handler.update(node_data)
        # succeeds, because Devices don't care about architecture.

    @transactional
    def test_update_updates_node(self):
        user = factory.make_admin()
        handler = DeviceHandler(user, {}, None)
        node = factory.make_Node(interface=True, node_type=NODE_TYPE.DEVICE)
        node_data = self.dehydrate_device(node, user)
        new_zone = factory.make_Zone()
        new_hostname = factory.make_name("hostname")
        new_description = factory.make_name("description")
        new_tags = [factory.make_Tag(definition="").id for _ in range(3)]
        node_data["hostname"] = new_hostname
        node_data["description"] = new_description
        node_data["zone"] = {"name": new_zone.name}
        node_data["tags"] = new_tags
        updated_node = handler.update(node_data)
        self.assertEqual(updated_node["hostname"], new_hostname)
        self.assertEqual(updated_node["description"], new_description)
        self.assertEqual(updated_node["zone"]["id"], new_zone.id)
        self.assertCountEqual(updated_node["tags"], new_tags)

    @transactional
    def test_update_updates_node_non_admin_update_own(self):
        user = factory.make_User()
        handler = DeviceHandler(user, {}, None)
        node = factory.make_Node(
            owner=user, interface=True, node_type=NODE_TYPE.DEVICE
        )
        node_data = self.dehydrate_device(node, user)
        new_zone = factory.make_Zone()
        new_hostname = factory.make_name("hostname")
        new_tags = [factory.make_Tag(definition="").id for _ in range(3)]
        node_data["hostname"] = new_hostname
        node_data["zone"] = {"name": new_zone.name}
        node_data["tags"] = new_tags
        updated_node = handler.update(node_data)
        self.assertEqual(updated_node["hostname"], new_hostname)
        self.assertEqual(updated_node["zone"]["id"], new_zone.id)
        self.assertCountEqual(updated_node["tags"], new_tags)

    @transactional
    def test_update_updates_node_non_admin_not_update_own(self):
        user1 = factory.make_User()
        user2 = factory.make_User()
        handler = DeviceHandler(user1, {}, None)
        node = factory.make_Node(
            owner=user2, interface=True, node_type=NODE_TYPE.DEVICE
        )
        node_data = self.dehydrate_device(node, user1)
        new_zone = factory.make_Zone()
        new_hostname = factory.make_name("hostname")
        node_data["hostname"] = new_hostname
        node_data["zone"] = {"name": new_zone.name}
        self.assertRaises(HandlerDoesNotExistError, handler.update, node_data)

    @transactional
    def test_update_owned_with_rbac(self):
        rbac = self.useFixture(RBACEnabled())
        user = factory.make_User(is_local=False)
        rbac.store.allow(
            user.username, factory.make_ResourcePool(), "admin-machines"
        )
        node = factory.make_Node(owner=user, node_type=NODE_TYPE.DEVICE)
        handler = DeviceHandler(user, {}, None)
        new_hostname = factory.make_name("hostname")
        updated_node = handler.update(
            {"system_id": node.system_id, "hostname": new_hostname}
        )
        self.assertEqual(updated_node["hostname"], new_hostname)

    @transactional
    def test_delete_interface_admin(self):
        user = factory.make_admin()
        node = factory.make_Node(node_type=NODE_TYPE.DEVICE)
        handler = DeviceHandler(user, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        handler.delete_interface(
            {"system_id": node.system_id, "interface_id": interface.id}
        )
        self.assertIsNone(reload_object(interface))

    @transactional
    def test_delete_interface_non_admin(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user, node_type=NODE_TYPE.DEVICE)
        handler = DeviceHandler(user, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        handler.delete_interface(
            {"system_id": node.system_id, "interface_id": interface.id}
        )
        self.assertIsNone(reload_object(interface))

    @transactional
    def test_link_subnet_calls_update_link_by_id_if_link_id(self):
        user = factory.make_admin()
        node = factory.make_Node(node_type=NODE_TYPE.DEVICE)
        handler = DeviceHandler(user, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        subnet = factory.make_Subnet()
        sip = factory.make_StaticIPAddress(interface=interface)
        link_id = sip.id
        ip_assignment = factory.pick_enum(DEVICE_IP_ASSIGNMENT_TYPE)
        if ip_assignment == DEVICE_IP_ASSIGNMENT_TYPE.STATIC:
            mode = INTERFACE_LINK_TYPE.STATIC
        elif ip_assignment == DEVICE_IP_ASSIGNMENT_TYPE.DYNAMIC:
            mode = INTERFACE_LINK_TYPE.DHCP
        else:
            mode = INTERFACE_LINK_TYPE.LINK_UP
        ip_address = factory.make_ip_address()
        self.patch_autospec(Interface, "update_link_by_id")
        handler.link_subnet(
            {
                "system_id": node.system_id,
                "interface_id": interface.id,
                "link_id": link_id,
                "subnet": subnet.id,
                "ip_assignment": ip_assignment,
                "ip_address": ip_address,
            }
        )
        self.assertThat(
            Interface.update_link_by_id,
            MockCalledOnceWith(
                ANY, link_id, mode, subnet, ip_address=ip_address
            ),
        )

    @transactional
    def test_link_subnet_calls_link_subnet_if_link_id_deleted(self):
        user = factory.make_admin()
        node = factory.make_Node(node_type=NODE_TYPE.DEVICE)
        handler = DeviceHandler(user, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        subnet = factory.make_Subnet()
        sip = factory.make_StaticIPAddress(interface=interface, subnet=subnet)
        link_id = sip.id
        ip_assignment = factory.pick_enum(DEVICE_IP_ASSIGNMENT_TYPE)
        if ip_assignment == DEVICE_IP_ASSIGNMENT_TYPE.STATIC:
            mode = INTERFACE_LINK_TYPE.STATIC
        elif ip_assignment == DEVICE_IP_ASSIGNMENT_TYPE.DYNAMIC:
            mode = INTERFACE_LINK_TYPE.DHCP
        else:
            mode = INTERFACE_LINK_TYPE.LINK_UP
        ip_address = factory.make_ip_address()
        sip.delete()
        self.patch_autospec(Interface, "link_subnet")
        handler.link_subnet(
            {
                "system_id": node.system_id,
                "interface_id": interface.id,
                "subnet": subnet.id,
                "link_id": link_id,
                "ip_assignment": ip_assignment,
                "ip_address": ip_address,
            }
        )
        if ip_assignment == DEVICE_IP_ASSIGNMENT_TYPE.STATIC:
            self.assertThat(
                Interface.link_subnet,
                MockCalledOnceWith(ANY, mode, subnet, ip_address=ip_address),
            )
        else:
            self.assertThat(Interface.link_subnet, MockNotCalled())

    @transactional
    def test_link_subnet_calls_link_subnet_if_not_link_id(self):
        user = factory.make_admin()
        node = factory.make_Node(node_type=NODE_TYPE.DEVICE)
        handler = DeviceHandler(user, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        subnet = factory.make_Subnet()
        ip_assignment = factory.pick_enum(DEVICE_IP_ASSIGNMENT_TYPE)
        if ip_assignment == DEVICE_IP_ASSIGNMENT_TYPE.STATIC:
            mode = INTERFACE_LINK_TYPE.STATIC
        elif ip_assignment == DEVICE_IP_ASSIGNMENT_TYPE.DYNAMIC:
            mode = INTERFACE_LINK_TYPE.DHCP
        else:
            mode = INTERFACE_LINK_TYPE.LINK_UP
        ip_address = factory.make_ip_address()
        self.patch_autospec(Interface, "link_subnet")
        handler.link_subnet(
            {
                "system_id": node.system_id,
                "interface_id": interface.id,
                "subnet": subnet.id,
                "ip_assignment": ip_assignment,
                "ip_address": ip_address,
            }
        )
        if ip_assignment == DEVICE_IP_ASSIGNMENT_TYPE.STATIC:
            self.assertThat(
                Interface.link_subnet,
                MockCalledOnceWith(ANY, mode, subnet, ip_address=ip_address),
            )
        else:
            self.assertThat(Interface.link_subnet, MockNotCalled())

    @transactional
    def test_unlink_subnet(self):
        user = factory.make_admin()
        node = factory.make_Node(node_type=NODE_TYPE.DEVICE)
        handler = DeviceHandler(user, {}, None)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        link_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="", interface=interface
        )
        handler.delete_interface(
            {
                "system_id": node.system_id,
                "interface_id": interface.id,
                "link_id": link_ip.id,
            }
        )
        self.assertIsNone(reload_object(link_ip))
