# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the script result API."""


from base64 import b64encode
import http.client
from io import BytesIO
import os
import random
import re
import tarfile
import time

from django.urls import reverse

from maasserver.api.scriptresults import fmt_time
from maasserver.preseed import CURTIN_ERROR_TARFILE
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object
from metadataserver.enum import (
    HARDWARE_TYPE,
    HARDWARE_TYPE_CHOICES,
    RESULT_TYPE_CHOICES,
)


class TestNodeScriptResultsAPI(APITestCase.ForUser):
    """Tests for /api/2.0/nodes/<system_id>/results/."""

    @staticmethod
    def get_script_results_uri(node):
        """Return the script's URI on the API."""
        return reverse("script_results_handler", args=[node.system_id])

    def test_hander_path(self):
        node = factory.make_Node()
        self.assertEqual(
            "/MAAS/api/2.0/nodes/%s/results/" % node.system_id,
            self.get_script_results_uri(node),
        )

    def test_GET(self):
        node = factory.make_Node()
        script_set_ids = []
        for _ in range(3):
            script_set = factory.make_ScriptSet(node=node)
            script_set_ids.append(script_set.id)
            for _ in range(3):
                factory.make_ScriptResult(script_set=script_set)

        # Script sets for different nodes.
        for _ in range(3):
            factory.make_ScriptSet()

        response = self.client.get(self.get_script_results_uri(node))
        self.assertEqual(response.status_code, http.client.OK)
        parsed_results = json_load_bytes(response.content)

        self.assertCountEqual(
            script_set_ids, [result["id"] for result in parsed_results]
        )
        for script_set in parsed_results:
            for result in script_set["results"]:
                for key in ["output", "stdout", "stderr", "result"]:
                    self.assertNotIn(key, result)

    def test_GET_filters_by_type(self):
        node = factory.make_Node()
        result_type = factory.pick_choice(RESULT_TYPE_CHOICES)
        script_sets = [
            factory.make_ScriptSet(result_type=result_type, node=node)
            for _ in range(3)
        ]

        for _ in range(10):
            factory.make_ScriptSet(
                node=node,
                result_type=factory.pick_choice(
                    RESULT_TYPE_CHOICES, but_not=[result_type]
                ),
            )

        response = self.client.get(
            self.get_script_results_uri(node), {"type": result_type}
        )
        self.assertEqual(response.status_code, http.client.OK)
        parsed_results = json_load_bytes(response.content)

        self.assertCountEqual(
            [script_set.id for script_set in script_sets],
            [parsed_result["id"] for parsed_result in parsed_results],
        )

    def test_GET_filters_by_hardware_type(self):
        hardware_type = factory.pick_choice(HARDWARE_TYPE_CHOICES)
        script_set = factory.make_ScriptSet()
        scripts = [
            factory.make_Script(hardware_type=hardware_type) for _ in range(3)
        ]
        for script in scripts:
            factory.make_ScriptResult(script_set=script_set, script=script)

        for _ in range(10):
            script = factory.make_Script(
                hardware_type=factory.pick_choice(
                    HARDWARE_TYPE_CHOICES, but_not=[hardware_type]
                )
            )
            factory.make_ScriptResult(script_set=script_set, script=script)

        response = self.client.get(
            self.get_script_results_uri(script_set.node),
            {"hardware_type": hardware_type},
        )
        self.assertEqual(response.status_code, http.client.OK)
        parsed_results = json_load_bytes(response.content)

        self.assertCountEqual(
            [script.id for script in scripts],
            [
                parsed_result["script_id"]
                for parsed_result in parsed_results[0]["results"]
            ],
        )

    def test_GET_include_output(self):
        node = factory.make_Node()
        script_set_ids = []
        for _ in range(3):
            script_set = factory.make_ScriptSet(node=node)
            script_set_ids.append(script_set.id)
            for _ in range(3):
                factory.make_ScriptResult(script_set=script_set)

        # Script sets for different nodes.
        for _ in range(3):
            factory.make_ScriptSet()

        response = self.client.get(
            self.get_script_results_uri(node), {"include_output": True}
        )
        self.assertEqual(response.status_code, http.client.OK)
        parsed_results = json_load_bytes(response.content)

        self.assertCountEqual(
            script_set_ids, [result["id"] for result in parsed_results]
        )
        for script_set in parsed_results:
            for result in script_set["results"]:
                for key in ["output", "stdout", "stderr", "result"]:
                    self.assertIn(key, result)

    def test_GET_filters(self):
        node = factory.make_Node()
        scripts = [factory.make_Script() for _ in range(3)]
        name_filter_script = random.choice(scripts)
        tag_filter_script = random.choice(scripts)
        script_set_ids = []
        for _ in range(3):
            script_set = factory.make_ScriptSet(node=node)
            script_set_ids.append(script_set.id)
            for script in scripts:
                factory.make_ScriptResult(script_set=script_set, script=script)

        # Script sets for different nodes.
        for _ in range(3):
            factory.make_ScriptSet()

        response = self.client.get(
            self.get_script_results_uri(node),
            {
                "filters": ",".join(
                    [
                        name_filter_script.name,
                        random.choice(
                            [
                                tag
                                for tag in tag_filter_script.tags
                                if "tag" in tag
                            ]
                        ),
                    ]
                )
            },
        )
        self.assertEqual(response.status_code, http.client.OK)
        parsed_results = json_load_bytes(response.content)

        self.assertCountEqual(
            script_set_ids, [result["id"] for result in parsed_results]
        )
        for script_set in parsed_results:
            for result in script_set["results"]:
                self.assertIn(
                    result["name"],
                    {name_filter_script.name, tag_filter_script.name},
                )
                for key in ["output", "stdout", "stderr", "result"]:
                    self.assertNotIn(key, result)


