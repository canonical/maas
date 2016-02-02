# Copyright 2014-2016 Canonical Ltd. This software is licnesed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module;`maasserver.rpc.rackcontroller`."""

__all__ = []

import random

from django.db import IntegrityError
from fixtures import FakeLogger
from maasserver import worker_user
from maasserver.enum import NODE_TYPE
from maasserver.models import (
    Interface,
    Node,
    RackController,
)
from maasserver.rpc.rackcontrollers import (
    register_new_rackcontroller,
    register_rackcontroller,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestRegisterRackController(MAASServerTestCase):

    def test_sets_owner_to_worker(self):
        node = factory.make_Node()
        rack_registered = register_rackcontroller(system_id=node.system_id)
        self.assertEqual(worker_user.get_worker_user(), rack_registered.owner)

    def test_finds_existing_node_by_system_id(self):
        node = factory.make_Node()
        rack_registered = register_rackcontroller(system_id=node.system_id)
        self.assertEqual(node.system_id, rack_registered.system_id)

    def test_finds_existing_node_by_hostname(self):
        node = factory.make_Node()
        rack_registered = register_rackcontroller(hostname=node.hostname)
        self.assertEqual(node.system_id, rack_registered.system_id)

    def test_finds_existing_node_by_mac(self):
        node = factory.make_Node()
        nic = factory.make_Interface(node=node)
        mac = nic.mac_address.raw
        rack_registered = register_rackcontroller(mac_addresses=[mac])
        self.assertEqual(node.system_id, rack_registered.system_id)

    def test_finds_existing_node_sets_needs_refresh_to_false(self):
        node = factory.make_Node()
        rack_registered = register_rackcontroller(system_id=node.system_id)
        self.assertFalse(rack_registered.needs_refresh)

    def test_find_existing_keeps_type(self):
        node_type = random.choice(
            (NODE_TYPE.RACK_CONTROLLER, NODE_TYPE.REGION_AND_RACK_CONTROLLER))
        node = factory.make_Node(node_type=node_type)
        register_rackcontroller(system_id=node.system_id)
        self.assertEqual(node_type, node.node_type)

    def test_logs_finding_existing_node(self):
        logger = self.useFixture(FakeLogger("maas"))
        node = factory.make_Node(node_type=NODE_TYPE.RACK_CONTROLLER)
        register_rackcontroller(system_id=node.system_id)
        self.assertEqual(
            "Registering existing rack controller %s." % node.hostname,
            logger.output.strip())

    def test_converts_region_controller(self):
        node = factory.make_Node(node_type=NODE_TYPE.REGION_CONTROLLER)
        rack_registered = register_rackcontroller(system_id=node.system_id)
        self.assertEqual(
            rack_registered.node_type, NODE_TYPE.REGION_AND_RACK_CONTROLLER)

    def test_logs_converting_region_controller(self):
        logger = self.useFixture(FakeLogger("maas"))
        node = factory.make_Node(node_type=NODE_TYPE.REGION_CONTROLLER)
        register_rackcontroller(system_id=node.system_id)
        self.assertEqual(
            "Converting %s into a region and rack controller." % node.hostname,
            logger.output.strip())

    def test_converts_existing_node(self):
        node = factory.make_Node(node_type=NODE_TYPE.MACHINE)
        rack_registered = register_rackcontroller(system_id=node.system_id)
        self.assertEqual(rack_registered.node_type, NODE_TYPE.RACK_CONTROLLER)

    def test_logs_converting_existing_node(self):
        logger = self.useFixture(FakeLogger("maas"))
        node = factory.make_Node(node_type=NODE_TYPE.MACHINE)
        register_rackcontroller(system_id=node.system_id)
        self.assertEqual(
            "Converting %s into a rack controller." % node.hostname,
            logger.output.strip())

    def test_creates_new_rackcontroller(self):
        factory.make_Node()
        node_count = len(Node.objects.all())
        interface_count = len(Interface.objects.all())
        register_rackcontroller(mac_addresses=[factory.make_MAC()])
        self.assertEqual(node_count + 1, len(Node.objects.all()))
        self.assertEqual(interface_count + 1, len(Interface.objects.all()))

    def test_creates_new_rackcontroller_sets_needs_refresh_to_true(self):
        rack_registered = register_rackcontroller(
            mac_addresses=[factory.make_MAC()])
        self.assertTrue(rack_registered.needs_refresh)

    def test_logs_creating_new_rackcontroller(self):
        logger = self.useFixture(FakeLogger("maas"))
        hostname = factory.make_name("hostname")
        register_rackcontroller(hostname=hostname)
        self.assertEqual(
            "%s has been created as a new rack controller" % hostname,
            logger.output.strip())

    def test_retries_existing_on_new_integrity_error(self):
        hostname = factory.make_name("hostname")
        node = factory.make_Node(hostname=hostname)
        patched_create = self.patch(RackController.objects, 'create')
        patched_create.side_effect = IntegrityError()
        rack_registered = register_new_rackcontroller(None, hostname, [])
        self.assertEqual(rack_registered.system_id, node.system_id)

    def test_raises_exception_on_new_and_existing_failure(self):
        patched_create = self.patch(RackController.objects, 'create')
        patched_create.side_effect = IntegrityError()
        self.assertRaises(
            IntegrityError, register_new_rackcontroller,
            None, factory.make_name("hostname"), [])

    def test_logs_retrying_existing_on_new_integrity_error(self):
        logger = self.useFixture(FakeLogger("maas"))
        hostname = factory.make_name("hostname")
        patched_create = self.patch(RackController.objects, 'create')
        patched_create.side_effect = IntegrityError()
        try:
            register_new_rackcontroller(None, hostname, [])
        except IntegrityError:
            pass
        self.assertEqual(
            "Rack controller(%s) currently being registered, retrying..." %
            hostname, logger.output.strip())
