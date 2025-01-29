# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import random
from unittest.mock import call

from django.core.exceptions import ValidationError
from netaddr import IPNetwork
from testtools import TestCase

from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
)
from maasserver.enum import IPADDRESS_TYPE, IPRANGE_TYPE
from maasserver.models import IPRange
from maasserver.models import iprange as iprange_module
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit_hooks, reload_object


def make_plain_subnet():
    return factory.make_Subnet(
        cidr="192.168.0.0/24", gateway_ip="192.168.0.1", dns_servers=[]
    )


def make_plain_ipv6_subnet():
    return factory.make_Subnet(
        cidr="2001::/64", gateway_ip="2001::1", dns_servers=[]
    )


class TestIPRange(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        unittest_case = super(TestCase, self)
        self.assertRaises = unittest_case.assertRaises

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean_fields()
        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": ["Enter a valid IPv4 or IPv6 address."],
                "end_ip": ["Enter a valid IPv4 or IPv6 address."],
            },
        )

    def test_requires_start_ip_address(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            end_ip="192.168.0.1",
            type=IPRANGE_TYPE.RESERVED,
            user=factory.make_User(),
            subnet=subnet,
            comment="The quick brown fox jumps over the lazy dog.",
        )
        with self.assertRaises(ValidationError) as cm:
            iprange.clean_fields()
        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": ["This field cannot be null."],
            },
        )

    def test_requires_end_ip_address(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            start_ip="192.168.0.1",
            type=IPRANGE_TYPE.RESERVED,
            user=factory.make_User(),
            subnet=subnet,
            comment="The quick brown fox jumps over the lazy dog.",
        )
        with self.assertRaises(ValidationError) as cm:
            iprange.clean_fields()
        self.assertEqual(
            cm.exception.message_dict,
            {
                "end_ip": ["This field cannot be null."],
            },
        )

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()
        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [
                    "Start IP address and end IP address must be in the same address family."
                ],
                "end_ip": [
                    "Start IP address and end IP address must be in the same address family."
                ],
            },
        )

    def test_requires_subnet(self):
        iprange = IPRange(
            start_ip="192.168.0.1",
            end_ip="192.168.0.254",
            type=IPRANGE_TYPE.RESERVED,
            user=factory.make_User(),
            comment="The quick brown weasel jumps over the lazy elephant.",
        )
        with self.assertRaises(ValidationError) as cm:
            iprange.clean_fields()
        self.assertEqual(
            cm.exception.message_dict,
            {"subnet": ["This field cannot be null."]},
        )

    def test_requires_start_ip_and_end_ip(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
            user=factory.make_User(),
            comment="The quick brown cow jumps over the lazy moon.",
        )
        with self.assertRaises(ValidationError) as cm:
            iprange.clean_fields()
        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": ["This field cannot be null."],
                "end_ip": ["This field cannot be null."],
            },
        )

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()
        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [
                    f"IP addresses must be within subnet: {subnet.cidr}."
                ],
                "end_ip": [
                    f"IP addresses must be within subnet: {subnet.cidr}."
                ],
            },
        )

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()
        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [
                    f"Start IP address must be within subnet: {subnet.cidr}."
                ],
            },
        )

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()
        self.assertEqual(
            cm.exception.message_dict,
            {
                "end_ip": [
                    f"End IP address must be within subnet: {subnet.cidr}."
                ],
            },
        )

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()
        self.assertEqual(
            cm.exception.message_dict,
            {
                "end_ip": [
                    "End IP address must not be less than Start IP address."
                ],
            },
        )

    def test_requires_end_ip_to_not_be_broadcast(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            start_ip="192.168.0.254",
            end_ip="192.168.0.255",
            user=factory.make_User(),
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
        )
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()
        self.assertEqual(
            cm.exception.message_dict,
            {
                "end_ip": [
                    "Broadcast address cannot be included in IP range."
                ],
            },
        )

    def test_requires_start_ip_to_not_be_network(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            start_ip="192.168.0.0",
            end_ip="192.168.0.5",
            user=factory.make_User(),
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
        )
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()
        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [
                    "Reserved network address cannot be included in IP range."
                ],
            },
        )

    def test_requires_start_ip_to_not_be_ipv6_reserved_anycast(self):
        subnet = make_plain_ipv6_subnet()
        iprange = IPRange(
            start_ip="2001::",
            end_ip="2001::1",
            user=factory.make_User(),
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
        )
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()
        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [
                    "Reserved network address cannot be included in IP range."
                ],
            },
        )

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()
        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [
                    "IPv6 dynamic range must be at least 256 addresses in size."
                ],
                "end_ip": [
                    "IPv6 dynamic range must be at least 256 addresses in size."
                ],
            },
        )

    def test_requires_type(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            start_ip="192.168.0.1",
            end_ip="192.168.0.254",
            user=factory.make_User(),
            subnet=subnet,
            comment="The quick brown mule jumps over the lazy cheetah.",
        )
        with self.assertRaises(ValidationError) as cm:
            iprange.clean_fields()
        self.assertEqual(
            cm.exception.message_dict,
            {"type": ["This field cannot be blank."]},
        )

    def test_user_optional(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            start_ip="192.168.0.2",
            end_ip="192.168.0.254",
            type=IPRANGE_TYPE.DYNAMIC,
            subnet=subnet,
            comment="The quick brown owl jumps over the lazy alligator.",
        )
        iprange.clean_fields()

    def test_comment_optional(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            start_ip="192.168.0.2",
            end_ip="192.168.0.254",
            subnet=subnet,
            type=IPRANGE_TYPE.RESERVED,
            user=factory.make_User(),
        )
        iprange.clean_fields()

    def test_save_calls_dhcp_configure_workflow(self):
        mock_start_workflow = self.patch(iprange_module, "start_workflow")

        subnet = make_plain_subnet()
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.2",
            end_ip="192.168.0.5",
        )

        with post_commit_hooks:
            subnet.vlan.dhcp_on = True
            subnet.vlan.save()
            iprange.save()

        mock_start_workflow.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(ip_range_ids=[iprange.id]),
            task_queue="region",
        )

    def test_delete_calls_dhcp_configure_workflow(self):
        mock_start_workflow = self.patch(iprange_module, "start_workflow")

        subnet = make_plain_subnet()
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.2",
            end_ip="192.168.0.5",
        )

        with post_commit_hooks:
            subnet.vlan.dhcp_on = True
            subnet.vlan.save()
            iprange.save()
            iprange.delete()

        self.assertIn(
            call(
                workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
                param=ConfigureDHCPParam(subnet_ids=[subnet.id]),
                task_queue="region",
            ),
            mock_start_workflow.mock_calls,
        )


