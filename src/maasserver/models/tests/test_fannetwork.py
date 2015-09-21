# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the FanNetwork model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


import random

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from maasserver.enum import NODE_PERMISSION
from maasserver.models.fannetwork import FanNetwork
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools import ExpectedException


class TestFanNetworkManagerGetFanNetworkOr404(MAASServerTestCase):

    def test__user_view_returns_fannetwork(self):
        user = factory.make_User()
        fannetwork = factory.make_FanNetwork()
        self.assertEquals(
            fannetwork,
            FanNetwork.objects.get_fannetwork_or_404(
                fannetwork.id, user, NODE_PERMISSION.VIEW))

    def test__user_edit_raises_PermissionError(self):
        user = factory.make_User()
        fannetwork = factory.make_FanNetwork()
        with ExpectedException(PermissionDenied):
            FanNetwork.objects.get_fannetwork_or_404(
                fannetwork.id, user, NODE_PERMISSION.EDIT)

    def test__user_admin_raises_PermissionError(self):
        user = factory.make_User()
        fannetwork = factory.make_FanNetwork()
        with ExpectedException(PermissionDenied):
            FanNetwork.objects.get_fannetwork_or_404(
                fannetwork.id, user, NODE_PERMISSION.ADMIN)

    def test__admin_view_returns_fannetwork(self):
        admin = factory.make_admin()
        fannetwork = factory.make_FanNetwork()
        self.assertEquals(
            fannetwork,
            FanNetwork.objects.get_fannetwork_or_404(
                fannetwork.id, admin, NODE_PERMISSION.VIEW))

    def test__admin_edit_returns_fannetwork(self):
        admin = factory.make_admin()
        fannetwork = factory.make_FanNetwork()
        self.assertEquals(
            fannetwork,
            FanNetwork.objects.get_fannetwork_or_404(
                fannetwork.id, admin, NODE_PERMISSION.EDIT))

    def test__admin_admin_returns_fannetwork(self):
        admin = factory.make_admin()
        fannetwork = factory.make_FanNetwork()
        self.assertEquals(
            fannetwork,
            FanNetwork.objects.get_fannetwork_or_404(
                fannetwork.id, admin, NODE_PERMISSION.ADMIN))


class TestFanNetwork(MAASServerTestCase):

    def test_creates_fannetwork(self):
        name = factory.make_name('name')
        fannetwork = factory.make_FanNetwork(name=name)
        self.assertEqual(name, fannetwork.name)

    def test_can_delete_fannetwork(self):
        fannetwork = factory.make_FanNetwork()
        fannetwork.delete()
        self.assertItemsEqual([], FanNetwork.objects.filter(id=fannetwork.id))

    def test_cannot_create_ipv6_fannetwork(self):
        with ExpectedException(ValidationError):
            factory.make_FanNetwork(
                underlay="2001:db8:1:1::/96", overlay="2001:db8:2:1::/64")

    def test_rejects_undersize_overlay(self):
        slash = random.randint(4, 28)
        with ExpectedException(ValidationError):
            factory.make_FanNetwork(
                underlay=factory.make_ipv4_network(slash=slash),
                overlay=factory.make_ipv4_network(slash=slash + 2))

    def test_rejects_overlapping_networks(self):
        with ExpectedException(ValidationError):
            factory.make_FanNetwork(
                underlay="10.0.0.0/8", overlay="10.0.1.0/24")

    def test_stores_host_reserve(self):
        host_reserve = random.randint(0, 200)
        fannetwork = factory.make_FanNetwork(
            underlay=factory.make_ipv4_network(slash=16),
            overlay=factory.make_ipv4_network(slash=8),
            host_reserve=host_reserve)
        self.assertEqual(host_reserve, fannetwork.host_reserve)

    def test_rejects_negative_host_reserve(self):
        with ExpectedException(ValidationError):
            factory.make_FanNetwork(host_reserve=-1)

    def test_rejects_host_reserve_too_big(self):
        with ExpectedException(ValidationError):
            factory.make_FanNetwork(
                underlay=factory.make_ipv4_network(slash=16),
                overlay=factory.make_ipv4_network(slash=8),
                host_reserve=256)

    def test_stores_dhcp(self):
        dhcp = (random.random > 0.5)
        fannetwork = factory.make_FanNetwork(dhcp=dhcp)
        self.assertEqual(dhcp, fannetwork.dhcp)

    def test_stores_bridge(self):
        bridge = factory.make_name('bridge')
        fannetwork = factory.make_FanNetwork(bridge=bridge)
        self.assertEqual(bridge, fannetwork.bridge)

    def test_stores_off(self):
        off = (random.random > 0.5)
        fannetwork = factory.make_FanNetwork(off=off)
        self.assertEqual(off, fannetwork.off)

    def test_rejects_invalid_bridge_name(self):
        bridge = factory.make_name(prefix='bridge', sep='.')
        with ExpectedException(ValidationError):
            factory.make_FanNetwork(bridge=bridge)
