# Copyright 2017-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Script form."""


from datetime import timedelta
import json
import random

from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpRequest

from maascommon.events import AUDIT
from maasserver.forms.script import (
    CommissioningScriptForm,
    ScriptForm,
    TestingScriptForm,
)
from maasserver.models import Event, Script, VersionedTextFile
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from metadataserver.enum import (
    HARDWARE_TYPE,
    HARDWARE_TYPE_CHOICES,
    SCRIPT_PARALLEL,
    SCRIPT_PARALLEL_CHOICES,
    SCRIPT_TYPE,
    SCRIPT_TYPE_CHOICES,
)


class TestScriptForm(MAASServerTestCase):
    def test_create_requires_name(self):
        form = ScriptForm(data={"script": factory.make_script_content()})
        self.assertFalse(form.is_valid())
        self.assertCountEqual([], VersionedTextFile.objects.all())

    def test_create_requires_script(self):
        form = ScriptForm(data={"name": factory.make_string()})
        self.assertFalse(form.is_valid())
        self.assertCountEqual([], VersionedTextFile.objects.all())

    def test_create_with_default_values(self):
        name = factory.make_name("name")
        script_content = factory.make_script_content()

        form = ScriptForm(data={"name": name, "script": script_content})
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()

        self.assertEqual(name, script.name)
        self.assertEqual("", script.title)
        self.assertEqual("", script.description)
        self.assertEqual(1, len(script.tags))
        self.assertEqual(SCRIPT_TYPE.TESTING, script.script_type)
        self.assertEqual(HARDWARE_TYPE.NODE, script.hardware_type)
        self.assertEqual(SCRIPT_PARALLEL.DISABLED, script.parallel)
        self.assertEqual({}, script.packages)
        self.assertEqual({}, script.results)
        self.assertEqual({}, script.parameters)
        self.assertEqual(timedelta(0), script.timeout)
        self.assertFalse(script.destructive)
        self.assertEqual(script_content, script.script.data)
        self.assertFalse(script.default)
        self.assertEqual([], script.for_hardware)
        self.assertFalse(script.may_reboot)
        self.assertFalse(script.recommission)

    def test_create_with_defined_values(self):
        name = factory.make_name("name")
        title = factory.make_name("title")
        description = factory.make_name("description")
        tags = [factory.make_name("tag") for _ in range(3)]
        script_type = factory.pick_choice(SCRIPT_TYPE_CHOICES)
        hardware_type = factory.pick_choice(HARDWARE_TYPE_CHOICES)
        parallel = factory.pick_choice(SCRIPT_PARALLEL_CHOICES)
        packages = {"apt": [factory.make_name("package")]}
        timeout = random.randint(0, 1000)
        destructive = factory.pick_bool()
        script_content = factory.make_script_content()
        comment = factory.make_name("comment")
        may_reboot = factory.pick_bool()
        if script_type == SCRIPT_TYPE.COMMISSIONING:
            for_hardware = [
                "modalias:%s" % factory.make_name("mod_alias"),
                "pci:%04X:%04x"
                % (random.randint(0, 9999), random.randint(0, 9999)),
                "usb:%04x:%04X"
                % (random.randint(0, 9999), random.randint(0, 9999)),
                "system_vendor:%s" % factory.make_name("system_name"),
                "system_product:%s" % factory.make_name("system_product"),
                "system_version:%s" % factory.make_name("system_version"),
                "mainboard_vendor:%s" % factory.make_name("mobo_vendor"),
                "mainboard_product:%s" % factory.make_name("mobo_product"),
            ]
            recommission = factory.pick_bool()
        else:
            for_hardware = []
            recommission = False

        form = ScriptForm(
            data={
                "name": name,
                "title": title,
                "description": description,
                "tags": ",".join(tags),
                "type": script_type,
                "hardware_type": hardware_type,
                "parallel": parallel,
                "packages": json.dumps(packages),
                "timeout": str(timeout),
                "destructive": destructive,
                "script": script_content,
                "comment": comment,
                "may_reboot": may_reboot,
                "for_hardware": ",".join(for_hardware),
                "recommission": recommission,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()

        self.assertEqual(name, script.name)
        self.assertEqual(title, script.title)
        self.assertEqual(description, script.description)
        for tag in tags:
            self.assertIn(tag, script.tags)
        self.assertEqual(script_type, script.script_type)
        self.assertEqual(hardware_type, script.hardware_type)
        self.assertEqual(parallel, script.parallel)
        self.assertEqual(packages, script.packages)
        self.assertEqual({}, script.results)
        self.assertEqual({}, script.parameters)
        self.assertEqual(packages, script.packages)
        self.assertEqual(timedelta(0, timeout), script.timeout)
        self.assertEqual(destructive, script.destructive)
        self.assertEqual(script_content, script.script.data)
        self.assertEqual(comment, script.script.comment)
        self.assertEqual(may_reboot, script.may_reboot)
        self.assertCountEqual(for_hardware, script.for_hardware)
        self.assertEqual(recommission, script.recommission)
        self.assertFalse(script.default)

    def test_create_setting_default_has_no_effect(self):
        form = ScriptForm(
            data={
                "name": factory.make_name("name"),
                "script": factory.make_script_content(),
                "default": True,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()
        self.assertFalse(script.default)

    def test_update(self):
        script = factory.make_Script()
        name = factory.make_name("name")
        title = factory.make_name("title")
        description = factory.make_name("description")
        tags = [factory.make_name("tag") for _ in range(3)]
        script_type = factory.pick_choice(SCRIPT_TYPE_CHOICES)
        hardware_type = factory.pick_choice(HARDWARE_TYPE_CHOICES)
        parallel = factory.pick_choice(SCRIPT_PARALLEL_CHOICES)
        packages = {"apt": [factory.make_name("package")]}
        timeout = random.randint(0, 1000)
        destructive = factory.pick_bool()
        script_content = factory.make_script_content()
        comment = factory.make_name("comment")
        orig_script_content = script.script.data
        may_reboot = factory.pick_bool()
        apply_configured_networking = factory.pick_bool()
        if script_type == SCRIPT_TYPE.COMMISSIONING:
            for_hardware = [
                "modalias:%s" % factory.make_name("mod_alias"),
                "pci:%04x:%04X"
                % (random.randint(0, 9999), random.randint(0, 9999)),
                "usb:%04x:%04X"
                % (random.randint(0, 9999), random.randint(0, 9999)),
                "system_vendor:%s" % factory.make_name("system_name"),
                "system_product:%s" % factory.make_name("system_product"),
                "system_version:%s" % factory.make_name("system_version"),
                "mainboard_vendor:%s" % factory.make_name("mobo_vendor"),
                "mainboard_product:%s" % factory.make_name("mobo_product"),
            ]
            recommission = factory.pick_bool()
        else:
            for_hardware = []
            recommission = False

        form = ScriptForm(
            data={
                "name": name,
                "title": title,
                "description": description,
                "tags": ",".join(tags),
                "type": script_type,
                "hardware_type": hardware_type,
                "parallel": parallel,
                "packages": json.dumps(packages),
                "timeout": str(timeout),
                "destructive": destructive,
                "script": script_content,
                "comment": comment,
                "may_reboot": may_reboot,
                "for_hardware": ",".join(for_hardware),
                "recommission": recommission,
                "apply_configured_networking": apply_configured_networking,
            },
            instance=script,
        )
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()

        self.assertEqual(name, script.name)
        self.assertEqual(title, script.title)
        self.assertEqual(description, script.description)
        for tag in tags:
            self.assertIn(tag, script.tags)
        self.assertEqual(script_type, script.script_type)
        self.assertEqual(hardware_type, script.hardware_type)
        self.assertEqual(parallel, script.parallel)
        self.assertEqual({}, script.results)
        self.assertEqual({}, script.parameters)
        self.assertEqual(packages, script.packages)
        self.assertEqual(timedelta(0, timeout), script.timeout)
        self.assertEqual(destructive, script.destructive)
        self.assertEqual(script_content, script.script.data)
        self.assertEqual(comment, script.script.comment)
        self.assertEqual(
            orig_script_content, script.script.previous_version.data
        )
        self.assertIsNone(script.script.previous_version.comment)
        self.assertEqual(
            apply_configured_networking, script.apply_configured_networking
        )
        self.assertFalse(script.default)

    def test_update_no_fields_mandatory(self):
        script = factory.make_Script()
        form = ScriptForm(data={}, instance=script)
        self.assertTrue(form.is_valid(), form.errors)

    def test_update_setting_default_has_no_effect(self):
        script = factory.make_Script(default=True)
        form = ScriptForm(data={"default": False}, instance=script)
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()
        self.assertTrue(script.default)

    def test_update_prohibits_most_field_updates_on_default_script(self):
        script = factory.make_Script(default=True)
        for name, field in ScriptForm.base_fields.items():
            if name in ["tags", "timeout"]:
                continue
            elif name == "script_type":
                value = factory.pick_choice(SCRIPT_TYPE_CHOICES)
            elif name == "hardware_type":
                value = factory.pick_choice(HARDWARE_TYPE_CHOICES)
            elif name == "parallel":
                value = factory.pick_choice(SCRIPT_PARALLEL_CHOICES)
            elif name in ["destructive", "may_reboot"]:
                value = factory.pick_bool()
            elif name == "packages":
                value = json.dumps({"apt": [factory.make_name("package")]})
            elif name == "timeout":
                value = str(random.randint(0, 1000))
            elif name == "comment":
                # A comment must be done with a script
                continue
            elif name in ["for_hardware", "recommission"]:
                # Only available on commissioning scripts
                continue
            else:
                value = factory.make_string()
            form = ScriptForm(data={name: value}, instance=script)
            self.assertFalse(form.is_valid())
            self.assertEqual(1, VersionedTextFile.objects.all().count())

    def test_update_edit_default_allows_update_of_all_fields(self):
        script = factory.make_Script(default=True)
        for name, field in ScriptForm.base_fields.items():
            if name == "script_type":
                value = factory.pick_choice(SCRIPT_TYPE_CHOICES)
            elif name == "hardware_type":
                value = factory.pick_choice(HARDWARE_TYPE_CHOICES)
            elif name == "parallel":
                value = factory.pick_choice(SCRIPT_PARALLEL_CHOICES)
            elif name in ["destructive", "may_reboot"]:
                value = factory.pick_bool()
            elif name == "packages":
                value = json.dumps({"apt": [factory.make_name("package")]})
            elif name == "timeout":
                value = str(random.randint(0, 1000))
            elif name == "script":
                value = factory.make_script_content()
            elif name == "comment":
                # A comment must be done with a script
                continue
            elif name in ["for_hardware", "recommission"]:
                # Only available on commissioning scripts
                continue
            else:
                value = factory.make_string()
            form = ScriptForm(
                data={name: value}, instance=script, edit_default=True
            )
            self.assertTrue(form.is_valid(), form.errors)

    def test_update_allows_editing_tag_and_timeout_on_default_script(self):
        script = factory.make_Script(default=True, destructive=False)
        tags = [factory.make_name("tag") for _ in range(3)]
        timeout = random.randint(0, 1000)

        form = ScriptForm(
            data={"tags": ",".join(tags), "timeout": str(timeout)},
            instance=script,
        )
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()

        for tag in tags:
            self.assertIn(tag, script.tags)
        self.assertEqual(timedelta(0, timeout), script.timeout)

    def test_update_requires_script_with_comment(self):
        script = factory.make_Script()
        form = ScriptForm(
            data={"comment": factory.make_name("comment")}, instance=script
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "comment": [
                    '"comment" may only be used when specifying a "script" '
                    "as well."
                ]
            },
            form.errors,
        )

    def test_update_script_doesnt_effect_other_fields(self):
        script = factory.make_Script()
        script_content = factory.make_script_content()
        name = script.name
        title = script.title
        description = script.description
        tags = script.tags
        script_type = script.script_type
        hardware_type = script.hardware_type
        parallel = script.parallel
        results = script.results
        parameters = script.parameters
        packages = script.packages
        timeout = script.timeout
        destructive = script.destructive
        may_reboot = script.may_reboot
        for_hardware = script.for_hardware
        recommission = script.recommission

        form = ScriptForm(data={"script": script_content}, instance=script)
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()

        self.assertEqual(name, script.name)
        self.assertEqual(title, script.title)
        self.assertEqual(description, script.description)
        self.assertEqual(tags, script.tags)
        self.assertEqual(script_type, script.script_type)
        self.assertEqual(hardware_type, script.hardware_type)
        self.assertEqual(packages, script.packages)
        self.assertEqual(parallel, script.parallel)
        self.assertEqual(results, script.results)
        self.assertEqual(parameters, script.parameters)
        self.assertEqual(timeout, script.timeout)
        self.assertEqual(destructive, script.destructive)
        self.assertFalse(script.default)
        self.assertEqual(script_content, script.script.data)
        self.assertEqual(may_reboot, script.may_reboot)
        self.assertCountEqual(for_hardware, script.for_hardware)
        self.assertEqual(recommission, script.recommission)

    def test_yaml_doesnt_update_tags(self):
        script = factory.make_Script()
        orig_tags = script.tags

        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {"tags": [factory.make_name("tag") for _ in range(3)]}
                )
            },
            instance=script,
        )
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()
        self.assertCountEqual(orig_tags, script.tags)

    def test_yaml_doesnt_update_timeout(self):
        script = factory.make_Script()
        orig_timeout = script.timeout

        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {"timeout": random.randint(0, 1000)}
                )
            },
            instance=script,
        )
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()
        self.assertEqual(orig_timeout, script.timeout)

    def test_can_use_script_type_name(self):
        script_type = factory.pick_choice(SCRIPT_TYPE_CHOICES)
        form = ScriptForm(
            data={
                "name": factory.make_name("name"),
                "script": factory.make_script_content(),
                "type": script_type,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()

        self.assertEqual(script_type, script.script_type)

    def test_errors_on_invalid_script_type(self):
        form = ScriptForm(
            data={
                "name": factory.make_name("name"),
                "script": factory.make_script_content(),
                "type": factory.make_string(),
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "script_type": [
                    "Script type must be commissioning, testing or release"
                ]
            },
            form.errors,
        )
        self.assertCountEqual([], VersionedTextFile.objects.all())

    def test_can_use_hardware_type_name(self):
        hardware_type = factory.pick_choice(HARDWARE_TYPE_CHOICES)
        form = ScriptForm(
            data={
                "name": factory.make_name("name"),
                "script": factory.make_script_content(),
                "hardware_type": hardware_type,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()

        self.assertEqual(hardware_type, script.hardware_type)

    def test_errors_on_invalid_hardware_type(self):
        form = ScriptForm(
            data={
                "name": factory.make_name("name"),
                "script": factory.make_script_content(),
                "hardware_type": factory.make_string(),
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "hardware_type": [
                    "Hardware type must be node, cpu, memory, storage, or gpu"
                ]
            },
            form.errors,
        )
        self.assertCountEqual([], VersionedTextFile.objects.all())

    def test_can_use_parallel(self):
        script_parallel = factory.pick_choice(SCRIPT_PARALLEL_CHOICES)
        form = ScriptForm(
            data={
                "name": factory.make_name("name"),
                "script": factory.make_script_content(),
                "parallel": script_parallel,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()

        self.assertEqual(script_parallel, script.parallel)

    def test_errors_on_invalid_parallel_name(self):
        form = ScriptForm(
            data={
                "name": factory.make_name("name"),
                "script": factory.make_script_content(),
                "parallel": factory.make_string(),
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "parallel": [
                    "Script parallel must be disabled, instance, or any."
                ]
            },
            form.errors,
        )
        self.assertCountEqual([], VersionedTextFile.objects.all())

    def test_errors_on_no_shebang_in_script(self):
        form = ScriptForm(
            data={
                "name": factory.make_name("name"),
                "script": factory.make_string(),
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual({"script": ["Must start with shebang."]}, form.errors)

    def test_errors_on_invalid_parameters(self):
        form = ScriptForm(
            data={
                "name": factory.make_name("name"),
                "script": factory.make_string(),
                "parameters": {"storage": {"type": "error"}},
            }
        )
        self.assertFalse(form.is_valid())
        self.assertCountEqual([], VersionedTextFile.objects.all())

    def test_errors_on_reserved_name(self):
        form = ScriptForm(
            data={"name": "none", "script": factory.make_script_content()}
        )
        self.assertFalse(form.is_valid())
        self.assertEqual({"name": ['"none" is a reserved name.']}, form.errors)

    def test_errors_on_digit_name(self):
        form = ScriptForm(
            data={
                "name": str(random.randint(0, 1000)),
                "script": factory.make_script_content(),
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual({"name": ["Cannot be a number."]}, form.errors)

    def test_errors_on_whitespace_in_name(self):
        name = factory.make_name("with space")
        form = ScriptForm(
            data={
                "name": name,
                "script": factory.make_script_content(),
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "name": [
                    "Name '%s' contains disallowed characters, e.g. space or quotes."
                    % name
                ]
            },
            form.errors,
        )

    def test_errors_on_quotes_in_name(self):
        name = factory.make_name("l'horreur")
        form = ScriptForm(
            data={
                "name": name,
                "script": factory.make_script_content(),
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "name": [
                    "Name '%s' contains disallowed characters, e.g. space or quotes."
                    % name
                ]
            },
            form.errors,
        )

    def test_type_aliased_to_script_type(self):
        script_type = factory.pick_choice(SCRIPT_TYPE_CHOICES)
        form = ScriptForm(
            data={
                "name": factory.make_name("name"),
                "script": factory.make_script_content(),
                "type": script_type,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()
        self.assertEqual(script_type, script.script_type)

    def test_loads_yaml_embedded_attributes(self):
        embedded_yaml = {
            "name": factory.make_name("name"),
            "title": factory.make_name("title"),
            "description": factory.make_name("description"),
            "tags": [factory.make_name("tag") for _ in range(3)],
            "script_type": factory.pick_choice(SCRIPT_TYPE_CHOICES),
            "hardware_type": factory.pick_choice(HARDWARE_TYPE_CHOICES),
            "parallel": factory.pick_choice(SCRIPT_PARALLEL_CHOICES),
            "results": ["write_speed"],
            "parameters": [{"type": "storage"}, {"type": "runtime"}],
            "packages": {"apt": [factory.make_name("package")]},
            "timeout": random.randint(0, 1000),
            "destructive": factory.pick_bool(),
            "may_reboot": factory.pick_bool(),
        }
        if embedded_yaml["script_type"] == SCRIPT_TYPE.COMMISSIONING:
            embedded_yaml["for_hardware"] = [
                "modalias:%s" % factory.make_name("mod_alias"),
                "pci:%04X:%04x"
                % (random.randint(0, 9999), random.randint(0, 9999)),
                "usb:%04X:%04x"
                % (random.randint(0, 9999), random.randint(0, 9999)),
                "system_vendor:%s" % factory.make_name("system_name"),
                "system_product:%s" % factory.make_name("system_product"),
                "system_version:%s" % factory.make_name("system_version"),
                "mainboard_vendor:%s" % factory.make_name("mobo_vendor"),
                "mainboard_product:%s" % factory.make_name("mobo_product"),
            ]
            embedded_yaml["recommission"] = factory.pick_bool()
        script_content = factory.make_script_content(embedded_yaml)
        form = ScriptForm(data={"script": script_content})
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()
        self.assertEqual(embedded_yaml["name"], script.name)
        self.assertEqual(embedded_yaml["title"], script.title)
        self.assertEqual(embedded_yaml["description"], script.description)
        for tag in embedded_yaml["tags"]:
            self.assertIn(tag, script.tags)
        self.assertEqual(embedded_yaml["script_type"], script.script_type)
        self.assertEqual(embedded_yaml["hardware_type"], script.hardware_type)
        self.assertEqual(embedded_yaml["parallel"], script.parallel)
        self.assertCountEqual(embedded_yaml["results"], script.results)
        self.assertCountEqual(embedded_yaml["parameters"], script.parameters)
        self.assertEqual(embedded_yaml["packages"], script.packages)
        self.assertEqual(
            timedelta(0, embedded_yaml["timeout"]), script.timeout
        )
        self.assertEqual(embedded_yaml["destructive"], script.destructive)
        self.assertEqual(embedded_yaml["may_reboot"], script.may_reboot)
        if embedded_yaml["script_type"] == SCRIPT_TYPE.COMMISSIONING:
            self.assertCountEqual(
                embedded_yaml["for_hardware"], script.for_hardware
            )
            self.assertEqual(
                embedded_yaml["recommission"], script.recommission
            )
        else:
            self.assertCountEqual([], script.for_hardware)
            self.assertFalse(script.recommission)
        self.assertFalse(script.default)
        self.assertEqual(script_content, script.script.data)

    def test_only_loads_when_script_updated(self):
        script = factory.make_Script(
            script=factory.make_script_content(
                {"name": factory.make_name("name")}
            )
        )
        name = factory.make_name("name")
        form = ScriptForm(instance=script, data={"name": name})
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()
        self.assertEqual(name, script.name)

    def test_user_option_unable_to_over_yaml_value(self):
        name = factory.make_name("name")
        form = ScriptForm(
            data={
                "name": name,
                "script": factory.make_script_content(
                    {"name": factory.make_name("name")}
                ),
            }
        )
        self.assertFalse(form.is_valid())

    def test_user_option_can_match_yaml_value(self):
        name = factory.make_name("name")
        script_type = factory.pick_choice(SCRIPT_TYPE_CHOICES)
        form = ScriptForm(
            data={
                "name": name,
                "script_type": script_type,
                "script": factory.make_script_content(
                    {"name": name, "script_type": script_type}
                ),
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_errors_on_bad_yaml(self):
        form = ScriptForm(
            data={
                "name": factory.make_name("name"),
                "script": factory.make_script_content("# {"),
            }
        )
        self.assertFalse(form.is_valid())

    def test_errors_on_missing_comment_on_yaml(self):
        form = ScriptForm(
            data={
                "name": factory.make_name("name"),
                "script": factory.make_script_content(
                    factory.make_name("bad_yaml")
                ),
            }
        )
        self.assertFalse(form.is_valid())

    def test_ignores_other_version_yaml(self):
        script = factory.make_Script()
        name = script.name
        form = ScriptForm(
            instance=script,
            data={
                "script": factory.make_script_content(
                    {"name": factory.make_name("name")}, version="9.0"
                )
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()
        self.assertEqual(name, script.name)

    def tests_yaml_tags_can_be_string(self):
        tags = [factory.make_name("tag") for _ in range(3)]
        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {"name": factory.make_name("name"), "tags": ",".join(tags)}
                )
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()
        for tag in tags:
            self.assertIn(tag, script.tags)

    def tests_yaml_tags_can_be_list_of_strings(self):
        tags = [factory.make_name("tag") for _ in range(3)]
        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {"name": factory.make_name("name"), "tags": tags}
                )
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()
        for tag in tags:
            self.assertIn(tag, script.tags)

    def tests_yaml_tags_errors_on_non_list_or_string(self):
        form = ScriptForm(
            data={
                "name": factory.make_name("name"),
                "script": factory.make_script_content({"tags": {}}),
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "tags": [
                    "Embedded tags must be a string of comma seperated values, "
                    "or a list of strings."
                ]
            },
            form.errors,
        )
        self.assertCountEqual([], VersionedTextFile.objects.all())

    def tests_yaml_tags_errors_on_list_of_non_string(self):
        form = ScriptForm(
            data={
                "name": factory.make_name("name"),
                "script": factory.make_script_content(
                    {"tags": [{} for _ in range(3)]}
                ),
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "tags": [
                    "Embedded tags must be a string of comma seperated values, "
                    "or a list of strings."
                ]
            },
            form.errors,
        )
        self.assertCountEqual([], VersionedTextFile.objects.all())

    def test_packages_validate(self):
        apt_pkgs = [factory.make_name("apt_pkg") for _ in range(3)]
        snap_pkg = {
            "name": factory.make_name("snap_pkg"),
            "channel": random.choice(["stable", "edge", "beta", "candidate"]),
            "mode": random.choice(["classic", "dev", "jail"]),
        }
        url = factory.make_url()
        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {
                        "name": factory.make_name("name"),
                        "packages": {
                            "apt": apt_pkgs,
                            "snap": snap_pkg,
                            "url": url,
                        },
                    }
                )
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()
        self.assertEqual(
            {"apt": apt_pkgs, "snap": [snap_pkg], "url": [url]},
            script.packages,
        )

    def test_converts_single_package_to_list(self):
        apt_pkg = factory.make_name("apt_pkg")
        snap_pkg = factory.make_name("snap_pkg")
        url = factory.make_url()
        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {
                        "name": factory.make_name("name"),
                        "packages": {
                            "apt": apt_pkg,
                            "snap": snap_pkg,
                            "url": url,
                        },
                    }
                )
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()
        self.assertEqual(
            {"apt": [apt_pkg], "snap": [snap_pkg], "url": [url]},
            script.packages,
        )

    def test_errors_when_apt_package_isnt_string(self):
        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {
                        "name": factory.make_name("name"),
                        "packages": {"apt": {}},
                    }
                )
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {"packages": ["Each apt package must be a string."]}, form.errors
        )
        self.assertCountEqual([], VersionedTextFile.objects.all())

    def test_errors_when_url_package_isnt_string(self):
        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {
                        "name": factory.make_name("name"),
                        "packages": {"url": {}},
                    }
                )
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {"packages": ["Each url package must be a string."]}, form.errors
        )
        self.assertCountEqual([], VersionedTextFile.objects.all())

    def test_snap_package_dict_requires_name(self):
        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {
                        "name": factory.make_name("name"),
                        "packages": {"snap": {}},
                    }
                )
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {"packages": ["Snap package name must be defined."]}, form.errors
        )
        self.assertCountEqual([], VersionedTextFile.objects.all())

    def test_snap_package_channel_must_be_valid(self):
        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {
                        "name": factory.make_name("name"),
                        "packages": {
                            "snap": {
                                "name": factory.make_name("script_name"),
                                "channel": factory.make_name("channel"),
                            }
                        },
                    }
                )
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "packages": [
                    "Snap channel must be stable, edge, beta, or candidate."
                ]
            },
            form.errors,
        )
        self.assertCountEqual([], VersionedTextFile.objects.all())

    def test_snap_package_mode_must_be_valid(self):
        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {
                        "name": factory.make_name("name"),
                        "packages": {
                            "snap": {
                                "name": factory.make_name("script_name"),
                                "mode": factory.make_name("mode"),
                            }
                        },
                    }
                )
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {"packages": ["Snap mode must be classic, dev, or jail."]},
            form.errors,
        )
        self.assertCountEqual([], VersionedTextFile.objects.all())

    def test_snap_package_list_must_be_strings(self):
        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {
                        "name": factory.make_name("name"),
                        "packages": {"snap": [[]]},
                    }
                )
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {"packages": ["Snap package must be a string."]}, form.errors
        )
        self.assertCountEqual([], VersionedTextFile.objects.all())

    def test_allows_list_of_results(self):
        results = [factory.make_name("result") for _ in range(3)]
        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {"name": factory.make_name("name"), "results": results}
                )
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()
        self.assertCountEqual(results, script.results)

    def test_allows_dictionary_of_results(self):
        results = {
            factory.make_name("result_key"): {
                "title": factory.make_name("result_title") for _ in range(3)
            }
            for _ in range(3)
        }
        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {"name": factory.make_name("name"), "results": results}
                )
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()
        self.assertEqual(results, script.results)

    def test_results_list_must_be_strings(self):
        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {"name": factory.make_name("name"), "results": [None]}
                )
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {"results": ["Each result in a result list must be a string."]},
            form.errors,
        )
        self.assertCountEqual([], VersionedTextFile.objects.all())

    def test_allows_dict_of_results(self):
        results = {
            factory.make_name("result"): {
                "title": factory.make_name("result_title"),
                "description": factory.make_name("description"),
            }
            for _ in range(3)
        }
        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {"name": factory.make_name("name"), "results": results}
                )
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()
        self.assertEqual(results, script.results)

    def test_dict_of_results_requires_title(self):
        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {
                        "name": factory.make_name("name"),
                        "results": {factory.make_name("result"): {}},
                    }
                )
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {"results": ["title must be included in a result dictionary."]},
            form.errors,
        )
        self.assertCountEqual([], VersionedTextFile.objects.all())

    def test_title_description_of_result_must_be_strings(self):
        results = {
            factory.make_name("result"): {"title": None, "description": None}
        }
        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {"name": factory.make_name("name"), "results": results}
                )
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "results": [
                    "title must be a string.",
                    "description must be a string.",
                ]
            },
            form.errors,
        )
        self.assertCountEqual([], VersionedTextFile.objects.all())

    def test_results_must_be_list_or_dict(self):
        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {"name": factory.make_name("name"), "results": None}
                )
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "results": [
                    "results must be a list of strings or a dictionary of "
                    "dictionaries."
                ]
            },
            form.errors,
        )
        self.assertCountEqual([], VersionedTextFile.objects.all())

    def test_errors_when_hardware_not_a_list(self):
        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {"name": factory.make_name("name"), "for_hardware": {}}
                )
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {"for_hardware": ["Must be a list or string"]}, form.errors
        )
        self.assertCountEqual([], VersionedTextFile.objects.all())

    def test_errors_when_hardware_invalid(self):
        hw_id = factory.make_name("hw_id")
        form = ScriptForm(
            data={
                "script": factory.make_script_content(
                    {"name": factory.make_name("name"), "for_hardware": hw_id}
                )
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "for_hardware": [
                    "Hardware identifier '%s' must be a modalias, PCI ID, "
                    "USB ID, system vendor, system product, system version, "
                    "mainboard vendor, or mainboard product." % hw_id
                ]
            },
            form.errors,
        )
        self.assertCountEqual([], VersionedTextFile.objects.all())


