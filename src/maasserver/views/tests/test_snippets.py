# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver snippets."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from django.core.urlresolvers import reverse
from lxml.html import fromstring
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import (
    HasLength,
    Not,
    )


class SnippetsTest(MAASServerTestCase):

    def test_index_page_containts_add_node_snippet(self):
        self.client_log_in()
        index_page = self.client.get(reverse('index'))
        doc = fromstring(index_page.content)
        self.assertEqual(
            'text/x-template', doc.cssselect('#add-node')[0].attrib['type'])

    def test_add_node_snippet_hides_osystem_distro_series_labels(self):
        self.client_log_in()
        index_page = self.client.get(reverse('index'))
        doc = fromstring(index_page.content)
        content_text = doc.cssselect('#add-node')[0].text_content()
        add_node_snippet = fromstring(content_text)
        self.expectThat(
            add_node_snippet.cssselect("label[for=id_osystem].hidden"),
            Not(HasLength(0)), "No hidden id_osystem label")
        self.expectThat(
            add_node_snippet.cssselect("label[for=id_distro_series].hidden"),
            Not(HasLength(0)), "No hidden id_distro_series label")
