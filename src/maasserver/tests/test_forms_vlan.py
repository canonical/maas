# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for VLAN forms."""

__all__ = []

import random

from maasserver.forms_vlan import VLANForm
from maasserver.models.vlan import DEFAULT_MTU
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase


class TestVLANForm(MAASServerTestCase):

    def test__requires_vid(self):
        fabric = factory.make_Fabric()
        form = VLANForm(fabric=fabric, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({
            "vid": [
                "This field is required.",
                "Vid must be between 0 and 4095.",
                ],
            }, form.errors)

    def test__creates_vlan(self):
        fabric = factory.make_Fabric()
        vlan_name = factory.make_name("vlan")
        vid = random.randint(1, 1000)
        mtu = random.randint(552, 4096)
        form = VLANForm(fabric=fabric, data={
            "name": vlan_name,
            "vid": vid,
            "mtu": mtu,
        })
        self.assertTrue(form.is_valid(), form.errors)
        vlan = form.save()
        self.assertEqual(vlan_name, vlan.name)
        self.assertEqual(vid, vlan.vid)
        self.assertEqual(fabric, vlan.fabric)
        self.assertEqual(mtu, vlan.mtu)

    def test__creates_vlan_with_default_mtu(self):
        fabric = factory.make_Fabric()
        vlan_name = factory.make_name("vlan")
        vid = random.randint(1, 1000)
        form = VLANForm(fabric=fabric, data={
            "name": vlan_name,
            "vid": vid,
        })
        self.assertTrue(form.is_valid(), form.errors)
        vlan = form.save()
        self.assertEqual(vlan_name, vlan.name)
        self.assertEqual(vid, vlan.vid)
        self.assertEqual(fabric, vlan.fabric)
        self.assertEqual(DEFAULT_MTU, vlan.mtu)

    def test__doest_require_name_vid_or_mtu_on_update(self):
        vlan = factory.make_VLAN()
        form = VLANForm(instance=vlan, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test__cannot_edit_default_vlan(self):
        fabric = factory.make_Fabric()
        form = VLANForm(instance=fabric.get_default_vlan(), data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({
            "__all__": [
                "Cannot modify the default VLAN for a fabric.",
                ],
            }, form.errors)

    def test__updates_vlan(self):
        vlan = factory.make_VLAN()
        new_name = factory.make_name("vlan")
        new_vid = random.randint(1, 1000)
        new_mtu = random.randint(552, 4096)
        form = VLANForm(instance=vlan, data={
            "name": new_name,
            "vid": new_vid,
            "mtu": new_mtu,
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(new_name, reload_object(vlan).name)
        self.assertEqual(new_vid, reload_object(vlan).vid)
        self.assertEqual(new_mtu, reload_object(vlan).mtu)