class TestIPRangeSavePreventsOverlapping(MAASServerTestCase):
    overlaps = "Requested %s range conflicts with an existing %srange."
    dynamic_overlaps = overlaps % (IPRANGE_TYPE.DYNAMIC, "IP address or ")
    reserved_overlaps = overlaps % (IPRANGE_TYPE.RESERVED, "")

    no_room = "There is no room for any %s ranges on this subnet."
    dynamic_no_room = no_room % IPRANGE_TYPE.DYNAMIC
    reserved_no_room = no_room % IPRANGE_TYPE.RESERVED

    def setUp(self):
        super().setUp()
        unittest_case = super(TestCase, self)
        self.assertRaises = unittest_case.assertRaises

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()

        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [self.dynamic_overlaps],
                "end_ip": [self.dynamic_overlaps],
            },
        )

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()

        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [self.dynamic_overlaps],
                "end_ip": [self.dynamic_overlaps],
            },
        )
        # Try as reserved range.
        iprange.type = IPRANGE_TYPE.RESERVED
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()

        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [self.reserved_overlaps],
                "end_ip": [self.reserved_overlaps],
            },
        )

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()

        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [self.dynamic_overlaps],
                "end_ip": [self.dynamic_overlaps],
            },
        )

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()

        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [self.dynamic_overlaps],
                "end_ip": [self.dynamic_overlaps],
            },
        )

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()

        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [self.dynamic_overlaps],
                "end_ip": [self.dynamic_overlaps],
            },
        )

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()

        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [self.dynamic_overlaps],
                "end_ip": [self.dynamic_overlaps],
            },
        )

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()

        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [self.dynamic_overlaps],
                "end_ip": [self.dynamic_overlaps],
            },
        )

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()

        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [self.dynamic_no_room],
                "end_ip": [self.dynamic_no_room],
            },
        )
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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()

        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [self.reserved_no_room],
                "end_ip": [self.reserved_no_room],
            },
        )

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()

        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [self.dynamic_overlaps],
                "end_ip": [self.dynamic_overlaps],
            },
        )
        # Make sure original range isn't deleted after failure to modify.
        iprange = reload_object(iprange)
        self.assertEqual(iprange.id, instance_id)

    def test_dynamic_range_cant_overlap_gateway_ip(self):
        subnet = make_plain_subnet()
        iprange = IPRange(
            subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            start_ip="192.168.0.1",
            end_ip="192.168.0.5",
        )
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()

        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [self.dynamic_overlaps],
                "end_ip": [self.dynamic_overlaps],
            },
        )

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
        iprange.clean()

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()

        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [self.reserved_overlaps],
                "end_ip": [self.reserved_overlaps],
            },
        )

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()

        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [self.reserved_overlaps],
                "end_ip": [self.reserved_overlaps],
            },
        )

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()

        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [self.dynamic_overlaps],
                "end_ip": [self.dynamic_overlaps],
            },
        )

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()

        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [self.dynamic_overlaps],
                "end_ip": [self.dynamic_overlaps],
            },
        )

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()

        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [self.dynamic_overlaps],
                "end_ip": [self.dynamic_overlaps],
            },
        )

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
        iprange.clean()

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
        iprange.clean()

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()

        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [self.dynamic_overlaps],
                "end_ip": [self.dynamic_overlaps],
            },
        )

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
        with self.assertRaises(ValidationError) as cm:
            iprange.clean()

        self.assertEqual(
            cm.exception.message_dict,
            {
                "start_ip": [self.dynamic_overlaps],
                "end_ip": [self.dynamic_overlaps],
            },
        )
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
