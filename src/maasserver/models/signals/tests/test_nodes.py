# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the behaviour of node signals."""

__all__ = []

import random

from maasserver.enum import (
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_TYPE,
)
from maasserver.models.service import (
    RACK_SERVICES,
    REGION_SERVICES,
    Service,
)
from maasserver.models.signals import power
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

    def setUp(self):
        super(TestNodePreviousStatus, self).setUp()
        # Disable power signals: some status transitions prompt a power check.
        self.addCleanup(power.signals.enable)
        power.signals.disable()

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

    def test_chaning_status_doesnt_store_blacklisted_statuses(self):
        black_listed_statuses = [
            NODE_STATUS.RESCUE_MODE,
            NODE_STATUS.ENTERING_RESCUE_MODE,
            NODE_STATUS.FAILED_ENTERING_RESCUE_MODE,
            NODE_STATUS.EXITING_RESCUE_MODE,
            NODE_STATUS.FAILED_EXITING_RESCUE_MODE,
            NODE_STATUS.TESTING,
            NODE_STATUS.FAILED_TESTING,
        ]
        status = random.choice(black_listed_statuses)
        previous_status = factory.pick_choice(
            NODE_STATUS_CHOICES, but_not=black_listed_statuses)
        node = factory.make_Node(
            previous_status=previous_status, status=status)
        node.status = random.choice(NODE_TRANSITIONS[node.status])
        node.save()
        self.assertEquals(previous_status, node.previous_status)


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