class TestCommissioningScriptForm(MAASServerTestCase):
    def test_creates_commissioning_script_from_embedded_yaml_name(self):
        request = HttpRequest()
        request.user = factory.make_User()
        name = factory.make_name("name")
        content = factory.make_script_content({"name": name})
        uploaded_file = SimpleUploadedFile(
            content=content.encode("ascii"), name=factory.make_name("filename")
        )
        form = CommissioningScriptForm(files={"content": uploaded_file})
        self.assertTrue(form.is_valid(), form._errors)
        form.save(request)
        new_script = Script.objects.get(name=name)
        self.assertEqual(SCRIPT_TYPE.COMMISSIONING, new_script.script_type)
        self.assertEqual(content, new_script.script.data)

    def test_creates_commissioning_script_from_filename(self):
        request = HttpRequest()
        request.user = factory.make_User()
        content = factory.make_script_content()
        name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(
            content=content.encode("ascii"), name=name
        )
        form = CommissioningScriptForm(files={"content": uploaded_file})
        self.assertTrue(form.is_valid(), form._errors)
        form.save(request)
        new_script = Script.objects.get(name=name)
        self.assertEqual(SCRIPT_TYPE.COMMISSIONING, new_script.script_type)
        self.assertEqual(content, new_script.script.data)

    def test_updates_commissioning_script(self):
        request = HttpRequest()
        request.user = factory.make_User()
        script = factory.make_Script(script_type=SCRIPT_TYPE.COMMISSIONING)
        content = factory.make_script_content()
        uploaded_file = SimpleUploadedFile(
            content=content.encode("ascii"), name=script.name
        )
        form = CommissioningScriptForm(files={"content": uploaded_file})
        self.assertTrue(form.is_valid(), form._errors)
        form.save(request)
        new_script = Script.objects.get(name=script.name)
        self.assertEqual(SCRIPT_TYPE.COMMISSIONING, new_script.script_type)
        self.assertEqual(content, new_script.script.data)

    def test_creates_audit_event(self):
        request = HttpRequest()
        request.user = factory.make_User()
        content = factory.make_script_content()
        name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(
            content=content.encode("ascii"), name=name
        )
        form = CommissioningScriptForm(files={"content": uploaded_file})
        self.assertTrue(form.is_valid(), form._errors)
        form.save(request)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(event.description, "Saved script '%s'." % name)

    def test_propagates_script_form_errors(self):
        # Regression test for LP:1712422
        uploaded_file = SimpleUploadedFile(
            content=factory.make_script_content().encode("ascii"), name="none"
        )
        form = CommissioningScriptForm(files={"content": uploaded_file})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {"content": ['name: "none" is a reserved name.']}, form.errors
        )

    def test_not_valid_when_empty(self):
        # Regression test for LP:1712423
        form = CommissioningScriptForm()
        self.assertFalse(form.is_valid())


