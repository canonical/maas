# Copyright 2017-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.script`"""


from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import dehydrate_datetime
from maasserver.websockets.handlers.script import ScriptHandler


class TestScriptHandler(MAASServerTestCase):
    def dehydrate_script(self, script):
        return {
            "id": script.id,
            "name": script.name,
            "title": script.title,
            "description": script.description,
            "tags": script.tags,
            "script_type": script.script_type,
            "hardware_type": script.hardware_type,
            "parallel": script.parallel,
            "results": script.results,
            "parameters": script.parameters,
            "packages": script.packages,
            "timeout": "0%s" % str(script.timeout),
            "destructive": script.destructive,
            "default": script.default,
            "script": script.script_id,
            "for_hardware": script.for_hardware,
            "may_reboot": script.may_reboot,
            "recommission": script.recommission,
            "apply_configured_networking": script.apply_configured_networking,
            "created": dehydrate_datetime(script.created),
            "updated": dehydrate_datetime(script.updated),
        }

    def test_list(self):
        user = factory.make_User()
        handler = ScriptHandler(user, {}, None)
        parameters = {"interface": {"type": "interface"}}
        expected_scripts = sorted(
            [
                self.dehydrate_script(
                    factory.make_Script(parameters=parameters)
                )
                for _ in range(3)
            ],
            key=lambda i: i["id"],
        )
        sorted_results = sorted(handler.list({}), key=lambda i: i["id"])
        for expected, real in zip(expected_scripts, sorted_results):
            self.assertDictEqual(expected, real)
