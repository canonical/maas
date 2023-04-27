# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import copy
from datetime import timedelta
import random

from testtools.matchers import ContainsAll

from maasserver.models import ControllerInfo, Script, VersionedTextFile
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from metadataserver.builtin_scripts import (
    BUILTIN_SCRIPTS,
    load_builtin_scripts,
)
from metadataserver.enum import SCRIPT_TYPE_CHOICES
from provisioningserver.refresh.node_info_scripts import NODE_INFO_SCRIPTS


class TestBuiltinScripts(MAASServerTestCase):
    """Test that builtin scripts get properly added and updated."""

    def setUp(self):
        super().setUp()
        self.controller = factory.make_RegionRackController()
        ControllerInfo.objects.set_version(self.controller, "3.0.0")

    def test_creates_scripts(self):
        load_builtin_scripts()

        for script in BUILTIN_SCRIPTS:
            script_in_db = Script.objects.get(name=script.name)

            # While MAAS allows user scripts to leave these fields blank,
            # builtin scripts should always have values.
            self.assertTrue(script_in_db.title, script.name)
            self.assertTrue(script_in_db.description, script.name)
            self.assertTrue(script_in_db.script.data, script.name)
            self.assertNotEqual([], script_in_db.tags, script.name)

            # These values should always be set by the script loader.
            self.assertEqual(
                "Created by maas-3.0.0",
                script_in_db.script.comment,
                script.name,
            )
            self.assertTrue(script_in_db.default, script.name)
            if (
                script.name in NODE_INFO_SCRIPTS
                and NODE_INFO_SCRIPTS[script.name]["run_on_controller"]
            ):
                self.assertIn("deploy-info", script_in_db.tags)
            else:
                self.assertNotIn("deploy-info", script_in_db.tags)

    def test_update_script(self):
        load_builtin_scripts()
        update_script_values = random.choice(BUILTIN_SCRIPTS)
        script = Script.objects.get(name=update_script_values.name)

        # Fields which we can update
        orig_title = script.title
        orig_description = script.description
        orig_script_type = script.script_type
        orig_results = script.results
        orig_parameters = script.parameters

        script.title = factory.make_string()
        script.description = factory.make_string()
        script.script_type = factory.pick_choice(SCRIPT_TYPE_CHOICES)
        script.results = [factory.make_name("result")]
        script.script.parameters = {
            factory.make_name("param"): {"type": "storage"}
        }

        # Put fake old data in to simulate updating a script.
        old_script = VersionedTextFile.objects.create(
            data=factory.make_string()
        )
        script.script = old_script

        # Change maas version
        ControllerInfo.objects.set_version(self.controller, "3.0.1")
        # User changeable fields.
        user_tags = [factory.make_name("tag") for _ in range(3)]
        script.tags = copy.deepcopy(user_tags)
        user_timeout = timedelta(random.randint(0, 1000))
        script.timeout = user_timeout
        script.save()

        load_builtin_scripts()
        script = reload_object(script)

        self.assertEqual(orig_title, script.title, script.name)
        self.assertEqual(orig_description, script.description, script.name)
        self.assertEqual(orig_script_type, script.script_type, script.name)
        self.assertDictEqual(orig_results, script.results, script.name)
        self.assertDictEqual(orig_parameters, script.parameters, script.name)

        self.assertThat(script.tags, ContainsAll(user_tags))
        self.assertEqual(user_timeout, script.timeout)

        self.assertEqual(old_script, script.script.previous_version)
        self.assertEqual("Updated by maas-3.0.1", script.script.comment)
        self.assertTrue(script.default)

    def test_update_removes_deploy_info_tag(self):
        load_builtin_scripts()
        script = (
            Script.objects.filter(default=True)
            .exclude(tags__contains=["deploy-info"])
            .first()
        )

        script.add_tag("deploy-info")
        # Put fake old data in to simulate updating a script.
        old_script = VersionedTextFile.objects.create(
            data=factory.make_string()
        )
        script.script = old_script
        script.save()

        load_builtin_scripts()
        script = reload_object(script)

        self.assertNotIn("deploy-info", script.tags)

    def test_update_tag_unchanged_content(self):
        load_builtin_scripts()
        untagged_script = (
            Script.objects.filter(default=True)
            .exclude(tags__contains=["deploy-info"])
            .first()
        )
        tagged_script = Script.objects.filter(
            default=True, tags__contains=["deploy-info"]
        ).first()

        untagged_script.add_tag("deploy-info")
        untagged_script.save()
        tagged_script.remove_tag("deploy-info")
        tagged_script.save()

        load_builtin_scripts()
        untagged_script = reload_object(untagged_script)
        tagged_script = reload_object(tagged_script)

        self.assertNotIn("deploy-info", untagged_script.tags)
        self.assertIn("deploy-info", tagged_script.tags)

    def test_update_doesnt_revert_script(self):
        load_builtin_scripts()
        update_script_index = random.randint(0, len(BUILTIN_SCRIPTS) - 2)
        update_script_values = BUILTIN_SCRIPTS[update_script_index]
        script = Script.objects.get(name=update_script_values.name)
        # Put fake new data in to simulate another MAAS region updating
        # to a newer version.
        new_script = factory.make_string()
        script.script = script.script.update(new_script)

        # Change maas version
        ControllerInfo.objects.set_version(self.controller, "3.0.1")
        # Fake user updates
        user_tags = [factory.make_name("tag") for _ in range(3)]
        script.tags = user_tags
        user_timeout = timedelta(random.randint(0, 1000))
        script.timeout = user_timeout
        script.save()

        # Test that subsequent scripts still get updated
        second_update_script_values = BUILTIN_SCRIPTS[update_script_index + 1]
        second_script = Script.objects.get(
            name=second_update_script_values.name
        )
        # Put fake old data in to simulate updating a script.
        orig_title = second_script.title
        orig_description = second_script.description
        orig_script_type = second_script.script_type
        orig_results = second_script.results
        orig_parameters = second_script.parameters

        second_script.title = factory.make_string()
        second_script.description = factory.make_string()
        second_script.script_type = factory.pick_choice(SCRIPT_TYPE_CHOICES)
        second_script.results = [factory.make_name("result")]
        second_script.script.parameters = {
            factory.make_name("param"): {"type": "storage"}
        }

        # Put fake old data in to simulate updating a script.
        old_script = VersionedTextFile.objects.create(
            data=factory.make_string()
        )
        second_script.script = old_script

        second_script.save()

        load_builtin_scripts()

        script = reload_object(script)
        self.assertEqual(update_script_values.name, script.name)
        self.assertEqual(new_script, script.script.data)
        self.assertTrue(min(tag in script.tags for tag in user_tags))
        self.assertEqual(user_timeout, script.timeout)
        self.assertTrue(script.default)

        second_script = reload_object(second_script)
        self.assertEqual(orig_title, second_script.title)
        self.assertEqual(orig_description, second_script.description)
        self.assertEqual(orig_script_type, second_script.script_type)
        self.assertDictEqual(orig_results, second_script.results)
        self.assertDictEqual(orig_parameters, second_script.parameters)
        self.assertEqual(old_script, second_script.script.previous_version)
        self.assertEqual("Updated by maas-3.0.1", second_script.script.comment)
        self.assertTrue(second_script.default)