class TestNodeScriptResultAPI(APITestCase.ForUser):
    """Tests for /api/2.0/nodes/<system_id>/results/<id>."""

    scenarios = (
        ("id", {"id_value": None, "key": None}),
        (
            "commissioning",
            {
                "id_value": "current-commissioning",
                "key": "current_commissioning_script_set",
            },
        ),
        (
            "testing",
            {
                "id_value": "current-testing",
                "key": "current_testing_script_set",
            },
        ),
        (
            "installation",
            {
                "id_value": "current-installation",
                "key": "current_installation_script_set",
            },
        ),
    )

    def get_script_result_uri(self, script_set):
        """Return the script's URI on the API."""
        return reverse(
            "script_result_handler",
            args=[script_set.node.system_id, self.get_id(script_set)],
        )

    def make_scriptset(self, *args, **kwargs):
        script_set = factory.make_ScriptSet(*args, **kwargs)
        if self.key is not None:
            setattr(script_set.node, self.key, script_set)
            script_set.node.save()
        return script_set

    def get_id(self, script_set):
        if self.id_value is None:
            return script_set.id
        else:
            return self.id_value

    def test_hander_path(self):
        script_set = self.make_scriptset()
        self.assertEqual(
            "/MAAS/api/2.0/nodes/%s/results/%s/"
            % (script_set.node.system_id, self.get_id(script_set)),
            self.get_script_result_uri(script_set),
        )

    def test_GET(self):
        script_set = self.make_scriptset()
        script_results = {}
        for _ in range(3):
            script_result = factory.make_ScriptResult(script_set=script_set)
            script_results[script_result.name] = script_result

        response = self.client.get(self.get_script_result_uri(script_set))
        self.assertEqual(response.status_code, http.client.OK)
        parsed_result = json_load_bytes(response.content)
        results = parsed_result.pop("results")

        self.assertDictEqual(
            {
                "id": script_set.id,
                "system_id": script_set.node.system_id,
                "type": script_set.result_type,
                "type_name": script_set.result_type_name,
                "last_ping": fmt_time(script_set.last_ping),
                "status": script_set.status,
                "status_name": script_set.status_name,
                "started": fmt_time(script_set.started),
                "ended": fmt_time(script_set.ended),
                "runtime": script_set.runtime,
                "resource_uri": "/MAAS/api/2.0/nodes/%s/results/%d/"
                % (script_set.node.system_id, script_set.id),
            },
            parsed_result,
        )
        for result in results:
            script_result = script_results[result["name"]]
            self.assertDictEqual(
                {
                    "id": script_result.id,
                    "name": script_result.name,
                    "created": fmt_time(script_result.created),
                    "updated": fmt_time(script_result.updated),
                    "status": script_result.status,
                    "status_name": script_result.status_name,
                    "exit_status": script_result.exit_status,
                    "started": fmt_time(script_result.started),
                    "ended": fmt_time(script_result.ended),
                    "runtime": script_result.runtime,
                    "starttime": script_result.starttime,
                    "endtime": script_result.endtime,
                    "estimated_runtime": script_result.estimated_runtime,
                    "parameters": script_result.parameters,
                    "script_id": script_result.script_id,
                    "script_revision_id": script_result.script_version_id,
                    "suppressed": script_result.suppressed,
                },
                result,
            )

    def test_GET_redacts_password_parameter(self):
        string_script = factory.make_Script(
            parameters={"string": {"type": "string"}}
        )
        password_script = factory.make_Script(
            parameters={"password": {"type": "password"}}
        )
        string = factory.make_name("string")
        password = factory.make_name("password")
        script_set = self.make_scriptset()
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

        response = self.client.get(self.get_script_result_uri(script_set))
        self.assertEqual(response.status_code, http.client.OK)
        parsed_result = json_load_bytes(response.content)

        for result in parsed_result["results"]:
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

    def test_GET_include_output(self):
        script_set = self.make_scriptset()
        script_results = {}
        for _ in range(3):
            script_result = factory.make_ScriptResult(script_set=script_set)
            script_results[script_result.name] = script_result

        response = self.client.get(
            self.get_script_result_uri(script_set), {"include_output": True}
        )
        self.assertEqual(response.status_code, http.client.OK)
        parsed_result = json_load_bytes(response.content)
        results = parsed_result.pop("results")

        self.assertDictEqual(
            {
                "id": script_set.id,
                "system_id": script_set.node.system_id,
                "type": script_set.result_type,
                "type_name": script_set.result_type_name,
                "last_ping": fmt_time(script_set.last_ping),
                "status": script_set.status,
                "status_name": script_set.status_name,
                "started": fmt_time(script_set.started),
                "ended": fmt_time(script_set.ended),
                "runtime": script_set.runtime,
                "resource_uri": "/MAAS/api/2.0/nodes/%s/results/%d/"
                % (script_set.node.system_id, script_set.id),
            },
            parsed_result,
        )
        for result in results:
            script_result = script_results[result["name"]]
            self.assertDictEqual(
                {
                    "id": script_result.id,
                    "name": script_result.name,
                    "created": fmt_time(script_result.created),
                    "updated": fmt_time(script_result.updated),
                    "status": script_result.status,
                    "status_name": script_result.status_name,
                    "exit_status": script_result.exit_status,
                    "started": fmt_time(script_result.started),
                    "ended": fmt_time(script_result.ended),
                    "runtime": script_result.runtime,
                    "starttime": script_result.starttime,
                    "endtime": script_result.endtime,
                    "estimated_runtime": script_result.estimated_runtime,
                    "parameters": script_result.parameters,
                    "script_id": script_result.script_id,
                    "script_revision_id": script_result.script_version_id,
                    "suppressed": script_result.suppressed,
                    "output": b64encode(script_result.output).decode(),
                    "stdout": b64encode(script_result.stdout).decode(),
                    "stderr": b64encode(script_result.stderr).decode(),
                    "result": b64encode(script_result.result).decode(),
                },
                result,
            )

    def test_GET_filters(self):
        scripts = [factory.make_Script() for _ in range(10)]
        script_set = self.make_scriptset()
        script_results = {}
        for script in scripts:
            script_result = factory.make_ScriptResult(
                script_set=script_set, script=script
            )
            script_results[script_result.name] = script_result
        results_list = list(script_results.values())
        filtered_results = [random.choice(results_list) for _ in range(3)]

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {
                "filters": "%s,%s,%d"
                % (
                    filtered_results[0].name,
                    random.choice(
                        [
                            tag
                            for tag in filtered_results[1].script.tags
                            if "tag" in tag
                        ]
                    ),
                    filtered_results[2].id,
                )
            },
        )
        self.assertEqual(response.status_code, http.client.OK)
        parsed_result = json_load_bytes(response.content)
        results = parsed_result.pop("results")

        self.assertDictEqual(
            {
                "id": script_set.id,
                "system_id": script_set.node.system_id,
                "type": script_set.result_type,
                "type_name": script_set.result_type_name,
                "last_ping": fmt_time(script_set.last_ping),
                "status": script_set.status,
                "status_name": script_set.status_name,
                "started": fmt_time(script_set.started),
                "ended": fmt_time(script_set.ended),
                "runtime": script_set.runtime,
                "resource_uri": "/MAAS/api/2.0/nodes/%s/results/%d/"
                % (script_set.node.system_id, script_set.id),
            },
            parsed_result,
        )
        for result in results:
            self.assertIn(
                result["name"],
                [script_result.name for script_result in filtered_results],
            )
            script_result = script_results[result["name"]]
            self.assertDictEqual(
                {
                    "id": script_result.id,
                    "name": script_result.name,
                    "created": fmt_time(script_result.created),
                    "updated": fmt_time(script_result.updated),
                    "status": script_result.status,
                    "status_name": script_result.status_name,
                    "exit_status": script_result.exit_status,
                    "started": fmt_time(script_result.started),
                    "ended": fmt_time(script_result.ended),
                    "runtime": script_result.runtime,
                    "starttime": script_result.starttime,
                    "endtime": script_result.endtime,
                    "estimated_runtime": script_result.estimated_runtime,
                    "parameters": script_result.parameters,
                    "script_id": script_result.script_id,
                    "script_revision_id": script_result.script_version_id,
                    "suppressed": script_result.suppressed,
                },
                result,
            )

    def test_GET_filters_by_hardware_type(self):
        script_set = self.make_scriptset()
        hardware_type = factory.pick_choice(HARDWARE_TYPE_CHOICES)
        scripts = [
            factory.make_Script(hardware_type=hardware_type) for _ in range(3)
        ]
        for script in scripts:
            factory.make_ScriptResult(script_set=script_set, script=script)
        for _ in range(3):
            script = factory.make_Script(
                hardware_type=factory.pick_choice(
                    HARDWARE_TYPE_CHOICES, but_not=[hardware_type]
                )
            )
            factory.make_ScriptResult(script_set=script_set, script=script)

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {"hardware_type": hardware_type},
        )
        self.assertEqual(response.status_code, http.client.OK)
        parsed_result = json_load_bytes(response.content)
        results = parsed_result.pop("results")
        self.assertCountEqual(
            [script.id for script in scripts],
            [result["script_id"] for result in results],
        )

    def test_DELETE(self):
        # Users are unable to delete the current-commissioning or
        # current-installation script sets.
        if self.id_value in ("current-commissioning", "current-installation"):
            return
        self.become_admin()
        script_set = self.make_scriptset()
        response = self.client.delete(self.get_script_result_uri(script_set))
        self.assertEqual(response.status_code, http.client.NO_CONTENT)
        self.assertIsNone(reload_object(script_set))

    def test_DELETE_admin_only(self):
        script_set = self.make_scriptset()
        response = self.client.delete(self.get_script_result_uri(script_set))
        self.assertEqual(response.status_code, http.client.FORBIDDEN)
        self.assertIsNotNone(reload_object(script_set))

    def test_PUT_admin_only(self):
        script_set = self.make_scriptset()
        response = self.client.put(self.get_script_result_uri(script_set))
        self.assertEqual(response.status_code, http.client.FORBIDDEN)
        self.assertIsNotNone(reload_object(script_set))

    def test_PUT_include_output(self):
        self.become_admin()
        script_set = self.make_scriptset()
        script_results = {}
        for _ in range(3):
            script_result = factory.make_ScriptResult(script_set=script_set)
            script_results[script_result.name] = script_result

        response = self.client.put(
            self.get_script_result_uri(script_set), {"include_output": True}
        )
        self.assertEqual(response.status_code, http.client.OK)
        parsed_result = json_load_bytes(response.content)
        results = parsed_result.pop("results")

        self.assertDictEqual(
            {
                "id": script_set.id,
                "system_id": script_set.node.system_id,
                "type": script_set.result_type,
                "type_name": script_set.result_type_name,
                "last_ping": fmt_time(script_set.last_ping),
                "status": script_set.status,
                "status_name": script_set.status_name,
                "started": fmt_time(script_set.started),
                "ended": fmt_time(script_set.ended),
                "runtime": script_set.runtime,
                "resource_uri": "/MAAS/api/2.0/nodes/%s/results/%d/"
                % (script_set.node.system_id, script_set.id),
            },
            parsed_result,
        )
        for result in results:
            script_result = script_results[result["name"]]
            self.assertDictEqual(
                {
                    "id": script_result.id,
                    "name": script_result.name,
                    "created": fmt_time(script_result.created),
                    "updated": fmt_time(script_result.updated),
                    "status": script_result.status,
                    "status_name": script_result.status_name,
                    "exit_status": script_result.exit_status,
                    "started": fmt_time(script_result.started),
                    "ended": fmt_time(script_result.ended),
                    "runtime": script_result.runtime,
                    "starttime": script_result.starttime,
                    "endtime": script_result.endtime,
                    "estimated_runtime": script_result.estimated_runtime,
                    "parameters": script_result.parameters,
                    "script_id": script_result.script_id,
                    "script_revision_id": script_result.script_version_id,
                    "suppressed": script_result.suppressed,
                    "output": b64encode(script_result.output).decode(),
                    "stdout": b64encode(script_result.stdout).decode(),
                    "stderr": b64encode(script_result.stderr).decode(),
                    "result": b64encode(script_result.result).decode(),
                },
                result,
            )

    def test_PUT_filters(self):
        self.become_admin()
        scripts = [factory.make_Script() for _ in range(10)]
        script_set = self.make_scriptset()
        script_results = {}
        for script in scripts:
            script_result = factory.make_ScriptResult(
                script_set=script_set, script=script
            )
            script_results[script_result.name] = script_result
        results_list = list(script_results.values())
        filtered_results = [random.choice(results_list) for _ in range(3)]

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {
                "filters": "%s,%s,%d"
                % (
                    filtered_results[0].name,
                    random.choice(
                        [
                            tag
                            for tag in filtered_results[1].script.tags
                            if "tag" in tag
                        ]
                    ),
                    filtered_results[2].id,
                )
            },
        )
        self.assertEqual(response.status_code, http.client.OK)
        parsed_result = json_load_bytes(response.content)
        results = parsed_result.pop("results")

        self.assertDictEqual(
            {
                "id": script_set.id,
                "system_id": script_set.node.system_id,
                "type": script_set.result_type,
                "type_name": script_set.result_type_name,
                "last_ping": fmt_time(script_set.last_ping),
                "status": script_set.status,
                "status_name": script_set.status_name,
                "started": fmt_time(script_set.started),
                "ended": fmt_time(script_set.ended),
                "runtime": script_set.runtime,
                "resource_uri": "/MAAS/api/2.0/nodes/%s/results/%d/"
                % (script_set.node.system_id, script_set.id),
            },
            parsed_result,
        )
        for result in results:
            self.assertIn(
                result["name"],
                [script_result.name for script_result in filtered_results],
            )
            script_result = script_results[result["name"]]
            self.assertDictEqual(
                {
                    "id": script_result.id,
                    "name": script_result.name,
                    "created": fmt_time(script_result.created),
                    "updated": fmt_time(script_result.updated),
                    "status": script_result.status,
                    "status_name": script_result.status_name,
                    "exit_status": script_result.exit_status,
                    "started": fmt_time(script_result.started),
                    "ended": fmt_time(script_result.ended),
                    "runtime": script_result.runtime,
                    "starttime": script_result.starttime,
                    "endtime": script_result.endtime,
                    "estimated_runtime": script_result.estimated_runtime,
                    "parameters": script_result.parameters,
                    "script_id": script_result.script_id,
                    "script_revision_id": script_result.script_version_id,
                    "suppressed": script_result.suppressed,
                },
                result,
            )

    def test_PUT_updates_suppressed(self):
        # This test does two passes.
        # On the first pass, we set the default false suppressed field
        # of all the script results to True, while on the second pass
        # we set them all back to False.
        self.become_admin()
        node = factory.make_Node()
        hardware_type = factory.pick_choice(HARDWARE_TYPE_CHOICES)
        script_set = self.make_scriptset(node=node)
        scripts = [
            factory.make_Script(hardware_type=hardware_type) for _ in range(3)
        ]
        for script in scripts:
            factory.make_ScriptResult(script_set=script_set, script=script)
        response = self.client.put(
            self.get_script_result_uri(script_set), {"suppressed": True}
        )
        self.assertEqual(response.status_code, http.client.OK)
        script_set = reload_object(script_set)
        self.assertIsNotNone(script_set)
        for script_result in script_set:
            self.assertTrue(script_result.suppressed)
        response = self.client.put(
            self.get_script_result_uri(script_set), {"suppressed": False}
        )
        self.assertEqual(response.status_code, http.client.OK)
        script_set = reload_object(script_set)
        self.assertIsNotNone(script_set)
        for script_result in script_set:
            self.assertFalse(script_result.suppressed)

    def test_PUT_suppressed_raises_validation_error(self):
        self.become_admin()
        node = factory.make_Node()
        factory.pick_choice(HARDWARE_TYPE_CHOICES)
        script_set = self.make_scriptset(node=node)
        response = self.client.put(
            self.get_script_result_uri(script_set), {"suppressed": "testing"}
        )
        self.assertEqual(response.status_code, http.client.BAD_REQUEST)

    def test_PUT_suppressed_and_filters_by_script_result_id(self):
        self.become_admin()
        node = factory.make_Node()
        hardware_type = factory.pick_choice(HARDWARE_TYPE_CHOICES)
        script_set = self.make_scriptset(node=node)
        script = factory.make_Script(hardware_type=hardware_type)
        script_result = factory.make_ScriptResult(script_set, script=script)

        # Make some additional scripts and script results
        scripts = [
            factory.make_Script(hardware_type=hardware_type) for _ in range(3)
        ]
        script_results = []
        for script in scripts:
            script_results.append(
                factory.make_ScriptResult(script_set=script_set, script=script)
            )

        response = self.client.put(
            self.get_script_result_uri(script_set),
            {"suppressed": True, "filters": script_result.id},
        )
        self.assertEqual(response.status_code, http.client.OK)
        script_set = reload_object(script_set)
        self.assertIsNotNone(script_set)
        self.assertEqual(script_set.id, script_result.script_set.id)
        script_result = reload_object(script_result)
        self.assertTrue(script_result.suppressed)
        for script_result in script_results:
            script_result = reload_object(script_result)
            self.assertFalse(script_result.suppressed)

    def test_PUT_suppressed_and_filters_by_script_result_script_name(self):
        self.become_admin()
        node = factory.make_Node()
        hardware_type = factory.pick_choice(HARDWARE_TYPE_CHOICES)
        script_set = self.make_scriptset(node=node)
        script = factory.make_Script(hardware_type=hardware_type)
        script_result = factory.make_ScriptResult(script_set, script=script)

        # Make some additional scripts and script results
        scripts = [
            factory.make_Script(hardware_type=hardware_type) for _ in range(3)
        ]
        script_results = []
        for script in scripts:
            script_results.append(
                factory.make_ScriptResult(script_set=script_set, script=script)
            )

        response = self.client.put(
            self.get_script_result_uri(script_set),
            {"suppressed": True, "filters": script_result.script_name},
        )
        self.assertEqual(response.status_code, http.client.OK)
        script_set = reload_object(script_set)
        self.assertIsNotNone(script_set)
        self.assertEqual(script_set.id, script_result.script_set.id)
        script_result = reload_object(script_result)
        self.assertTrue(script_result.suppressed)
        for script_result in script_results:
            script_result = reload_object(script_result)
            self.assertFalse(script_result.suppressed)

    def test_PUT_suppressed_and_filters_by_hardware_type(self):
        self.become_admin()
        node = factory.make_Node()
        hardware_type = factory.pick_choice(HARDWARE_TYPE_CHOICES)
        script_set = self.make_scriptset(node=node)
        script = factory.make_Script(hardware_type=hardware_type)
        script_result = factory.make_ScriptResult(script_set, script=script)

        # Make some additional scripts and script results
        scripts = [
            factory.make_Script(
                hardware_type=factory.pick_choice(
                    HARDWARE_TYPE_CHOICES, but_not=[hardware_type]
                )
            )
            for _ in range(3)
        ]
        script_results = []
        for script in scripts:
            script_results.append(
                factory.make_ScriptResult(script_set=script_set, script=script)
            )

        response = self.client.put(
            self.get_script_result_uri(script_set),
            {"suppressed": True, "hardware_type": hardware_type},
        )
        self.assertEqual(response.status_code, http.client.OK)
        script_set = reload_object(script_set)
        self.assertIsNotNone(script_set)
        self.assertEqual(script_set.id, script_result.script_set.id)
        script_result = reload_object(script_result)
        self.assertTrue(script_result.suppressed)
        self.assertEqual(hardware_type, script_result.script.hardware_type)
        for script_result in script_results:
            script_result = reload_object(script_result)
            self.assertFalse(script_result.suppressed)

    def test_download(self):
        script_set = self.make_scriptset()
        script_results = [
            factory.make_ScriptResult(script_set=script_set) for _ in range(3)
        ]

        response = self.client.get(
            self.get_script_result_uri(script_set), {"op": "download"}
        )
        self.assertEqual(response.status_code, http.client.OK)

        binary = BytesIO()
        for script_result in sorted(
            list(script_results), key=lambda script_result: script_result.name
        ):
            dashes = "-" * int((80.0 - (2 + len(script_result.name))) / 2)
            binary.write(
                (f"{dashes} {script_result.name} {dashes}\n").encode()
            )
            binary.write(script_result.output)
            binary.write(b"\n")
        self.assertEqual(binary.getvalue(), response.content)

    def test_download_single(self):
        script_set = self.make_scriptset()
        script_result = factory.make_ScriptResult(script_set=script_set)

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {"op": "download", "filter": script_result.id},
        )
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(script_result.output, response.content)

    def test_download_filetype_txt(self):
        script_set = self.make_scriptset()
        script_result = factory.make_ScriptResult(script_set=script_set)

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {"op": "download", "filetype": "txt", "filters": script_result.id},
        )
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(script_result.output, response.content)

    def test_download_filetype_tar_xz(self):
        script_set = self.make_scriptset()
        script_results = [
            factory.make_ScriptResult(script_set=script_set) for _ in range(3)
        ]

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {"op": "download", "filetype": "tar.xz"},
        )
        self.assertEqual(response.status_code, http.client.OK)

        root_dir = "{}-{}-{}".format(
            script_set.node.hostname,
            script_set.result_type_name.lower(),
            script_set.id,
        )
        with tarfile.open(mode="r", fileobj=BytesIO(response.content)) as tar:
            for script_result in script_results:
                path = os.path.join(root_dir, script_result.name)
                member = tar.getmember(path)
                self.assertEqual(
                    time.mktime(script_result.updated.timetuple()),
                    member.mtime,
                )
                self.assertEqual(0o644, member.mode)
                self.assertEqual(
                    script_result.output, tar.extractfile(path).read()
                )

    def test_download_filetype_unknown(self):
        script_set = self.make_scriptset()
        factory.make_ScriptResult(script_set=script_set)

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {"op": "download", "filetype": factory.make_name("filetype")},
        )
        self.assertEqual(response.status_code, http.client.BAD_REQUEST)

    def test_download_output_combined(self):
        script_set = self.make_scriptset()
        script_result = factory.make_ScriptResult(script_set=script_set)

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {
                "op": "download",
                "filter": script_result.id,
                "output": "combined",
            },
        )
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(script_result.output, response.content)

    def test_download_output_stdout(self):
        script_set = self.make_scriptset()
        script_result = factory.make_ScriptResult(script_set=script_set)

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {"op": "download", "filter": script_result.id, "output": "stdout"},
        )
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(script_result.stdout, response.content)

    def test_download_output_stderr(self):
        script_set = self.make_scriptset()
        script_result = factory.make_ScriptResult(script_set=script_set)

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {"op": "download", "filter": script_result.id, "output": "stderr"},
        )
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(script_result.stderr, response.content)

    def test_download_output_result(self):
        script_set = self.make_scriptset()
        script_result = factory.make_ScriptResult(script_set=script_set)

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {"op": "download", "filter": script_result.id, "output": "result"},
        )
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(script_result.result, response.content)

    def test_download_output_all(self):
        script_set = self.make_scriptset()
        script_result = factory.make_ScriptResult(script_set=script_set)

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {"op": "download", "filter": script_result.id, "output": "all"},
        )
        self.assertEqual(response.status_code, http.client.OK)

        binary = BytesIO()
        dashes = "-" * int((80.0 - (2 + len(script_result.name))) / 2)
        binary.write(f"{dashes} {script_result.name} {dashes}\n".encode())
        binary.write(script_result.output)
        binary.write(b"\n")
        filename = "%s.out" % script_result.name
        dashes = "-" * int((80.0 - (2 + len(filename))) / 2)
        binary.write((f"{dashes} {filename} {dashes}\n").encode())
        binary.write(script_result.stdout)
        binary.write(b"\n")
        filename = "%s.err" % script_result.name
        dashes = "-" * int((80.0 - (2 + len(filename))) / 2)
        binary.write((f"{dashes} {filename} {dashes}\n").encode())
        binary.write(script_result.stderr)
        binary.write(b"\n")
        filename = "%s.yaml" % script_result.name
        dashes = "-" * int((80.0 - (2 + len(filename))) / 2)
        binary.write((f"{dashes} {filename} {dashes}\n").encode())
        binary.write(script_result.result)
        binary.write(b"\n")
        self.assertEqual(binary.getvalue(), response.content)

    def test_download_filters(self):
        scripts = [factory.make_Script() for _ in range(10)]
        script_set = self.make_scriptset()
        script_results = {}
        for script in scripts:
            script_result = factory.make_ScriptResult(
                script_set=script_set, script=script
            )
            script_results[script_result.name] = script_result
        results_list = list(script_results.values())
        filtered_results = [random.choice(results_list) for _ in range(3)]

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {
                "op": "download",
                "filetype": "tar.xz",
                "filters": "%s,%s,%d"
                % (
                    filtered_results[0].name,
                    random.choice(
                        [
                            tag
                            for tag in filtered_results[1].script.tags
                            if "tag" in tag
                        ]
                    ),
                    filtered_results[2].id,
                ),
            },
        )
        self.assertEqual(response.status_code, http.client.OK)

        root_dir = "{}-{}-{}".format(
            script_set.node.hostname,
            script_set.result_type_name.lower(),
            script_set.id,
        )
        with tarfile.open(mode="r", fileobj=BytesIO(response.content)) as tar:
            self.assertEqual(len(set(filtered_results)), len(tar.getmembers()))
            for script_result in filtered_results:
                path = os.path.join(root_dir, script_result.name)
                member = tar.getmember(path)
                self.assertEqual(
                    time.mktime(script_result.updated.timetuple()),
                    member.mtime,
                )
                self.assertEqual(0o644, member.mode)
                self.assertEqual(
                    script_result.output, tar.extractfile(path).read()
                )

    def test_download_filters_by_hardware_type(self):
        hardware_type = factory.pick_choice(HARDWARE_TYPE_CHOICES)
        script = factory.make_Script(hardware_type=hardware_type)
        other_script = factory.make_Script(
            hardware_type=factory.pick_choice(
                HARDWARE_TYPE_CHOICES, but_not=[hardware_type]
            )
        )
        script_set = self.make_scriptset()
        script_result = factory.make_ScriptResult(
            script_set=script_set, script=script
        )
        factory.make_ScriptResult(script_set=script_set, script=other_script)

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {
                "op": "download",
                "filter": script_result.id,
                "hardware_type": hardware_type,
            },
        )
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(script_result.output, response.content)

    def test_download_shows_results_from_all_disks(self):
        # Regression test for #LP:1755060
        script = factory.make_Script(hardware_type=HARDWARE_TYPE.STORAGE)
        script_set = self.make_scriptset()
        script_results = []
        for _ in range(3):
            bd = factory.make_PhysicalBlockDevice(node=script_set.node)
            script_results.append(
                factory.make_ScriptResult(
                    script_set=script_set,
                    script=script,
                    physical_blockdevice=bd,
                )
            )

        response = self.client.get(
            self.get_script_result_uri(script_set), {"op": "download"}
        )

        self.assertCountEqual(
            re.findall(r"(name-\w+ - /dev/[\w-]+)", response.content.decode()),
            [
                "%s - /dev/%s"
                % (script_result.name, script_result.physical_blockdevice.name)
                for script_result in sorted(
                    script_results,
                    key=lambda script_result: (
                        script_result.physical_blockdevice.name
                    ),
                )
            ],
        )
        for script_result in script_results:
            self.assertIn(script_result.output, response.content)

    def test_download_shows_results_from_all_interfaces(self):
        script = factory.make_Script(hardware_type=HARDWARE_TYPE.NETWORK)
        script_set = self.make_scriptset()
        script_results = []
        for _ in range(3):
            interface = factory.make_Interface(node=script_set.node)
            script_results.append(
                factory.make_ScriptResult(
                    script_set=script_set, script=script, interface=interface
                )
            )

        response = self.client.get(
            self.get_script_result_uri(script_set), {"op": "download"}
        )

        self.assertCountEqual(
            re.findall(r"(name-\w+ - [\w-]+)", response.content.decode()),
            [
                f"{script_result.name} - {script_result.interface.name}"
                for script_result in sorted(
                    script_results,
                    key=lambda script_result: (script_result.interface.name),
                )
            ],
        )
        for script_result in script_results:
            self.assertIn(script_result.output, response.content)

    def test_download_binary(self):
        script_set = self.make_scriptset()
        # If only one file is being downloaded the raw contents is given. This
        # allows piping of results. When multiple results are given the output
        # is shown deliminated by the test name. As binary data is usually
        # unreadable the output isn't shown.
        curtin_error_tarfile = factory.make_ScriptResult(
            script_set=script_set, script_name=CURTIN_ERROR_TARFILE
        )
        other_result = factory.make_ScriptResult(script_set=script_set)

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {"op": "download", "output": "all"},
        )
        self.assertEqual(response.status_code, http.client.OK)
        binary = BytesIO()
        dashes = "-" * int((80.0 - (2 + len(curtin_error_tarfile.name))) / 2)
        binary.write(
            f"{dashes} {curtin_error_tarfile.name} {dashes}\n".encode()
        )
        binary.write(b"Binary file\n")
        dashes = "-" * int((80.0 - (2 + len(other_result.name))) / 2)
        binary.write(f"{dashes} {other_result.name} {dashes}\n".encode())
        binary.write(other_result.output)
        binary.write(b"\n")
        filename = "%s.out" % other_result.name
        dashes = "-" * int((80.0 - (2 + len(filename))) / 2)
        binary.write((f"{dashes} {filename} {dashes}\n").encode())
        binary.write(other_result.stdout)
        binary.write(b"\n")
        filename = "%s.err" % other_result.name
        dashes = "-" * int((80.0 - (2 + len(filename))) / 2)
        binary.write((f"{dashes} {filename} {dashes}\n").encode())
        binary.write(other_result.stderr)
        binary.write(b"\n")
        filename = "%s.yaml" % other_result.name
        dashes = "-" * int((80.0 - (2 + len(filename))) / 2)
        binary.write((f"{dashes} {filename} {dashes}\n").encode())
        binary.write(other_result.result)
        binary.write(b"\n")
        self.assertEqual(binary.getvalue(), response.content)
