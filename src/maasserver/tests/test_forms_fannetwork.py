# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for FanNetwork forms."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random

from maasserver.forms_fannetwork import FanNetworkForm
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase


class TestFanNetworkForm(MAASServerTestCase):

    def test__requires_name(self):
        slash = random.randint(12, 28)
        underlay = factory.make_ipv4_network(slash=slash)
        overlay = factory.make_ipv4_network(slash=slash - 4)
        form = FanNetworkForm({
            "overlay": unicode(overlay),
            "underlay": unicode(underlay),
        })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "name": ["This field is required."],
        }, form.errors)

    def test__requires_overlay(self):
        slash = random.randint(12, 28)
        underlay = factory.make_ipv4_network(slash=slash)
        form = FanNetworkForm({
            "name": factory.make_name("fannetwork"),
            "underlay": unicode(underlay),
        })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "overlay": ["This field is required."],
        }, form.errors)

    def test__requires_underlay(self):
        slash = random.randint(12, 28)
        overlay = factory.make_ipv4_network(slash=slash - 4)
        form = FanNetworkForm({
            "name": factory.make_name("fannetwork"),
            "overlay": unicode(overlay),
        })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "underlay": ["This field is required."],
            }, form.errors)

    def test__creates_fannetwork(self):
        fannetwork_name = factory.make_name("fannetwork")
        slash = random.randint(12, 28)
        underlay = factory.make_ipv4_network(slash=slash)
        overlay = factory.make_ipv4_network(slash=slash - 4)
        form = FanNetworkForm({
            "name": fannetwork_name,
            "overlay": unicode(overlay),
            "underlay": unicode(underlay),
        })
        self.assertTrue(form.is_valid(), form.errors)
        fannetwork = form.save()
        self.assertEquals(fannetwork_name, fannetwork.name)

    def test__doest_require_name_on_update(self):
        fannetwork = factory.make_FanNetwork()
        form = FanNetworkForm(instance=fannetwork, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test__updates_fannetwork(self):
        new_name = factory.make_name("fannetwork")
        fannetwork = factory.make_FanNetwork()
        form = FanNetworkForm(instance=fannetwork, data={
            "name": new_name,
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEquals(new_name, reload_object(fannetwork).name)
