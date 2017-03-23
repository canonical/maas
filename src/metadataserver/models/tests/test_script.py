# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = []

from datetime import timedelta
import random

from maasserver.models import VersionedTextFile
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from metadataserver.models import Script


class TestScriptManager(MAASServerTestCase):
    """Test the ScriptManager."""

    def test_create_accepts_str_for_script(self):
        name = factory.make_name('name')
        script_str = factory.make_string()
        comment = factory.make_name('comment')

        script = Script.objects.create(
            name=name, script=script_str, comment=comment)

        self.assertEquals(script_str, script.script.data)
        self.assertEquals(comment, script.script.comment)

    def test_create_accepts_ver_txt_file_for_script(self):
        name = factory.make_name('name')
        script_str = factory.make_string()
        ver_txt_file = VersionedTextFile.objects.create(data=script_str)

        script = Script.objects.create(name=name, script=ver_txt_file)

        self.assertEquals(script_str, script.script.data)
        self.assertEquals(ver_txt_file, script.script)

    def test_create_accepts_int_for_timeout(self):
        name = factory.make_name('name')
        script_str = factory.make_string()
        timeout = random.randint(0, 1000)

        script = Script.objects.create(
            name=name, script=script_str, timeout=timeout)

        self.assertEquals(timedelta(seconds=timeout), script.timeout)

    def test_create_accepts_timedelta_for_timeout(self):
        name = factory.make_name('name')
        script_str = factory.make_string()
        timeout = timedelta(random.randint(0, 1000))

        script = Script.objects.create(
            name=name, script=script_str, timeout=timeout)

        self.assertEquals(timeout, script.timeout)


class TestScript(MAASServerTestCase):
    """Test the Script model."""

    def test_add_tag(self):
        script = factory.make_Script()
        new_tag = factory.make_name('tag')
        script.add_tag(new_tag)
        script.save()
        self.assertIn(new_tag, reload_object(script).tags)

    def test_add_tag_only_adds_new_tag(self):
        script = factory.make_Script()
        new_tag = factory.make_name('tag')
        script.add_tag(new_tag)
        script.add_tag(new_tag)
        script.save()
        script = reload_object(script)
        self.assertEquals(len(set(script.tags)), len(script.tags))

    def test_remove_tag(self):
        script = factory.make_Script()
        removed_tag = random.choice(script.tags)
        script.remove_tag(removed_tag)
        script.save()
        self.assertNotIn(removed_tag, reload_object(script).tags)

    def test_remove_tags_ignores_nonexistant_tag(self):
        script = factory.make_Script()
        tag_count = len(script.tags)
        script.remove_tag(factory.make_name('tag'))
        script.save()
        self.assertEquals(tag_count, len(reload_object(script).tags))
