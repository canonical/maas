# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver nodes views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django.core.urlresolvers import reverse
from lxml.etree import XPath
from lxml.html import fromstring
from maasserver.testing import get_content_links
from maasserver.testing.factory import factory
from maasserver.testing.testcase import LoggedInTestCase
from maasserver.views import tags as tags_views
from maastesting.matchers import ContainsAll


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
        self.assertThat(
            content_text, ContainsAll([tag.comment, tag.definition]))

    def test_view_tag_includes_node_links(self):
        tag = factory.make_tag()
        node = factory.make_node()
        node.tags.add(tag)
        mac = factory.make_mac_address(node=node).mac_address
        tag_link = reverse('tag-view', args=[tag.name])
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(tag_link)
        doc = fromstring(response.content)
        content_text = doc.cssselect('#content')[0].text_content()
        self.assertThat(
            content_text, ContainsAll([unicode(mac), '%s' % node.hostname]))
        self.assertNotIn(node.system_id, content_text)
        self.assertIn(node_link, get_content_links(response))

    def test_view_tag_num_queries_is_independent_of_num_nodes(self):
        tag = factory.make_tag()
        tag_link = reverse('tag-view', args=[tag.name])
        nodegroup = factory.make_node_group()
        nodes = [factory.make_node(nodegroup=nodegroup, mac=True)
                 for i in range(20)]
        for node in nodes[:10]:
            node.tags.add(tag)
        num_queries, response = self.getNumQueries(self.client.get, tag_link)
        self.assertEqual(
            10,
            len([link for link in get_content_links(response)
                if link.startswith('/nodes/node')]))
        # Need to get the tag, and the nodes, and the macs of the nodes
        self.assertTrue(num_queries > 3)
        for node in nodes[10:]:
            node.tags.add(tag)
        num_bonus_queries, response = self.getNumQueries(
            self.client.get, tag_link)
        self.assertEqual(num_queries, num_bonus_queries)
        self.assertEqual(
            20,
            len([link for link in get_content_links(response)
                if link.startswith('/nodes/node')]))

    def test_view_tag_hides_private_nodes(self):
        tag = factory.make_tag()
        node = factory.make_node()
        node2 = factory.make_node(owner=factory.make_user())
        node.tags.add(tag)
        node2.tags.add(tag)
        tag_link = reverse('tag-view', args=[tag.name])
        response = self.client.get(tag_link)
        doc = fromstring(response.content)
        content_text = doc.cssselect('#content')[0].text_content()
        self.assertIn(node.hostname, content_text)
        self.assertNotIn(node2.hostname, content_text)

    def test_view_tag_shows_kernel_params(self):
        tag = factory.make_tag(kernel_opts='--test tag params')
        node = factory.make_node()
        node.tags = [tag]
        tag_link = reverse('tag-view', args=[tag.name])
        response = self.client.get(tag_link)
        doc = fromstring(response.content)
        kernel_opts = doc.cssselect('.kernel-opts-tag')[0].text_content()
        self.assertIn('Kernel Parameters', kernel_opts)
        self.assertIn(tag.kernel_opts, kernel_opts)

    def test_view_tag_paginates_nodes(self):
        """Listing of nodes with tag is split across multiple pages

        Copy-coded from NodeViewsTest.test_node_list_paginates evilly.
        """
        # Set a very small page size to save creating lots of nodes
        page_size = 2
        self.patch(tags_views.TagView, 'paginate_by', page_size)
        tag = factory.make_tag()
        nodes = [
            factory.make_node(created="2012-10-12 12:00:%02d" % i)
            for i in range(page_size * 2 + 1)
        ]
        for node in nodes:
            node.tags = [tag]
        # Order node links with newest first as the view is expected to
        node_links = [
            reverse('node-view', args=[node.system_id])
            for node in reversed(nodes)
        ]
        expr_node_links = XPath("//div[@id='nodes']/table//a/@href")
        expr_page_anchors = XPath("//div[@class='pagination']//a")
        # Fetch first page, should link newest two nodes and page 2
        response = self.client.get(reverse('tag-view', args=[tag.name]))
        page1 = fromstring(response.content)
        self.assertEqual(node_links[:page_size], expr_node_links(page1))
        self.assertEqual(
            [("next", "?page=2"), ("last", "?page=3")],
            [(a.text.lower(), a.get("href"))
             for a in expr_page_anchors(page1)])
        # Fetch second page, should link next nodes and adjacent pages
        response = self.client.get(
            reverse('tag-view', args=[tag.name]), {"page": 2})
        page2 = fromstring(response.content)
        self.assertEqual(
            node_links[page_size:page_size * 2],
            expr_node_links(page2))
        self.assertEqual(
            [("first", "."), ("previous", "."),
             ("next", "?page=3"), ("last", "?page=3")],
            [(a.text.lower(), a.get("href"))
             for a in expr_page_anchors(page2)])
        # Fetch third page, should link oldest node and node list page
        response = self.client.get(
            reverse('tag-view', args=[tag.name]), {"page": 3})
        page3 = fromstring(response.content)
        self.assertEqual(node_links[page_size * 2:], expr_node_links(page3))
        self.assertEqual(
            [("first", "."), ("previous", "?page=2")],
            [(a.text.lower(), a.get("href"))
             for a in expr_page_anchors(page3)])
