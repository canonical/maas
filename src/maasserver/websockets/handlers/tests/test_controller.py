# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.controller`"""

__all__ = []

from maasserver.enum import NODE_TYPE
from maasserver.forms import AdminMachineWithMACAddressesForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import dehydrate_datetime
from maasserver.websockets.handlers.controller import ControllerHandler
from testscenarios import multiply_scenarios
from testtools.matchers import (
    ContainsDict,
    Equals,
)


class TestControllerHandler(MAASServerTestCase):

    def make_controllers(self, number):
        """Create `number` of new nodes."""
        for counter in range(number):
            factory.make_RackController()

    def test_last_image_sync(self):
        owner = factory.make_admin()
        handler = ControllerHandler(owner, {})
        node = factory.make_RackController(owner=owner)
        result = handler.list({})
        self.assertEqual(1, len(result))
        self.assertEqual(NODE_TYPE.RACK_CONTROLLER, result[0].get('node_type'))
        self.assertEqual(result[0].get(
            'last_image_sync'), dehydrate_datetime(node.last_image_sync))
        data = handler.get({"system_id": node.system_id})
        self.assertEqual(data.get("last_image_sync"), dehydrate_datetime(
            node.last_image_sync))

    def test_last_image_sync_returns_none_for_none(self):
        owner = factory.make_admin()
        handler = ControllerHandler(owner, {})
        node = factory.make_RackController(owner=owner, last_image_sync=None)
        result = handler.list({})
        self.assertEqual(1, len(result))
        self.assertEqual(NODE_TYPE.RACK_CONTROLLER, result[0].get('node_type'))
        self.assertIsNone(result[0].get("last_image_sync"))
        data = handler.get({"system_id": node.system_id})
        self.assertIsNone(data.get("last_image_sync"))

    def test_list_ignores_devices_and_nodes(self):
        owner = factory.make_admin()
        handler = ControllerHandler(owner, {})
        # Create a device.
        factory.make_Node(owner=owner, node_type=NODE_TYPE.DEVICE)
        # Create a device with Node parent.
        node = factory.make_Node(owner=owner)
        device_with_parent = factory.make_Node(owner=owner, interface=True)
        device_with_parent.parent = node
        device_with_parent.save()
        node = factory.make_RackController(owner=owner)
        result = handler.list({})
        self.assertEqual(1, len(result))
        self.assertEqual(NODE_TYPE.RACK_CONTROLLER, result[0].get('node_type'))

    def test_get_form_class_for_create(self):
        user = factory.make_admin()
        handler = ControllerHandler(user, {})
        self.assertEqual(
            AdminMachineWithMACAddressesForm,
            handler.get_form_class("create"))

    def test_get_form_class_for_update(self):
        user = factory.make_admin()
        handler = ControllerHandler(user, {})
        self.assertEqual(
            AdminMachineWithMACAddressesForm,
            handler.get_form_class("update"))

    def test_check_images(self):
        owner = factory.make_admin()
        handler = ControllerHandler(owner, {})
        node1 = factory.make_RackController(owner=owner)
        node2 = factory.make_RackController(owner=owner)
        data = handler.check_images([
            {"system_id": node1.system_id},
            {"system_id": node2.system_id}])
        self.assertEqual({
            node1.system_id: "Unknown",
            node2.system_id: "Unknown"}, data)


class TestControllerHandlerScenarios(MAASServerTestCase):

    scenarios_controllers = (
        ("rack", dict(
            make_controller=factory.make_RackController)),
        ("region", dict(
            make_controller=factory.make_RegionController)),
        ("region+rack", dict(
            make_controller=factory.make_RegionRackController)),
    )

    scenarios_fetch_types = (
        ("in-full", dict(for_list=False)),
        ("for-list", dict(for_list=True)),
    )

    scenarios = multiply_scenarios(
        scenarios_controllers, scenarios_fetch_types)

    def test_fully_dehydrated_controller_contains_essential_fields(self):
        user = factory.make_User()
        controller = self.make_controller()
        handler = ControllerHandler(user, {})
        data = handler.full_dehydrate(controller, for_list=False)
        self.assertThat(data, ContainsDict({
            handler._meta.pk: Equals(
                getattr(controller, handler._meta.pk)),
            handler._meta.batch_key: Equals(
                getattr(controller, handler._meta.batch_key)),
        }))
