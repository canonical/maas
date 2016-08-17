# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `StaticRoute`."""

__all__ = []

from django.core.exceptions import ValidationError
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestStaticRoute(MAASServerTestCase):

    def test_unique_together(self):
        route = factory.make_StaticRoute()
        self.assertRaises(
            ValidationError, factory.make_StaticRoute,
            source=route.source, destination=route.destination,
            gateway_ip=route.gateway_ip)

    def test_source_cannot_be_destination(self):
        subnet = factory.make_Subnet()
        gateway_ip = factory.pick_ip_in_Subnet(subnet)
        error = self.assertRaises(
            ValidationError, factory.make_StaticRoute,
            source=subnet, destination=subnet, gateway_ip=gateway_ip)
        self.assertEqual(
            str(
                {'__all__': [
                    "source and destination cannot be the same subnet."]}),
            str(error))

    def test_source_must_be_same_version_of_destination(self):
        source = factory.make_Subnet(version=4)
        dest = factory.make_Subnet(version=6)
        gateway_ip = factory.pick_ip_in_Subnet(source)
        error = self.assertRaises(
            ValidationError, factory.make_StaticRoute,
            source=source, destination=dest, gateway_ip=gateway_ip)
        self.assertEqual(
            str(
                {'__all__': [
                    "source and destination must be the same IP version."]}),
            str(error))

    def test_gateway_ip_must_be_in_source(self):
        source = factory.make_Subnet(version=4)
        dest = factory.make_Subnet(version=4)
        gateway_ip = factory.pick_ip_in_Subnet(dest)
        error = self.assertRaises(
            ValidationError, factory.make_StaticRoute,
            source=source, destination=dest, gateway_ip=gateway_ip)
        self.assertEqual(
            str(
                {'__all__': [
                    "gateway_ip must be with in the source subnet."]}),
            str(error))
