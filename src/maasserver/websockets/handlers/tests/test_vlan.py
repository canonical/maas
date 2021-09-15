# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.vlan`"""


import random

from testtools import ExpectedException
from testtools.matchers import Contains, ContainsDict, Equals, Is

from maasserver.enum import INTERFACE_TYPE
from maasserver.models.vlan import VLAN
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.websockets.base import (
    dehydrate_datetime,
    HandlerPermissionError,
    HandlerValidationError,
)
from maasserver.websockets.handlers.vlan import VLANHandler


class TestVLANHandler(MAASServerTestCase):
    def dehydrate_vlan(self, vlan, for_list=False):
        data = {
            "id": vlan.id,
            "name": vlan.name,
            "description": vlan.description,
            "vid": vlan.vid,
            "mtu": vlan.mtu,
            "fabric": vlan.fabric_id,
            "space": vlan.space_id,
            "updated": dehydrate_datetime(vlan.updated),
            "created": dehydrate_datetime(vlan.created),
            "dhcp_on": vlan.dhcp_on,
            "external_dhcp": vlan.external_dhcp,
            "primary_rack": vlan.primary_rack,
            "secondary_rack": vlan.secondary_rack,
            "relay_vlan": vlan.relay_vlan_id,
        }
        data["rack_sids"] = sorted(
            list(
                {
                    interface.node.system_id
                    for interface in vlan.interface_set.all()
                    if interface.node_id is not None
                    and interface.node.is_rack_controller
                }
            )
        )
        if not for_list:
            data["node_ids"] = sorted(
                list(
                    {
                        interface.node_id
                        for interface in vlan.interface_set.all()
                        if interface.node_id is not None
                    }
                )
            )
            data["space_ids"] = sorted(
                {subnet.space.id for subnet in vlan.subnet_set.all()}
            )
        return data

    def test_get(self):
        user = factory.make_User()
        handler = VLANHandler(user, {}, None)
        vlan = factory.make_VLAN(space=factory.make_Space())
        for _ in range(3):
            factory.make_Subnet(vlan=vlan)
        for _ in range(3):
            node = factory.make_Node(interface=True)
            interface = node.get_boot_interface()
            interface.vlan = vlan
            interface.save()
        self.assertEqual(
            self.dehydrate_vlan(vlan), handler.get({"id": vlan.id})
        )

    def test_list(self):
        user = factory.make_User()
        handler = VLANHandler(user, {}, None)
        factory.make_VLAN()
        expected_vlans = [
            self.dehydrate_vlan(vlan, for_list=True)
            for vlan in VLAN.objects.all()
        ]
        self.assertCountEqual(expected_vlans, handler.list({}))

    def test_create(self):
        admin = factory.make_admin()
        handler = VLANHandler(admin, {}, None)
        fabric = factory.make_Fabric()
        vid = random.randint(1, 4094)
        name = factory.make_name("vlan")
        new_vlan = handler.create(
            {"fabric": fabric.id, "vid": vid, "name": name}
        )
        self.assertThat(
            new_vlan,
            ContainsDict(
                {
                    "fabric": Equals(fabric.id),
                    "name": Equals(name),
                    "vid": Equals(vid),
                }
            ),
        )


class TestVLANHandlerDelete(MAASServerTestCase):
    def test_delete_as_admin_success(self):
        user = factory.make_admin()
        handler = VLANHandler(user, {}, None)
        vlan = factory.make_VLAN()
        handler.delete({"id": vlan.id})
        vlan = reload_object(vlan)
        self.assertThat(vlan, Equals(None))

    def test_delete_as_non_admin_asserts(self):
        user = factory.make_User()
        handler = VLANHandler(user, {}, None)
        vlan = factory.make_VLAN()
        with ExpectedException(HandlerPermissionError):
            handler.delete({"id": vlan.id})


