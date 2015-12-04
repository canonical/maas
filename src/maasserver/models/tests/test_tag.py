# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver models."""

__all__ = []

from django.core.exceptions import ValidationError
from maasserver import populate_tags as populate_tags_module
from maasserver.models.tag import Tag
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith


class TagTest(MAASServerTestCase):

    def test_factory_make_Tag(self):
        """
        The generated system_id looks good.

        """
        tag = factory.make_Tag('tag-name', '//node[@id=display]')
        self.assertEqual('tag-name', tag.name)
        self.assertEqual('//node[@id=display]', tag.definition)
        self.assertEqual('', tag.comment)
        self.assertIs(None, tag.kernel_opts)
        self.assertIsNot(None, tag.updated)
        self.assertIsNot(None, tag.created)

    def test_factory_make_Tag_with_hardware_details(self):
        tag = factory.make_Tag('a-tag', 'true', kernel_opts="console=ttyS0")
        self.assertEqual('a-tag', tag.name)
        self.assertEqual('true', tag.definition)
        self.assertEqual('', tag.comment)
        self.assertEqual('console=ttyS0', tag.kernel_opts)
        self.assertIsNot(None, tag.updated)
        self.assertIsNot(None, tag.created)

    def test_add_tag_to_node(self):
        node = factory.make_Node()
        tag = factory.make_Tag()
        tag.save()
        node.tags.add(tag)
        self.assertEqual([tag.id], [t.id for t in node.tags.all()])
        self.assertEqual([node.id], [n.id for n in tag.node_set.all()])

    def test_valid_tag_names(self):
        for valid in ['valid-dash', 'under_score', 'long' * 50]:
            tag = factory.make_Tag(name=valid)
            self.assertEqual(valid, tag.name)

    def test_validate_traps_invalid_tag_name(self):
        for invalid in ['invalid:name', 'no spaces', 'no\ttabs',
                        'no&ampersand', 'no!shouting', '',
                        'too-long' * 33, '\xb5']:
            self.assertRaises(ValidationError, factory.make_Tag, name=invalid)

    def test_applies_tags_to_nodes(self):
        populate_tags = self.patch_autospec(
            populate_tags_module, "populate_tags")
        tag = factory.make_Tag(definition='//node/child')
        self.assertThat(populate_tags, MockCalledOnceWith(tag))

    def test_will_not_save_invalid_xpath(self):
        tag = factory.make_Tag(definition='//node/foo')
        tag.definition = 'invalid::tag'
        self.assertRaises(ValidationError, tag.save)


class TestTagIsDefined(MAASServerTestCase):
    """Tests for the `Tag.is_defined` property."""

    scenarios = (
        ("null", dict(definition=None, expected=False)),
        ("empty", dict(definition="", expected=False)),
        ("whitespace", dict(definition="   \t\n ", expected=False)),
        ("defined", dict(definition="//node", expected=True)),
    )

    def test_is_defined(self):
        tag = Tag(name="tag", definition=self.definition)
        self.assertIs(self.expected, tag.is_defined)


class TestTagPopulateNodes(MAASServerTestCase):

    def test__does_nothing_if_tag_is_not_defined(self):
        tag = factory.make_Tag(definition="")
        self.assertFalse(tag.is_defined)
        nodes = [factory.make_Node() for _ in range(3)]
        tag.node_set.add(*nodes)
        tag.populate_nodes()
        # The set of related nodes is unchanged.
        self.assertItemsEqual(nodes, tag.node_set.all())

    def test__checks_definition_before_proceeding(self):
        tag = factory.make_Tag(definition="")
        tag.definition = "invalid::definition"
        self.assertRaises(ValidationError, tag.populate_nodes)

    def test__clears_node_set(self):
        self.patch_autospec(populate_tags_module, "populate_tags")

        tag = factory.make_Tag(definition="")
        # Define the tag now but don't save because .save() calls
        # populate_nodes(), but we want to do it explicitly here.
        tag.definition = "//foo"
        nodes = [factory.make_Node() for _ in range(3)]
        tag.node_set.add(*nodes)
        tag.populate_nodes()
        self.assertItemsEqual([], tag.node_set.all())

    def test__calls_populate_tags(self):
        populate_tags = self.patch_autospec(
            populate_tags_module, "populate_tags")

        tag = factory.make_Tag(definition="")
        # Define the tag now but don't save because .save() calls
        # populate_nodes(), but we want to do it explicitly here.
        tag.definition = "//foo"
        tag.populate_nodes()
        self.assertThat(populate_tags, MockCalledOnceWith(tag))
