# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import copy
from datetime import timedelta
import random

from testtools.matchers import ContainsAll, Equals, Not

from maasserver.models import VersionedTextFile
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from metadataserver.builtin_scripts import (
    BUILTIN_SCRIPTS,
    load_builtin_scripts,
)
from metadataserver.enum import SCRIPT_TYPE_CHOICES
from metadataserver.models import Script
from provisioningserver.utils.version import get_running_version


class TestBuiltinScripts(MAASServerTestCase):
    """Test that builtin scripts get properly added and updated."""

    def test_creates_scripts(self):
        load_builtin_scripts()

        for script in BUILTIN_SCRIPTS:
            script_in_db = Script.objects.get(name=script.name)

            # While MAAS allows user scripts to leave these fields blank,
            # builtin scripts should always have values.
            self.assertTrue(script_in_db.title, script.name)
            self.assertTrue(script_in_db.description, script.name)
            self.assertTrue(script_in_db.script.data, script.name)
            self.assertThat(script_in_db.tags, Not(Equals([])), script.name)

            # These values should always be set by the script loader.
            self.assertEquals(
                "Created by maas-%s" % get_running_version(),
                script_in_db.script.comment,
                script.name,
            )
            self.assertTrue(script_in_db.default, script.name)

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

        # User changeable fields.
        user_tags = [factory.make_name("tag") for _ in range(3)]
        script.tags = copy.deepcopy(user_tags)
        user_timeout = timedelta(random.randint(0, 1000))
        script.timeout = user_timeout
        script.save()

        load_builtin_scripts()
        script = reload_object(script)

        self.assertEquals(orig_title, script.title, script.name)
        self.assertEquals(orig_description, script.description, script.name)
        self.assertEquals(orig_script_type, script.script_type, script.name)
        self.assertDictEqual(orig_results, script.results, script.name)
        self.assertDictEqual(orig_parameters, script.parameters, script.name)

        self.assertThat(script.tags, ContainsAll(user_tags))
        self.assertEquals(user_timeout, script.timeout)

        self.assertEquals(old_script, script.script.previous_version)
        self.assertEquals(
            "Updated by maas-%s" % get_running_version(), script.script.comment
        )
        self.assertTrue(script.default)

    def test_update_doesnt_revert_script(self):
        load_builtin_scripts()
        update_script_index = random.randint(0, len(BUILTIN_SCRIPTS) - 2)
        update_script_values = BUILTIN_SCRIPTS[update_script_index]
        script = Script.objects.get(name=update_script_values.name)
        # Put fake new data in to simulate another MAAS region updating
        # to a newer version.
        new_script = factory.make_string()
        script.script = script.script.update(new_script)

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
        self.assertEquals(update_script_values.name, script.name)
        self.assertEquals(new_script, script.script.data)
        self.assertTrue(min([tag in script.tags for tag in user_tags]))
        self.assertEquals(user_timeout, script.timeout)
        self.assertTrue(script.default)

        second_script = reload_object(second_script)
        self.assertEquals(orig_title, second_script.title)
        self.assertEquals(orig_description, second_script.description)
        self.assertEquals(orig_script_type, second_script.script_type)
        self.assertDictEqual(orig_results, second_script.results)
        self.assertDictEqual(orig_parameters, second_script.parameters)
        self.assertEquals(old_script, second_script.script.previous_version)
        self.assertEquals(
            "Updated by maas-%s" % get_running_version(),
            second_script.script.comment,
        )
        self.assertTrue(second_script.default)
