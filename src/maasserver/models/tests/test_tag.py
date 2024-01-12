# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import ANY

from django.core.exceptions import ValidationError
from twisted.internet import reactor

from maasserver import populate_tags
from maasserver.models import tag as tag_module
from maasserver.models.tag import Tag
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.threads import deferToDatabase


class TagTest(MAASServerTestCase):
    def test_factory_make_Tag(self):
        """The generated system_id looks good."""
        tag = factory.make_Tag("tag-name", "//node[@id=display]")
        self.assertEqual("tag-name", tag.name)
        self.assertEqual("//node[@id=display]", tag.definition)
        self.assertEqual("", tag.comment)
        self.assertEqual(tag.kernel_opts, "")
        self.assertIsNotNone(tag.updated)
        self.assertIsNotNone(tag.created)

    def test_factory_make_Tag_with_hardware_details(self):
        tag = factory.make_Tag("a-tag", "true", kernel_opts="console=ttyS0")
        self.assertEqual("a-tag", tag.name)
        self.assertEqual("true", tag.definition)
        self.assertEqual("", tag.comment)
        self.assertEqual("console=ttyS0", tag.kernel_opts)
        self.assertIsNotNone(tag.updated)
        self.assertIsNotNone(tag.created)

    def test_add_tag_to_node(self):
        node = factory.make_Node()
        tag = factory.make_Tag()
        tag.save()
        node.tags.add(tag)
        self.assertEqual([tag.id], [t.id for t in node.tags.all()])
        self.assertEqual([node.id], [n.id for n in tag.node_set.all()])

    def test_valid_tag_names(self):
        for valid in ["valid-dash", "under_score", "long" * 50]:
            tag = factory.make_Tag(name=valid)
            self.assertEqual(valid, tag.name)

    def test_validate_traps_invalid_tag_name(self):
        for invalid in [
            "invalid:name",
            "no spaces",
            "no\ttabs",
            "no&ampersand",
            "no!shouting",
            "",
            "too-long" * 33,
            "\xb5",
        ]:
            self.assertRaises(ValidationError, factory.make_Tag, name=invalid)

    def test_validate_traps_invalid_tag_definitions(self):
        self.assertRaises(
            ValidationError, factory.make_Tag, definition="invalid::definition"
        )

    def test_applies_tags_to_nodes_on_save(self):
        populate_nodes = self.patch_autospec(Tag, "populate_nodes")
        tag = Tag(name=factory.make_name("tag"), definition="//node/child")
        populate_nodes.assert_not_called()
        tag.save()
        populate_nodes.assert_called_once_with(tag)

    def test_will_not_save_invalid_xpath(self):
        tag = factory.make_Tag(definition="//node/foo")
        tag.definition = "invalid::tag"
        self.assertRaises(ValidationError, tag.save)


class TestTagIsDefined(MAASServerTestCase):
    """Tests for the `Tag.is_defined` property."""

    scenarios = (
        ("empty", dict(definition="", expected=False)),
        ("whitespace", dict(definition="   \t\n ", expected=False)),
        ("defined", dict(definition="//node", expected=True)),
    )

    def test_is_defined(self):
        tag = Tag(name="tag", definition=self.definition)
        self.assertIs(self.expected, tag.is_defined)


class TestTagPopulateNodesLater(MAASServerTestCase):
    def test_populates_if_tag_is_defined(self):
        post_commit_do = self.patch(tag_module, "post_commit_do")

        tag = Tag(name=factory.make_name("tag"), definition="//foo")
        tag.save(populate=False)

        self.assertTrue(tag.is_defined)
        post_commit_do.assert_not_called()
        tag._populate_nodes_later()
        post_commit_do.assert_called_once_with(
            reactor.callLater,
            0,
            deferToDatabase,
            populate_tags.populate_tags,
            tag,
        )

    def test_does_nothing_if_tag_is_not_defined(self):
        post_commit_do = self.patch(tag_module, "post_commit_do")

        tag = Tag(name=factory.make_name("tag"), definition="")
        tag.save(populate=False)

        self.assertFalse(tag.is_defined)
        post_commit_do.assert_not_called()
        tag._populate_nodes_later()
        post_commit_do.assert_not_called()

    def test_does_not_clear_node_set_before_populating(self):
        post_commit_do = self.patch(tag_module, "post_commit_do")

        tag = Tag(name=factory.make_name("tag"), definition="//foo")
        tag.save(populate=False)

        nodes = [factory.make_Node() for _ in range(3)]
        tag.node_set.add(*nodes)
        tag._populate_nodes_later()
        self.assertCountEqual(nodes, tag.node_set.all())
        post_commit_do.assert_called_once_with(
            reactor.callLater,
            0,
            deferToDatabase,
            populate_tags.populate_tags,
            tag,
        )

    def test_later_is_the_default(self):
        tag = Tag(name=factory.make_name("tag"))
        self.patch(tag, "_populate_nodes_later")
        tag._populate_nodes_later.assert_not_called()
        tag.save()
        tag._populate_nodes_later.assert_called_once_with()


class TestTagPopulateNodesNow(MAASServerTestCase):
    def test_populates_if_tag_is_defined(self):
        populate_multiple = self.patch_autospec(
            populate_tags, "populate_tag_for_multiple_nodes"
        )

        tag = Tag(name=factory.make_name("tag"), definition="//foo")
        tag.save(populate=False)

        self.assertTrue(tag.is_defined)
        populate_multiple.assert_not_called()
        tag._populate_nodes_now()
        populate_multiple.assert_called_once_with(tag, ANY)

    def test_does_nothing_if_tag_is_not_defined(self):
        populate_multiple = self.patch_autospec(
            populate_tags, "populate_tag_for_multiple_nodes"
        )

        tag = Tag(name=factory.make_name("tag"), definition="")
        tag.save(populate=False)

        self.assertFalse(tag.is_defined)
        populate_multiple.assert_not_called()
        tag._populate_nodes_now()
        populate_multiple.assert_not_called()

    def test_clears_node_set_before_populating(self):
        tag = Tag(name=factory.make_name("tag"), definition="//foo")
        tag.save(populate=False)

        nodes = [factory.make_Node() for _ in range(3)]
        tag.node_set.add(*nodes)
        tag._populate_nodes_now()
        self.assertCountEqual([], tag.node_set.all())
