# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for FanNetwork forms."""


import random

from maasserver.forms.fannetwork import FanNetworkForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestFanNetworkForm(MAASServerTestCase):
    def test_requires_name(self):
        slash = random.randint(12, 28)
        underlay = factory.make_ipv4_network(slash=slash)
        overlay = factory.make_ipv4_network(slash=slash - 4)
        form = FanNetworkForm(
            {"overlay": str(overlay), "underlay": str(underlay)}
        )
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({"name": ["This field is required."]}, form.errors)

    def test_requires_overlay(self):
        slash = random.randint(12, 28)
        underlay = factory.make_ipv4_network(slash=slash)
        form = FanNetworkForm(
            {
                "name": factory.make_name("fannetwork"),
                "underlay": str(underlay),
            }
        )
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({"overlay": ["This field is required."]}, form.errors)

    def test_requires_underlay(self):
        slash = random.randint(12, 28)
        overlay = factory.make_ipv4_network(slash=slash - 4)
        form = FanNetworkForm(
            {"name": factory.make_name("fannetwork"), "overlay": str(overlay)}
        )
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {"underlay": ["This field is required."]}, form.errors
        )

    def test_creates_fannetwork(self):
        fannetwork_name = factory.make_name("fannetwork")
        slash = random.randint(12, 28)
        underlay = factory.make_ipv4_network(slash=slash)
        overlay = factory.make_ipv4_network(slash=slash - 4)
        form = FanNetworkForm(
            {
                "name": fannetwork_name,
                "overlay": str(overlay),
                "underlay": str(underlay),
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        fannetwork = form.save()
        self.assertEqual(fannetwork_name, fannetwork.name)

    def test_doest_require_name_on_update(self):
        fannetwork = factory.make_FanNetwork()
        form = FanNetworkForm(instance=fannetwork, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test_updates_fannetwork(self):
        new_name = factory.make_name("fannetwork")
        fannetwork = factory.make_FanNetwork()
        form = FanNetworkForm(instance=fannetwork, data={"name": new_name})
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(new_name, reload_object(fannetwork).name)
