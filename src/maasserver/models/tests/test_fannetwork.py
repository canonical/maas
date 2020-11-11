# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the FanNetwork model."""


import random

from django.core.exceptions import PermissionDenied, ValidationError
from testtools import ExpectedException

from maasserver.models.fannetwork import FanNetwork
from maasserver.permissions import NodePermission
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestFanNetworkManagerGetFanNetworkOr404(MAASServerTestCase):
    def test_user_view_returns_fannetwork(self):
        user = factory.make_User()
        fannetwork = factory.make_FanNetwork()
        self.assertEqual(
            fannetwork,
            FanNetwork.objects.get_fannetwork_or_404(
                fannetwork.id, user, NodePermission.view
            ),
        )

    def test_user_edit_raises_PermissionError(self):
        user = factory.make_User()
        fannetwork = factory.make_FanNetwork()
        with ExpectedException(PermissionDenied):
            FanNetwork.objects.get_fannetwork_or_404(
                fannetwork.id, user, NodePermission.edit
            )

    def test_user_admin_raises_PermissionError(self):
        user = factory.make_User()
        fannetwork = factory.make_FanNetwork()
        with ExpectedException(PermissionDenied):
            FanNetwork.objects.get_fannetwork_or_404(
                fannetwork.id, user, NodePermission.admin
            )

    def test_admin_view_returns_fannetwork(self):
        admin = factory.make_admin()
        fannetwork = factory.make_FanNetwork()
        self.assertEqual(
            fannetwork,
            FanNetwork.objects.get_fannetwork_or_404(
                fannetwork.id, admin, NodePermission.view
            ),
        )

    def test_admin_edit_returns_fannetwork(self):
        admin = factory.make_admin()
        fannetwork = factory.make_FanNetwork()
        self.assertEqual(
            fannetwork,
            FanNetwork.objects.get_fannetwork_or_404(
                fannetwork.id, admin, NodePermission.edit
            ),
        )

    def test_admin_admin_returns_fannetwork(self):
        admin = factory.make_admin()
        fannetwork = factory.make_FanNetwork()
        self.assertEqual(
            fannetwork,
            FanNetwork.objects.get_fannetwork_or_404(
                fannetwork.id, admin, NodePermission.admin
            ),
        )


class TestFanNetwork(MAASServerTestCase):
    def test_creates_fannetwork(self):
        name = factory.make_name("name")
        fannetwork = factory.make_FanNetwork(name=name)
        self.assertEqual(name, fannetwork.name)

    def test_can_delete_fannetwork(self):
        fannetwork = factory.make_FanNetwork()
        fannetwork.delete()
        self.assertItemsEqual([], FanNetwork.objects.filter(id=fannetwork.id))

    def test_cannot_create_ipv6_fannetwork(self):
        with ExpectedException(ValidationError):
            factory.make_FanNetwork(
                underlay="2001:db8:1:1::/96", overlay="2001:db8:2:1::/64"
            )

    def test_rejects_undersize_overlay(self):
        slash = random.randint(4, 28)
        with ExpectedException(ValidationError):
            factory.make_FanNetwork(
                underlay=factory.make_ipv4_network(slash=slash),
                overlay=factory.make_ipv4_network(slash=slash + 2),
            )

    def test_rejects_overlapping_networks(self):
        with ExpectedException(ValidationError):
            factory.make_FanNetwork(
                underlay="10.0.0.0/8", overlay="10.0.1.0/24"
            )

    def test_stores_host_reserve(self):
        host_reserve = random.randint(1, 200)
        fannetwork = factory.make_FanNetwork(
            underlay=factory.make_ipv4_network(slash=16),
            overlay=factory.make_ipv4_network(slash=8),
            host_reserve=host_reserve,
        )
        self.assertEqual(host_reserve, fannetwork.host_reserve)

    def test_rejects_negative_host_reserve(self):
        with ExpectedException(ValidationError):
            factory.make_FanNetwork(host_reserve=-1)

    def test_rejects_host_reserve_too_big(self):
        with ExpectedException(ValidationError):
            factory.make_FanNetwork(
                underlay=factory.make_ipv4_network(slash=16),
                overlay=factory.make_ipv4_network(slash=8),
                host_reserve=256,
            )

    def test_stores_dhcp(self):
        dhcp = factory.pick_bool()
        fannetwork = factory.make_FanNetwork(dhcp=dhcp)
        self.assertEqual(dhcp, fannetwork.dhcp)

    def test_stores_bridge(self):
        bridge = factory.make_name("bridge")
        fannetwork = factory.make_FanNetwork(bridge=bridge)
        self.assertEqual(bridge, fannetwork.bridge)

    def test_stores_off(self):
        off = factory.pick_bool()
        fannetwork = factory.make_FanNetwork(off=off)
        self.assertEqual(off, fannetwork.off)

    def test_rejects_invalid_bridge_name(self):
        bridge = factory.make_name(prefix="bridge", sep=".")
        with ExpectedException(ValidationError):
            factory.make_FanNetwork(bridge=bridge)
