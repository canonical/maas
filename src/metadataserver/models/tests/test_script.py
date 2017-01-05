# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = []

import random

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


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
