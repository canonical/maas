# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `StaticRoute`."""

from django.core.exceptions import PermissionDenied, ValidationError

from maasserver.models.staticroute import StaticRoute
from maasserver.permissions import NodePermission
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestStaticRouteManagerGetStaticRouteOr404(MAASServerTestCase):
    def test_user_view_returns_staticroute(self):
        user = factory.make_User()
        route = factory.make_StaticRoute()
        self.assertEqual(
            route,
            StaticRoute.objects.get_staticroute_or_404(
                route.id, user, NodePermission.view
            ),
        )

    def test_user_edit_raises_PermissionError(self):
        user = factory.make_User()
        route = factory.make_StaticRoute()
        self.assertRaises(
            PermissionDenied,
            StaticRoute.objects.get_staticroute_or_404,
            route.id,
            user,
            NodePermission.edit,
        )

    def test_user_admin_raises_PermissionError(self):
        user = factory.make_User()
        route = factory.make_StaticRoute()
        self.assertRaises(
            PermissionDenied,
            StaticRoute.objects.get_staticroute_or_404,
            route.id,
            user,
            NodePermission.admin,
        )

    def test_admin_view_returns_fabric(self):
        admin = factory.make_admin()
        route = factory.make_StaticRoute()
        self.assertEqual(
            route,
            StaticRoute.objects.get_staticroute_or_404(
                route.id, admin, NodePermission.view
            ),
        )

    def test_admin_edit_returns_fabric(self):
        admin = factory.make_admin()
        route = factory.make_StaticRoute()
        self.assertEqual(
            route,
            StaticRoute.objects.get_staticroute_or_404(
                route.id, admin, NodePermission.edit
            ),
        )

    def test_admin_admin_returns_fabric(self):
        admin = factory.make_admin()
        route = factory.make_StaticRoute()
        self.assertEqual(
            route,
            StaticRoute.objects.get_staticroute_or_404(
                route.id, admin, NodePermission.admin
            ),
        )


class TestStaticRoute(MAASServerTestCase):
    def test_unique_together(self):
        route = factory.make_StaticRoute()
        self.assertRaises(
            ValidationError,
            factory.make_StaticRoute,
            source=route.source,
            destination=route.destination,
            gateway_ip=route.gateway_ip,
        )

    def test_source_cannot_be_destination(self):
        subnet = factory.make_Subnet()
        gateway_ip = factory.pick_ip_in_Subnet(subnet)
        error = self.assertRaises(
            ValidationError,
            factory.make_StaticRoute,
            source=subnet,
            destination=subnet,
            gateway_ip=gateway_ip,
        )
        self.assertEqual(
            str(
                {
                    "__all__": [
                        "source and destination cannot be the same subnet."
                    ]
                }
            ),
            str(error),
        )

    def test_source_must_be_same_version_of_destination(self):
        source = factory.make_Subnet(version=4)
        dest = factory.make_Subnet(version=6)
        gateway_ip = factory.pick_ip_in_Subnet(source)
        error = self.assertRaises(
            ValidationError,
            factory.make_StaticRoute,
            source=source,
            destination=dest,
            gateway_ip=gateway_ip,
        )
        self.assertEqual(
            str(
                {
                    "__all__": [
                        "source and destination must be the same IP version."
                    ]
                }
            ),
            str(error),
        )

    def test_gateway_ip_must_be_in_source(self):
        source = factory.make_Subnet(version=4)
        dest = factory.make_Subnet(version=4)
        gateway_ip = factory.pick_ip_in_Subnet(dest)
        error = self.assertRaises(
            ValidationError,
            factory.make_StaticRoute,
            source=source,
            destination=dest,
            gateway_ip=gateway_ip,
        )
        self.assertEqual(
            str(
                {"__all__": ["gateway_ip must be with in the source subnet."]}
            ),
            str(error),
        )
