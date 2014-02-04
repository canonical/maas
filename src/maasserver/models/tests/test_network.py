# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :class:`Network`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from random import randint

from django.core.exceptions import ValidationError
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestNetwork(MAASServerTestCase):

    def test_instantiation(self):
        name = factory.make_name('net')
        network = factory.getRandomNetwork()
        vlan_tag = randint(0, 0xffe)
        description = factory.getRandomString()

        network = factory.make_network(
            name=name, network=network, vlan_tag=vlan_tag,
            description=description)

        self.assertAttributes(
            network,
            {
                'name': name,
                'ip': network.ip,
                'netmask': network.netmask,
                'vlan_tag': vlan_tag,
                'description': description,
            })

    def test_vlan_tag_can_be_zero_through_hex_ffe(self):
        min_tag = 0
        max_tag = 0xfff - 1
        self.assertEqual(
            min_tag, factory.make_network(vlan_tag=min_tag).vlan_tag)
        self.assertEqual(
            max_tag, factory.make_network(vlan_tag=max_tag).vlan_tag)

    def test_reserved_vlan_tag_does_not_validate(self):
        self.assertRaises(
            ValidationError, factory.make_network, vlan_tag=0xFFF)

    def test_out_of_range_vlan_tags_do_not_validate(self):
        self.assertRaises(
            ValidationError, factory.make_network, vlan_tag=0x1000)
        self.assertRaises(
            ValidationError, factory.make_network, vlan_tag=-1)
