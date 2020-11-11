# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the IPRange model."""


import random

from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from netaddr import IPNetwork
from testtools import ExpectedException

from maasserver.enum import IPADDRESS_TYPE, IPRANGE_TYPE
from maasserver.models import IPRange
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


def make_plain_subnet():
    return factory.make_Subnet(
        cidr="192.168.0.0/24", gateway_ip="192.168.0.1", dns_servers=[]
    )


def make_plain_ipv6_subnet():
    return factory.make_Subnet(
        cidr="2001::/64", gateway_ip="2001::1", dns_servers=[]
    )


class IPRangeTest(MAASServerTestCase):
    def test_create(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            start_ip="192.168.0.2",
            end_ip="192.168.0.254",
            type=IPRANGE_TYPE.RESERVED,
            user=factory.make_User(),
            comment="The quick brown fox jumps over the lazy dog.",
            subnet=subnet,
        )
        iprange.save()

    def test_requires_valid_ip_addresses(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            start_ip="x192.x168.x0.x1",
            end_ip="y192.y168.y0.y254",
            type=IPRANGE_TYPE.RESERVED,
            user=factory.make_User(),
            comment="The quick brown fox jumps over the lazy dog.",
            subnet=subnet,
        )
        with ExpectedException(ValidationError, ".*Enter a valid.*"):
            iprange.save()

    def test_requires_start_ip_address(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            start_ip="192.168.0.1",
            type=IPRANGE_TYPE.RESERVED,
            user=factory.make_User(),
            subnet=subnet,
            comment="The quick brown fox jumps over the lazy dog.",
        )
        with ExpectedException(ValidationError, ".*both required.*"):
            iprange.save()

    def test_requires_end_ip_address(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            end_ip="192.168.0.1",
            type=IPRANGE_TYPE.RESERVED,
            user=factory.make_User(),
            subnet=subnet,
            comment="The quick brown fox jumps over the lazy dog.",
        )
        with ExpectedException(ValidationError, ".*both required.*"):
            iprange.save()

    def test_requires_matching_address_family(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            start_ip="192.168.0.1",
            end_ip="2001:db8::1",
            type=IPRANGE_TYPE.RESERVED,
            user=factory.make_User(),
            subnet=subnet,
            comment="The quick brown fox jumps over the lazy dog.",
        )
        with ExpectedException(ValidationError, ".*same address family.*"):
            iprange.save()

    def test_requires_subnet(self):
        iprange = IPRange(
            start_ip="192.168.0.1",
            end_ip="192.168.0.254",
            type=IPRANGE_TYPE.RESERVED,
            user=factory.make_User(),
            comment="The quick brown weasel jumps over the lazy elephant.",
        )
        with ExpectedException(IntegrityError):
            iprange.save()

    def test_requires_start_ip_and_end_ip(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
            user=factory.make_User(),
            comment="The quick brown cow jumps over the lazy moon.",
        )
        with ExpectedException(ValidationError, ".*are both required.*"):
            iprange.save()

    def test_requires_start_ip_and_end_ip_to_be_within_subnet(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            start_ip="192.168.1.1",
            end_ip="192.168.1.254",
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
            user=factory.make_User(),
            comment="The quick brown cow jumps over the lazy moon.",
        )
        with ExpectedException(
            ValidationError, ".*addresses must be within subnet.*"
        ):
            iprange.save()

    def test_requires_start_ip_to_be_within_subnet(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            start_ip="19.168.0.1",
            end_ip="192.168.0.254",
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            user=factory.make_User(),
            comment="The quick brown cow jumps over the lazy moon.",
        )
        with ExpectedException(
            ValidationError, ".*Start IP address must be within subnet.*"
        ):
            iprange.save()

    def test_requires_end_ip_to_be_within_subnet(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            start_ip="192.168.0.1",
            end_ip="193.168.0.254",
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            user=factory.make_User(),
            comment="The quick brown cow jumps over the lazy moon.",
        )
        with ExpectedException(
            ValidationError, ".*End IP address must be within subnet.*"
        ):
            iprange.save()

    def test_requires_end_ip_to_be_greater_or_equal_to_start_ip(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            start_ip="192.168.0.2",
            end_ip="192.168.0.1",
            user=factory.make_User(),
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            comment="The quick brown cow jumps over the lazy moon.",
        )
        with ExpectedException(
            ValidationError, ".*End IP address must not be less than.*"
        ):
            iprange.save()

    def test_requires_end_ip_to_not_be_broadcast(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            start_ip="192.168.0.254",
            end_ip="192.168.0.255",
            user=factory.make_User(),
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
        )
        with ExpectedException(
            ValidationError,
            ".*Broadcast address cannot be included in IP range.*",
        ):
            iprange.save()

    def test_requires_start_ip_to_not_be_network(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            start_ip="192.168.0.0",
            end_ip="192.168.0.5",
            user=factory.make_User(),
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
        )
        with ExpectedException(
            ValidationError,
            ".*Reserved network address cannot be included in IP range.*",
        ):
            iprange.save()

    def test_requires_start_ip_to_not_be_ipv6_reserved_anycast(self):
        subnet = make_plain_ipv6_subnet()
        iprange = IPRange(
            start_ip="2001::",
            end_ip="2001::1",
            user=factory.make_User(),
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
        )
        with ExpectedException(
            ValidationError,
            ".*Reserved network address cannot be included in IP range.*",
        ):
            iprange.save()

    def test_requires_256_addresses_for_ipv6_dynamic(self):
        subnet = factory.make_Subnet(
            cidr="2001:db8::/64", gateway_ip="fe80::1", dns_servers=[]
        )
        iprange = IPRange(
            start_ip="2001:db8::1",
            end_ip="2001:db8::ff",
            user=factory.make_User(),
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            comment="This is a comment.",
        )
        with ExpectedException(
            ValidationError,
            ".*IPv6 dynamic range must be at least 256 addresses in size.",
        ):
            iprange.save()

    def test_requires_type(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            start_ip="192.168.0.1",
            end_ip="192.168.0.254",
            user=factory.make_User(),
            subnet=subnet,
            comment="The quick brown mule jumps over the lazy cheetah.",
        )
        with ExpectedException(ValidationError):
            iprange.save()

    def test_user_optional(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            start_ip="192.168.0.2",
            end_ip="192.168.0.254",
            type=IPRANGE_TYPE.DYNAMIC,
            subnet=subnet,
            comment="The quick brown owl jumps over the lazy alligator.",
        )
        iprange.save()

    def test_comment_optional(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            start_ip="192.168.0.2",
            end_ip="192.168.0.254",
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
            user=factory.make_User(),
        )
        iprange.save()


