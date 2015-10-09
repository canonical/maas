# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for VLAN forms."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random

from maasserver.forms_vlan import VLANForm
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase


class TestVLANForm(MAASServerTestCase):

    def test__requires_vid(self):
        fabric = factory.make_Fabric()
        form = VLANForm(fabric=fabric, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "vid": [
                "This field is required.",
                "Vid must be between 0 and 4095.",
                ],
            }, form.errors)

    def test__creates_vlan(self):
        fabric = factory.make_Fabric()
        vlan_name = factory.make_name("vlan")
        vid = random.randint(1, 1000)
        form = VLANForm(fabric=fabric, data={
            "name": vlan_name,
            "vid": vid,
        })
        self.assertTrue(form.is_valid(), form.errors)
        vlan = form.save()
        self.assertEquals(vlan_name, vlan.name)
        self.assertEquals(vid, vlan.vid)
        self.assertEquals(fabric, vlan.fabric)

    def test__doest_require_name_or_vid_on_update(self):
        vlan = factory.make_VLAN()
        form = VLANForm(instance=vlan, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test__cannot_edit_default_vlan(self):
        fabric = factory.make_Fabric()
        form = VLANForm(instance=fabric.get_default_vlan(), data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "__all__": [
                "Cannot modify the default VLAN for a fabric.",
                ],
            }, form.errors)

    def test__updates_vlan(self):
        vlan = factory.make_VLAN()
        new_name = factory.make_name("vlan")
        new_vid = random.randint(1, 1000)
        form = VLANForm(instance=vlan, data={
            "name": new_name,
            "vid": new_vid,
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEquals(new_name, reload_object(vlan).name)
        self.assertEquals(new_vid, reload_object(vlan).vid)
