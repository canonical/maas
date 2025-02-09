# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.node_result`"""

import random
from unittest.mock import sentinel

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.websockets.base import (
    dehydrate_datetime,
    HandlerDoesNotExistError,
    HandlerPKError,
)
from maasserver.websockets.handlers.node_result import NodeResultHandler
from maastesting.djangotestcase import CountQueries
from metadataserver.enum import (
    HARDWARE_TYPE,
    HARDWARE_TYPE_CHOICES,
    RESULT_TYPE,
    RESULT_TYPE_CHOICES,
    SCRIPT_STATUS,
)


class TestNodeResultHandler(MAASServerTestCase):
    def dehydrate_script_result(self, script_result, handler):
        results = script_result.read_results().get("results", {})
        data = {
            "id": script_result.id,
            "updated": dehydrate_datetime(script_result.updated),
            "script": script_result.script_id,
            "parameters": script_result.parameters,
            "physical_blockdevice": script_result.physical_blockdevice_id,
            "interface": script_result.interface_id,
            "script_version": script_result.script_version_id,
            "status": script_result.status,
            "status_name": script_result.status_name,
            "exit_status": script_result.exit_status,
            "started": dehydrate_datetime(script_result.started),
            "ended": dehydrate_datetime(script_result.ended),
            "runtime": script_result.runtime,
            "starttime": script_result.starttime,
            "endtime": script_result.endtime,
            "estimated_runtime": script_result.estimated_runtime,
            "name": script_result.name,
            "result_type": script_result.script_set.result_type,
            "hardware_type": script_result.script.hardware_type,
            "tags": ", ".join(script_result.script.tags),
            "results": [
                {
                    "name": key,
                    "title": key,
                    "description": "",
                    "value": value,
                    "surfaced": False,
                }
                for key, value in results.items()
            ],
            "suppressed": script_result.suppressed,
        }

        return data

    def dehydrate_script_results(self, script_results, handler):
        return [
            self.dehydrate_script_result(script_result, handler)
            for script_result in script_results
        ]

    def test_get_node(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        node = factory.make_Node()
        self.assertEqual(node, handler.get_node({"system_id": node.system_id}))
        self.assertDictEqual(
            {node.system_id: node}, handler.cache["system_ids"]
        )

    def test_get_node_from_cache(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        fake_system_id = factory.make_name("system_id")
        fake_node = factory.make_name("node")
        handler.cache["system_ids"][fake_system_id] = fake_node
        self.assertEqual(
            fake_node, handler.get_node({"system_id": fake_system_id})
        )

    def test_get_node_errors_no_system_id(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        self.assertRaises(HandlerPKError, handler.get_node, {})

    def test_get_node_errors_invalid_system_id(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        self.assertRaises(
            HandlerDoesNotExistError,
            handler.get_node,
            {"system_id": factory.make_name("system_id")},
        )

    def test_list_raises_error_if_node_doesnt_exist(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        node = factory.make_Node()
        node.delete()
        self.assertRaises(
            HandlerDoesNotExistError,
            handler.list,
            {"system_id": node.system_id},
        )

    def test_list_only_returns_script_results_for_node(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        node = factory.make_Node()
        script_results = [
            factory.make_ScriptResult(
                script_set=factory.make_ScriptSet(node=node)
            )
            for _ in range(3)
        ]
        # Other script_results.
        for _ in range(3):
            factory.make_ScriptResult()
        self.assertCountEqual(
            self.dehydrate_script_results(script_results, handler),
            handler.list({"system_id": node.system_id}),
        )

    def test_list_result_type(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        node = factory.make_Node()
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PASSED,
            script_set=factory.make_ScriptSet(
                node=node, result_type=RESULT_TYPE.TESTING
            ),
        )
        # Create extra script results with different result types.
        for _ in range(3):
            factory.make_ScriptResult(
                script_set=factory.make_ScriptSet(
                    node=node,
                    result_type=random.choice(
                        [
                            result_type_id
                            for result_type_id, _ in RESULT_TYPE_CHOICES
                            if result_type_id != RESULT_TYPE.TESTING
                        ]
                    ),
                )
            )
        expected_output = [
            self.dehydrate_script_result(script_result, handler)
        ]
        self.assertEqual(
            expected_output,
            handler.list(
                {
                    "system_id": node.system_id,
                    "result_type": RESULT_TYPE.TESTING,
                }
            ),
        )

    def test_list_hardware_type(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        node = factory.make_Node()
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PASSED,
            script=factory.make_Script(hardware_type=HARDWARE_TYPE.STORAGE),
            script_set=factory.make_ScriptSet(node=node),
        )
        # Create extra script results with different hardware types.
        for _ in range(3):
            factory.make_ScriptResult(
                script=factory.make_Script(
                    hardware_type=random.choice(
                        [
                            hardware_type_id
                            for hardware_type_id, _ in HARDWARE_TYPE_CHOICES
                            if hardware_type_id != HARDWARE_TYPE.STORAGE
                        ]
                    )
                ),
                script_set=factory.make_ScriptSet(node=node),
            )
        expected_output = [
            self.dehydrate_script_result(script_result, handler)
        ]
        self.assertEqual(
            expected_output,
            handler.list(
                {
                    "system_id": node.system_id,
                    "hardware_type": HARDWARE_TYPE.STORAGE,
                }
            ),
        )

    def test_list_physical_blockdevice_id(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        node = factory.make_Node()
        physical_blockdevice = factory.make_PhysicalBlockDevice(node=node)
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PASSED,
            physical_blockdevice=physical_blockdevice,
            script_set=factory.make_ScriptSet(node=node),
        )
        # Create extra script results with different physical block devices.
        for _ in range(3):
            factory.make_ScriptResult(
                physical_blockdevice=factory.make_PhysicalBlockDevice(
                    node=node
                ),
                script_set=factory.make_ScriptSet(node=node),
            )
        expected_output = [
            self.dehydrate_script_result(script_result, handler)
        ]
        self.assertEqual(
            expected_output,
            handler.list(
                {
                    "system_id": node.system_id,
                    "physical_blockdevice_id": physical_blockdevice.id,
                }
            ),
        )

    def test_list_interface_id(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        node = factory.make_Node()
        interface = factory.make_Interface(node=node)
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PASSED,
            interface=interface,
            script_set=factory.make_ScriptSet(node=node),
        )
        # Create extra script results with different interfaces.
        for _ in range(3):
            factory.make_ScriptResult(
                interface=factory.make_Interface(node=node),
                script_set=factory.make_ScriptSet(node=node),
            )
        expected_output = [
            self.dehydrate_script_result(script_result, handler)
        ]
        self.assertEqual(
            expected_output,
            handler.list(
                {"system_id": node.system_id, "interface_id": interface.id}
            ),
        )

    def test_list_has_surfaced(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        node = factory.make_Node()
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PASSED,
            script_set=factory.make_ScriptSet(node=node),
        )
        # Create extra script results with different nodes.
        for _ in range(3):
            factory.make_ScriptResult(
                result=b"", script_set=factory.make_ScriptSet(node=node)
            )
        expected_output = [
            self.dehydrate_script_result(script_result, handler)
        ]
        self.assertEqual(
            expected_output,
            handler.list({"system_id": node.system_id, "has_surfaced": True}),
        )

    def test_list_start(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        node = factory.make_Node()
        script_set = factory.make_ScriptSet(node=node)
        for _ in range(6):
            factory.make_ScriptResult(script_set=script_set)
        start = random.randint(0, 5)
        self.assertEqual(
            6 - start,
            len(handler.list({"system_id": node.system_id, "start": start})),
        )

    def test_list_limit(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        node = factory.make_Node()
        script_set = factory.make_ScriptSet(node=node)
        for _ in range(6):
            factory.make_ScriptResult(script_set=script_set)
        limit = random.randint(0, 6)
        self.assertEqual(
            limit,
            len(handler.list({"system_id": node.system_id, "limit": limit})),
        )

    def test_list_adds_to_loaded_pks(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        node = factory.make_Node()
        script_set = factory.make_ScriptSet(node=node)
        pks = [
            factory.make_ScriptResult(script_set=script_set).id
            for _ in range(3)
        ]
        handler.list({"system_id": node.system_id})
        self.assertCountEqual(pks, handler.cache["loaded_pks"])

    def test_list_redacts_password_parameter(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        node = factory.make_Node()
        script_set = factory.make_ScriptSet(node=node)
        string_script = factory.make_Script(
            parameters={"string": {"type": "string"}}
        )
        password_script = factory.make_Script(
            parameters={"password": {"type": "password"}}
        )
        string = factory.make_name("string")
        password = factory.make_name("password")
        string_script_result = factory.make_ScriptResult(
            script_set=script_set,
            script=string_script,
            parameters={"string": {"type": "string", "value": string}},
        )
        password_script_result = factory.make_ScriptResult(
            script_set=script_set,
            script=password_script,
            parameters={"password": {"type": "password", "value": password}},
        )

        for result in handler.list({"system_id": node.system_id}):
            if result["id"] == string_script_result.id:
                self.assertEqual(
                    {"string": {"type": "string", "value": string}},
                    result["parameters"],
                )
                self.assertEqual(
                    string,
                    reload_object(string_script_result).parameters["string"][
                        "value"
                    ],
                )
            else:
                self.assertEqual(
                    {"password": {"type": "password", "value": "REDACTED"}},
                    result["parameters"],
                )
                self.assertEqual(
                    password,
                    reload_object(password_script_result).parameters[
                        "password"
                    ]["value"],
                )

    def test_get_result_data_gets_output(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        node = factory.make_Node()
        combined = factory.make_string().encode("utf-8")
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PASSED,
            output=combined,
            script_set=factory.make_ScriptSet(node=node),
        )
        self.assertEqual(
            combined.decode(),
            handler.get_result_data(
                {"id": script_result.id, "data_type": "combined"}
            ),
        )

    def test_get_result_data_gets_stdout(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        node = factory.make_Node()
        stdout = factory.make_string().encode("utf-8")
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PASSED,
            stdout=stdout,
            script_set=factory.make_ScriptSet(node=node),
        )
        self.assertEqual(
            stdout.decode(),
            handler.get_result_data(
                {"id": script_result.id, "data_type": "stdout"}
            ),
        )

    def test_get_result_data_gets_stderr(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        node = factory.make_Node()
        stderr = factory.make_string().encode("utf-8")
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PASSED,
            stderr=stderr,
            script_set=factory.make_ScriptSet(node=node),
        )
        self.assertEqual(
            stderr.decode(),
            handler.get_result_data(
                {"id": script_result.id, "data_type": "stderr"}
            ),
        )

    def test_get_result_data_gets_result(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        node = factory.make_Node()
        result = factory.make_string().encode("utf-8")
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PASSED,
            result=result,
            script_set=factory.make_ScriptSet(node=node),
        )
        self.assertEqual(
            result.decode(),
            handler.get_result_data(
                {"id": script_result.id, "data_type": "result"}
            ),
        )

    def test_get_result_data_unknown_id(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        id = random.randint(0, 100)
        self.assertEqual(
            "Unknown ScriptResult id %s" % id,
            handler.get_result_data({"id": id}),
        )

    def test_get_result_data_gets_unknown_data_type(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        node = factory.make_Node()
        combined = factory.make_string().encode("utf-8")
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PASSED,
            output=combined,
            script_set=factory.make_ScriptSet(node=node),
        )
        unknown_data_type = factory.make_name("data_type")
        self.assertEqual(
            "Unknown data_type %s" % unknown_data_type,
            handler.get_result_data(
                {"id": script_result.id, "data_type": unknown_data_type}
            ),
        )

    def test_get_history(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        node = factory.make_Node(owner=user)
        script = factory.make_Script()
        script_results = []
        for _ in range(10):
            script_set = factory.make_ScriptSet(node=node)
            script_results.append(
                factory.make_ScriptResult(
                    script=script,
                    script_set=script_set,
                    status=SCRIPT_STATUS.PASSED,
                )
            )
        latest_script_result = script_results[-1]
        script_results = sorted(
            script_results, key=lambda i: i.id, reverse=True
        )
        queries = CountQueries()
        with queries:
            ret = handler.get_history({"id": latest_script_result.id})
        self.assertEqual(4, queries.count)
        for script_result, out in zip(script_results, ret):
            self.assertDictEqual(
                {
                    "id": script_result.id,
                    "updated": dehydrate_datetime(script_result.updated),
                    "status": script_result.status,
                    "status_name": script_result.status_name,
                    "runtime": script_result.runtime,
                    "starttime": script_result.starttime,
                    "endtime": script_result.endtime,
                    "estimated_runtime": script_result.estimated_runtime,
                    "suppressed": script_result.suppressed,
                },
                out,
            )

    def test_clear_removes_system_id_from_cache(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        node = factory.make_Node()
        handler.list({"system_id": node.system_id})
        handler.clear({"system_id": node.system_id})
        self.assertDictEqual({}, handler.cache["system_ids"])

    def test_on_listen_returns_None_if_obj_no_longer_exists(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        mock_listen = self.patch(handler, "listen")
        mock_listen.side_effect = HandlerDoesNotExistError()
        self.assertIsNone(
            handler.on_listen(
                sentinel.channel, sentinel.action, random.randint(1, 1000)
            )
        )

    def test_on_listen_returns_None_if_listen_returns_None(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        mock_listen = self.patch(handler, "listen")
        mock_listen.return_value = None
        self.assertIsNone(
            handler.on_listen(
                sentinel.channel, sentinel.action, random.randint(1, 1000)
            )
        )

    def test_on_listen_returns_None_if_system_id_not_in_cache(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        script_result = factory.make_ScriptResult()
        self.assertIsNone(
            handler.on_listen(
                sentinel.channel, sentinel.action, script_result.id
            )
        )

    def test_on_listen_returns_handler_name_action_and_event(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {}, None)
        script_result = factory.make_ScriptResult()
        node = script_result.script_set.node
        handler.cache["system_ids"][node.system_id] = node
        self.assertEqual(
            (
                handler._meta.handler_name,
                sentinel.action,
                self.dehydrate_script_result(script_result, handler),
            ),
            handler.on_listen(
                sentinel.channel, sentinel.action, script_result.id
            ),
        )
