# Copyright 2015-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import random

from maasserver.enum import (
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_TYPE,
    NODE_TYPE_CHOICES,
)
from maasserver.models import Node, RackController, StaticIPAddress
from maasserver.models.nodekey import NodeKey
from maasserver.models.service import RACK_SERVICES, REGION_SERVICES, Service
from maasserver.models.signals import power
from maasserver.node_status import NODE_TRANSITIONS
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from provisioningserver.enum import POWER_STATE, POWER_STATE_CHOICES


class TestNodeDeletion(MAASServerTestCase):
    def test_deleting_node_updates_event_node_hostname(self):
        """Test that event's `node_hostname` is set when the node is going to be
        deleted."""
        node = factory.make_Node()
        node_hostname = node.hostname
        events = [factory.make_Event(node=node) for _ in range(3)]
        node.delete()
        for event in events:
            self.assertEqual(event.node_hostname, node_hostname)

    def test_deleting_node_sets_node_to_null(self):
        node = factory.make_Node()
        events = [factory.make_Event(node=node) for _ in range(3)]
        node.delete()
        for event in events:
            event = reload_object(event)
            self.assertIsNone(event.node)


class TestNodePreviousStatus(MAASServerTestCase):
    """Test that `previous_status` is set when the status is changed."""

    def setUp(self):
        super().setUp()
        # Disable power signals: some status transitions prompt a power check.
        self.addCleanup(power.signals.enable)
        power.signals.disable()

    def test_changing_status_updates_previous_status(self):
        node = factory.make_Node()
        old_status = node.status
        new_status = random.choice(NODE_TRANSITIONS[node.status])
        node.update_status(new_status)
        node.save()
        self.assertEqual(node.status, new_status)
        self.assertEqual(node.previous_status, old_status)

    def test_chaning_status_doesnt_store_blacklisted_statuses(self):
        black_listed_statuses = [
            NODE_STATUS.RESCUE_MODE,
            NODE_STATUS.ENTERING_RESCUE_MODE,
            NODE_STATUS.FAILED_ENTERING_RESCUE_MODE,
            NODE_STATUS.EXITING_RESCUE_MODE,
            NODE_STATUS.FAILED_EXITING_RESCUE_MODE,
            NODE_STATUS.TESTING,
        ]
        status = random.choice(black_listed_statuses)
        previous_status = factory.pick_choice(
            NODE_STATUS_CHOICES, but_not=black_listed_statuses
        )
        node = factory.make_Node(
            previous_status=previous_status, status=status
        )
        node.update_status(random.choice(NODE_TRANSITIONS[node.status]))
        node.save()
        self.assertEqual(previous_status, node.previous_status)


class TestNodeClearsOwnerNEWOrREADYStatus(MAASServerTestCase):
    """Test that `owner` is cleared when the status is set to
    NEW or READY state.
    """

    def setUp(self):
        super().setUp()
        # Disable power signals: some status transitions prompt a power check.
        self.addCleanup(power.signals.enable)
        power.signals.disable()

    def test_changing_to_new_status_clears_owner(self):
        node = factory.make_Node(
            owner=factory.make_User(), status=NODE_STATUS.COMMISSIONING
        )
        node.update_status(NODE_STATUS.NEW)
        node.save()
        self.assertIsNone(node.owner)

    def test_changing_to_ready_status_clears_owner(self):
        node = factory.make_Node(owner=factory.make_User())
        node.update_status(NODE_STATUS.READY)
        node.save()
        self.assertIsNone(node.owner)