class TestTestingScriptForm(MAASServerTestCase):
    def test_creates_test_script_from_embedded_yaml_name(self):
        request = HttpRequest()
        request.user = factory.make_User()
        name = factory.make_name("name")
        content = factory.make_script_content({"name": name})
        uploaded_file = SimpleUploadedFile(
            content=content.encode("ascii"), name=factory.make_name("filename")
        )
        form = TestingScriptForm(files={"content": uploaded_file})
        self.assertTrue(form.is_valid(), form._errors)
        form.save(request)
        new_script = Script.objects.get(name=name)
        self.assertEqual(SCRIPT_TYPE.TESTING, new_script.script_type)
        self.assertEqual(content, new_script.script.data)

    def test_creates_test_script_from_filename(self):
        request = HttpRequest()
        request.user = factory.make_User()
        content = factory.make_script_content()
        name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(
            content=content.encode("ascii"), name=name
        )
        form = TestingScriptForm(files={"content": uploaded_file})
        self.assertTrue(form.is_valid(), form._errors)
        form.save(request)
        new_script = Script.objects.get(name=name)
        self.assertEqual(SCRIPT_TYPE.TESTING, new_script.script_type)
        self.assertEqual(content, new_script.script.data)

    def test_updates_test_script(self):
        request = HttpRequest()
        request.user = factory.make_User()
        script = factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
        content = factory.make_script_content()
        uploaded_file = SimpleUploadedFile(
            content=content.encode("ascii"), name=script.name
        )
        form = TestingScriptForm(files={"content": uploaded_file})
        self.assertTrue(form.is_valid(), form._errors)
        form.save(request)
        new_script = Script.objects.get(name=script.name)
        self.assertEqual(SCRIPT_TYPE.TESTING, new_script.script_type)
        self.assertEqual(content, new_script.script.data)

    def test_creates_audit_event(self):
        request = HttpRequest()
        request.user = factory.make_User()
        content = factory.make_script_content()
        name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(
            content=content.encode("ascii"), name=name
        )
        form = TestingScriptForm(files={"content": uploaded_file})
        self.assertTrue(form.is_valid(), form._errors)
        form.save(request)
        new_script = Script.objects.get(name=name)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description, "Saved script '%s'." % new_script.name
        )

    def test_propagates_script_form_errors(self):
        # Regression test for LP:1712422
        uploaded_file = SimpleUploadedFile(
            content=factory.make_script_content().encode("ascii"), name="none"
        )
        form = TestingScriptForm(files={"content": uploaded_file})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {"content": ['name: "none" is a reserved name.']}, form.errors
        )

    def test_not_valid_when_empty(self):
        # Regression test for LP:1712423
        form = TestingScriptForm()
        self.assertFalse(form.is_valid())
