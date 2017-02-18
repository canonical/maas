# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the behaviour of node signals."""

__all__ = []

import random
from unittest.mock import Mock

import crochet
from maasserver.enum import (
    NODE_CREATION_TYPE,
    NODE_STATUS,
    NODE_TYPE,
    NODE_TYPE_CHOICES,
)
from maasserver.exceptions import PodProblem
from maasserver.models.service import (
    RACK_SERVICES,
    REGION_SERVICES,
    Service,
)
from maasserver.models.signals import nodes as nodes_signals
from maasserver.node_status import NODE_TRANSITIONS
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from metadataserver.models.nodekey import NodeKey
from provisioningserver.drivers.pod import (
    Capabilities,
    DiscoveredPodHints,
)
from provisioningserver.rpc.cluster import DecomposeMachine
from provisioningserver.rpc.exceptions import PodActionFail
from testtools.matchers import (
    Equals,
    HasLength,
    Is,
    MatchesStructure,
    Not,
)
from twisted.internet.defer import (
    fail,
    succeed,
)


class TestNodePreviousStatus(MAASServerTestCase):
    """Test that `previous_status` is set when the status is changed."""

    def test_changing_status_updates_previous_status(self):
        node = factory.make_Node()
        old_status = node.status
        new_status = random.choice(NODE_TRANSITIONS[node.status])
        node.status = new_status
        node.save()
        self.assertThat(
            node,
            MatchesStructure.byEquality(
                status=new_status, previous_status=old_status))


