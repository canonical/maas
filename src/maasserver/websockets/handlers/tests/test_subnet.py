# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.subnet`"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.models.subnet import Subnet
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.handlers.subnet import SubnetHandler
from maasserver.websockets.handlers.timestampedmodel import dehydrate_datetime
from provisioningserver.utils.network import IPRangeStatistics
from testtools.matchers import Equals


class TestSubnetHandler(MAASServerTestCase):

    def dehydrate_subnet(self, subnet, for_list=False):
        data = {
            "id": subnet.id,
            "updated": dehydrate_datetime(subnet.updated),
            "created": dehydrate_datetime(subnet.created),
            "name": subnet.name,
            "dns_servers": [server for server in subnet.dns_servers],
            "vlan": subnet.vlan_id,
            "space": subnet.space_id,
            "cidr": subnet.cidr,
            "gateway_ip": subnet.gateway_ip,
        }
        full_range = subnet.get_iprange_usage()
        metadata = IPRangeStatistics(full_range)
        data['statistics'] = metadata.render_json()
        if not for_list:
            data["ip_addresses"] = subnet.render_json_for_related_ips(
                with_username=True, with_node_summary=True)
        return data

    def test_get(self):
        user = factory.make_User()
        handler = SubnetHandler(user, {})
        subnet = factory.make_Subnet()
        expected_data = self.dehydrate_subnet(subnet)
        result = handler.get({"id": subnet.id})
        self.assertThat(result, Equals(expected_data))

    def test_list(self):
        user = factory.make_User()
        handler = SubnetHandler(user, {})
        factory.make_Subnet()
        expected_subnets = [
            self.dehydrate_subnet(subnet, for_list=True)
            for subnet in Subnet.objects.all()
            ]
        self.assertItemsEqual(
            expected_subnets,
            handler.list({}))
