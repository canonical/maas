# Copyright 2017-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from datetime import timedelta
import random

from django.core.exceptions import ValidationError

from maasserver.models import Script, VersionedTextFile
from maasserver.models.script import (
    translate_hardware_type,
    translate_script_parallel,
    translate_script_type,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from metadataserver.enum import (
    HARDWARE_TYPE,
    HARDWARE_TYPE_CHOICES,
    SCRIPT_PARALLEL,
    SCRIPT_TYPE,
)


class TestTranslateScriptType(MAASServerTestCase):
    """Test translate_script_type."""

    scenarios = [
        (
            "numeric testing",
            {
                "value": SCRIPT_TYPE.TESTING,
                "return_value": SCRIPT_TYPE.TESTING,
            },
        ),
        (
            "numeric commissioning",
            {
                "value": SCRIPT_TYPE.COMMISSIONING,
                "return_value": SCRIPT_TYPE.COMMISSIONING,
            },
        ),
        (
            "numeric string testing",
            {
                "value": str(SCRIPT_TYPE.TESTING),
                "return_value": SCRIPT_TYPE.TESTING,
            },
        ),
        (
            "numeric string commissioning",
            {
                "value": str(SCRIPT_TYPE.COMMISSIONING),
                "return_value": SCRIPT_TYPE.COMMISSIONING,
            },
        ),
        (
            "invalid id",
            {
                "value": random.randint(100, 1000),
                "exception": "Invalid script type numeric value.",
            },
        ),
        ("test", {"value": "test", "return_value": SCRIPT_TYPE.TESTING}),
        ("testing", {"value": "testing", "return_value": SCRIPT_TYPE.TESTING}),
        (
            "commission",
            {"value": "commission", "return_value": SCRIPT_TYPE.COMMISSIONING},
        ),
        (
            "commissioning",
            {
                "value": "commissioning",
                "return_value": SCRIPT_TYPE.COMMISSIONING,
            },
        ),
        (
            "invalid value",
            {
                "value": factory.make_name("value"),
                "exception": "Script type must be testing or commissioning",
            },
        ),
    ]

    def test_translate_script_type(self):
        if hasattr(self, "exception"):
            with self.assertRaisesRegex(ValidationError, self.exception):
                translate_script_type(self.value)
        else:
            self.assertEqual(
                self.return_value, translate_script_type(self.value)
            )


class TestTranslateHardwareType(MAASServerTestCase):
    """Test translate_hardware_type."""

    scenarios = [
        (
            "numeric node",
            {"value": HARDWARE_TYPE.NODE, "return_value": HARDWARE_TYPE.NODE},
        ),
        (
            "numeric cpu",
            {"value": HARDWARE_TYPE.CPU, "return_value": HARDWARE_TYPE.CPU},
        ),
        (
            "numeric memory",
            {
                "value": HARDWARE_TYPE.MEMORY,
                "return_value": HARDWARE_TYPE.MEMORY,
            },
        ),
        (
            "numeric storage",
            {
                "value": HARDWARE_TYPE.STORAGE,
                "return_value": HARDWARE_TYPE.STORAGE,
            },
        ),
        (
            "numeric string node",
            {
                "value": str(HARDWARE_TYPE.NODE),
                "return_value": HARDWARE_TYPE.NODE,
            },
        ),
        (
            "numeric string cpu",
            {
                "value": str(HARDWARE_TYPE.CPU),
                "return_value": HARDWARE_TYPE.CPU,
            },
        ),
        (
            "numeric string memory",
            {
                "value": str(HARDWARE_TYPE.MEMORY),
                "return_value": HARDWARE_TYPE.MEMORY,
            },
        ),
        (
            "numeric string storage",
            {
                "value": str(HARDWARE_TYPE.STORAGE),
                "return_value": HARDWARE_TYPE.STORAGE,
            },
        ),
        (
            "numeric string gpu",
            {
                "value": str(HARDWARE_TYPE.GPU),
                "return_value": HARDWARE_TYPE.GPU,
            },
        ),
        (
            "invalid id",
            {
                "value": random.randint(100, 1000),
                "exception": "Invalid hardware type numeric value.",
            },
        ),
        ("node", {"value": "node", "return_value": HARDWARE_TYPE.NODE}),
        ("machine", {"value": "machine", "return_value": HARDWARE_TYPE.NODE}),
        (
            "controller",
            {"value": "controller", "return_value": HARDWARE_TYPE.NODE},
        ),
        ("other", {"value": "other", "return_value": HARDWARE_TYPE.NODE}),
        ("generic", {"value": "generic", "return_value": HARDWARE_TYPE.NODE}),
        ("cpu", {"value": "cpu", "return_value": HARDWARE_TYPE.CPU}),
        (
            "processor",
            {"value": "processor", "return_value": HARDWARE_TYPE.CPU},
        ),
        ("memory", {"value": "memory", "return_value": HARDWARE_TYPE.MEMORY}),
        ("ram", {"value": "ram", "return_value": HARDWARE_TYPE.MEMORY}),
        (
            "storage",
            {"value": "storage", "return_value": HARDWARE_TYPE.STORAGE},
        ),
        ("disk", {"value": "disk", "return_value": HARDWARE_TYPE.STORAGE}),
        ("ssd", {"value": "ssd", "return_value": HARDWARE_TYPE.STORAGE}),
        (
            "network",
            {"value": "network", "return_value": HARDWARE_TYPE.NETWORK},
        ),
        ("net", {"value": "net", "return_value": HARDWARE_TYPE.NETWORK}),
        (
            "interface",
            {"value": "interface", "return_value": HARDWARE_TYPE.NETWORK},
        ),
        (
            "gpu",
            {
                "value": "gpu",
                "return_value": HARDWARE_TYPE.GPU,
            },
        ),
        (
            "graphics",
            {
                "value": "graphics",
                "return_value": HARDWARE_TYPE.GPU,
            },
        ),
        (
            "invalid value",
            {
                "value": factory.make_name("value"),
                "exception": "Hardware type must be node, cpu, memory, storage, or gpu",
            },
        ),
    ]

    def test_translate_hardware_type(self):
        if hasattr(self, "exception"):
            with self.assertRaisesRegex(ValidationError, self.exception):
                translate_hardware_type(self.value)
        else:
            self.assertEqual(
                self.return_value, translate_hardware_type(self.value)
            )


class TestTranslateScriptParallel(MAASServerTestCase):
    """Test translate_script_parallel."""

    scenarios = [
        (
            "numeric disabled",
            {
                "value": SCRIPT_PARALLEL.DISABLED,
                "return_value": SCRIPT_PARALLEL.DISABLED,
            },
        ),
        (
            "numeric instance",
            {
                "value": SCRIPT_PARALLEL.INSTANCE,
                "return_value": SCRIPT_PARALLEL.INSTANCE,
            },
        ),
        (
            "numeric any",
            {
                "value": SCRIPT_PARALLEL.ANY,
                "return_value": SCRIPT_PARALLEL.ANY,
            },
        ),
        (
            "numeric string disabled",
            {
                "value": str(SCRIPT_PARALLEL.DISABLED),
                "return_value": SCRIPT_PARALLEL.DISABLED,
            },
        ),
        (
            "numeric string instance",
            {
                "value": str(SCRIPT_PARALLEL.INSTANCE),
                "return_value": SCRIPT_PARALLEL.INSTANCE,
            },
        ),
        (
            "numeric string any",
            {
                "value": str(SCRIPT_PARALLEL.ANY),
                "return_value": SCRIPT_PARALLEL.ANY,
            },
        ),
        (
            "invalid id",
            {
                "value": random.randint(100, 1000),
                "exception": "Invalid script parallel numeric value.",
            },
        ),
        (
            "disabled",
            {"value": "disabled", "return_value": SCRIPT_PARALLEL.DISABLED},
        ),
        ("none", {"value": "none", "return_value": SCRIPT_PARALLEL.DISABLED}),
        (
            "instance",
            {"value": "instance", "return_value": SCRIPT_PARALLEL.INSTANCE},
        ),
        ("name", {"value": "name", "return_value": SCRIPT_PARALLEL.INSTANCE}),
        ("any", {"value": "any", "return_value": SCRIPT_PARALLEL.ANY}),
        ("enabled", {"value": "enabled", "return_value": SCRIPT_PARALLEL.ANY}),
        (
            "invalid value",
            {
                "value": factory.make_name("value"),
                "exception": "Script parallel must be disabled, instance, or any.",
            },
        ),
    ]

    def test_translate_script_parallel(self):
        if hasattr(self, "exception"):
            with self.assertRaisesRegex(ValidationError, self.exception):
                translate_script_parallel(self.value)
        else:
            self.assertEqual(
                self.return_value, translate_script_parallel(self.value)
            )


class TestScriptManager(MAASServerTestCase):
    """Test the ScriptManager."""

    def test_create_accepts_str_for_script(self):
        name = factory.make_name("name")
        script_str = factory.make_string()
        comment = factory.make_name("comment")

        script = Script.objects.create(
            name=name, script=script_str, comment=comment
        )

        self.assertEqual(script_str, script.script.data)
        self.assertEqual(comment, script.script.comment)

    def test_create_accepts_ver_txt_file_for_script(self):
        name = factory.make_name("name")
        script_str = factory.make_string()
        ver_txt_file = VersionedTextFile.objects.create(data=script_str)

        script = Script.objects.create(name=name, script=ver_txt_file)

        self.assertEqual(script_str, script.script.data)
        self.assertEqual(ver_txt_file, script.script)

    def test_create_accepts_int_for_timeout(self):
        name = factory.make_name("name")
        script_str = factory.make_string()
        timeout = random.randint(0, 1000)

        script = Script.objects.create(
            name=name, script=script_str, timeout=timeout
        )

        self.assertEqual(timedelta(seconds=timeout), script.timeout)

    def test_create_accepts_timedelta_for_timeout(self):
        name = factory.make_name("name")
        script_str = factory.make_string()
        timeout = timedelta(random.randint(0, 1000))

        script = Script.objects.create(
            name=name, script=script_str, timeout=timeout
        )

        self.assertEqual(timeout, script.timeout)


class TestScript(MAASServerTestCase):
    """Test the Script model."""

    def test_add_tag(self):
        script = factory.make_Script()
        new_tag = factory.make_name("tag")
        script.add_tag(new_tag)
        script.save()
        self.assertIn(new_tag, reload_object(script).tags)

    def test_add_tag_only_adds_new_tag(self):
        script = factory.make_Script()
        new_tag = factory.make_name("tag")
        script.add_tag(new_tag)
        script.add_tag(new_tag)
        script.save()
        script = reload_object(script)
        self.assertEqual(len(set(script.tags)), len(script.tags))

    def test_remove_tag(self):
        script = factory.make_Script()
        removed_tag = random.choice(
            [tag for tag in script.tags if "tag" in tag]
        )
        script.remove_tag(removed_tag)
        script.save()
        self.assertNotIn(removed_tag, reload_object(script).tags)

    def test_remove_tags_ignores_nonexistant_tag(self):
        script = factory.make_Script()
        tag_count = len(script.tags)
        script.remove_tag(factory.make_name("tag"))
        script.save()
        self.assertEqual(tag_count, len(reload_object(script).tags))

    def test_destructive_true_adds_tag(self):
        script = factory.make_Script(destructive=False)
        script.destructive = True
        script.save()
        self.assertIn("destructive", reload_object(script).tags)

    def test_destructive_false_removes_tag(self):
        script = factory.make_Script(destructive=True)
        script.destructive = False
        script.save()
        self.assertNotIn("destructive", reload_object(script).tags)

    def test_adds_tags_for_hardware_types(self):
        script = factory.make_Script(tags=[], destructive=False)
        for hw_type, hw_type_label in HARDWARE_TYPE_CHOICES:
            script.hardware_type = hw_type
            script.save()
            self.assertEqual([hw_type_label.lower()], script.tags)
