# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.cluster`"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.clusterrpc.power_parameters import (
    get_all_power_types_from_clusters,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.handlers.cluster import (
    ClusterHandler,
    dehydrate_ip_address,
)
from maasserver.websockets.handlers.timestampedmodel import dehydrate_datetime
from maastesting.djangotestcase import count_queries


class TestClusterHandler(MAASServerTestCase):

    def dehydrate_interface(self, interface):
        """Dehydrate a `NodeGroupInterface`."""
        return {
            "id": interface.id,
            "ip": "%s" % interface.ip,
            "name": interface.name,
            "management": interface.management,
            "interface": interface.interface,
            "subnet_mask": dehydrate_ip_address(interface.subnet_mask),
            "broadcast_ip": dehydrate_ip_address(interface.broadcast_ip),
            "router_ip": dehydrate_ip_address(interface.router_ip),
            "dynamic_range": {
                "low": dehydrate_ip_address(interface.ip_range_low),
                "high": dehydrate_ip_address(interface.ip_range_high),
                },
            "static_range": {
                "low": dehydrate_ip_address(
                    interface.static_ip_range_low),
                "high": dehydrate_ip_address(
                    interface.static_ip_range_high),
                },
            "foreign_dhcp_ip": dehydrate_ip_address(
                interface.foreign_dhcp_ip),
            "network": (
                "%s" % interface.network
                if interface.network is not None else None),
            }

    def dehydrate_cluster(self, cluster):
        power_types = get_all_power_types_from_clusters(nodegroups=[cluster])
        data = {
            "id": cluster.id,
            "cluster_name": cluster.cluster_name,
            "name": cluster.name,
            "status": cluster.status,
            "uuid": cluster.uuid,
            "default_disable_ipv4": cluster.default_disable_ipv4,
            "connected": cluster.is_connected(),
            "state": cluster.get_state(),
            "power_types": power_types,
            "updated": dehydrate_datetime(cluster.updated),
            "created": dehydrate_datetime(cluster.created),
            "interfaces": [
                self.dehydrate_interface(interface)
                for interface in cluster.nodegroupinterface_set.all()
                ],
            }
        return data

    def make_nodegroup(self, number):
        """Create `number` of new nodegroups."""
        for counter in range(number):
            nodegroup = factory.make_NodeGroup()
            for _ in range(3):
                factory.make_NodeGroupInterface(nodegroup)

    def test_get(self):
        user = factory.make_User()
        handler = ClusterHandler(user, {})
        nodegroup = factory.make_NodeGroup()
        for _ in range(3):
            factory.make_NodeGroupInterface(nodegroup)
        self.assertEquals(
            self.dehydrate_cluster(nodegroup),
            handler.get({"id": nodegroup.id}))

    def test_list(self):
        user = factory.make_User()
        handler = ClusterHandler(user, {})
        nodegroup = factory.make_NodeGroup()
        for _ in range(3):
            factory.make_NodeGroupInterface(nodegroup)
        self.assertItemsEqual(
            [self.dehydrate_cluster(nodegroup)],
            handler.list({}))

    def test_list_num_queries_is_independent_of_num_clusters(self):
        user = factory.make_User()
        handler = ClusterHandler(user, {})
        self.make_nodegroup(10)
        query_10_count, _ = count_queries(handler.list, {})
        self.make_nodegroup(10)
        query_20_count, _ = count_queries(handler.list, {})

        # This check is to notify the developer that a change was made that
        # affects the number of queries performed when doing a cluster listing.
        # It is important to keep this number as low as possible. A larger
        # number means regiond has to do more work slowing down its process
        # and slowing down the client waiting for the response.
        self.assertEquals(
            query_10_count, 3,
            "Number of queries has changed; make sure this is expected.")
        self.assertEquals(
            query_10_count, query_20_count,
            "Number of queries is not independent to the number of clusters.")
