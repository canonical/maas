# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasserver.forms.reservedip import ReservedIPForm
from maasserver.models.reservedip import ReservedIP
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestReservedIPForm(MAASServerTestCase):
    def test_empty_form_fails_validation(self):
        form = ReservedIPForm({})
        self.assertFalse(form.is_valid())

    def test_form_requires_ip(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        vlan = subnet.vlan
        data = {
            "subnet": subnet.id,
            "vlan": vlan,
            "mac_address": factory.make_mac_address(),
            "comment": factory.make_name("comment"),
        }

        form = ReservedIPForm(data)

        self.assertFalse(form.is_valid())
        self.assertIn("This field is required.", form.errors["ip"])

    def test_form_requires_subnet(self):
        data = {
            "ip": "10.0.0.15",
            "mac_address": factory.make_mac_address(),
            "comment": factory.make_name("comment"),
        }

        form = ReservedIPForm(data)

        self.assertFalse(form.is_valid())
        self.assertIn("This field is required.", form.errors["subnet"])

    def test_subnet_and_vlan_are_optional_if_they_can_be_found(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        vlan = subnet.vlan
        data = {
            "ip": "10.0.0.15",
            "mac_address": factory.make_mac_address(),
            "comment": factory.make_name("comment"),
        }

        form = ReservedIPForm(data)

        self.assertTrue(form.is_valid())
        reserved_ip = form.save()
        self.assertEqual(reserved_ip.subnet, subnet)
        self.assertEqual(reserved_ip.vlan, vlan)

    def test_mac_address_is_optional(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        vlan = subnet.vlan
        data = {
            "ip": "10.0.0.15",
            "subnet": subnet.id,
            "vlan": vlan.id,
            "comment": factory.make_name("comment"),
        }

        form = ReservedIPForm(data)

        self.assertTrue(form.is_valid())
        reserved_ip = form.save()
        self.assertEqual(reserved_ip.mac_address, None)

    def test_comment_is_optional(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        data = {
            "ip": "10.0.0.15",
            "subnet": subnet.id,
            "mac_address": factory.make_mac_address(),
        }

        form = ReservedIPForm(data)

        self.assertTrue(form.is_valid())
        reserved_ip = form.save()
        self.assertEqual(reserved_ip.comment, "")

    def test_create_reserved_ip(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        vlan = subnet.vlan
        data = {
            "ip": "10.0.0.15",
            "subnet": subnet.id,
            "vlan": vlan.id,
            "mac_address": "00:11:22:33:44:55",
            "comment": "this is a comment",
        }

        form = ReservedIPForm(data)

        self.assertTrue(form.is_valid())
        reserved_ip = form.save()
        self.assertEqual(reserved_ip.ip, "10.0.0.15")
        self.assertEqual(reserved_ip.subnet, subnet)
        self.assertEqual(reserved_ip.vlan, vlan)
        self.assertEqual(reserved_ip.mac_address, "00:11:22:33:44:55")
        self.assertEqual(reserved_ip.comment, "this is a comment")

    def test_update(self):
        factory.make_Subnet(cidr="10.0.0.0/24")
        (reserved_ip := ReservedIP(ip="10.0.0.121")).save()
        data = {"comment": "this is a comment"}

        form = ReservedIPForm(instance=reserved_ip, data=data)

        self.assertTrue(form.is_valid())
        reserved_ip = form.save()
        self.assertEqual(reserved_ip.ip, "10.0.0.121")
        self.assertEqual(reserved_ip.comment, "this is a comment")
