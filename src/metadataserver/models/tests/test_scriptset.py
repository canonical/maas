# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = []

import random

from django.core.exceptions import ValidationError
from maasserver.enum import NODE_TYPE
from maasserver.exceptions import NoScriptsFound
from maasserver.models import Config
from maasserver.preseed import CURTIN_INSTALL_LOG
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from metadataserver.enum import (
    RESULT_TYPE,
    SCRIPT_TYPE,
)
from metadataserver.models import ScriptSet
from provisioningserver.refresh.node_info_scripts import NODE_INFO_SCRIPTS


class TestScriptSetManager(MAASServerTestCase):
    """Test the ScriptSet manager."""

    def test_clean_old_ignores_new_script_set(self):
        # Make sure the created script_set isn't cleaned up. This can happen
        # when multiple script_sets last_ping are set to None.
        script_set_limit = Config.objects.get_config(
            'max_node_installation_results')
        node = factory.make_Node()
        for _ in range(script_set_limit * 2):
            ScriptSet.objects.create(
                node=node, result_type=RESULT_TYPE.INSTALLATION,
                last_ping=None)

        script_set = ScriptSet.objects.create_installation_script_set(node)
        # If the new script_set was cleaned up this will fail.
        node.current_installation_script_set = script_set
        node.save()

        self.assertEquals(
            script_set_limit,
            ScriptSet.objects.filter(
                node=node,
                result_type=RESULT_TYPE.INSTALLATION).count())

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
        self.assertEquals(
            node.power_state, script_set.power_state_before_transition)

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
        self.assertEquals(
            node.power_state, script_set.power_state_before_transition)

    def test_create_commissioning_script_set_adds_all_user_scripts(self):
        script = factory.make_Script(script_type=SCRIPT_TYPE.COMMISSIONING)
        node = factory.make_Node()
        expected_scripts = list(NODE_INFO_SCRIPTS)
        expected_scripts.append(script.name)

        script_set = ScriptSet.objects.create_commissioning_script_set(node)

        self.assertItemsEqual(
            expected_scripts,
            [script_result.name for script_result in script_set])
        self.assertEquals(RESULT_TYPE.COMMISSIONING, script_set.result_type)
        self.assertEquals(
            node.power_state, script_set.power_state_before_transition)

    def test_create_commissioning_script_set_adds_selected_scripts(self):
        scripts = [
            factory.make_Script(script_type=SCRIPT_TYPE.COMMISSIONING)
            for _ in range(10)
        ]
        node = factory.make_Node()
        script_selected_by_tag = random.choice(scripts)
        script_selected_by_name = random.choice(scripts)
        script_selected_by_id = random.choice(scripts)
        expected_scripts = list(NODE_INFO_SCRIPTS)
        expected_scripts.append(script_selected_by_tag.name)
        expected_scripts.append(script_selected_by_name.name)
        expected_scripts.append(script_selected_by_id.name)

        script_set = ScriptSet.objects.create_commissioning_script_set(
            node, scripts=[
                random.choice(script_selected_by_tag.tags),
                script_selected_by_name.name,
                script_selected_by_id.id,
            ])
        self.assertItemsEqual(
            set(expected_scripts),
            [script_result.name for script_result in script_set])
        self.assertEquals(RESULT_TYPE.COMMISSIONING, script_set.result_type)
        self.assertEquals(
            node.power_state, script_set.power_state_before_transition)

    def test_create_commissioning_script_set_cleans_up_past_limit(self):
        script_set_limit = Config.objects.get_config(
            'max_node_commissioning_results')
        node = factory.make_Node()
        for _ in range(script_set_limit * 2):
            factory.make_ScriptSet(
                node=node, result_type=RESULT_TYPE.COMMISSIONING)

        ScriptSet.objects.create_commissioning_script_set(node)

        self.assertEquals(
            script_set_limit,
            ScriptSet.objects.filter(
                node=node,
                result_type=RESULT_TYPE.COMMISSIONING).count())

    def test_create_commissioning_script_set_cleans_up_current(self):
        Config.objects.set_config('max_node_commissioning_results', 1)
        node = factory.make_Node()
        script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.COMMISSIONING)
        node.current_commissioning_script_set = script_set
        node.save()

        ScriptSet.objects.create_commissioning_script_set(node)

        self.assertEquals(
            1,
            ScriptSet.objects.filter(
                node=node,
                result_type=RESULT_TYPE.COMMISSIONING).count())

    def test_create_testing_script_set(self):
        node = factory.make_Node()
        expected_scripts = [
            factory.make_Script(
                script_type=SCRIPT_TYPE.TESTING, tags=['commissioning']).name
            for _ in range(3)
        ]

        script_set = ScriptSet.objects.create_testing_script_set(node)

        self.assertItemsEqual(
            expected_scripts,
            [script_result.name for script_result in script_set])
        self.assertEquals(RESULT_TYPE.TESTING, script_set.result_type)
        self.assertEquals(
            node.power_state, script_set.power_state_before_transition)

    def test_create_testing_script_set_adds_selected_scripts(self):
        scripts = [
            factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
            for _ in range(10)
        ]
        script_selected_by_tag = random.choice(scripts)
        script_selected_by_name = random.choice(scripts)
        script_selected_by_id = random.choice(scripts)
        node = factory.make_Node()
        expected_scripts = [
            script_selected_by_tag.name,
            script_selected_by_name.name,
            script_selected_by_id.name,
        ]

        script_set = ScriptSet.objects.create_testing_script_set(
            node, scripts=[
                random.choice(script_selected_by_tag.tags),
                script_selected_by_name.name,
                script_selected_by_id.id,
            ])

        self.assertItemsEqual(
            set(expected_scripts),
            [script_result.name for script_result in script_set])
        self.assertEquals(RESULT_TYPE.TESTING, script_set.result_type)
        self.assertEquals(
            node.power_state, script_set.power_state_before_transition)

    def test_create_testing_script_raises_exception_when_none_found(self):
        node = factory.make_Node()
        self.assertRaises(
            NoScriptsFound,
            ScriptSet.objects.create_testing_script_set, node)

    def test_create_testing_script_set_cleans_up_past_limit(self):
        script_set_limit = Config.objects.get_config(
            'max_node_testing_results')
        node = factory.make_Node()
        for _ in range(script_set_limit * 2):
            factory.make_ScriptSet(
                node=node, result_type=RESULT_TYPE.TESTING)

        script = factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
        ScriptSet.objects.create_testing_script_set(
            node, scripts=[script.name])

        self.assertEquals(
            script_set_limit,
            ScriptSet.objects.filter(
                node=node,
                result_type=RESULT_TYPE.TESTING).count())

    def test_create_testing_script_set_cleans_up_current(self):
        Config.objects.set_config('max_node_testing_results', 1)
        node = factory.make_Node()
        script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.TESTING)
        node.current_testing_script_set = script_set
        node.save()

        script = factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
        ScriptSet.objects.create_testing_script_set(
            node, scripts=[script.name])

        self.assertEquals(
            1,
            ScriptSet.objects.filter(
                node=node,
                result_type=RESULT_TYPE.TESTING).count())

    def test_create_installation_script_set(self):
        node = factory.make_Node()

        script_set = ScriptSet.objects.create_installation_script_set(node)
        self.assertItemsEqual(
            [CURTIN_INSTALL_LOG],
            [script_result.name for script_result in script_set])
        self.assertEquals(RESULT_TYPE.INSTALLATION, script_set.result_type)
        self.assertEquals(
            node.power_state, script_set.power_state_before_transition)

    def test_create_installation_script_set_cleans_up_past_limit(self):
        script_set_limit = Config.objects.get_config(
            'max_node_installation_results')
        node = factory.make_Node()
        for _ in range(script_set_limit * 2):
            factory.make_ScriptSet(
                node=node, result_type=RESULT_TYPE.INSTALLATION)

        ScriptSet.objects.create_installation_script_set(node)

        self.assertEquals(
            script_set_limit,
            ScriptSet.objects.filter(
                node=node,
                result_type=RESULT_TYPE.INSTALLATION).count())

    def test_create_installation_script_set_cleans_up_current(self):
        Config.objects.get_config('max_node_installation_results', 1)
        node = factory.make_Node()
        script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.INSTALLATION)
        node.current_installation_script_set = script_set
        node.save()

        ScriptSet.objects.create_installation_script_set(node)

        self.assertEquals(
            1,
            ScriptSet.objects.filter(
                node=node,
                result_type=RESULT_TYPE.INSTALLATION).count())


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

    def test_delete(self):
        node = factory.make_Node(with_empty_script_sets=True)
        orig_commissioning_script_set = node.current_commissioning_script_set
        orig_testing_script_set = node.current_testing_script_set
        orig_installation_script_set = node.current_installation_script_set
        script_set = factory.make_ScriptSet(node=node)

        script_set.delete()

        node = reload_object(node)
        self.assertIsNone(reload_object(script_set))
        self.assertEquals(
            orig_commissioning_script_set,
            node.current_commissioning_script_set)
        self.assertEquals(
            orig_testing_script_set, node.current_testing_script_set)
        self.assertEquals(
            orig_installation_script_set, node.current_installation_script_set)

    def test_delete_prevents_del_of_current_commissioning_script_set(self):
        node = factory.make_Node(with_empty_script_sets=True)
        self.assertRaises(
            ValidationError, node.current_commissioning_script_set.delete)

    def test_delete_prevents_del_of_current_installation_script_set(self):
        node = factory.make_Node(with_empty_script_sets=True)
        self.assertRaises(
            ValidationError, node.current_installation_script_set.delete)

    def test_delete_sets_current_testing_script_set_to_older_version(self):
        node = factory.make_Node(with_empty_script_sets=True)
        previous_script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.TESTING)
        node.current_testing_script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.TESTING)
        node.save()

        node.current_testing_script_set.delete()
        self.assertEquals(
            previous_script_set,
            reload_object(node).current_testing_script_set)
