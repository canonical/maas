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

    def test_reserved_tags_do_not_validate(self):
        self.assertRaises(
            ValidationError, factory.make_network, vlan_tag=0xFFF)
        self.assertRaises(
            ValidationError, factory.make_network, vlan_tag=0x000)

    def test_out_of_range_tag_do_not_validate(self):
        self.assertRaises(
            ValidationError, factory.make_network, vlan_tag=0x1000)
        self.assertRaises(
            ValidationError, factory.make_network, vlan_tag=-1)
