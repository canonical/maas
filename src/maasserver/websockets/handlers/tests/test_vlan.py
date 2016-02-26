# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.vlan`"""

__all__ = []

from django.core.exceptions import ValidationError
from maasserver.models.vlan import VLAN
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.handlers.timestampedmodel import dehydrate_datetime
from maasserver.websockets.handlers.vlan import VLANHandler
from testtools import ExpectedException
from testtools.matchers import (
    Equals,
    Is,
)


class TestVLANHandler(MAASServerTestCase):

    def dehydrate_vlan(self, vlan, for_list=False):
        data = {
            "id": vlan.id,
            "name": vlan.name,
            "vid": vlan.vid,
            "mtu": vlan.mtu,
            "fabric": vlan.fabric_id,
            "updated": dehydrate_datetime(vlan.updated),
            "created": dehydrate_datetime(vlan.created),
            "dhcp_on": vlan.dhcp_on,
            "primary_rack": vlan.primary_rack,
            "secondary_rack": vlan.secondary_rack,
            "subnet_ids": sorted([
                subnet.id
                for subnet in vlan.subnet_set.all()
            ]),
            "nodes_count": len({
                interface.node_id
                for interface in vlan.interface_set.all()
                if interface.node_id is not None
            }),
        }
        if not for_list:
            data['node_ids'] = sorted(list({
                interface.node_id
                for interface in vlan.interface_set.all()
                if interface.node_id is not None
            }))
            data['space_ids'] = sorted([
                subnet.space.id
                for subnet in vlan.subnet_set.all()
                ])
        return data

    def test_get(self):
        user = factory.make_User()
        handler = VLANHandler(user, {})
        vlan = factory.make_VLAN()
        for _ in range(3):
            factory.make_Subnet(vlan=vlan)
        for _ in range(3):
            node = factory.make_Node(interface=True)
            interface = node.get_boot_interface()
            interface.vlan = vlan
            interface.save()
        self.assertEqual(
            self.dehydrate_vlan(vlan),
            handler.get({"id": vlan.id}))

    def test_list(self):
        user = factory.make_User()
        handler = VLANHandler(user, {})
        factory.make_VLAN()
        expected_vlans = [
            self.dehydrate_vlan(vlan, for_list=True)
            for vlan in VLAN.objects.all()
            ]
        self.assertItemsEqual(
            expected_vlans,
            handler.list({}))


class TestVLANHandlerDelete(MAASServerTestCase):

    def test__delete_as_admin_success(self):
        user = factory.make_admin()
        handler = VLANHandler(user, {})
        vlan = factory.make_VLAN()
        handler.delete({
            "id": vlan.id,
        })
        vlan = reload_object(vlan)
        self.assertThat(vlan, Equals(None))

    def test__delete_as_non_admin_asserts(self):
        user = factory.make_User()
        handler = VLANHandler(user, {})
        vlan = factory.make_VLAN()
        with ExpectedException(AssertionError, "Permission denied."):
            handler.delete({
                "id": vlan.id,
            })

    def test__reloads_user(self):
        user = factory.make_admin()
        handler = VLANHandler(user, {})
        vlan = factory.make_VLAN()
        user.is_superuser = False
        user.save()
        with ExpectedException(AssertionError, "Permission denied."):
            handler.delete({
                "id": vlan.id,
            })


class TestVLANHandlerConfigureDHCP(MAASServerTestCase):

    def test__configure_dhcp_with_one_parameter(self):
        rack = factory.make_RackController()
        user = factory.make_admin()
        handler = VLANHandler(user, {})
        vlan = factory.make_VLAN()
        handler.configure_dhcp({
            "id": vlan.id,
            "controllers": [rack.system_id]
        })
        vlan = reload_object(vlan)
        self.assertThat(vlan.dhcp_on, Equals(True))
        self.assertThat(vlan.primary_rack, Equals(rack))

    def test__configure_dhcp_with_two_parameters(self):
        rack = factory.make_RackController()
        rack2 = factory.make_RackController()
        user = factory.make_admin()
        handler = VLANHandler(user, {})
        vlan = factory.make_VLAN()
        handler.configure_dhcp({
            "id": vlan.id,
            "controllers": [rack.system_id, rack2.system_id]
        })
        vlan = reload_object(vlan)
        self.assertThat(vlan.dhcp_on, Equals(True))
        self.assertThat(vlan.primary_rack, Equals(rack))
        self.assertThat(vlan.secondary_rack, Equals(rack2))

    def test__configure_dhcp_with_duplicate_raises(self):
        rack = factory.make_RackController()
        user = factory.make_admin()
        handler = VLANHandler(user, {})
        vlan = factory.make_VLAN()
        with ExpectedException(ValidationError):
            handler.configure_dhcp({
                "id": vlan.id,
                "controllers": [rack.system_id, rack.system_id]
            })

    def test__configure_dhcp_with_no_parameters_disables_dhcp(self):
        rack = factory.make_RackController()
        user = factory.make_admin()
        handler = VLANHandler(user, {})
        vlan = factory.make_VLAN(dhcp_on=True, primary_rack=rack)
        handler.configure_dhcp({
            "id": vlan.id,
            "controllers": []
        })
        vlan = reload_object(vlan)
        self.assertThat(vlan.dhcp_on, Equals(False))
        self.assertThat(vlan.primary_rack, Is(None))
        self.assertThat(vlan.secondary_rack, Is(None))

    def test__non_superuser_asserts(self):
        rack = factory.make_RackController()
        user = factory.make_User()
        handler = VLANHandler(user, {})
        vlan = factory.make_VLAN(dhcp_on=True, primary_rack=rack)
        with ExpectedException(AssertionError, "Permission denied."):
            handler.configure_dhcp({
                "id": vlan.id,
                "controllers": []
            })

    def test__non_superuser_reloads_user(self):
        rack = factory.make_RackController()
        user = factory.make_admin()
        handler = VLANHandler(user, {})
        user.is_superuser = False
        user.save()
        vlan = factory.make_VLAN(dhcp_on=True, primary_rack=rack)
        with ExpectedException(AssertionError, "Permission denied."):
            handler.configure_dhcp({
                "id": vlan.id,
                "controllers": []
            })