class TestNodeKeyPolicy(MAASServerTestCase):
    """Test that `NodeKey`s are cleared when nodes change ownership."""

    def test_changing_owner_clears_node_key(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Ensure the node has an owner.
        node.owner = factory.make_User()
        node.save()
        # Ensure there's a token.
        token = NodeKey.objects.get_token_for_node(node)
        self.assertThat(token, Not(Is(None)))
        # Change the owner.
        node.owner = factory.make_User()
        node.save()
        # The token has been deleted.
        token = reload_object(token)
        self.assertThat(token, Is(None))

    def test_clearing_owner_clears_node_key(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Ensure the node has an owner.
        node.owner = factory.make_User()
        node.save()
        # Ensure there's a token.
        token = NodeKey.objects.get_token_for_node(node)
        self.assertThat(token, Not(Is(None)))
        # Remove the owner.
        node.owner = None
        node.save()
        # The token has been deleted.
        token = reload_object(token)
        self.assertThat(token, Is(None))

    def test_setting_owner_clears_node_key(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Ensure the node has no owner.
        node.owner = None
        node.save()
        # Ensure there's a token.
        token = NodeKey.objects.get_token_for_node(node)
        self.assertThat(token, Not(Is(None)))
        # Set the owner.
        node.owner = factory.make_User()
        node.save()
        # The token has been deleted.
        token = reload_object(token)
        self.assertThat(token, Is(None))


class TestNodeCreateServices(MAASServerTestCase):
    """Test that services are created when a node is created
    or node_type changes.
    """

    def test_doesnt_create_services_for_machine(self):
        machine = factory.make_Node()
        services = Service.objects.filter(node=machine)
        self.assertThat(
            {service.name for service in services},
            HasLength(0))

    def test_doesnt_create_services_for_device(self):
        device = factory.make_Device()
        services = Service.objects.filter(node=device)
        self.assertThat(
            {service.name for service in services},
            HasLength(0))

    def test_creates_services_for_rack_controller(self):
        rack_controller = factory.make_RackController()
        services = Service.objects.filter(node=rack_controller)
        self.assertThat(
            {service.name for service in services},
            Equals(RACK_SERVICES))

    def test_creates_services_for_region_controller(self):
        region_controller = factory.make_RegionController()
        services = Service.objects.filter(node=region_controller)
        self.assertThat(
            {service.name for service in services},
            Equals(REGION_SERVICES))

    def test_creates_services_when_region_converts_to_region_rack(self):
        controller = factory.make_RegionController()
        controller.node_type = NODE_TYPE.REGION_AND_RACK_CONTROLLER
        controller.save()
        services = Service.objects.filter(node=controller)
        self.assertThat(
            {service.name for service in services},
            Equals(REGION_SERVICES | RACK_SERVICES))

    def test_creates_services_when_rack_controller_becomes_just_region(self):
        controller = factory.make_RackController()
        controller.node_type = NODE_TYPE.REGION_CONTROLLER
        controller.save()
        services = Service.objects.filter(node=controller)
        self.assertThat(
            {service.name for service in services},
            Equals(REGION_SERVICES))


class TestDecomposeMachine(MAASServerTestCase):
    """Test that a machine in a composable pod is decomposed."""

    def make_composable_pod(self):
        return factory.make_Pod(capabilities=[Capabilities.COMPOSABLE])

    def fake_rpc_client(self):
        client = Mock()
        client.return_value = succeed({})
        self.patch(
            nodes_signals,
            "getClientFromIdentifiers").return_value = succeed(client)
        return client

    def test_does_nothing_unless_machine(self):
        pod = self.make_composable_pod()
        client = self.fake_rpc_client()
        for node_type, _ in NODE_TYPE_CHOICES:
            if node_type != NODE_TYPE.MACHINE:
                node = factory.make_Node(node_type=node_type)
                node.bmc = pod
                node.save()
                node.delete()
        self.assertThat(client, MockNotCalled())

    def test_does_nothing_if_machine_without_bmc(self):
        client = self.fake_rpc_client()
        machine = factory.make_Node()
        machine.bmc = None
        machine.save()
        machine.delete()
        self.assertThat(client, MockNotCalled())

    def test_does_nothing_if_standard_bmc(self):
        client = self.fake_rpc_client()
        machine = factory.make_Node()
        machine.bmc = factory.make_BMC()
        machine.save()
        machine.delete()
        self.assertThat(client, MockNotCalled())

    def test_does_nothing_if_none_composable_pod(self):
        client = self.fake_rpc_client()
        machine = factory.make_Node()
        machine.bmc = factory.make_Pod()
        machine.save()
        machine.delete()
        self.assertThat(client, MockNotCalled())

    def test_does_nothing_if_pre_existing_machine(self):
        client = self.fake_rpc_client()
        machine = factory.make_Node()
        machine.bmc = self.make_composable_pod()
        machine.save()
        machine.delete()
        self.assertThat(client, MockNotCalled())

    def test_performs_decompose_machine(self):
        hints = DiscoveredPodHints(
            cores=random.randint(1, 8),
            cpu_speed=random.randint(1000, 2000),
            memory=random.randint(1024, 8192), local_storage=0)
        pod = self.make_composable_pod()
        client = self.fake_rpc_client()
        client.return_value = succeed({
            'hints': hints,
        })
        machine = factory.make_Node(
            creation_type=NODE_CREATION_TYPE.MANUAL)
        machine.bmc = pod
        machine.instance_power_parameters = {
            'power_id': factory.make_name('power_id'),
        }
        machine.save()
        machine.delete()
        self.assertThat(
            client, MockCalledOnceWith(
                DecomposeMachine,
                type=pod.power_type, context=machine.power_parameters,
                pod_id=pod.id, name=pod.name))
        self.assertThat(pod.hints, MatchesStructure.byEquality(
            cores=hints.cores,
            memory=hints.memory,
            local_storage=hints.local_storage,
        ))

    def test_decompose_machine_handles_timeout(self):
        pod = self.make_composable_pod()
        client = self.fake_rpc_client()
        client.side_effect = crochet.TimeoutError()
        machine = factory.make_Node(
            creation_type=NODE_CREATION_TYPE.MANUAL)
        machine.bmc = pod
        machine.instance_power_parameters = {
            'power_id': factory.make_name('power_id'),
        }
        machine.save()
        error = self.assertRaises(PodProblem, machine.delete)
        self.assertEquals(
            "Unable to decomposed machine because '%s' driver timed out "
            "after 60 seconds." % pod.power_type, str(error))

    def test_errors_raised_up(self):
        pod = self.make_composable_pod()
        client = self.fake_rpc_client()
        client.return_value = fail(PodActionFail())
        machine = factory.make_Node(
            creation_type=NODE_CREATION_TYPE.MANUAL)
        machine.bmc = pod
        machine.instance_power_parameters = {
            'power_id': factory.make_name('power_id'),
        }
        machine.save()
        self.assertRaises(PodProblem, machine.delete)
