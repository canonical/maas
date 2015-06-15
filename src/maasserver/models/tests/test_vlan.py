# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the VLAN model."""

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
from maasserver.models.vlan import VLAN
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import MatchesStructure
from testtools.testcase import ExpectedException


class VLANTest(MAASServerTestCase):

    def test_creates_vlan(self):
        name = factory.make_name('name')
        vid = random.randint(3, 55)
        fabric = factory.make_Fabric()
        vlan = VLAN(vid=vid, name=name, fabric=fabric)
        vlan.save()
        self.assertThat(vlan, MatchesStructure.byEquality(
            vid=vid, name=name))

    def test_is_fabric_default_detects_default_vlan(self):
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        fabric.default_vlan = vlan
        fabric.save()
        self.assertTrue(vlan.is_fabric_default())

    def test_is_fabric_default_detects_non_default_vlan(self):
        vlan = factory.make_VLAN()
        self.assertFalse(vlan.is_fabric_default())


class VLANVidValidationTest(MAASServerTestCase):

    scenarios = [
        ('0', {'vid': 0, 'valid': True}),
        ('12', {'vid': 12, 'valid': True}),
        ('250', {'vid': 250, 'valid': True}),
        ('3000', {'vid': 3000, 'valid': True}),
        ('4095', {'vid': 4095, 'valid': True}),
        ('-23', {'vid': -23, 'valid': False}),
        ('4096', {'vid': 4096, 'valid': False}),
        ('10000', {'vid': 10000, 'valid': False}),
    ]

    def test_validates_vid(self):
        fabric = factory.make_Fabric()
        # Remove the auto-created default VLAN so that
        # we can create it in this test.
        default_vlan = fabric.default_vlan
        fabric.default_vlan = None
        fabric.save()
        default_vlan.delete()
        name = factory.make_name('name')
        vlan = VLAN(vid=self.vid, name=name, fabric=fabric)
        if self.valid:
            # No exception.
            self.assertIsNone(vlan.save())

        else:
            with ExpectedException(ValidationError):
                vlan.save()
