# Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.switch`"""


from django.http import HttpRequest
from testtools import ExpectedException

from maasserver.enum import NODE_TYPE
from maasserver.exceptions import NodeActionError
from maasserver.testing.factory import factory
from maasserver.testing.fixtures import RBACForceOffFixture
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.orm import reload_object, transactional
from maasserver.websockets.base import HandlerDoesNotExistError
from maasserver.websockets.handlers.switch import SwitchHandler
from maastesting.djangotestcase import count_queries


class TestSwitchHandler(MAASTransactionServerTestCase):
    @transactional
    def test_get_no_switch(self):
        owner = factory.make_User()
        handler = SwitchHandler(owner, {}, None)
        device = factory.make_Device(owner=owner)
        self.assertRaises(
            HandlerDoesNotExistError,
            handler.get,
            {"system_id": device.system_id},
        )

    @transactional
    def test_get_device_switch(self):
        owner = factory.make_User()
        handler = SwitchHandler(owner, {}, None)
        device = factory.make_Device(owner=owner)
        factory.make_Switch(node=device)
        result = handler.get({"system_id": device.system_id})
        self.assertEqual(device.system_id, result["system_id"])
        self.assertEqual(NODE_TYPE.DEVICE, result["node_type"])

    @transactional
    def test_get_machine_switch(self):
        owner = factory.make_User()
        handler = SwitchHandler(owner, {}, None)
        machine = factory.make_Machine(owner=owner)
        factory.make_Switch(node=machine)
        handler._script_results = {}
        result = handler.get({"system_id": machine.system_id})
        self.assertEqual(machine.system_id, result["system_id"])
        self.assertEqual(NODE_TYPE.MACHINE, result["node_type"])

    @transactional
    def test_list_switches(self):
        owner = factory.make_User()
        handler = SwitchHandler(owner, {}, None)
        device = factory.make_Device(owner=owner)
        machine = factory.make_Machine(owner=owner)
        factory.make_Switch(node=device)
        factory.make_Switch(node=machine)
        self.assertItemsEqual(
            [device.system_id, machine.system_id],
            [result["system_id"] for result in handler.list({})],
        )

    @transactional
    def test_list_ignores_nodes_that_arent_switches(self):
        owner = factory.make_User()
        handler = SwitchHandler(owner, {}, None)
        factory.make_Device(owner=owner)
        factory.make_Machine(owner=owner)
        self.assertItemsEqual([], handler.list({}))

    @transactional
    def test_list_ignores_switches_with_parents(self):
        owner = factory.make_User()
        handler = SwitchHandler(owner, {}, None)
        node = factory.make_Node(owner=owner)
        device_with_parent = factory.make_Device(owner=owner)
        device_with_parent.parent = node
        device_with_parent.save()
        factory.make_Switch(node=device_with_parent)
        self.assertItemsEqual([], handler.list({}))

    @transactional
    def test_list_num_queries_is_independent_of_num_devices(self):
        # Prevent RBAC from making a query.
        self.useFixture(RBACForceOffFixture())

        owner = factory.make_User()
        handler = SwitchHandler(owner, {}, None)
        for _ in range(10):
            device = factory.make_Device(owner=owner)
            factory.make_Switch(node=device)
        query_10_count, _ = count_queries(handler.list, {})
        for _ in range(10):
            device = factory.make_Device(owner=owner)
            factory.make_Switch(node=device)
        query_20_count, _ = count_queries(handler.list, {})

        # This check is to notify the developer that a change was made that
        # affects the number of queries performed when doing a node listing.
        # It is important to keep this number as low as possible. A larger
        # number means regiond has to do more work slowing down its process
        # and slowing down the client waiting for the response.
        self.assertEqual(
            query_10_count,
            query_20_count,
            "Number of queries has changed; make sure this is expected.",
        )

    @transactional
    def test_list_returns_switches_only_viewable_by_user(self):
        user1 = factory.make_User()
        user2 = factory.make_User()
        device1 = factory.make_Device(owner=user1)
        factory.make_Switch(node=device1)
        device2 = factory.make_Device(owner=user2)
        factory.make_Switch(node=device2)
        # Create another device not ownered by user.
        handler = SwitchHandler(user1, {}, None)
        self.assertItemsEqual(
            [device1.system_id],
            [result["system_id"] for result in handler.list({})],
        )

    @transactional
    def test_list_switches_includes_link_type_device(self):
        owner = factory.make_User()
        handler = SwitchHandler(owner, {}, None)
        device = factory.make_Device(owner=owner)
        factory.make_Switch(node=device)
        self.assertItemsEqual(
            ["device"], [result["link_type"] for result in handler.list({})]
        )

    @transactional
    def test_list_switches_includes_link_type_machine(self):
        owner = factory.make_User()
        handler = SwitchHandler(owner, {}, None)
        machine = factory.make_Machine(owner=owner)
        factory.make_Switch(node=machine)
        self.assertItemsEqual(
            ["machine"], [result["link_type"] for result in handler.list({})]
        )

    @transactional
    def test_list_switches_includes_link_type_controller(self):
        owner = factory.make_admin()
        handler = SwitchHandler(owner, {}, None)
        controller1 = factory.make_RackController(owner=owner)
        controller2 = factory.make_RegionController(owner=owner)
        controller3 = factory.make_RegionRackController(owner=owner)
        factory.make_Switch(node=controller1)
        factory.make_Switch(node=controller2)
        factory.make_Switch(node=controller3)
        self.assertItemsEqual(
            ["controller", "controller", "controller"],
            [result["link_type"] for result in handler.list({})],
        )

    @transactional
    def test_get_object_returns_switch_if_super_user(self):
        admin = factory.make_admin()
        user = factory.make_User()
        device = factory.make_Device(owner=user)
        factory.make_Switch(node=device)
        handler = SwitchHandler(admin, {}, None)
        self.assertEqual(
            [device.system_id],
            [result["system_id"] for result in handler.list({})],
        )

    @transactional
    def test_get_object_returns_node_if_owner(self):
        user = factory.make_User()
        device = factory.make_Device(owner=user)
        factory.make_Switch(node=device)
        handler = SwitchHandler(user, {}, None)
        self.assertEqual(
            device.system_id,
            handler.get_object({"system_id": device.system_id}).system_id,
        )

    def test_get_object_raises_exception_if_owner_by_another_user(self):
        user1 = factory.make_User()
        user2 = factory.make_User()
        device = factory.make_Device(owner=user1)
        factory.make_Switch(node=device)
        handler = SwitchHandler(user2, {}, None)
        with ExpectedException(HandlerDoesNotExistError):
            handler.get_object({"system_id": device.system_id})

    @transactional
    def test_missing_action_raises_error(self):
        user = factory.make_User()
        device = factory.make_Device(owner=user)
        factory.make_Switch(node=device)
        handler = SwitchHandler(user, {}, None)
        with ExpectedException(NodeActionError):
            handler.action({"system_id": device.system_id})

    @transactional
    def test_invalid_action_raises_error(self):
        user = factory.make_User()
        device = factory.make_Device(owner=user)
        factory.make_Switch(node=device)
        handler = SwitchHandler(user, {}, None)
        self.assertRaises(
            NodeActionError,
            handler.action,
            {"system_id": device.system_id, "action": "unknown"},
        )

    @transactional
    def test_action_performs_action(self):
        admin = factory.make_admin()
        request = HttpRequest()
        request.user = admin
        device = factory.make_Device(owner=admin)
        factory.make_Switch(node=device)
        handler = SwitchHandler(admin, {}, request)
        handler.action(
            {
                "request": request,
                "system_id": device.system_id,
                "action": "delete",
            }
        )
        self.assertIsNone(reload_object(device))

    @transactional
    def test_action_performs_action_passing_extra(self):
        admin = factory.make_admin()
        request = HttpRequest()
        request.user = admin
        device = factory.make_Device(owner=admin)
        factory.make_Switch(node=device)
        zone = factory.make_Zone()
        handler = SwitchHandler(admin, {}, request)
        handler.action(
            {
                "request": request,
                "system_id": device.system_id,
                "action": "set-zone",
                "extra": {"zone_id": zone.id},
            }
        )
        device = reload_object(device)
        self.assertEqual(device.zone, zone)

    @transactional
    def test_on_listen_switch_update(self):
        admin = factory.make_admin()
        node = factory.make_Node(owner=admin)
        factory.make_Switch(node=node)
        handler = SwitchHandler(admin, {}, None)
        handler.list({})  # Populate the cache with the switch in it.
        obj_type, action, obj = handler.on_listen(
            "switch", "update", node.system_id
        )
        self.assertEqual("switch", obj_type)
        self.assertEqual("update", action)
        self.assertEqual(node.system_id, obj["system_id"])

    @transactional
    def test_on_listen_switch_create(self):
        admin = factory.make_admin()
        handler = SwitchHandler(admin, {}, None)
        handler.list({})  # Populate the cache with no switches.
        node = factory.make_Node(owner=admin)
        factory.make_Switch(node=node)
        obj_type, action, obj = handler.on_listen(
            "switch", "create", node.system_id
        )
        self.assertEqual("switch", obj_type)
        self.assertEqual("create", action)
        self.assertEqual(node.system_id, obj["system_id"])

    @transactional
    def test_on_listen_non_switch_create(self):
        admin = factory.make_admin()
        handler = SwitchHandler(admin, {}, None)
        node = factory.make_Node(owner=admin)
        handler.list({})  # Populate the cache with no switches.
        for obj_type in ["device", "controller", "machine"]:
            result = handler.on_listen(obj_type, "create", node.system_id)
            self.assertIsNone(result)
            self.assertNotIn(node.system_id, handler.cache["loaded_pks"])

    @transactional
    def test_on_listen_non_switch_delete(self):
        admin = factory.make_admin()
        handler = SwitchHandler(admin, {}, None)
        node = factory.make_Node(owner=admin)
        factory.make_Switch(node=node)
        handler.list({})  # Populate the cache with the switch in it.
        for obj_type in ["device", "controller", "machine"]:
            result = handler.on_listen(obj_type, "create", node.system_id)
            self.assertIsNone(result)
            self.assertIn(node.system_id, handler.cache["loaded_pks"])

    @transactional
    def test_on_listen_non_switch_update(self):
        admin = factory.make_admin()
        handler = SwitchHandler(admin, {}, None)
        node = factory.make_Node(owner=admin)
        handler.list({})  # Populate the cache with no switches.
        for obj_type in ["device", "controller", "machine"]:
            result = handler.on_listen(obj_type, "update", node.system_id)
            self.assertIsNone(result)
            self.assertNotIn(node.system_id, handler.cache["loaded_pks"])

    @transactional
    def test_on_listen_non_switch_event_update(self):
        admin = factory.make_admin()
        handler = SwitchHandler(admin, {}, None)
        node = factory.make_Node(owner=admin)
        factory.make_Switch(node=node)
        handler.list({})  # Populate the cache with the switch in it.
        for obj_type in ["device", "controller", "machine"]:
            new_hostname = "updated-{}".format(obj_type)
            node.hostname = new_hostname
            node.save()
            listen_obj_type, action, obj = handler.on_listen(
                obj_type, "update", node.system_id
            )
            self.assertIn(node.system_id, handler.cache["loaded_pks"])
            self.assertEqual("switch", listen_obj_type)
            self.assertEqual("update", action)
            self.assertEqual(node.system_id, obj["system_id"])
            self.assertEqual(new_hostname, obj["hostname"])
