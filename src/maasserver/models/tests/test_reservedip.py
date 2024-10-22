# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests of the ReservedIP model."""

from django.core.exceptions import ValidationError
import pytest

from maasserver.models.reservedip import ReservedIP
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestReservedIP(MAASServerTestCase):
    """Test class for the ReservedIp model."""

    def test_create_reserved_ipv4(self):
        subnet = factory.make_Subnet(cidr="192.168.0.0/24")

        reserved_ip = ReservedIP(
            ip="192.168.0.15",
            subnet=subnet,
            mac_address="00:11:22:33:44:55",
            comment="this is a comment",
        )

        reserved_ip.full_clean()
        self.assertEqual(reserved_ip.ip, "192.168.0.15")
        self.assertEqual(reserved_ip.subnet.id, subnet.id)
        self.assertEqual(reserved_ip.mac_address, "00:11:22:33:44:55")
        self.assertEqual(reserved_ip.comment, "this is a comment")

    def test_create_reserved_ipv6(self):
        subnet = factory.make_Subnet(cidr="2002::/64")
        ip = factory.pick_ip_in_Subnet(subnet=subnet)
        reserved_ip = ReservedIP(
            ip=ip,
            subnet=subnet,
            mac_address="00:11:22:33:44:55",
            comment="this is a comment",
        )

        reserved_ip.full_clean()
        self.assertEqual(reserved_ip.ip, ip)
        self.assertEqual(reserved_ip.subnet.id, subnet.id)
        self.assertEqual(reserved_ip.mac_address, "00:11:22:33:44:55")
        self.assertEqual(reserved_ip.comment, "this is a comment")

    def test_create_requires_a_valid_ip_address(self):
        subnet = factory.make_Subnet(cidr="192.168.0.0/24")

        msgs = (
            "This field cannot be null.",
            "Enter a valid IPv4 or IPv6 address.",
        )
        for value, msg in [
            (None, {"ip": [msgs[0]]}),
            ("192.168.x.10", {"ip": [msgs[1]]}),
        ]:
            reserved_ip = ReservedIP(
                ip=value,
                subnet=subnet,
                mac_address="00:11:22:33:44:55",
                comment="Test: creating a reserved IP",
            )

            with pytest.raises(ValidationError) as exc_info:
                reserved_ip.full_clean()
            self.assertEqual(exc_info.value.message_dict, msg)

    def test_create_requires_ip_address_has_not_been_reserved(self):
        subnet = factory.make_Subnet(cidr="192.168.0.0/24")

        ReservedIP(
            ip="192.168.0.15",
            mac_address=factory.make_mac_address(),
            subnet=subnet,
        ).save()

        with pytest.raises(ValidationError) as exc_info:
            ReservedIP(
                ip="192.168.0.15",
                mac_address=factory.make_mac_address(),
                subnet=subnet,
            ).full_clean()
        self.assertEqual(
            exc_info.value.message_dict,
            {"ip": ["Reserved IP with this IP address already exists."]},
        )

    def test_create_empty_mac_address(self):
        subnet = factory.make_Subnet(cidr="192.168.0.0/24")

        # valid values for mac_address
        reserved_ip = ReservedIP(
            ip="192.168.0.10",
            subnet=subnet,
            mac_address=None,
        )

        with pytest.raises(ValidationError) as exc_info:
            reserved_ip.full_clean()
        self.assertEqual(
            exc_info.value.message_dict,
            {"mac_address": ["This field cannot be null."]},
        )

    def test_create_invalid_mac_address(self):
        subnet = factory.make_Subnet(cidr="192.168.0.0/24")

        # no valid values for mac_address
        reserved_ip = ReservedIP(
            ip="192.168.0.10",
            subnet=subnet,
            mac_address="00:11:22:33:44:gg",
            comment="Test: creating a reserved IP",
        )
        with pytest.raises(ValidationError) as exc_info:
            reserved_ip.full_clean()
        self.assertEqual(
            exc_info.value.message_dict,
            {
                "mac_address": [
                    "'00:11:22:33:44:gg' is not a valid MAC address."
                ]
            },
        )

    def test_reserved_ip_to_str(self):
        fabric = factory.make_Fabric(name="fabric")
        vlan = factory.make_VLAN(name="vlan", fabric=fabric)
        subnet = factory.make_Subnet(cidr="10.0.0.0/24", vlan=vlan)

        self.assertEqual(
            str(
                ReservedIP(
                    ip="10.0.0.55",
                    subnet=subnet,
                    mac_address=None,
                )
            ),
            "10.0.0.55 (10.0.0.0/24)",
        )

        self.assertEqual(
            str(
                ReservedIP(
                    ip="10.0.0.55",
                    subnet=subnet,
                    mac_address="00:11:22:33:44:55",
                )
            ),
            "10.0.0.55 (10.0.0.0/24), 00:11:22:33:44:55",
        )

        self.assertEqual(
            str(
                ReservedIP(
                    ip="10.0.0.55",
                    subnet=subnet,
                    mac_address=None,
                    comment="this is a comment.",
                )
            ),
            "10.0.0.55 (10.0.0.0/24), this is a comment.",
        )

        self.assertEqual(
            str(
                ReservedIP(
                    ip="10.0.0.55",
                    subnet=subnet,
                    mac_address="00:11:22:33:44:55",
                    comment="this is a comment.",
                )
            ),
            "10.0.0.55 (10.0.0.0/24), 00:11:22:33:44:55, this is a comment.",
        )
