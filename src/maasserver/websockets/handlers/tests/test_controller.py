# Copyright 2016-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.controller`"""


from unittest import skip

from testscenarios import multiply_scenarios
from testtools.matchers import ContainsDict, Equals

from maasserver.config import RegionConfiguration
from maasserver.enum import NODE_TYPE
from maasserver.forms import ControllerForm
from maasserver.models import Config, ControllerInfo
from maasserver.testing.factory import factory
from maasserver.testing.fixtures import RBACForceOffFixture
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import (
    dehydrate_datetime,
    HandlerPermissionError,
)
from maasserver.websockets.handlers.controller import ControllerHandler
from maastesting.djangotestcase import count_queries
from metadataserver.enum import RESULT_TYPE, SCRIPT_STATUS


class TestControllerHandler(MAASServerTestCase):
    def make_controllers(self, number):
        """Create `number` of new nodes."""
        for counter in range(number):
            factory.make_RackController()

    def test_last_image_sync(self):
        owner = factory.make_admin()
        handler = ControllerHandler(owner, {}, None)
        node = factory.make_RackController(owner=owner)
        result = handler.list({})
        self.assertEqual(1, len(result))
        self.assertEqual(NODE_TYPE.RACK_CONTROLLER, result[0].get("node_type"))
        self.assertEqual(
            result[0].get("last_image_sync"),
            dehydrate_datetime(node.last_image_sync),
        )
        data = handler.get({"system_id": node.system_id})
        self.assertEqual(
            data.get("last_image_sync"),
            dehydrate_datetime(node.last_image_sync),
        )

    def test_last_image_sync_returns_none_for_none(self):
        owner = factory.make_admin()
        handler = ControllerHandler(owner, {}, None)
        node = factory.make_RackController(owner=owner, last_image_sync=None)
        result = handler.list({})
        self.assertEqual(1, len(result))
        self.assertEqual(NODE_TYPE.RACK_CONTROLLER, result[0].get("node_type"))
        self.assertIsNone(result[0].get("last_image_sync"))
        data = handler.get({"system_id": node.system_id})
        self.assertIsNone(data.get("last_image_sync"))

    def test_list_ignores_devices_and_nodes(self):
        owner = factory.make_admin()
        handler = ControllerHandler(owner, {}, None)
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
        self.assertEqual(NODE_TYPE.RACK_CONTROLLER, result[0].get("node_type"))

    def test_list_num_queries_is_the_expected_number(self):
        self.useFixture(RBACForceOffFixture())

        owner = factory.make_admin()
        for _ in range(10):
            node = factory.make_RegionRackController(owner=owner)
            commissioning_script_set = factory.make_ScriptSet(
                node=node, result_type=RESULT_TYPE.COMMISSIONING
            )
            testing_script_set = factory.make_ScriptSet(
                node=node, result_type=RESULT_TYPE.TESTING
            )
            node.current_commissioning_script_set = commissioning_script_set
            node.current_testing_script_set = testing_script_set
            node.save()
            for __ in range(10):
                factory.make_ScriptResult(
                    status=SCRIPT_STATUS.PASSED,
                    script_set=commissioning_script_set,
                )
                factory.make_ScriptResult(
                    status=SCRIPT_STATUS.PASSED, script_set=testing_script_set
                )

        handler = ControllerHandler(owner, {}, None)
        queries_one, _ = count_queries(handler.list, {"limit": 1})
        queries_total, _ = count_queries(handler.list, {})
        # This check is to notify the developer that a change was made that
        # affects the number of queries performed when doing a node listing.
        # It is important to keep this number as low as possible. A larger
        # number means regiond has to do more work slowing down its process
        # and slowing down the client waiting for the response.
        self.assertEqual(
            queries_one,
            4,
            "Number of queries has changed; make sure this is expected.",
        )
        self.assertEqual(
            queries_total,
            4,
            "Number of queries has changed; make sure this is expected.",
        )

    @skip("XXX: ltrager 2919-11-29 bug=1854546")
    def test_get_num_queries_is_the_expected_number(self):
        owner = factory.make_admin()
        node = factory.make_RegionRackController(owner=owner)
        commissioning_script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.COMMISSIONING
        )
        testing_script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.TESTING
        )
        node.current_commissioning_script_set = commissioning_script_set
        node.current_testing_script_set = testing_script_set
        node.save()
        for __ in range(10):
            factory.make_ScriptResult(
                status=SCRIPT_STATUS.PASSED,
                script_set=commissioning_script_set,
            )
            factory.make_ScriptResult(
                status=SCRIPT_STATUS.PASSED, script_set=testing_script_set
            )

        handler = ControllerHandler(owner, {}, None)
        queries, _ = count_queries(handler.get, {"system_id": node.system_id})
        # This check is to notify the developer that a change was made that
        # affects the number of queries performed when doing a node get.
        # It is important to keep this number as low as possible. A larger
        # number means regiond has to do more work slowing down its process
        # and slowing down the client waiting for the response.
        self.assertEqual(
            queries,
            36,
            "Number of queries has changed; make sure this is expected.",
        )

    def test_get_form_class_for_create(self):
        user = factory.make_admin()
        handler = ControllerHandler(user, {}, None)
        self.assertEqual(ControllerForm, handler.get_form_class("create"))

    def test_get_form_class_for_update(self):
        user = factory.make_admin()
        handler = ControllerHandler(user, {}, None)
        self.assertEqual(ControllerForm, handler.get_form_class("update"))

    def test_check_images(self):
        owner = factory.make_admin()
        handler = ControllerHandler(owner, {}, None)
        node1 = factory.make_RackController(owner=owner)
        node2 = factory.make_RackController(owner=owner)
        data = handler.check_images(
            [{"system_id": node1.system_id}, {"system_id": node2.system_id}]
        )
        self.assertEqual(
            {node1.system_id: "Unknown", node2.system_id: "Unknown"}, data
        )

    def test_dehydrate_show_os_info_returns_true(self):
        owner = factory.make_admin()
        rack = factory.make_RackController()
        handler = ControllerHandler(owner, {}, None)
        self.assertTrue(handler.dehydrate_show_os_info(rack))

    def test_dehydrate_includes_version(self):
        owner = factory.make_admin()
        handler = ControllerHandler(owner, {}, None)
        rack = factory.make_RackController()
        version = "2.3.0~alpha1-6000-g.abc123"
        ControllerInfo.objects.set_version(rack, version)
        result = handler.list({})
        self.assertEqual(version, result[0].get("version"))
        self.assertEqual("2.3.0~alpha1", result[0].get("version__short"))
        self.assertEqual(
            "2.3.0~alpha1 (6000-g.abc123)",
            result[0].get("version__long"),
        )

    def test_dehydrate_includes_tags(self):
        owner = factory.make_admin()
        handler = ControllerHandler(owner, {}, None)
        region = factory.make_RegionRackController()
        tags = []
        for _ in range(3):
            tag = factory.make_Tag(definition="")
            tag.node_set.add(region)
            tag.save()
            tags.append(tag.name)
        result = handler.list({})
        self.assertEqual(tags, result[0].get("tags"))

    def test_register_info_non_admin(self):
        user = factory.make_User()
        handler = ControllerHandler(user, {}, None)
        self.assertRaises(HandlerPermissionError, handler.register_info, {})

    def test_register_info(self):
        admin = factory.make_admin()
        handler = ControllerHandler(admin, {}, None)
        observed = handler.register_info({})
        rpc_shared_secret = Config.objects.get_config("rpc_shared_secret")
        with RegionConfiguration.open() as config:
            maas_url = config.maas_url
        self.assertEqual(
            {"url": maas_url, "secret": rpc_shared_secret}, observed
        )


class TestControllerHandlerScenarios(MAASServerTestCase):

    scenarios_controllers = (
        ("rack", dict(make_controller=factory.make_RackController)),
        ("region", dict(make_controller=factory.make_RegionController)),
        (
            "region+rack",
            dict(make_controller=factory.make_RegionRackController),
        ),
    )

    scenarios_fetch_types = (
        ("in-full", dict(for_list=False)),
        ("for-list", dict(for_list=True)),
    )

    scenarios = multiply_scenarios(
        scenarios_controllers, scenarios_fetch_types
    )

    def test_fully_dehydrated_controller_contains_essential_fields(self):
        user = factory.make_User()
        controller = self.make_controller()
        handler = ControllerHandler(user, {}, None)
        data = handler.full_dehydrate(controller, for_list=False)
        self.assertThat(
            data,
            ContainsDict(
                {
                    handler._meta.pk: Equals(
                        getattr(controller, handler._meta.pk)
                    ),
                    handler._meta.batch_key: Equals(
                        getattr(controller, handler._meta.batch_key)
                    ),
                }
            ),
        )
