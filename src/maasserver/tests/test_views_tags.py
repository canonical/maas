# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver nodes views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from django.core.urlresolvers import reverse
from lxml.html import fromstring
from maastesting.matchers import ContainsAll
from maasserver.testing import (
    get_content_links,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    LoggedInTestCase,
    )


class TagViewsTest(LoggedInTestCase):

    def test_view_tag_displays_tag_info(self):
        # The tag page features the basic information about the tag.
        tag = factory.make_tag(name='the-named-tag',
                               comment='Human description of the tag',
                               definition='//xpath')
        tag_link = reverse('tag-view', args=[tag.name])
        response = self.client.get(tag_link)
        doc = fromstring(response.content)
        content_text = doc.cssselect('#content')[0].text_content()
        self.assertThat(content_text,
                        ContainsAll([tag.name, tag.comment, tag.definition]))

    def test_view_tag_includes_node_links(self):
        tag = factory.make_tag()
        node = factory.make_node(set_hostname=True)
        node.tags.add(tag)
        mac = factory.make_mac_address(node=node).mac_address
        tag_link = reverse('tag-view', args=[tag.name])
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(tag_link)
        doc = fromstring(response.content)
        content_text = doc.cssselect('#content')[0].text_content()
        self.assertThat(content_text,
                        ContainsAll([mac, '(%s)' % node.hostname]))
        self.assertNotIn(node.system_id, content_text)
        self.assertIn(node_link, get_content_links(response))

    def test_view_tag_hides_private_nodes(self):
        tag = factory.make_tag()
        node = factory.make_node(set_hostname=True)
        node2 = factory.make_node(owner=factory.make_user(), set_hostname=True)
        node.tags.add(tag)
        node2.tags.add(tag)
        tag_link = reverse('tag-view', args=[tag.name])
        response = self.client.get(tag_link)
        doc = fromstring(response.content)
        content_text = doc.cssselect('#content')[0].text_content()
        self.assertIn(node.hostname, content_text)
        self.assertNotIn(node2.hostname, content_text)
