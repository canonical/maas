# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for static route forms."""

import random

from maasserver.forms.staticroute import StaticRouteForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestStaticRouteForm(MAASServerTestCase):
    def test_requires_source_destination_gateway_ip(self):
        form = StaticRouteForm({})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {
                "source": ["This field is required."],
                "destination": ["This field is required."],
                "gateway_ip": ["This field is required."],
            },
            form.errors,
        )

    def test_creates_staticroute(self):
        source = factory.make_Subnet()
        version = source.get_ipnetwork().version
        dest = factory.make_Subnet(version=version)
        gateway_ip = factory.pick_ip_in_Subnet(source)
        form = StaticRouteForm(
            {
                "source": source.id,
                "destination": dest.id,
                "gateway_ip": gateway_ip,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        staticroute = form.save()
        self.assertEqual(source, staticroute.source)
        self.assertEqual(dest, staticroute.destination)
        self.assertEqual(gateway_ip, staticroute.gateway_ip)
        self.assertEqual(0, staticroute.metric)

    def test_doest_require_any_fields_on_update(self):
        static_route = factory.make_StaticRoute()
        form = StaticRouteForm(instance=static_route, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test_updates_staticroute(self):
        static_route = factory.make_StaticRoute()
        new_source = factory.make_Subnet()
        version = new_source.get_ipnetwork().version
        new_dest = factory.make_Subnet(version=version)
        new_gateway_ip = factory.pick_ip_in_Subnet(new_source)
        new_metric = random.randint(0, 500)
        form = StaticRouteForm(
            instance=static_route,
            data={
                "source": new_source.id,
                "destination": new_dest.id,
                "gateway_ip": new_gateway_ip,
                "metric": new_metric,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        staticroute = form.save()
        self.assertEqual(new_source, staticroute.source)
        self.assertEqual(new_dest, staticroute.destination)
        self.assertEqual(new_gateway_ip, staticroute.gateway_ip)
        self.assertEqual(new_metric, staticroute.metric)
