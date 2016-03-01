# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.iprange`"""

__all__ = []

from maasserver.models.iprange import IPRange
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.handlers.iprange import IPRangeHandler
from maasserver.websockets.handlers.timestampedmodel import dehydrate_datetime


class TestIPRangeHandler(MAASServerTestCase):

    def dehydrate_iprange(self, iprange, for_list=False):
        data = {
            "id": iprange.id,
            "created": dehydrate_datetime(iprange.created),
            "updated": dehydrate_datetime(iprange.updated),
            "subnet": iprange.subnet_id,
            "start_ip": iprange.start_ip,
            "end_ip": iprange.end_ip,
            "comment": iprange.comment,
            "user": iprange.user_id,
            "type": iprange.type,
        }
        return data

    def test_get(self):
        user = factory.make_User()
        handler = IPRangeHandler(user, {})
        subnet = factory.make_ipv4_Subnet_with_IPRanges()
        iprange = subnet.iprange_set.first()
        self.assertEqual(
            self.dehydrate_iprange(iprange),
            handler.get({"id": iprange.id}))

    def test_list(self):
        user = factory.make_User()
        handler = IPRangeHandler(user, {})
        factory.make_ipv4_Subnet_with_IPRanges()
        expected_ipranges = [
            self.dehydrate_iprange(iprange, for_list=True)
            for iprange in IPRange.objects.all()
            ]
        self.assertItemsEqual(
            expected_ipranges,
            handler.list({}))