class TestNodeKeyPolicy(MAASServerTestCase):
    """Test that `NodeKey`s are cleared when nodes change ownership."""

    def test_changing_owner_clears_node_key(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Ensure the node has an owner.
        node.owner = factory.make_User()
        node.save()
        # Ensure there's a token.
        token = NodeKey.objects.get_token_for_node(node)
        self.assertIsNotNone(token)
        # Change the owner.
        node.owner = factory.make_User()
        node.save()
        # The token has been deleted.
        token = reload_object(token)
        self.assertIsNone(token)

    def test_clearing_owner_clears_node_key(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Ensure the node has an owner.
        node.owner = factory.make_User()
        node.save()
        # Ensure there's a token.
        token = NodeKey.objects.get_token_for_node(node)
        self.assertIsNotNone(token)
        # Remove the owner.
        node.owner = None
        node.save()
        # The token has been deleted.
        token = reload_object(token)
        self.assertIsNone(token)

    def test_setting_owner_clears_node_key(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Ensure the node has no owner.
        node.owner = None
        node.save()
        # Ensure there's a token.
        token = NodeKey.objects.get_token_for_node(node)
        self.assertIsNotNone(token)
        # Set the owner.
        node.owner = factory.make_User()
        node.save()
        # The token has been deleted.
        token = reload_object(token)
        self.assertIsNone(token)


class TestNodeCreateServices(MAASServerTestCase):
    """Test that services are created when a node is created
    or node_type changes.
    """

    def test_doesnt_create_services_for_machine(self):
        machine = factory.make_Node()
        services = Service.objects.filter(node=machine)
        self.assertEqual({service.name for service in services}, set())

    def test_doesnt_create_services_for_device(self):
        device = factory.make_Device()
        services = Service.objects.filter(node=device)
        self.assertEqual({service.name for service in services}, set())

    def test_creates_services_for_rack_controller(self):
        rack_controller = factory.make_RackController()
        services = Service.objects.filter(node=rack_controller)
        self.assertEqual(RACK_SERVICES, {service.name for service in services})

    def test_creates_services_for_region_controller(self):
        region_controller = factory.make_RegionController()
        services = Service.objects.filter(node=region_controller)
        self.assertEqual(
            REGION_SERVICES, {service.name for service in services}
        )

    def test_creates_services_when_region_converts_to_region_rack(self):
        controller = factory.make_RegionController()
        controller.node_type = NODE_TYPE.REGION_AND_RACK_CONTROLLER
        controller.save()
        services = Service.objects.filter(node=controller)
        self.assertEqual(
            REGION_SERVICES | RACK_SERVICES,
            {service.name for service in services},
        )

    def test_creates_services_when_rack_controller_becomes_just_region(self):
        controller = factory.make_RackController()
        controller.node_type = NODE_TYPE.REGION_CONTROLLER
        controller.save()
        services = Service.objects.filter(node=controller)
        self.assertEqual(
            REGION_SERVICES, {service.name for service in services}
        )


class TestNodeDefaultNUMANode(MAASServerTestCase):
    def test_create_node_creates_default_numanode(self):
        node = Node()
        node.save()
        [numanode] = node.numanode_set.all()
        self.assertIs(numanode.node, node)
        self.assertEqual(numanode.index, 0)

    def test_create_node_creates_default_numanode_controller(self):
        node = RackController()
        node.save()
        [numanode] = node.numanode_set.all()
        self.assertIs(numanode.node, node)
        self.assertEqual(numanode.index, 0)

    def test_update_doesnt_create_numanode(self):
        node = factory.make_Node()
        [numanode] = node.numanode_set.all()
        node.hostname = factory.make_string()
        node.save()
        [new_numanode] = node.numanode_set.all()
        self.assertEqual(new_numanode.id, numanode.id)

    def test_not_for_devices(self):
        device = factory.make_Device()
        self.assertEqual(device.numanode_set.count(), 0)


class TestNodeReleasesAutoIPs(MAASServerTestCase):
    """Test that auto ips are released when node power is off."""

    def __init__(self, *args, **kwargs):
        self.reserved_statuses = [
            NODE_STATUS.COMMISSIONING,
            NODE_STATUS.DEPLOYED,
            NODE_STATUS.DEPLOYING,
            NODE_STATUS.DISK_ERASING,
            NODE_STATUS.RESCUE_MODE,
            NODE_STATUS.ENTERING_RESCUE_MODE,
            NODE_STATUS.TESTING,
        ]
        self.scenarios = [
            (status_label, {"status": status})
            for status, status_label in NODE_STATUS_CHOICES
            if status not in self.reserved_statuses
        ]
        super().__init__(*args, **kwargs)

    def test_releases_interface_config_when_turned_off(self):
        machine = factory.make_Machine_with_Interface_on_Subnet(
            status=random.choice(self.reserved_statuses),
            power_state=POWER_STATE.ON,
        )
        for interface in machine.current_config.interface_set.all():
            interface.claim_auto_ips()

        # Hack to get around node transition model
        Node.objects.filter(id=machine.id).update(status=self.status)
        machine = reload_object(machine)
        machine.power_state = POWER_STATE.OFF
        machine.save()

        for ip in StaticIPAddress.objects.filter(
            interface__node_config__node=machine,
            alloc_type=IPADDRESS_TYPE.AUTO,
        ):
            self.assertIsNone(ip.ip)

    def test_does_nothing_if_not_off(self):
        machine = factory.make_Machine_with_Interface_on_Subnet(
            status=random.choice(self.reserved_statuses),
            power_state=POWER_STATE.ON,
        )
        for interface in machine.current_config.interface_set.all():
            interface.claim_auto_ips()

        # Hack to get around node transition model
        Node.objects.filter(id=machine.id).update(status=self.status)
        machine = reload_object(machine)
        machine.power_state = factory.pick_choice(
            POWER_STATE_CHOICES, but_not=[POWER_STATE.OFF]
        )
        machine.save()

        for ip in StaticIPAddress.objects.filter(
            interface__node_config__node=machine,
            alloc_type=IPADDRESS_TYPE.AUTO,
        ):
            self.assertIsNotNone(ip.ip)

    def test_does_nothing_if_reserved_status(self):
        machine = factory.make_Machine_with_Interface_on_Subnet(
            status=self.status, power_state=POWER_STATE.ON
        )
        for interface in machine.current_config.interface_set.all():
            interface.claim_auto_ips()

        # Hack to get around node transition model
        Node.objects.filter(id=machine.id).update(
            status=random.choice(self.reserved_statuses)
        )
        machine = reload_object(machine)
        machine.power_state = POWER_STATE.OFF
        machine.save()

        for ip in StaticIPAddress.objects.filter(
            interface__node_config__node=machine,
            alloc_type=IPADDRESS_TYPE.AUTO,
        ):
            self.assertIsNotNone(ip.ip)

    def test_does_nothing_if_not_machine(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            node_type=factory.pick_choice(
                NODE_TYPE_CHOICES, but_not=[NODE_TYPE.MACHINE]
            ),
            status=random.choice(self.reserved_statuses),
            power_state=POWER_STATE.ON,
        )
        for interface in node.current_config.interface_set.all():
            interface.claim_auto_ips()

        # Hack to get around node transition model
        Node.objects.filter(id=node.id).update(status=self.status)
        node = reload_object(node)
        node.power_state = POWER_STATE.OFF
        node.save()

        for ip in StaticIPAddress.objects.filter(
            interface__node_config__node=node, alloc_type=IPADDRESS_TYPE.AUTO
        ):
            self.assertIsNotNone(ip.ip)
