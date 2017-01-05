# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = []

import json
import random
from unittest.mock import MagicMock

from maasserver.models import (
    Event,
    EventType,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from metadataserver.enum import (
    RESULT_TYPE,
    SCRIPT_STATUS,
    SCRIPT_STATUS_CHOICES,
)
from metadataserver.models import scriptresult as scriptresult_module
from provisioningserver.events import EVENT_TYPES


class TestScriptResult(MAASServerTestCase):
    """Test the ScriptResult model."""

    def test__name_returns_script_name(self):
        script_result = factory.make_ScriptResult()
        self.assertEquals(script_result.script.name, script_result.name)

    def test__name_returns_model_script_name_when_no_script(self):
        script_result = factory.make_ScriptResult()
        script_result.script = None
        script_name = factory.make_name('script_name')
        script_result.script_name = script_name
        self.assertEquals(script_name, script_result.name)

    def test__name_returns_unknown_when_no_script_or_model_script_name(self):
        script_result = factory.make_ScriptResult()
        script_result.script = None
        self.assertEquals('Unknown', script_result.name)

    def test_store_result_only_allows_status_running(self):
        # XXX ltrager 2016-12-07 - Only allow SCRIPT_STATUS.RUNNING once
        # status tracking is implemented.
        script_result = factory.make_ScriptResult(
            status=factory.pick_choice(
                SCRIPT_STATUS_CHOICES,
                [SCRIPT_STATUS.PENDING, SCRIPT_STATUS.RUNNING]))
        self.assertRaises(
            AssertionError, script_result.store_result, random.randint(0, 255))

    def test_store_result_only_allows_when_stdout_is_blank(self):
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.RUNNING, stdout=factory.make_bytes())
        self.assertRaises(
            AssertionError, script_result.store_result, random.randint(0, 255))

    def test_store_result_only_allows_when_stderr_is_blank(self):
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.RUNNING, stderr=factory.make_bytes())
        self.assertRaises(
            AssertionError, script_result.store_result, random.randint(0, 255))

    def test_store_result_only_allows_when_result_is_blank(self):
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.RUNNING, result=factory.make_string())
        self.assertRaises(
            AssertionError, script_result.store_result, random.randint(0, 255))

    def test_store_result_sets_status_to_passed_with_exit_code_zero(self):
        script_result = factory.make_ScriptResult(status=SCRIPT_STATUS.RUNNING)
        script_result.store_result(0)
        self.assertEquals(SCRIPT_STATUS.PASSED, script_result.status)
        self.assertEquals(0, script_result.exit_status)
        self.assertEquals(b'', script_result.stdout)
        self.assertEquals(b'', script_result.stderr)
        self.assertEquals('', script_result.result)
        self.assertEquals(
            script_result.script.script, script_result.script_version)

    def test_store_result_sets_status_to_failed_with_exit_code_zero(self):
        script_result = factory.make_ScriptResult(status=SCRIPT_STATUS.RUNNING)
        exit_status = random.randint(1, 255)
        script_result.store_result(exit_status)
        self.assertEquals(SCRIPT_STATUS.FAILED, script_result.status)
        self.assertEquals(exit_status, script_result.exit_status)
        self.assertEquals(b'', script_result.stdout)
        self.assertEquals(b'', script_result.stderr)
        self.assertEquals('', script_result.result)
        self.assertEquals(
            script_result.script.script, script_result.script_version)

    def test_store_result_stores_stdout(self):
        script_result = factory.make_ScriptResult(status=SCRIPT_STATUS.RUNNING)
        exit_status = random.randint(0, 255)
        stdout = factory.make_bytes()

        script_result.store_result(exit_status, stdout=stdout)

        self.assertEquals(exit_status, script_result.exit_status)
        self.assertEquals(stdout, script_result.stdout)
        self.assertEquals(b'', script_result.stderr)
        self.assertEquals('', script_result.result)
        self.assertEquals(
            script_result.script.script, script_result.script_version)

    def test_store_result_stores_stderr(self):
        script_result = factory.make_ScriptResult(status=SCRIPT_STATUS.RUNNING)
        exit_status = random.randint(0, 255)
        stderr = factory.make_bytes()

        script_result.store_result(exit_status, stderr=stderr)

        self.assertEquals(exit_status, script_result.exit_status)
        self.assertEquals(b'', script_result.stdout)
        self.assertEquals(stderr, script_result.stderr)
        self.assertEquals('', script_result.result)
        self.assertEquals(
            script_result.script.script, script_result.script_version)

    def test_store_result_stores_result(self):
        script_result = factory.make_ScriptResult(status=SCRIPT_STATUS.RUNNING)
        exit_status = random.randint(0, 255)
        result = {factory.make_name('key'): factory.make_name('value')}

        script_result.store_result(exit_status, result=json.dumps(result))

        self.assertEquals(exit_status, script_result.exit_status)
        self.assertEquals(b'', script_result.stdout)
        self.assertEquals(b'', script_result.stderr)
        self.assertItemsEqual(result, script_result.result)
        self.assertEquals(
            script_result.script.script, script_result.script_version)

    def test_store_result_stores_script_version(self):
        script = factory.make_Script()
        old_version = script.script
        script.script = script.script.update(factory.make_string())
        script.save()
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.RUNNING, script=script)
        exit_status = random.randint(0, 255)

        script_result.store_result(
            exit_status, script_version_id=old_version.id)

        self.assertEquals(exit_status, script_result.exit_status)
        self.assertEquals(b'', script_result.stdout)
        self.assertEquals(b'', script_result.stderr)
        self.assertEquals('', script_result.result)
        self.assertEquals(old_version, script_result.script_version)

    def test_store_result_sets_script_version_to_latest_when_not_given(self):
        script = factory.make_Script()
        script_result = factory.make_ScriptResult(
            status=SCRIPT_STATUS.RUNNING, script=script)
        exit_status = random.randint(0, 255)

        script_result.store_result(exit_status)

        self.assertEquals(exit_status, script_result.exit_status)
        self.assertEquals(b'', script_result.stdout)
        self.assertEquals(b'', script_result.stderr)
        self.assertEquals('', script_result.result)
        self.assertEquals(script.script, script_result.script_version)

    def test_store_result_logs_missing_script_version(self):
        mock_logger = self.patch(scriptresult_module.logger, 'error')
        script_result = factory.make_ScriptResult(status=SCRIPT_STATUS.RUNNING)
        exit_status = random.randint(0, 255)

        script_result.store_result(exit_status, script_version_id=-1)

        expected_msg = (
            "%s(%s) sent a script result for %s(%d) with an unknown "
            "script version(-1)." % (
                script_result.script_set.node.fqdn,
                script_result.script_set.node.system_id,
                script_result.script.name, script_result.script.id))
        event_type = EventType.objects.get(
            name=EVENT_TYPES.SCRIPT_RESULT_ERROR)
        event = Event.objects.get(
            node=script_result.script_set.node, type_id=event_type.id)
        self.assertEquals(expected_msg, event.description)
        self.assertThat(mock_logger, MockCalledOnceWith(expected_msg))

    def test_store_result_runs_builtin_commissioning_hooks(self):
        script_set = factory.make_ScriptSet(
            result_type=RESULT_TYPE.COMMISSIONING)
        script_result = factory.make_ScriptResult(
            script_set=script_set, status=SCRIPT_STATUS.RUNNING)
        exit_status = random.randint(0, 255)
        mock_hook = MagicMock()
        scriptresult_module.NODE_INFO_SCRIPTS[script_result.name] = {
            'hook': mock_hook,
        }
        self.addCleanup(
            scriptresult_module.NODE_INFO_SCRIPTS.pop, script_result.name)

        script_result.store_result(exit_status)

        self.assertThat(
            mock_hook,
            MockCalledOnceWith(
                node=script_set.node, output=b'', exit_status=exit_status))
