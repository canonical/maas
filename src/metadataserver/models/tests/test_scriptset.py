# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = []

import random

from maasserver.enum import NODE_TYPE
from maasserver.preseed import CURTIN_INSTALL_LOG
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from metadataserver.enum import (
    RESULT_TYPE,
    SCRIPT_TYPE,
)
from metadataserver.models import ScriptSet
from provisioningserver.refresh.node_info_scripts import NODE_INFO_SCRIPTS


class TestScriptSetManager(MAASServerTestCase):
    """Test the ScriptSet manager."""

    def test_create_commissioning_script_set(self):
        custom_scripts = [
            factory.make_Script(script_type=SCRIPT_TYPE.COMMISSIONING)
            for _ in range(3)
        ]
        node = factory.make_Node()

        script_set = ScriptSet.objects.create_commissioning_script_set(node)

        expected_scripts = list(NODE_INFO_SCRIPTS)
        expected_scripts += [
            script.name for script in custom_scripts]
        self.assertItemsEqual(
            expected_scripts,
            [script_result.name for script_result in script_set])
        self.assertEquals(RESULT_TYPE.COMMISSIONING, script_set.result_type)

    def test_create_commissioning_script_set_for_controller(self):
        for _ in range(3):
            factory.make_Script(script_type=SCRIPT_TYPE.COMMISSIONING)
        node = factory.make_Node(
            node_type=random.choice([
                NODE_TYPE.RACK_CONTROLLER,
                NODE_TYPE.REGION_CONTROLLER,
                NODE_TYPE.REGION_AND_RACK_CONTROLLER]),
        )

        script_set = ScriptSet.objects.create_commissioning_script_set(node)

        expected_scripts = [
            script_name
            for script_name, data in NODE_INFO_SCRIPTS.items()
            if data['run_on_controller']
        ]
        self.assertItemsEqual(
            expected_scripts,
            [script_result.name for script_result in script_set])
        self.assertEquals(RESULT_TYPE.COMMISSIONING, script_set.result_type)

    def test_create_testing_script_set(self):
        node = factory.make_Node()
        expected_scripts = [
            factory.make_Script(script_type=SCRIPT_TYPE.TESTING).name
            for _ in range(3)
        ]

        script_set = ScriptSet.objects.create_testing_script_set(node)

        self.assertItemsEqual(
            expected_scripts,
            [script_result.name for script_result in script_set])
        self.assertEquals(RESULT_TYPE.TESTING, script_set.result_type)

    def test_create_installation_script_set(self):
        node = factory.make_Node()

        script_set = ScriptSet.objects.create_installation_script_set(node)
        self.assertItemsEqual(
            [CURTIN_INSTALL_LOG],
            [script_result.name for script_result in script_set])
        self.assertEquals(RESULT_TYPE.INSTALLATION, script_set.result_type)


class TestScriptSet(MAASServerTestCase):
    """Test the ScriptSet model."""

    def test_find_script_result_by_id(self):
        script_set = factory.make_ScriptSet()
        script_results = [
            factory.make_ScriptResult(script_set=script_set)
            for _ in range(3)
        ]
        script_result = random.choice(script_results)
        self.assertEquals(
            script_result,
            script_set.find_script_result(script_result_id=script_result.id))

    def test_find_script_result_by_name(self):
        script_set = factory.make_ScriptSet()
        script_results = [
            factory.make_ScriptResult(script_set=script_set)
            for _ in range(3)
        ]
        script_result = random.choice(script_results)
        self.assertEquals(
            script_result,
            script_set.find_script_result(script_name=script_result.name))

    def test_find_script_result_returns_none_when_not_found(self):
        script_set = factory.make_ScriptSet()
        self.assertIsNone(script_set.find_script_result())
