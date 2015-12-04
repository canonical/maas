# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `NodeGroupInterface` part of region service."""

__all__ = []

from maasserver.rpc.nodegroupinterface import get_cluster_interfaces_as_dicts
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestGetClusterInterfacesAsDicts(MAASServerTestCase):

    def test__returns_cluster_interface(self):
        interface = factory.make_NodeGroupInterface(factory.make_NodeGroup())
        self.assertEqual(
            [
                {
                    'name': interface.name,
                    'interface': interface.interface,
                    'ip': interface.ip,
                },
            ],
            get_cluster_interfaces_as_dicts(interface.nodegroup.uuid))

    def test__returns_all_interfaces_on_cluster(self):
        nodegroup = factory.make_NodeGroup()
        interfaces = [
            factory.make_NodeGroupInterface(nodegroup)
            for _ in range(3)
            ]
        received_interfaces = get_cluster_interfaces_as_dicts(nodegroup.uuid)
        self.assertItemsEqual(
            [expected_interface.name for expected_interface in interfaces],
            [
                received_interface['name']
                for received_interface in received_interfaces
            ])

    def test__ignores_other_clusters(self):
        nodegroup = factory.make_NodeGroup()
        factory.make_NodeGroupInterface(factory.make_NodeGroup())
        self.assertEqual([], get_cluster_interfaces_as_dicts(nodegroup.uuid))
