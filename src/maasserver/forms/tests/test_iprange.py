# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for IPRange forms."""


from unittest.mock import Mock

from maasserver.enum import IPRANGE_TYPE
from maasserver.forms.iprange import IPRangeForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestIPRangeForm(MAASServerTestCase):
    def test_empty_form_fails_validation(self):
        form = IPRangeForm({})
        self.assertFalse(form.is_valid(), dict(form.errors))

    def test_requires_start_ip(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        comment = factory.make_name("comment")
        form = IPRangeForm(
            {
                "subnet": subnet.id,
                "type": IPRANGE_TYPE.RESERVED,
                "end_ip": "10.0.0.150",
                "comment": comment,
            }
        )
        self.assertFalse(form.is_valid(), dict(form.errors))
        self.assertIn("This field is required.", form.errors["start_ip"])

    def test_requires_end_ip(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        comment = factory.make_name("comment")
        form = IPRangeForm(
            {
                "subnet": subnet.id,
                "type": IPRANGE_TYPE.RESERVED,
                "start_ip": "10.0.0.100",
                "comment": comment,
            }
        )
        self.assertFalse(form.is_valid(), dict(form.errors))
        self.assertIn("This field is required.", form.errors["end_ip"])

    def test_requires_type(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        comment = factory.make_name("comment")
        form = IPRangeForm(
            {
                "subnet": subnet.id,
                "start_ip": "10.0.0.100",
                "end_ip": "10.0.0.150",
                "comment": comment,
            }
        )
        self.assertFalse(form.is_valid(), dict(form.errors))
        self.assertIn("This field is required.", form.errors["type"])

    def test_requires_subnet(self):
        comment = factory.make_name("comment")
        form = IPRangeForm(
            {
                "type": IPRANGE_TYPE.RESERVED,
                "start_ip": "10.0.0.100",
                "end_ip": "10.0.0.150",
                "comment": comment,
            }
        )
        self.assertFalse(form.is_valid(), dict(form.errors))
        self.assertIn("This field is required.", form.errors["subnet"])

    def test_subnet_optional_if_it_can_be_found(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        comment = factory.make_name("comment")
        form = IPRangeForm(
            {
                "type": IPRANGE_TYPE.RESERVED,
                "start_ip": "10.0.0.100",
                "end_ip": "10.0.0.150",
                "comment": comment,
            }
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        iprange = form.save()
        self.assertEqual(iprange.subnet, subnet)

    def test_comment_optional(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        form = IPRangeForm(
            {
                "subnet": subnet.id,
                "type": IPRANGE_TYPE.RESERVED,
                "start_ip": "10.0.0.100",
                "end_ip": "10.0.0.150",
            }
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        iprange = form.save()
        self.assertEqual("", iprange.comment)

    def test_creates_iprange(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        comment = factory.make_name("comment")
        form = IPRangeForm(
            {
                "subnet": subnet.id,
                "type": IPRANGE_TYPE.RESERVED,
                "start_ip": "10.0.0.100",
                "end_ip": "10.0.0.150",
                "comment": comment,
            }
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        iprange = form.save()
        self.assertEqual(iprange.subnet, subnet)
        self.assertEqual(iprange.start_ip, "10.0.0.100")
        self.assertEqual(iprange.end_ip, "10.0.0.150")
        self.assertEqual(iprange.type, IPRANGE_TYPE.RESERVED)
        self.assertEqual(iprange.comment, comment)

    def test_creates_iprange_with_user(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        comment = factory.make_name("comment")
        request = Mock()
        request.user = factory.make_User()
        form = IPRangeForm(
            request=request,
            data={
                "subnet": subnet.id,
                "type": IPRANGE_TYPE.RESERVED,
                "start_ip": "10.0.0.100",
                "end_ip": "10.0.0.150",
                "comment": comment,
            },
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        iprange = form.save()
        self.assertEqual(iprange.subnet, subnet)
        self.assertEqual(iprange.start_ip, "10.0.0.100")
        self.assertEqual(iprange.end_ip, "10.0.0.150")
        self.assertEqual(iprange.type, IPRANGE_TYPE.RESERVED)
        self.assertEqual(iprange.comment, comment)
        self.assertEqual(iprange.user, request.user)

    def test_creates_iprange_with_reserved_ips(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        factory.make_ReservedIP(
            ip="10.0.0.100", mac_address="00:11:22:33:44:55", subnet=subnet
        )
        comment = factory.make_name("comment")
        form = IPRangeForm(
            {
                "type": IPRANGE_TYPE.DYNAMIC,
                "subnet": subnet.id,
                "start_ip": "10.0.0.100",
                "end_ip": "10.0.0.150",
                "comment": comment,
            }
        )
        self.assertFalse(form.is_valid(), dict(form.errors))
        self.assertEqual(
            {"__all__": ["The dynamic IP range can't include reserved IPs"]},
            form.errors,
        )

    def test_updates_iprange(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges()
        iprange = subnet.get_dynamic_ranges().first()
        new_comment = factory.make_name("comment")
        form = IPRangeForm(instance=iprange, data={"comment": new_comment})
        self.assertTrue(form.is_valid(), dict(form.errors))
        form.save()
        self.assertEqual(new_comment, reload_object(iprange).comment)

    def test_update_iprange_user(self):
        user = factory.make_User()
        subnet = factory.make_ipv4_Subnet_with_IPRanges()
        iprange = subnet.get_dynamic_ranges().first()
        form = IPRangeForm(instance=iprange, data={"user": user.username})
        self.assertTrue(form.is_valid(), dict(form.errors))
        form.save()
        self.assertEqual(user, reload_object(iprange).user)
