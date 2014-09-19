# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test for RPC utility functions for Nodes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random

from django.core.exceptions import ValidationError
from maasserver.rpc.nodes import create_node
from maasserver.rpc.testing.fixtures import MockLiveRegionToClusterRPCFixture
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.drivers import PowerTypeRegistry
from provisioningserver.rpc.cluster import DescribePowerTypes
from provisioningserver.rpc.exceptions import NodeAlreadyExists
from provisioningserver.rpc.testing import always_succeed_with
from simplejson import dumps


class TestCreateNode(MAASServerTestCase):

    def prepare_cluster_rpc(self, cluster):
        self.useFixture(RegionEventLoopFixture('rpc'))
        self.useFixture(RunningEventLoopFixture())

        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(cluster, DescribePowerTypes)
        self.power_types = [item for name, item in PowerTypeRegistry]
        protocol.DescribePowerTypes.side_effect = always_succeed_with(
            {'power_types': self.power_types})
        return protocol

    def test_creates_node(self):
        cluster = factory.make_NodeGroup()
        cluster.accept()
        self.prepare_cluster_rpc(cluster)

        mac_addresses = [
            factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)
        power_type = random.choice(self.power_types)['name']
        power_parameters = dumps({})

        node = create_node(
            cluster.uuid, architecture, power_type, power_parameters,
            mac_addresses)

        self.assertEqual(
            (
                cluster,
                architecture,
                power_type,
                ''
            ),
            (
                node.nodegroup,
                node.architecture,
                node.power_type,
                node.power_parameters
            ))
        self.assertItemsEqual(
            mac_addresses,
            [mac.mac_address for mac in node.macaddress_set.all()])

    def test_raises_validation_errors_for_invalid_data(self):
        cluster = factory.make_NodeGroup()
        cluster.accept()
        self.prepare_cluster_rpc(cluster)

        self.assertRaises(
            ValidationError, create_node, cluster.uuid,
            architecture="spam/eggs", power_type="scrambled",
            power_parameters=dumps({}),
            mac_addresses=[factory.make_mac_address()])

    def test__raises_error_if_node_already_exists(self):
        cluster = factory.make_NodeGroup()
        cluster.accept()
        self.prepare_cluster_rpc(cluster)

        mac_addresses = [
            factory.make_mac_address() for _ in range(3)]
        architecture = make_usable_architecture(self)
        power_type = random.choice(self.power_types)['name']
        power_parameters = dumps({})

        create_node(
            cluster.uuid, architecture, power_type, power_parameters,
            mac_addresses)
        self.assertRaises(
            NodeAlreadyExists, create_node, cluster.uuid, architecture,
            power_type, power_parameters, [mac_addresses[0]])
