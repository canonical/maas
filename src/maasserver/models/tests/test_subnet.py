# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Subnet model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


import random

from django.core.exceptions import ValidationError
from maasserver.models.subnet import Subnet
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import MatchesStructure


class SubnetTest(MAASServerTestCase):

    def test_creates_subnet(self):
        name = factory.make_name('name')
        vlan = factory.make_VLAN()
        space = factory.make_Space()
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network.cidr)
        gateway_ip = factory.pick_ip_in_network(network)
        dns_servers = [
            factory.make_ip_address()
            for _ in range(random.randint(1, 3))]
        subnet = Subnet(
            name=name, vlan=vlan, cidr=cidr, gateway_ip=gateway_ip,
            space=space, dns_servers=dns_servers)
        subnet.save()
        subnet_from_db = Subnet.objects.get(name=name)
        self.assertThat(subnet_from_db, MatchesStructure.byEquality(
            name=name, vlan=vlan, cidr=cidr, space=space,
            gateway_ip=gateway_ip, dns_servers=dns_servers))

    def test_validates_gateway_ip(self):
        error = self.assertRaises(
            ValidationError, factory.make_Subnet, cidr='192.168.0.0/24',
            gateway_ip='10.0.0.0')
        self.assertEqual(
            {'gateway_ip': ["Gateway IP must be within CIDR range."]},
            error.message_dict)
