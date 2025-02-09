# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.staticrange`"""

import random

from maasserver.models.staticroute import StaticRoute
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import get_one
from maasserver.websockets.base import (
    dehydrate_datetime,
    HandlerPermissionError,
)
from maasserver.websockets.handlers.staticroute import StaticRouteHandler


class TestStaticRouteHandler(MAASServerTestCase):
    def dehydrate_staticroute(self, staticroute, for_list=False):
        data = {
            "id": staticroute.id,
            "created": dehydrate_datetime(staticroute.created),
            "updated": dehydrate_datetime(staticroute.updated),
            "source": staticroute.source_id,
            "destination": staticroute.destination_id,
            "gateway_ip": staticroute.gateway_ip,
            "metric": staticroute.metric,
        }
        return data

    def test_get(self):
        user = factory.make_User()
        handler = StaticRouteHandler(user, {}, None)
        staticroute = factory.make_StaticRoute()
        self.assertEqual(
            self.dehydrate_staticroute(staticroute),
            handler.get({"id": staticroute.id}),
        )

    def test_list(self):
        user = factory.make_User()
        handler = StaticRouteHandler(user, {}, None)
        for _ in range(3):
            factory.make_StaticRoute()
        expected_staticroutes = [
            self.dehydrate_staticroute(staticroute, for_list=True)
            for staticroute in StaticRoute.objects.all()
        ]
        self.assertCountEqual(expected_staticroutes, handler.list({}))

    def test_create(self):
        user = factory.make_admin()
        source = factory.make_Subnet()
        destination = factory.make_Subnet(
            version=source.get_ipnetwork().version
        )
        gateway_ip = factory.pick_ip_in_Subnet(source)
        metric = random.randint(0, 500)
        handler = StaticRouteHandler(user, {}, None)
        response = handler.create(
            {
                "source": source.id,
                "destination": destination.id,
                "gateway_ip": gateway_ip,
                "metric": metric,
            }
        )

        staticroute = StaticRoute.objects.get(id=response["id"])
        self.assertEqual(staticroute.source, source)
        self.assertEqual(staticroute.destination, destination)
        self.assertEqual(staticroute.gateway_ip, gateway_ip)
        self.assertEqual(staticroute.metric, metric)

    def test_create_admin_only(self):
        user = factory.make_User()
        source = factory.make_Subnet()
        destination = factory.make_Subnet(
            version=source.get_ipnetwork().version
        )
        gateway_ip = factory.pick_ip_in_Subnet(source)
        metric = random.randint(0, 500)
        handler = StaticRouteHandler(user, {}, None)
        self.assertRaises(
            HandlerPermissionError,
            handler.create,
            {
                "source": source.id,
                "destination": destination.id,
                "gateway_ip": gateway_ip,
                "metric": metric,
            },
        )

    def test_update(self):
        user = factory.make_admin()
        staticroute = factory.make_StaticRoute()
        handler = StaticRouteHandler(user, {}, None)
        data = self.dehydrate_staticroute(staticroute)
        data["metric"] = random.randint(0, 500)
        handler.update(data)
        a_staticroute = StaticRoute.objects.get(id=data["id"])
        self.assertEqual(a_staticroute.source, staticroute.source)
        self.assertEqual(a_staticroute.destination, staticroute.destination)
        self.assertEqual(a_staticroute.gateway_ip, staticroute.gateway_ip)
        self.assertEqual(a_staticroute.metric, data["metric"])

    def test_update_admin_only(self):
        user = factory.make_User()
        staticroute = factory.make_StaticRoute()
        handler = StaticRouteHandler(user, {}, None)
        data = self.dehydrate_staticroute(staticroute)
        data["metric"] = random.randint(0, 500)
        self.assertRaises(HandlerPermissionError, handler.update, data)

    def test_delete(self):
        user = factory.make_admin()
        staticroute = factory.make_StaticRoute()
        handler = StaticRouteHandler(user, {}, None)
        handler.delete({"id": staticroute.id})
        self.assertIsNone(
            get_one(StaticRoute.objects.filter(id=staticroute.id))
        )

    def test_delete_admin_only(self):
        user = factory.make_User()
        staticroute = factory.make_StaticRoute()
        handler = StaticRouteHandler(user, {}, None)
        self.assertRaises(
            HandlerPermissionError, handler.delete, {"id": staticroute.id}
        )
