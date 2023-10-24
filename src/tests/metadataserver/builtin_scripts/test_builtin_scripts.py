from datetime import timedelta
import random

import pytest

from maasserver.models import ControllerInfo, Script, VersionedTextFile
from maasserver.utils.orm import reload_object
from metadataserver.builtin_scripts import (
    BUILTIN_SCRIPTS,
    load_builtin_scripts,
)
from metadataserver.enum import SCRIPT_TYPE_CHOICES
from provisioningserver.refresh.node_info_scripts import NODE_INFO_SCRIPTS


@pytest.fixture
def controller(factory):
    controller = factory.make_RegionRackController()
    ControllerInfo.objects.set_version(controller, "3.0.0")
    yield controller


@pytest.mark.usefixtures("maasdb")
class TestBuiltinScripts:
    def test_creates_scripts(self, controller):
        load_builtin_scripts()

        for script in BUILTIN_SCRIPTS:
            script_in_db = Script.objects.get(name=script.name)

            # While MAAS allows user scripts to leave these fields blank,
            # builtin scripts should always have values.
            assert script_in_db.title
            assert script_in_db.description
            assert script_in_db.script.data
            assert script_in_db.tags

            # These values should always be set by the script loader.
            assert script_in_db.script.comment == "Created by maas-3.0.0"
            assert script_in_db.default

            is_deploy_info = (
                script.name in NODE_INFO_SCRIPTS
                and NODE_INFO_SCRIPTS[script.name]["run_on_controller"]
            )
            assert ("deploy-info" in script_in_db.tags) is is_deploy_info

    def test_update_script(self, factory, controller):
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
        ControllerInfo.objects.set_version(controller, "3.0.1")
        # User changeable fields.
        user_tags = {factory.make_name("tag") for _ in range(3)}
        script.tags = list(user_tags)
        user_timeout = timedelta(random.randint(0, 1000))
        script.timeout = user_timeout
        script.save()

        load_builtin_scripts()
        script = reload_object(script)
        assert orig_title == script.title
        assert orig_description == script.description
        assert orig_script_type == script.script_type
        assert orig_results == script.results
        assert orig_parameters == script.parameters

        assert not user_tags.difference(script.tags)
        assert user_timeout == script.timeout

        assert old_script == script.script.previous_version
        assert script.script.comment == "Updated by maas-3.0.1"
        assert script.default

    def test_update_removes_deploy_info_tag(self, factory):
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
        assert "deploy-info" not in script.tags

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

        assert "deploy-info" not in untagged_script.tags
        assert "deploy-info" in tagged_script.tags

    def test_update_doesnt_revert_script(self, factory, controller):
        load_builtin_scripts()
        update_script_index = random.randint(0, len(BUILTIN_SCRIPTS) - 2)
        update_script_values = BUILTIN_SCRIPTS[update_script_index]
        script = Script.objects.get(name=update_script_values.name)
        # Put fake new data in to simulate another MAAS region updating
        # to a newer version.
        new_script = factory.make_string()
        script.script = script.script.update(new_script)

        # Change maas version
        ControllerInfo.objects.set_version(controller, "3.0.1")
        # Fake user updates
        user_tags = {factory.make_name("tag") for _ in range(3)}
        script.tags = list(user_tags)
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
        assert update_script_values.name == script.name
        assert new_script == script.script.data
        assert not user_tags.difference(script.tags)
        assert script.timeout == user_timeout
        assert script.default

        second_script = reload_object(second_script)
        assert second_script.title == orig_title
        assert second_script.description == orig_description
        assert second_script.script_type == orig_script_type
        assert second_script.results == orig_results
        assert second_script.parameters == orig_parameters
        assert second_script.script.previous_version == old_script
        assert second_script.script.comment == "Updated by maas-3.0.1"
        assert second_script.default