class TestVLANHandlerConfigureDHCP(MAASServerTestCase):
    def test_configure_dhcp_with_one_parameter(self):
        user = factory.make_admin()
        handler = VLANHandler(user, {}, None)
        vlan = factory.make_VLAN()
        rack = factory.make_RackController()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        factory.make_ipv4_Subnet_with_IPRanges(vlan=vlan)
        handler.configure_dhcp(
            {"id": vlan.id, "controllers": [rack.system_id]}
        )
        vlan = reload_object(vlan)
        self.assertThat(vlan.dhcp_on, Equals(True))
        self.assertThat(vlan.primary_rack, Equals(rack))

    def test_configure_dhcp_with_two_parameters(self):
        user = factory.make_admin()
        handler = VLANHandler(user, {}, None)
        vlan = factory.make_VLAN()
        rack = factory.make_RackController()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        rack2 = factory.make_RackController()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=rack2, vlan=vlan)
        factory.make_ipv4_Subnet_with_IPRanges(vlan=vlan)
        handler.configure_dhcp(
            {"id": vlan.id, "controllers": [rack.system_id, rack2.system_id]}
        )
        vlan = reload_object(vlan)
        self.assertThat(vlan.dhcp_on, Equals(True))
        self.assertThat(vlan.primary_rack, Equals(rack))
        self.assertThat(vlan.secondary_rack, Equals(rack2))

    def test_configure_dhcp_with_duplicate_raises(self):
        user = factory.make_admin()
        handler = VLANHandler(user, {}, None)
        vlan = factory.make_VLAN()
        rack = factory.make_RackController()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        factory.make_ipv4_Subnet_with_IPRanges(vlan=vlan)
        with ExpectedException(HandlerValidationError):
            handler.configure_dhcp(
                {
                    "id": vlan.id,
                    "controllers": [rack.system_id, rack.system_id],
                }
            )

    def test_configure_dhcp_with_no_parameters_disables_dhcp(self):
        user = factory.make_admin()
        handler = VLANHandler(user, {}, None)
        rack = factory.make_RackController()
        vlan = factory.make_VLAN()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        vlan.dhcp_on = True
        vlan.primary_rack = rack
        vlan.save()
        factory.make_ipv4_Subnet_with_IPRanges(vlan=vlan)
        handler.configure_dhcp({"id": vlan.id, "controllers": []})
        vlan = reload_object(vlan)
        self.assertThat(vlan.dhcp_on, Equals(False))
        self.assertThat(vlan.primary_rack, Is(None))
        self.assertThat(vlan.secondary_rack, Is(None))

    def test_configure_dhcp_with_relay_vlan(self):
        user = factory.make_admin()
        handler = VLANHandler(user, {}, None)
        vlan = factory.make_VLAN()
        relay_vlan = factory.make_VLAN()
        handler.configure_dhcp(
            {"id": vlan.id, "controllers": [], "relay_vlan": relay_vlan.id}
        )
        vlan = reload_object(vlan)
        self.assertThat(vlan.dhcp_on, Equals(False))
        self.assertThat(vlan.relay_vlan, Equals(relay_vlan))

    def test_non_superuser_asserts(self):
        user = factory.make_User()
        handler = VLANHandler(user, {}, None)
        rack = factory.make_RackController()
        vlan = factory.make_VLAN()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        vlan.dhcp_on = True
        vlan.primary_rack = rack
        vlan.save()
        factory.make_ipv4_Subnet_with_IPRanges(vlan=vlan)
        with ExpectedException(HandlerPermissionError):
            handler.configure_dhcp({"id": vlan.id, "controllers": []})

    def test_configure_dhcp_optionally_creates_iprange(self):
        user = factory.make_admin()
        handler = VLANHandler(user, {}, None)
        vlan = factory.make_VLAN()
        rack = factory.make_RackController()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        subnet = factory.make_Subnet(
            vlan=vlan, cidr="10.0.0.0/24", gateway_ip=""
        )
        self.assertThat(subnet.get_dynamic_ranges().count(), Equals(0))
        handler.configure_dhcp(
            {
                "id": vlan.id,
                "controllers": [rack.system_id],
                "extra": {
                    "subnet": subnet.id,
                    "start": "10.0.0.2",
                    "end": "10.0.0.99",
                },
            }
        )
        vlan = reload_object(vlan)
        subnet = reload_object(subnet)
        self.assertThat(vlan.dhcp_on, Equals(True))
        self.assertThat(vlan.primary_rack, Equals(rack))
        self.assertThat(subnet.get_dynamic_ranges().count(), Equals(1))
        dynamic_range = subnet.get_dynamic_ranges().first()
        self.assertThat(dynamic_range.start_ip, Equals("10.0.0.2"))
        self.assertThat(dynamic_range.end_ip, Equals("10.0.0.99"))
        self.assertThat(dynamic_range.type, Equals("dynamic"))
        self.assertThat(dynamic_range.user_id, Equals(user.id))
        self.assertThat(dynamic_range.comment, Contains("Web UI"))

    def test_configure_dhcp_optionally_defines_gateway(self):
        user = factory.make_admin()
        handler = VLANHandler(user, {}, None)
        vlan = factory.make_VLAN()
        rack = factory.make_RackController()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        subnet = factory.make_Subnet(
            vlan=vlan, cidr="10.0.0.0/24", gateway_ip=""
        )
        factory.make_ipv4_Subnet_with_IPRanges(vlan=vlan)
        self.assertThat(subnet.get_dynamic_ranges().count(), Equals(0))
        handler.configure_dhcp(
            {
                "id": vlan.id,
                "controllers": [rack.system_id],
                "extra": {"subnet": subnet.id, "gateway": "10.0.0.1"},
            }
        )
        vlan = reload_object(vlan)
        subnet = reload_object(subnet)
        self.assertThat(vlan.dhcp_on, Equals(True))
        self.assertThat(vlan.primary_rack, Equals(rack))
        self.assertThat(subnet.get_dynamic_ranges().count(), Equals(0))
        self.assertThat(subnet.gateway_ip, Equals("10.0.0.1"))

    def test_configure_dhcp_optionally_defines_gateway_and_range(self):
        user = factory.make_admin()
        handler = VLANHandler(user, {}, None)
        vlan = factory.make_VLAN()
        rack = factory.make_RackController()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        subnet = factory.make_Subnet(
            vlan=vlan, cidr="10.0.0.0/24", gateway_ip=""
        )
        self.assertThat(subnet.get_dynamic_ranges().count(), Equals(0))
        handler.configure_dhcp(
            {
                "id": vlan.id,
                "controllers": [rack.system_id],
                "extra": {
                    "subnet": subnet.id,
                    "gateway": "10.0.0.1",
                    "start": "10.0.0.2",
                    "end": "10.0.0.99",
                },
            }
        )
        subnet = reload_object(subnet)
        vlan = reload_object(vlan)
        subnet = reload_object(subnet)
        self.assertThat(vlan.dhcp_on, Equals(True))
        self.assertThat(vlan.primary_rack, Equals(rack))
        self.assertThat(subnet.get_dynamic_ranges().count(), Equals(1))
        dynamic_range = subnet.get_dynamic_ranges().first()
        self.assertThat(subnet.gateway_ip, Equals("10.0.0.1"))
        self.assertThat(dynamic_range.start_ip, Equals("10.0.0.2"))
        self.assertThat(dynamic_range.end_ip, Equals("10.0.0.99"))
        self.assertThat(dynamic_range.type, Equals("dynamic"))
        self.assertThat(dynamic_range.user_id, Equals(user.id))
        self.assertThat(dynamic_range.comment, Contains("Web UI"))

    def test_configure_dhcp_ignores_empty_gateway(self):
        user = factory.make_admin()
        handler = VLANHandler(user, {}, None)
        vlan = factory.make_VLAN()
        rack = factory.make_RackController()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        subnet = factory.make_Subnet(
            vlan=vlan, cidr="10.0.0.0/24", gateway_ip=""
        )
        self.assertThat(subnet.get_dynamic_ranges().count(), Equals(0))
        handler.configure_dhcp(
            {
                "id": vlan.id,
                "controllers": [rack.system_id],
                "extra": {
                    "subnet": subnet.id,
                    "gateway": "",
                    "start": "10.0.0.2",
                    "end": "10.0.0.99",
                },
            }
        )
        subnet = reload_object(subnet)
        vlan = reload_object(vlan)
        subnet = reload_object(subnet)
        self.assertThat(vlan.dhcp_on, Equals(True))
        self.assertThat(vlan.primary_rack, Equals(rack))
        self.assertThat(subnet.get_dynamic_ranges().count(), Equals(1))
        dynamic_range = subnet.get_dynamic_ranges().first()
        self.assertThat(subnet.gateway_ip, Is(None))
        self.assertThat(dynamic_range.start_ip, Equals("10.0.0.2"))
        self.assertThat(dynamic_range.end_ip, Equals("10.0.0.99"))
        self.assertThat(dynamic_range.type, Equals("dynamic"))
        self.assertThat(dynamic_range.user_id, Equals(user.id))
        self.assertThat(dynamic_range.comment, Contains("Web UI"))

    def test_configure_dhcp_gateway_outside_subnet_raises(self):
        user = factory.make_admin()
        handler = VLANHandler(user, {}, None)
        vlan = factory.make_VLAN()
        rack = factory.make_RackController()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        subnet = factory.make_Subnet(
            vlan=vlan, cidr="10.0.0.0/24", gateway_ip=""
        )
        self.assertThat(subnet.get_dynamic_ranges().count(), Equals(0))
        with ExpectedException(ValueError):
            handler.configure_dhcp(
                {
                    "id": vlan.id,
                    "controllers": [rack.system_id],
                    "extra": {
                        "subnet": subnet.id,
                        "gateway": "1.0.0.1",
                        "start": "10.0.0.2",
                        "end": "10.0.0.99",
                    },
                }
            )

    def test_configure_dhcp_gateway_fe80_allowed(self):
        user = factory.make_admin()
        handler = VLANHandler(user, {}, None)
        vlan = factory.make_VLAN()
        rack = factory.make_RackController()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        subnet = factory.make_Subnet(
            vlan=vlan, cidr="2001:db8::/64", gateway_ip=""
        )
        self.assertThat(subnet.get_dynamic_ranges().count(), Equals(0))
        handler.configure_dhcp(
            {
                "id": vlan.id,
                "controllers": [rack.system_id],
                "extra": {
                    "subnet": subnet.id,
                    "gateway": "fe80::1",
                    "start": "2001:db8:0:0:1::",
                    "end": "2001:db8:0:0:1:ffff:ffff:ffff",
                },
            }
        )
        subnet = reload_object(subnet)
        self.assertEqual(subnet.gateway_ip, "fe80::1")

    def test_configure_dhcp_gateway_inside_range_raises(self):
        user = factory.make_admin()
        handler = VLANHandler(user, {}, None)
        vlan = factory.make_VLAN()
        rack = factory.make_RackController()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        subnet = factory.make_Subnet(
            vlan=vlan, cidr="10.0.0.0/24", gateway_ip=""
        )
        self.assertThat(subnet.get_dynamic_ranges().count(), Equals(0))
        with ExpectedException(ValueError):
            handler.configure_dhcp(
                {
                    "id": vlan.id,
                    "controllers": [rack.system_id],
                    "extra": {
                        "subnet": subnet.id,
                        "gateway": "10.0.0.1",
                        "start": "10.0.0.1",
                        "end": "10.0.0.99",
                    },
                }
            )
        vlan = reload_object(vlan)

    def test_configure_dhcp_gateway_raises_if_dynamic_range_required(self):
        user = factory.make_admin()
        handler = VLANHandler(user, {}, None)
        vlan = factory.make_VLAN()
        rack = factory.make_RackController()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        subnet = factory.make_Subnet(
            vlan=vlan, cidr="10.0.0.0/24", gateway_ip=""
        )
        self.assertThat(subnet.get_dynamic_ranges().count(), Equals(0))
        with ExpectedException(ValueError):
            handler.configure_dhcp(
                {
                    "id": vlan.id,
                    "controllers": [rack.system_id],
                    "extra": {
                        "subnet": subnet.id,
                        "gateway": "10.0.0.1",
                        "start": "",
                        "end": "",
                    },
                }
            )

    def test_configure_dhcp_ignores_undefined_subnet(self):
        user = factory.make_admin()
        handler = VLANHandler(user, {}, None)
        vlan = factory.make_VLAN()
        rack = factory.make_RackController()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        factory.make_ipv4_Subnet_with_IPRanges(vlan=vlan)
        handler.configure_dhcp(
            {
                "id": vlan.id,
                "controllers": [rack.system_id],
                "extra": {
                    "subnet": None,
                    "gateway": "",
                    "start": "",
                    "end": "",
                },
            }
        )
        vlan = reload_object(vlan)
        self.assertThat(vlan.dhcp_on, Equals(True))
        self.assertThat(vlan.primary_rack, Equals(rack))
