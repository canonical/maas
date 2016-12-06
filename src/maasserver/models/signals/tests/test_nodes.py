# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the behaviour of node signals."""

__all__ = []

import random

from maasserver.enum import (
    NODE_STATUS,
    NODE_TYPE,
)
from maasserver.models import ChassisHints
from maasserver.models.service import (
    RACK_SERVICES,
    REGION_SERVICES,
    Service,
)
from maasserver.node_status import NODE_TRANSITIONS
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from metadataserver.models.nodekey import NodeKey
from testtools.matchers import (
    Equals,
    HasLength,
    Is,
    MatchesStructure,
    Not,
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


class TestCreateChassisHints(MAASServerTestCase):

    def test_creates_hints_for_chassis(self):
        chassis = factory.make_Node(node_type=NODE_TYPE.CHASSIS)
        self.assertIsNotNone(chassis.chassis_hints)

    def test_creates_hints_device_converted_to_chassis(self):
        device = factory.make_Device()
        device.node_type = NODE_TYPE.CHASSIS
        device.save()
        self.assertIsNotNone(device.chassis_hints)

    def test_deletes_hints_when_chassis_converted_to_device(self):
        chassis = factory.make_Node(node_type=NODE_TYPE.CHASSIS)
        chassis.node_type = NODE_TYPE.DEVICE
        chassis.save()
        error = None
        try:
            reload_object(chassis).chassis_hints
        except ChassisHints.DoesNotExist as exc:
            error = exc
        self.assertIsNotNone(error)
