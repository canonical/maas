# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Script form."""

__all__ = []

from datetime import timedelta
import random

from maasserver.forms.script import ScriptForm
from maasserver.models import VersionedTextFile
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from metadataserver.enum import (
    SCRIPT_TYPE,
    SCRIPT_TYPE_CHOICES,
)


class TestScriptForm(MAASServerTestCase):

    def test__create_requires_name(self):
        form = ScriptForm(data={'script': factory.make_string()})
        self.assertFalse(form.is_valid())
        self.assertItemsEqual([], VersionedTextFile.objects.all())

    def test__create_requires_script(self):
        form = ScriptForm(data={'name': factory.make_string()})
        self.assertFalse(form.is_valid())
        self.assertItemsEqual([], VersionedTextFile.objects.all())

    def test__create_with_default_values(self):
        name = factory.make_name('name')
        script_content = factory.make_string()

        form = ScriptForm(data={'name': name, 'script': script_content})
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()

        self.assertEquals(name, script.name)
        self.assertEquals('', script.description)
        self.assertEquals([], script.tags)
        self.assertEquals(SCRIPT_TYPE.TESTING, script.script_type)
        self.assertEquals(timedelta(0), script.timeout)
        self.assertFalse(script.destructive)
        self.assertEquals(script_content, script.script.data)
        self.assertFalse(script.default)

    def test__create_with_defined_values(self):
        name = factory.make_name('name')
        description = factory.make_name('description')
        tags = [factory.make_name('tag') for _ in range(3)]
        script_type = factory.pick_choice(SCRIPT_TYPE_CHOICES)
        timeout = random.randint(0, 1000)
        destructive = factory.pick_bool()
        script_content = factory.make_string()
        comment = factory.make_name('comment')

        form = ScriptForm(data={
            'name': name,
            'description': description,
            'tags': ','.join(tags),
            'script_type': script_type,
            'timeout': str(timeout),
            'destructive': destructive,
            'script': script_content,
            'comment': comment,
        })
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()

        self.assertEquals(name, script.name)
        self.assertEquals(description, script.description)
        self.assertEquals(tags, script.tags)
        self.assertEquals(script_type, script.script_type)
        self.assertEquals(timedelta(0, timeout), script.timeout)
        self.assertEquals(destructive, script.destructive)
        self.assertEquals(script_content, script.script.data)
        self.assertEquals(comment, script.script.comment)
        self.assertFalse(script.default)

    def test__create_setting_default_has_no_effect(self):
        form = ScriptForm(data={
            'name': factory.make_name('name'),
            'script': factory.make_string(),
            'default': True,
        })
        self.assertTrue(form.is_valid())
        script = form.save()
        self.assertFalse(script.default)

    def test__update(self):
        script = factory.make_Script()
        name = factory.make_name('name')
        description = factory.make_name('description')
        tags = [factory.make_name('tag') for _ in range(3)]
        script_type = factory.pick_choice(SCRIPT_TYPE_CHOICES)
        timeout = random.randint(0, 1000)
        destructive = factory.pick_bool()
        script_content = factory.make_string()
        comment = factory.make_name('comment')
        orig_script_content = script.script.data

        form = ScriptForm(data={
            'name': name,
            'description': description,
            'tags': ','.join(tags),
            'script_type': script_type,
            'timeout': str(timeout),
            'destructive': destructive,
            'script': script_content,
            'comment': comment,
        }, instance=script)
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()

        self.assertEquals(name, script.name)
        self.assertEquals(description, script.description)
        self.assertEquals(tags, script.tags)
        self.assertEquals(script_type, script.script_type)
        self.assertEquals(timedelta(0, timeout), script.timeout)
        self.assertEquals(destructive, script.destructive)
        self.assertEquals(script_content, script.script.data)
        self.assertEquals(comment, script.script.comment)
        self.assertEquals(
            orig_script_content, script.script.previous_version.data)
        self.assertEquals(None, script.script.previous_version.comment)
        self.assertFalse(script.default)

    def test__update_no_fields_mandatory(self):
        script = factory.make_Script()
        form = ScriptForm(data={}, instance=script)
        self.assertTrue(form.is_valid(), form.errors)

    def test__update_setting_default_has_no_effect(self):
        script = factory.make_Script(default=True)
        form = ScriptForm(data={
            'default': False,
        }, instance=script)
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()
        self.assertTrue(script.default)

    def test__update_prohibits_most_field_updates_on_default_script(self):
        script = factory.make_Script(default=True)
        for name, field in ScriptForm.base_fields.items():
            if name in ['tags', 'timeout']:
                continue
            elif name == 'script_type':
                value = factory.pick_choice(SCRIPT_TYPE_CHOICES)
            elif name == 'destructive':
                value = factory.pick_bool()
            else:
                value = factory.make_string()
            form = ScriptForm(data={name: value}, instance=script)
            self.assertFalse(form.is_valid())
            self.assertEquals(1, VersionedTextFile.objects.all().count())

    def test__update_allows_editing_tag_and_timeout_on_default_script(self):
        script = factory.make_Script(default=True)
        tags = [factory.make_name('tag') for _ in range(3)]
        timeout = random.randint(0, 1000)

        form = ScriptForm(data={
            'tags': ','.join(tags),
            'timeout': str(timeout),
            }, instance=script)
        self.assertTrue(form.is_valid())
        script = form.save()

        self.assertEquals(tags, script.tags)
        self.assertEquals(timedelta(0, timeout), script.timeout)

    def test__update_requires_script_with_comment(self):
        script = factory.make_Script()
        form = ScriptForm(data={
            'comment': factory.make_name('comment'),
        }, instance=script)
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'comment': [
                    '"comment" may only be used when specifying a "script" '
                    'as well.'
                ]
            }, form.errors)

    def test__can_use_script_type_name(self):
        script_type_name = random.choice([
            'test', 'testing',
            'commission', 'commissioning'])
        if 'test' in script_type_name:
            script_type_id = SCRIPT_TYPE.TESTING
        else:
            script_type_id = SCRIPT_TYPE.COMMISSIONING
        # Check that no new types have been added.
        self.assertEquals(2, len(SCRIPT_TYPE_CHOICES))

        form = ScriptForm(data={
            'name': factory.make_name('name'),
            'script': factory.make_string(),
            'script_type': script_type_name,
        })
        self.assertTrue(form.is_valid(), form.errors)
        script = form.save()

        self.assertEquals(script_type_id, script.script_type)

    def test__errors_on_invalid_script_type(self):
        form = ScriptForm(data={
            'name': factory.make_name('name'),
            'script': factory.make_string(),
            'script_type': factory.make_string(),
        })
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'script_type': [
                    'Must be 2, test, testing, 0, commission, or '
                    'commissioning.']
            }, form.errors)
        self.assertItemsEqual([], VersionedTextFile.objects.all())

    def test__errors_on_reserved_name(self):
        form = ScriptForm(data={
            'name': 'none',
            'script': factory.make_string(),
        })
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {'name': ['"none" is a reserved name.']}, form.errors)
