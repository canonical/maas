# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.tag`"""


from maasserver.models.tag import Tag
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import dehydrate_datetime
from maasserver.websockets.handlers.tag import TagHandler


class TestTagHandler(MAASServerTestCase):
    def dehydrate_tag(self, tag):
        data = {
            "id": tag.id,
            "name": tag.name,
            "definition": tag.definition,
            "comment": tag.comment,
            "kernel_opts": tag.kernel_opts,
            "updated": dehydrate_datetime(tag.updated),
            "created": dehydrate_datetime(tag.created),
        }
        return data

    def test_get(self):
        user = factory.make_User()
        handler = TagHandler(user, {}, None)
        tag = factory.make_Tag()
        self.assertEqual(self.dehydrate_tag(tag), handler.get({"id": tag.id}))

    def test_list(self):
        user = factory.make_User()
        handler = TagHandler(user, {}, None)
        factory.make_Tag()
        expected_tags = [self.dehydrate_tag(tag) for tag in Tag.objects.all()]
        self.assertItemsEqual(expected_tags, handler.list({}))
