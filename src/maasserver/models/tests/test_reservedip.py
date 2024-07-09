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
        subnet_1 = factory.make_Subnet(cidr="192.168.0.0/24")
        vlan_1 = subnet_1.vlan
        subnet_2 = factory.make_Subnet(cidr="192.168.0.0/16")
        vlan_2 = subnet_2.vlan

        # test that create() can populate vlan and subnet if they are not
        # provided
        for test_vlan, test_subnet in zip(
            [None, None, vlan_1, vlan_1, vlan_2],
            [None, subnet_1, None, subnet_2],
        ):
            reserved_ip = ReservedIP(
                ip="192.168.0.15",
                subnet=test_subnet,
                vlan=test_vlan,
                mac_address="00:11:22:33:44:55",
                comment="this is a comment",
            )

            reserved_ip.full_clean()
            self.assertEqual(reserved_ip.ip, "192.168.0.15")
            self.assertEqual(
                reserved_ip.subnet.id,
                test_subnet.id if test_subnet is not None else subnet_1.id,
            )
            self.assertEqual(
                reserved_ip.vlan.id,
                test_vlan.id if test_vlan is not None else vlan_1.id,
            )
            self.assertEqual(reserved_ip.mac_address, "00:11:22:33:44:55")
            self.assertEqual(reserved_ip.comment, "this is a comment")

        # test that create() reserved IPs in the same VLAN with undefined MAC
        # address does not raise an error:
        # - If mac_address is stored as empty string (rather than as null) the
        #   uniqueness vlan-mac_address avoids to create more than 1 reserved
        #   IP with undefined MAC addresses in a VLAN.
        ReservedIP(
            ip="192.168.0.215",
            subnet=subnet_1,
            vlan=subnet_1.vlan,
        ).save()
        ReservedIP(
            ip="192.168.0.226",
            subnet=subnet_1,
            vlan=subnet_1.vlan,
        ).save()

    def test_create_reserved_ipv6(self):
        subnet_1 = factory.make_Subnet(cidr="2001::/64")
        vlan_1 = subnet_1.vlan
        subnet_2 = factory.make_Subnet(cidr="2001::/56")
        vlan_2 = subnet_2.vlan

        # testing that create() can populate vlan and subnet if they are not
        # provided
        for test_vlan, test_subnet in zip(
            [None, None, vlan_1, vlan_1, vlan_2],
            [None, subnet_1, None, subnet_2],
        ):
            reserved_ip = ReservedIP(
                ip="2001::45",
                subnet=test_subnet,
                vlan=test_vlan,
                mac_address="00:11:22:33:44:55",
                comment="this is a comment",
            )

            reserved_ip.full_clean()
            self.assertEqual(reserved_ip.ip, "2001::45")
            self.assertEqual(
                reserved_ip.subnet.id,
                test_subnet.id if test_subnet is not None else subnet_1.id,
            )
            self.assertEqual(
                reserved_ip.vlan.id,
                test_vlan.id if test_vlan is not None else vlan_1.id,
            )
            self.assertEqual(reserved_ip.mac_address, "00:11:22:33:44:55")
            self.assertEqual(reserved_ip.comment, "this is a comment")

    def test_create_requires_a_valid_ip_address(self):
        subnet = factory.make_Subnet(cidr="192.168.0.0/24")
        vlan = subnet.vlan

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
                vlan=vlan,
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
            subnet=subnet,
        ).save()

        with pytest.raises(ValidationError) as exc_info:
            ReservedIP(
                ip="192.168.0.15",
                subnet=subnet,
            ).full_clean()
        self.assertEqual(
            exc_info.value.message_dict,
            {"ip": ["Reserved IP with this IP address already exists."]},
        )

    def test_create_requires_mac_address_not_been_reserved_in_the_same_vlan(
        self,
    ):
        subnet_1 = factory.make_Subnet(cidr="192.168.0.0/24")
        ReservedIP(
            ip="192.168.0.15",
            subnet=subnet_1,
            mac_address="00:11:22:33:44:55",
        ).save()

        # same device (mac address) in the same VLAN is not allowed
        with pytest.raises(ValidationError) as exc_info:
            ReservedIP(
                ip="192.168.0.16",
                subnet=subnet_1,
                mac_address="00:11:22:33:44:55",
            ).save()
        self.assertEqual(
            exc_info.value.message_dict,
            {
                "__all__": [
                    "Reserved IP with this MAC address and VLAN already exists."
                ]
            },
        )

        # same device (mac address) in the another VLAN is allowed
        subnet_2 = factory.make_Subnet(cidr="10.0.0.0/24")
        ReservedIP(
            ip="10.0.0.101",
            vlan=subnet_2.vlan,
            mac_address="00:11:22:33:44:55",
        ).save()

    def test_create_requires_a_suitable_subnet(self):
        # no available subnet for the IP provided
        reserved_ip = ReservedIP(
            ip="192.200.0.10",
            mac_address="00:11:22:33:44:55",
            comment="Test: creating a reserved IP",
        )

        with pytest.raises(ValidationError) as exc_info:
            reserved_ip.full_clean()

        self.assertEqual(
            exc_info.value.message_dict,
            {"subnet": ["There is no suitable subnet for the IP provided."]},
        )

        # IP is not within the range of the provided subnet
        subnet = factory.make_Subnet(cidr="192.168.0.0/24")
        reserved_ip = ReservedIP(
            ip="192.168.1.10",
            subnet=subnet,
            mac_address="00:11:22:33:44:55",
            comment="Test: creating a reserved IP",
        )

        with pytest.raises(ValidationError) as exc_info:
            reserved_ip.full_clean()
        self.assertEqual(
            exc_info.value.message_dict,
            {"ip": ["The provided IP is not part of the subnet."]},
        )

    def test_create_requires_ip_not_to_be_network_address_ipv4(self):
        subnet = factory.make_Subnet(cidr="192.168.0.0/24")
        reserved_ip = ReservedIP(
            ip="192.168.0.0",
            subnet=subnet,
            mac_address="00:11:22:33:44:55",
            comment="Test: creating a reserved IP",
        )

        with pytest.raises(ValidationError) as exc_info:
            reserved_ip.full_clean()

        self.assertEqual(
            exc_info.value.message_dict,
            {"ip": ["The network address cannot be a reserved IP."]},
        )

    def test_create_requires_ip_not_to_be_network_address_ipv6(self):
        subnet = factory.make_Subnet(cidr="2002::/64")
        reserved_ip = ReservedIP(
            ip="2002::",
            subnet=subnet,
            mac_address="00:11:22:33:44:55",
            comment="Test: creating a reserved IP",
        )

        with pytest.raises(ValidationError) as exc_info:
            reserved_ip.full_clean()

        self.assertEqual(
            exc_info.value.message_dict,
            {"ip": ["The network address cannot be a reserved IP."]},
        )

    def test_create_requires_ip_not_to_be_broadcast_address(self):
        subnet = factory.make_Subnet(cidr="192.168.0.0/24")
        reserved_ip = ReservedIP(
            ip="192.168.0.255",
            subnet=subnet,
            mac_address="00:11:22:33:44:55",
            comment="Test: creating a reserved IP",
        )

        with pytest.raises(ValidationError) as exc_info:
            reserved_ip.full_clean()

        self.assertEqual(
            exc_info.value.message_dict,
            {"ip": ["The broadcast address cannot be a reserved IP."]},
        )

    def test_create_requires_a_valid_mac_address(self):
        subnet = factory.make_Subnet(cidr="192.168.0.0/24")

        # valid values for mac_address
        ReservedIP(
            ip="192.168.0.10",
            subnet=subnet,
            mac_address=None,
        ).clean_fields()
        ReservedIP(
            ip="192.168.0.10",
            subnet=subnet,
            mac_address="00:11:22:33:44:55",
        ).clean_fields()

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

        reserved_ip = ReservedIP(
            ip="192.168.0.10",
            subnet=subnet,
            mac_address="0011:22:33:44:55",
            comment="Test: creating a reserved IP",
        )
        with pytest.raises(ValidationError) as exc_info:
            reserved_ip.full_clean()
        self.assertEqual(
            exc_info.value.message_dict,
            {
                "mac_address": [
                    "'0011:22:33:44:55' is not a valid MAC address."
                ]
            },
        )

    def test_ip_is_in_subnet(self):
        subnet = factory.make_Subnet(cidr="192.168.0.0/24")
        reserved_ip = ReservedIP(
            ip="192.168.1.10",
            subnet=subnet,
            mac_address=None,
        )

        with pytest.raises(Exception) as exc_info:
            reserved_ip.clean()

        self.assertEqual(
            exc_info.value.message_dict,
            {"ip": ["The provided IP is not part of the subnet."]},
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
            "10.0.0.55 (10.0.0.0/24, fabric.vlan)",
        )

        self.assertEqual(
            str(
                ReservedIP(
                    ip="10.0.0.55",
                    subnet=subnet,
                    mac_address="00:11:22:33:44:55",
                )
            ),
            "10.0.0.55 (10.0.0.0/24, fabric.vlan), 00:11:22:33:44:55",
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
            "10.0.0.55 (10.0.0.0/24, fabric.vlan), this is a comment.",
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
            "10.0.0.55 (10.0.0.0/24, fabric.vlan), 00:11:22:33:44:55, this is a comment.",
        )
