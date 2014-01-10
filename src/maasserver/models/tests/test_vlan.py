# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :class:`Vlan`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django.core.exceptions import ValidationError
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestVlan(MAASServerTestCase):

    def test_instantiation(self):
        description = factory.getRandomString()
        vlan = factory.make_vlan(tag=0x001, description=description)
        self.assertEqual(
            (0x001, description),
            (vlan.tag, vlan.description))

    def test_reserved_tags_dont_validate(self):
        self.assertRaises(
            ValidationError, factory.make_vlan, tag=0xFFF)
        self.assertRaises(
            ValidationError, factory.make_vlan, tag=0x000)

    def test_out_of_range_tag_doesnt_validate(self):
        self.assertRaises(
            ValidationError, factory.make_vlan, tag=0x1000)
        self.assertRaises(
            ValidationError, factory.make_vlan, tag=-1)