class TestIPRangeSavePreventsOverlapping(MAASServerTestCase):

    overlaps = ".*Requested %s range conflicts with an existing %srange.*"
    dynamic_overlaps = overlaps % (IPRANGE_TYPE.DYNAMIC, "IP address or ")
    reserved_overlaps = overlaps % (IPRANGE_TYPE.RESERVED, "")

    no_room = ".*There is no room for any %s ranges on this subnet.*"
    dynamic_no_room = no_room % IPRANGE_TYPE.DYNAMIC
    reserved_no_room = no_room % IPRANGE_TYPE.RESERVED

    def test_no_save_duplicate_ipranges(self):
        subnet = make_plain_subnet()
        IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.100",
            end_ip="192.168.0.150",
        ).save()
        # Make the same range again, should fail to save.
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.100",
            end_ip="192.168.0.150",
        )
        with ExpectedException(ValidationError, self.dynamic_overlaps):
            iprange.save()

    def test_no_save_range_overlap_begin(self):
        subnet = make_plain_subnet()
        IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.100",
            end_ip="192.168.0.150",
        ).save()
        # Make an overlapping range across start_ip, should fail to save.
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.90",
            end_ip="192.168.0.100",
        )
        with ExpectedException(ValidationError, self.dynamic_overlaps):
            iprange.save()
        # Try as reserved range.
        iprange.type = IPRANGE_TYPE.RESERVED
        with ExpectedException(ValidationError, self.reserved_overlaps):
            iprange.save()

    def test_no_save_range_overlap_end(self):
        subnet = make_plain_subnet()
        IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.100",
            end_ip="192.168.0.150",
        ).save()
        # Make an overlapping range across end_ip, should fail to save.
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.140",
            end_ip="192.168.0.160",
        )
        with ExpectedException(ValidationError, self.dynamic_overlaps):
            iprange.save()

    def test_no_save_range_within_ranges(self):
        subnet = make_plain_subnet()
        IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.100",
            end_ip="192.168.0.150",
        ).save()
        # Make a contained range, should not save.
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.110",
            end_ip="192.168.0.140",
        )
        with ExpectedException(ValidationError, self.dynamic_overlaps):
            iprange.save()

    def test_no_save_range_spanning_existing_range(self):
        subnet = make_plain_subnet()
        IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.100",
            end_ip="192.168.0.150",
        ).save()
        # Make a contained range, should not save.
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.10",
            end_ip="192.168.0.240",
        )
        with ExpectedException(ValidationError, self.dynamic_overlaps):
            iprange.save()

    def test_no_save_range_within_existing_range(self):
        subnet = make_plain_subnet()
        IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.100",
            end_ip="192.168.0.150",
        ).save()
        # Make a contained range, should not save.
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.110",
            end_ip="192.168.0.140",
        )
        with ExpectedException(ValidationError, self.dynamic_overlaps):
            iprange.save()

    def test_no_save_range_within_existing_reserved_range(self):
        subnet = make_plain_subnet()
        IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
            start_ip="192.168.0.100",
            end_ip="192.168.0.150",
        ).save()
        # Make a contained range, should not save.
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.110",
            end_ip="192.168.0.140",
        )
        with ExpectedException(ValidationError, self.dynamic_overlaps):
            iprange.save()

    def test_no_save_when_no_ranges_available(self):
        subnet = make_plain_subnet()
        # Reserve the whole subnet, except gateway.
        IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
            start_ip="192.168.0.2",
            end_ip="192.168.0.254",
        ).save()
        # Try to make dynamic range at gateway (anywhere, actually) = no room!
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.1",
            end_ip="192.168.0.1",
        )
        with ExpectedException(ValidationError, self.dynamic_no_room):
            iprange.save()
        # We CAN reserve the gateway addr.
        IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
            start_ip="192.168.0.1",
            end_ip="192.168.0.1",
        ).save()
        # But now it's full - trying to save any reserved = no room!
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
            start_ip="192.168.0.25",
            end_ip="192.168.0.35",
        )
        with ExpectedException(ValidationError, self.reserved_no_room):
            iprange.save()

    def test_modify_existing_performs_validation(self):
        subnet = make_plain_subnet()
        IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.100",
            end_ip="192.168.0.150",
        ).save()
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.151",
            end_ip="192.168.0.200",
        )
        iprange.save()
        # Make sure safe modification works.
        iprange.start_ip = "192.168.0.210"
        iprange.end_ip = "192.168.0.250"
        iprange.save()
        # Modify again, but conflict with first range this time.
        instance_id = iprange.id
        iprange.start_ip = "192.168.0.110"
        iprange.end_ip = "192.168.0.140"
        with ExpectedException(ValidationError, self.dynamic_overlaps):
            iprange.save()
        # Make sure original range isn't deleted after failure to modify.
        iprange = reload_object(iprange)
        self.assertEqual(iprange.id, instance_id)

    def test_dynamic_range_cant_overlap_gateway_ip(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.2",
            end_ip="192.168.0.5",
        )
        iprange.save()
        # A DYNAMIC range cannot overlap the gateway IP.
        iprange.start_ip = "192.168.0.1"
        with ExpectedException(ValidationError, self.dynamic_overlaps):
            iprange.save()

    def test_reserved_range_can_overlap_gateway_ip(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
            start_ip="192.168.0.2",
            end_ip="192.168.0.5",
        )
        iprange.save()
        # A RESERVED range can overlap the gateway IP.
        iprange.start_ip = "192.168.0.1"
        iprange.save()

    def test_reserved_range_cannot_overlap_dynamic_ranges(self):
        subnet = factory.make_Subnet(
            cidr="192.168.0.0/24",
            gateway_ip="192.168.0.1",
            dns_servers=["192.168.0.50", "192.168.0.200"],
        )
        IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.2",
            end_ip="192.168.0.49",
        ).save()
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
            start_ip="192.168.0.25",
            end_ip="192.168.0.30",
        )
        with ExpectedException(ValidationError, self.reserved_overlaps):
            iprange.save()

    def test_reserved_range_cannot_overlap_reserved_ranges(self):
        subnet = factory.make_Subnet(
            cidr="192.168.0.0/24",
            gateway_ip="192.168.0.1",
            dns_servers=["192.168.0.50", "192.168.0.200"],
        )
        IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
            start_ip="192.168.0.1",
            end_ip="192.168.0.250",
        ).save()
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
            start_ip="192.168.0.250",
            end_ip="192.168.0.254",
        )
        with ExpectedException(ValidationError, self.reserved_overlaps):
            iprange.save()

    def test_reserved_range_can_overlap_most_ip_types(self):
        subnet = make_plain_subnet()
        factory.make_StaticIPAddress(
            subnet=subnet,
            alloc_type=random.choice(
                (
                    IPADDRESS_TYPE.AUTO,
                    IPADDRESS_TYPE.STICKY,
                    IPADDRESS_TYPE.USER_RESERVED,
                    IPADDRESS_TYPE.DISCOVERED,
                )
            ),
        )
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
            start_ip="192.168.0.1",
            end_ip="192.168.0.254",
        )
        iprange.save()

    def test_dynamic_range_cannot_overlap_auto_address(self):
        subnet = make_plain_subnet()
        factory.make_StaticIPAddress(
            subnet=subnet,
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_network(
                IPNetwork(subnet.cidr), but_not=["192.168.0.1"]
            ),
        )
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.2",
            end_ip="192.168.0.254",
        )
        with ExpectedException(ValidationError, self.dynamic_overlaps):
            iprange.save()

    def test_dynamic_range_cannot_overlap_sticky_address(self):
        subnet = make_plain_subnet()
        factory.make_StaticIPAddress(
            subnet=subnet,
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(
                IPNetwork(subnet.cidr), but_not=["192.168.0.1"]
            ),
        )
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.2",
            end_ip="192.168.0.254",
        )
        with ExpectedException(ValidationError, self.dynamic_overlaps):
            iprange.save()

    def test_dynamic_range_cannot_overlap_user_reserved_address(self):
        subnet = make_plain_subnet()
        factory.make_StaticIPAddress(
            subnet=subnet,
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            ip=factory.pick_ip_in_network(
                IPNetwork(subnet.cidr), but_not=["192.168.0.1"]
            ),
        )
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.2",
            end_ip="192.168.0.254",
        )
        with ExpectedException(ValidationError, self.dynamic_overlaps):
            iprange.save()

    # Regression for lp:1580772.
    def test_dynamic_range_can_overlap_discovered_ip(self):
        subnet = make_plain_subnet()
        factory.make_StaticIPAddress(
            ip="192.168.0.3",
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            subnet=subnet,
        )
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.2",
            end_ip="192.168.0.254",
        )
        iprange.save()

    # Regression for lp:1580772.
    def test_dynamic_range_can_match_discovered_ip(self):
        subnet = make_plain_subnet()
        factory.make_StaticIPAddress(
            ip="192.168.0.3",
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            subnet=subnet,
        )
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.3",
            end_ip="192.168.0.3",
        )
        iprange.save()

    def test_dynamic_range_cannot_overlap_dns_servers(self):
        subnet = factory.make_Subnet(
            cidr="192.168.0.0/24",
            gateway_ip="192.168.0.1",
            dns_servers=["192.168.0.50", "192.168.0.200"],
        )
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.1",
            end_ip="192.168.0.254",
        )
        with ExpectedException(ValidationError, self.dynamic_overlaps):
            iprange.save()

    def test_reserved_range_can_overlap_dns_servers(self):
        subnet = factory.make_Subnet(
            cidr="192.168.0.0/24",
            gateway_ip="192.168.0.1",
            dns_servers=["192.168.0.50", "192.168.0.200"],
        )
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
            start_ip="192.168.0.1",
            end_ip="192.168.0.254",
        )
        iprange.save()

    def test_change_reserved_to_dynamic(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
            start_ip="192.168.0.1",
            end_ip="192.168.0.5",
        )
        # Reserved should save OK overlapping gateway IP.
        iprange.save()

        # Dynamic should not save overlapping gateway IP.
        iprange.type = IPRANGE_TYPE.DYNAMIC
        with ExpectedException(ValidationError, self.dynamic_overlaps):
            iprange.save()
        # Fix start_ip and now it should save.
        iprange.start_ip = "192.168.0.2"
        iprange.save()

    def test_change_dynamic_to_reserved(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.2",
            end_ip="192.168.0.5",
        )
        iprange.save()
        # Reserved should save OK overlapping gateway IP.
        iprange.type = IPRANGE_TYPE.RESERVED
        iprange.start_ip = "192.168.0.1"
        iprange.save()

    def test_changing_end_ip_works(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.2",
            end_ip="192.168.0.5",
        )
        iprange.save()

        iprange.end_ip = "192.168.0.10"
        iprange.save()
