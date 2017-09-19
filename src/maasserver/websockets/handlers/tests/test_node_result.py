# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.node_result`"""

__all__ = []

import random

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import HandlerDoesNotExistError
from maasserver.websockets.handlers.node_result import NodeResultHandler
from metadataserver.enum import (
    HARDWARE_TYPE,
    HARDWARE_TYPE_CHOICES,
    RESULT_TYPE,
    RESULT_TYPE_CHOICES,
    SCRIPT_STATUS,
)


class TestNodeResultHandler(MAASServerTestCase):

    def dehydrate_script_result(self, script_result):
        data = {
            "id": script_result.id,
            "script_set": script_result.script_set.id,
            "script": script_result.script.id,
            "parameters": str(script_result.parameters),
            "script_version": script_result.script_version,
            "status": script_result.status,
            "exit_status": script_result.exit_status,
            "script_name": script_result.script_name,
            "started": script_result.started,
            "ended": script_result.ended,
            "history_list": sorted([
                {
                    "id": history.id,
                    "date": history.updated,
                } for history in script_result.history
            ])}
        if script_result.physical_blockdevice is not None:
            data["physical_blockdevice"] = (
                script_result.physical_blockdevice.id)
        else:
            data["physical_blockdevice"] = None

        return data

    def dehydrate_script_results(self, script_results):
        return [
            self.dehydrate_script_result(script_result)
            for script_result in script_results
            ]

    def test_list_raises_error_if_node_doesnt_exist(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {})
        node = factory.make_Node()
        node.delete()
        self.assertRaises(
            HandlerDoesNotExistError, handler.list,
            {"system_id": node.system_id})

    def test_list_only_returns_script_results_for_node(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {})
        node = factory.make_Node()
        script_results = [
            factory.make_ScriptResult(
                script_set=factory.make_ScriptSet(node=node))
            for _ in range(3)
            ]
        # Other script_results.
        for _ in range(3):
            factory.make_ScriptResult()
        self.assertItemsEqual(
            self.dehydrate_script_results(script_results),
            handler.list({"system_id": node.system_id}))

    def test_list_result_type(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {})
        node = factory.make_Node()
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PASSED,
            script_set=factory.make_ScriptSet(
                node=node, result_type=RESULT_TYPE.TESTING))
        # Create extra script results with different result types.
        for _ in range(3):
            factory.make_ScriptResult(
                script_set=factory.make_ScriptSet(
                    node=node, result_type=random.choice([
                        result_type_id
                        for result_type_id, _ in RESULT_TYPE_CHOICES
                        if result_type_id != RESULT_TYPE.TESTING
                    ])))
        expected_output = [self.dehydrate_script_result(script_result)]
        self.assertItemsEqual(expected_output, handler.list(
            {
                "system_id": node.system_id,
                "result_type": RESULT_TYPE.TESTING
            }))

    def test_list_hardware_type(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {})
        node = factory.make_Node()
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PASSED,
            script=factory.make_Script(
                hardware_type=HARDWARE_TYPE.STORAGE),
            script_set=factory.make_ScriptSet(node=node))
        # Create extra script results with different hardware types.
        for _ in range(3):
            factory.make_ScriptResult(
                script=factory.make_Script(
                    hardware_type=random.choice([
                        hardware_type_id
                        for hardware_type_id, _ in HARDWARE_TYPE_CHOICES
                        if hardware_type_id != HARDWARE_TYPE.STORAGE])),
                script_set=factory.make_ScriptSet(node=node))
        expected_output = [self.dehydrate_script_result(script_result)]
        self.assertItemsEqual(expected_output, handler.list(
            {
                "system_id": node.system_id,
                "hardware_type": HARDWARE_TYPE.STORAGE
            }))

    def test_list_physical_blockdevice_id(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {})
        node = factory.make_Node()
        physical_blockdevice = factory.make_PhysicalBlockDevice(node=node)
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PASSED,
            physical_blockdevice=physical_blockdevice,
            script_set=factory.make_ScriptSet(node=node))
        # Create extra script results with different physical block devices.
        for _ in range(3):
            factory.make_ScriptResult(
                physical_blockdevice=factory.make_PhysicalBlockDevice(
                    node=node),
                script_set=factory.make_ScriptSet(node=node))
        expected_output = [self.dehydrate_script_result(script_result)]
        self.assertItemsEqual(expected_output, handler.list(
            {
                "system_id": node.system_id,
                "physical_blockdevice_id": physical_blockdevice.id,
            }))

    def test_list_has_surfaced(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {})
        node = factory.make_Node()
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PASSED,
            script_set=factory.make_ScriptSet(node=node))
        # Create extra script results with different nodes.
        for _ in range(3):
            factory.make_ScriptResult(
                result=b'', script_set=factory.make_ScriptSet(node=node))
        expected_output = [self.dehydrate_script_result(script_result)]
        self.assertItemsEqual(expected_output, handler.list(
            {
                "system_id": node.system_id,
                "has_surfaced": True,
            }))

    def test_get_result_data_gets_output(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {})
        node = factory.make_Node()
        output = factory.make_string().encode('utf-8')
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PASSED, output=output,
            script_set=factory.make_ScriptSet(node=node))
        self.assertItemsEqual(script_result.output, handler.get_result_data(
            script_result.script.id, 'output'))

    def test_get_result_data_gets_stdout(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {})
        node = factory.make_Node()
        stdout = factory.make_string().encode('utf-8')
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PASSED, stdout=stdout,
            script_set=factory.make_ScriptSet(node=node))
        self.assertItemsEqual(script_result.stdout, handler.get_result_data(
            script_result.script.id, 'stdout'))

    def test_get_result_data_gets_stderr(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {})
        node = factory.make_Node()
        stderr = factory.make_string().encode('utf-8')
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PASSED, stderr=stderr,
            script_set=factory.make_ScriptSet(node=node))
        self.assertItemsEqual(script_result.stderr, handler.get_result_data(
            script_result.script.id, 'stderr'))

    def test_get_result_data_gets_result(self):
        user = factory.make_User()
        handler = NodeResultHandler(user, {})
        node = factory.make_Node()
        result = factory.make_string().encode('utf-8')
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.PASSED, result=result,
            script_set=factory.make_ScriptSet(node=node))
        self.assertItemsEqual(script_result.result, handler.get_result_data(
            script_result.script.id, 'result'))
