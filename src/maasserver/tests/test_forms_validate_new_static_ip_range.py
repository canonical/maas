# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `validate_new_static_ip_ranges`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django.core.exceptions import ValidationError
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
)
from maasserver.forms import (
    ERROR_MESSAGE_STATIC_IPS_OUTSIDE_RANGE,
    ERROR_MESSAGE_STATIC_RANGE_IN_USE,
    validate_new_static_ip_ranges,
)
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from netaddr import IPNetwork


class TestValidateNewStaticIPRanges(MAASServerTestCase):
    """Tests for `validate_new_static_ip_ranges`()."""

    def make_interface(self):
        network = IPNetwork("10.1.0.0/24")
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            network=network)
        [interface] = nodegroup.get_managed_interfaces()
        interface.ip_range_low = '10.1.0.1'
        interface.ip_range_high = '10.1.0.10'
        interface.static_ip_range_low = '10.1.0.50'
        interface.static_ip_range_high = '10.1.0.60'
        interface.save()
        return interface

    def test_raises_error_when_allocated_ips_fall_outside_new_range(self):
        interface = self.make_interface()
        StaticIPAddress.objects.allocate_new('10.1.0.56', '10.1.0.60')
        error = self.assertRaises(
            ValidationError,
            validate_new_static_ip_ranges,
            instance=interface,
            static_ip_range_low='10.1.0.50',
            static_ip_range_high='10.1.0.55')
        self.assertEqual(
            ERROR_MESSAGE_STATIC_IPS_OUTSIDE_RANGE,
            error.message)

    def test_removing_static_range_raises_error_if_ips_allocated(self):
        interface = self.make_interface()
        StaticIPAddress.objects.allocate_new('10.1.0.56', '10.1.0.60')
        error = self.assertRaises(
            ValidationError,
            validate_new_static_ip_ranges,
            instance=interface,
            static_ip_range_low='',
            static_ip_range_high='')
        self.assertEqual(
            ERROR_MESSAGE_STATIC_RANGE_IN_USE,
            error.message)

    def test_allows_range_expansion(self):
        interface = self.make_interface()
        StaticIPAddress.objects.allocate_new('10.1.0.56', '10.1.0.60')
        is_valid = validate_new_static_ip_ranges(
            interface, static_ip_range_low='10.1.0.40',
            static_ip_range_high='10.1.0.100')
        self.assertTrue(is_valid)

    def test_allows_allocated_ip_as_upper_bound(self):
        interface = self.make_interface()
        StaticIPAddress.objects.allocate_new('10.1.0.55', '10.1.0.55')
        is_valid = validate_new_static_ip_ranges(
            interface,
            static_ip_range_low=interface.static_ip_range_low,
            static_ip_range_high='10.1.0.55')
        self.assertTrue(is_valid)

    def test_allows_allocated_ip_as_lower_bound(self):
        interface = self.make_interface()
        StaticIPAddress.objects.allocate_new('10.1.0.55', '10.1.0.55')
        is_valid = validate_new_static_ip_ranges(
            interface, static_ip_range_low='10.1.0.55',
            static_ip_range_high=interface.static_ip_range_high)
        self.assertTrue(is_valid)

    def test_ignores_unmanaged_interfaces(self):
        interface = self.make_interface()
        interface.management = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
        interface.save()
        StaticIPAddress.objects.allocate_new(
            interface.static_ip_range_low, interface.static_ip_range_high)
        is_valid = validate_new_static_ip_ranges(
            interface, static_ip_range_low='10.1.0.57',
            static_ip_range_high='10.1.0.58')
        self.assertTrue(is_valid)

    def test_ignores_interfaces_with_no_static_range(self):
        interface = self.make_interface()
        interface.static_ip_range_low = None
        interface.static_ip_range_high = None
        interface.save()
        StaticIPAddress.objects.allocate_new('10.1.0.56', '10.1.0.60')
        is_valid = validate_new_static_ip_ranges(
            interface, static_ip_range_low='10.1.0.57',
            static_ip_range_high='10.1.0.58')
        self.assertTrue(is_valid)

    def test_ignores_unchanged_static_range(self):
        interface = self.make_interface()
        StaticIPAddress.objects.allocate_new(
            interface.static_ip_range_low, interface.static_ip_range_high)
        is_valid = validate_new_static_ip_ranges(
            interface,
            static_ip_range_low=interface.static_ip_range_low,
            static_ip_range_high=interface.static_ip_range_high)
        self.assertTrue(is_valid)
