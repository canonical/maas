# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the IPRange model."""

__all__ = []

from django.core.exceptions import ValidationError
from maasserver.enum import IPRANGE_TYPE
from maasserver.models import IPRange
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools import ExpectedException


class IPRangeTest(MAASServerTestCase):

    def test__create(self):
        subnet = factory.make_Subnet(cidr='192.168.0.0/24')
        iprange = IPRange(
            start_ip='192.168.0.1', end_ip='192.168.0.254',
            type=IPRANGE_TYPE.RESERVED, user=factory.make_User(),
            comment="The quick brown fox jumps over the lazy dog.",
            subnet=subnet)
        iprange.save()

    def test__requires_valid_ip_addresses(self):
        subnet = factory.make_Subnet(cidr='192.168.0.0/24')
        iprange = IPRange(
            start_ip='x192.x168.x0.x1', end_ip='y192.y168.y0.y254',
            type=IPRANGE_TYPE.RESERVED, user=factory.make_User(),
            comment="The quick brown fox jumps over the lazy dog.",
            subnet=subnet)
        with ExpectedException(ValidationError, '.*Enter a valid.*'):
            iprange.save()

    def test__requires_start_ip_address(self):
        subnet = factory.make_Subnet(cidr='192.168.0.0/24')
        iprange = IPRange(
            start_ip='192.168.0.1', type=IPRANGE_TYPE.RESERVED,
            user=factory.make_User(), subnet=subnet,
            comment="The quick brown fox jumps over the lazy dog.")
        with ExpectedException(ValidationError, '.*both required.*'):
            iprange.save()

    def test__requires_end_ip_address(self):
        subnet = factory.make_Subnet(cidr='192.168.0.0/24')
        iprange = IPRange(
            end_ip='192.168.0.1', type=IPRANGE_TYPE.RESERVED,
            user=factory.make_User(), subnet=subnet,
            comment="The quick brown fox jumps over the lazy dog.")
        with ExpectedException(ValidationError, '.*both required.*'):
            iprange.save()

    def test__requires_matching_address_family(self):
        subnet = factory.make_Subnet(cidr='192.168.0.0/24')
        iprange = IPRange(
            start_ip='192.168.0.1', end_ip='2001:db8::1',
            type=IPRANGE_TYPE.RESERVED,
            user=factory.make_User(), subnet=subnet,
            comment="The quick brown fox jumps over the lazy dog.")
        with ExpectedException(ValidationError, '.*same address family.*'):
            iprange.save()

    def test__requires_subnet(self):
        iprange = IPRange(
            start_ip='192.168.0.1', end_ip='192.168.0.254',
            type=IPRANGE_TYPE.RESERVED, user=factory.make_User(),
            comment="The quick brown weasel jumps over the lazy elephant.")
        with ExpectedException(ValidationError):
            iprange.save()

    def test__requires_start_ip_and_end_ip(self):
        subnet = factory.make_Subnet(cidr='192.168.0.0/24')
        iprange = IPRange(
            subnet=subnet, type=IPRANGE_TYPE.RESERVED,
            user=factory.make_User(),
            comment="The quick brown cow jumps over the lazy moon.")
        with ExpectedException(ValidationError, '.*are both required.*'):
            iprange.save()

    def test__requires_start_ip_and_end_ip_to_be_within_subnet(self):
        subnet = factory.make_Subnet(cidr='192.168.0.0/24')
        iprange = IPRange(
            start_ip='192.168.1.1', end_ip='192.168.1.254', subnet=subnet,
            type=IPRANGE_TYPE.RESERVED, user=factory.make_User(),
            comment="The quick brown cow jumps over the lazy moon.")
        with ExpectedException(
                ValidationError, '.*addresses must be within subnet.*'):
            iprange.save()

    def test__requires_start_ip_to_be_within_subnet(self):
        subnet = factory.make_Subnet(cidr='192.168.0.0/24')
        iprange = IPRange(
            start_ip='19.168.0.1', end_ip='192.168.0.254', subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC, user=factory.make_User(),
            comment="The quick brown cow jumps over the lazy moon.")
        with ExpectedException(
                ValidationError, '.*Start IP address must be within subnet.*'):
            iprange.save()

    def test__requires_end_ip_to_be_within_subnet(self):
        subnet = factory.make_Subnet(cidr='192.168.0.0/24')
        iprange = IPRange(
            start_ip='192.168.0.1', end_ip='193.168.0.254',
            subnet=subnet, type=IPRANGE_TYPE.DYNAMIC,
            user=factory.make_User(),
            comment="The quick brown cow jumps over the lazy moon.")
        with ExpectedException(
                ValidationError, '.*End IP address must be within subnet.*'):
            iprange.save()

    def test__requires_end_ip_to_be_greater_or_equal_to_start_ip(self):
        subnet = factory.make_Subnet(cidr='192.168.0.0/24')
        iprange = IPRange(
            start_ip='192.168.0.2', end_ip='192.168.0.1',
            user=factory.make_User(), subnet=subnet,
            type=IPRANGE_TYPE.DYNAMIC,
            comment="The quick brown cow jumps over the lazy moon.")
        with ExpectedException(
                ValidationError, '.*End IP address must not be less than.*'):
            iprange.save()

    def test__requires_type(self):
        subnet = factory.make_Subnet(cidr='192.168.0.0/24')
        iprange = IPRange(
            start_ip='192.168.0.1', end_ip='192.168.0.254',
            user=factory.make_User(), subnet=subnet,
            comment="The quick brown mule jumps over the lazy cheetah.")
        with ExpectedException(ValidationError):
            iprange.save()

    def test__user_optional(self):
        subnet = factory.make_Subnet(cidr='192.168.0.0/24')
        iprange = IPRange(
            start_ip='192.168.0.1', end_ip='192.168.0.254',
            type=IPRANGE_TYPE.DYNAMIC, subnet=subnet,
            comment="The quick brown owl jumps over the lazy alligator.")
        iprange.save()

    def test__comment_optional(self):
        subnet = factory.make_Subnet(cidr='192.168.0.0/24')
        iprange = IPRange(
            start_ip='192.168.0.1', end_ip='192.168.0.254', subnet=subnet,
            type=IPRANGE_TYPE.RESERVED, user=factory.make_User())
        iprange.save()
