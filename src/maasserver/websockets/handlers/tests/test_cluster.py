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
from maasserver.websockets.handlers.cluster import ClusterHandler
from maasserver.websockets.handlers.timestampedmodel import dehydrate_datetime


class TestClusterHandler(MAASServerTestCase):

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
            }
        return data

    def test_get(self):
        user = factory.make_User()
        handler = ClusterHandler(user, {})
        nodegroup = factory.make_NodeGroup()
        self.assertEquals(
            self.dehydrate_cluster(nodegroup),
            handler.get({"id": nodegroup.id}))

    def test_list(self):
        user = factory.make_User()
        handler = ClusterHandler(user, {})
        nodegroup = factory.make_NodeGroup()
        self.assertItemsEqual(
            [self.dehydrate_cluster(nodegroup)],
            handler.list({}))
