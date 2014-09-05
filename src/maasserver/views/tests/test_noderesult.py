# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `NodeResult` views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
from operator import attrgetter
from random import randint

from django.core.urlresolvers import reverse
from django.http.request import QueryDict
from lxml import html
from maasserver.testing import extract_redirect
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import get_one
from maasserver.views.noderesult import NodeCommissionResultListView
from mock import Mock
from provisioningserver.utils.text import normalise_whitespace
from testtools.matchers import HasLength


def extract_field(doc, field_name, containing_tag='span'):
    """Get the content text from one of the <li> fields on the page.

    This works on the basis that each of the fields has an `id` attribute
    which is unique on the page, and contains exactly one tag of the type
    given as `containing_tag`, which holds the field value.
    """
    field = get_one(doc.cssselect('#' + field_name))
    value = get_one(field.cssselect(containing_tag))
    return value.text_content().strip()


class TestNodeInstallResultView(MAASServerTestCase):

    def request_page(self, result):
        """Request and parse the  page for the given `NodeResult`.

        :return: The page's main content as an `lxml.html.HtmlElement`.
        """
        link = reverse('nodeinstallresult-view', args=[result.id])
        response = self.client.get(link)
        self.assertEqual(httplib.OK, response.status_code, response.content)
        doc = html.fromstring(response.content)
        return get_one(doc.cssselect('#content'))

    def test_installing_forbidden_without_edit_perm(self):
        self.client_log_in(as_admin=False)
        result = factory.make_NodeResult_for_installing()
        response = self.client.get(
            reverse('nodeinstallresult-view', args=[result.id]))
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_installing_allowed_with_edit_perm(self):
        password = 'test'
        user = factory.make_user(password=password)
        node = factory.make_node(owner=user)
        self.client.login(username=user.username, password=password)
        self.logged_in_user = user
        result = factory.make_NodeResult_for_installing(node=node)
        response = self.client.get(
            reverse('nodeinstallresult-view', args=[result.id]))
        self.assertEqual(httplib.OK, response.status_code)

    def test_installing_escapes_html_in_output(self):
        self.client_log_in(as_admin=True)
        # It's actually surprisingly hard to test for this, because lxml
        # un-escapes on parsing, and is very tolerant of malformed input.
        # Parsing an un-escaped A<B>C, however, would produce text "AC"
        # (because the <B> looks like a tag).
        result = factory.make_NodeResult_for_installing(data=b'A<B>C')
        doc = self.request_page(result)
        self.assertEqual('A<B>C', extract_field(doc, 'output', 'pre'))

    def test_installing_escapes_binary_in_output(self):
        self.client_log_in(as_admin=True)
        result = factory.make_NodeResult_for_installing(data=b'A\xffB')
        doc = self.request_page(result)
        self.assertEqual('A\ufffdB', extract_field(doc, 'output', 'pre'))

    def test_installing_hides_output_if_empty(self):
        self.client_log_in(as_admin=True)
        result = factory.make_NodeResult_for_installing(data=b'')
        doc = self.request_page(result)
        field = get_one(doc.cssselect('#output'))
        self.assertEqual('', field.text_content().strip())


class TestNodeCommissionResultView(MAASServerTestCase):

    def request_page(self, result):
        """Request and parse the  page for the given `NodeResult`.

        :return: The page's main content as an `lxml.html.HtmlElement`.
        """
        link = reverse('nodecommissionresult-view', args=[result.id])
        response = self.client.get(link)
        self.assertEqual(httplib.OK, response.status_code, response.content)
        doc = html.fromstring(response.content)
        return get_one(doc.cssselect('#content'))

    def test_commissioning_forbidden_without_edit_perm(self):
        self.client_log_in(as_admin=False)
        result = factory.make_NodeResult_for_commissioning()
        response = self.client.get(
            reverse('nodecommissionresult-view', args=[result.id]))
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_commissioning_allowed_with_edit_perm(self):
        password = 'test'
        user = factory.make_user(password=password)
        node = factory.make_node(owner=user)
        self.client.login(username=user.username, password=password)
        self.logged_in_user = user
        result = factory.make_NodeResult_for_commissioning(node=node)
        response = self.client.get(
            reverse('nodecommissionresult-view', args=[result.id]))
        self.assertEqual(httplib.OK, response.status_code)

    def test_commissioning_displays_result(self):
        self.client_log_in(as_admin=True)
        result = factory.make_NodeResult_for_commissioning(
            data=factory.make_string().encode('ascii'))
        doc = self.request_page(result)

        self.assertEqual(result.name, extract_field(doc, 'name'))
        self.assertEqual(
            result.node.hostname,
            extract_field(doc, 'node'))
        self.assertEqual(
            "%d" % result.script_result,
            extract_field(doc, 'script-result'))
        self.assertEqual(result.data, extract_field(doc, 'output', 'pre'))

    def test_commissioning_escapes_html_in_output(self):
        self.client_log_in(as_admin=True)
        # It's actually surprisingly hard to test for this, because lxml
        # un-escapes on parsing, and is very tolerant of malformed input.
        # Parsing an un-escaped A<B>C, however, would produce text "AC"
        # (because the <B> looks like a tag).
        result = factory.make_NodeResult_for_commissioning(data=b'A<B>C')
        doc = self.request_page(result)
        self.assertEqual('A<B>C', extract_field(doc, 'output', 'pre'))

    def test_commissioning_escapes_binary_in_output(self):
        self.client_log_in(as_admin=True)
        result = factory.make_NodeResult_for_commissioning(data=b'A\xffB')
        doc = self.request_page(result)
        self.assertEqual('A\ufffdB', extract_field(doc, 'output', 'pre'))

    def test_commissioning_hides_output_if_empty(self):
        self.client_log_in(as_admin=True)
        result = factory.make_NodeResult_for_commissioning(data=b'')
        doc = self.request_page(result)
        field = get_one(doc.cssselect('#output'))
        self.assertEqual('', field.text_content().strip())


class TestNodeCommissionResultListView(MAASServerTestCase):

    def make_query_string(self, nodes):
        """Compose a URL query string to filter for the given nodes."""
        return '&'.join('node=%s' % node.system_id for node in nodes)

    def request_page(self, nodes=None):
        """Request and parse the  page for the given `NodeResult`.

        :param node: Optional list of `Node` for which results should be
            displayed.  If not given, all results are displayed.
        :return: The page's main content as an `lxml.html.HtmlElement`.
        """
        link = reverse('nodecommissionresult-list')
        if nodes is not None:
            link += '?' + self.make_query_string(nodes)
        response = self.client.get(link)
        self.assertEqual(httplib.OK, response.status_code, response.content)
        return get_one(html.fromstring(response.content).cssselect('#content'))

    def make_view(self, nodes=None):
        if nodes is None:
            query_string = ''
        else:
            query_string = self.make_query_string(nodes)
        view = NodeCommissionResultListView()
        view.request = Mock()
        view.request.GET = QueryDict(query_string)
        return view

    def test_requires_admin(self):
        self.client_log_in(as_admin=False)
        response = self.client.get(reverse('nodecommissionresult-list'))
        self.assertEqual(reverse('login'), extract_redirect(response))

    def test_lists_empty_page(self):
        self.client_log_in(as_admin=True)
        content = self.request_page()
        self.assertIn(
            "No matching commissioning results.",
            content.text_content().strip())
        self.assertEqual([], content.cssselect('.result'))

    def test_lists_results(self):
        self.client_log_in(as_admin=True)
        result = factory.make_NodeResult_for_commissioning(script_result=0)
        content = self.request_page()
        result_row = get_one(content.cssselect('.result'))
        fields = result_row.cssselect('td')

        [script_result, output_file, time, node] = fields
        self.assertEqual('OK', script_result.text_content().strip())
        self.assertIn('%d' % result.created.year, time.text_content())
        self.assertEqual(result.node.hostname, node.text_content().strip())
        self.assertEqual(
            reverse('node-view', args=[result.node.system_id]),
            get_one(node.cssselect('a')).get('href'))
        self.assertEqual(result.name, output_file.text_content().strip())

    def test_shows_failure(self):
        self.client_log_in(as_admin=True)
        factory.make_NodeResult_for_commissioning(
            script_result=randint(1, 100))
        content = self.request_page()
        result_row = get_one(content.cssselect('.result'))
        fields = result_row.cssselect('td')
        [script_result, _, _, _] = fields
        self.assertEqual("FAILED", script_result.text_content().strip())
        self.assertNotEqual([], script_result.find_class('warning'))

    def test_links_to_result(self):
        self.client_log_in(as_admin=True)
        result = factory.make_NodeResult_for_commissioning(
            script_result=randint(1, 100))
        content = self.request_page()
        result_row = get_one(content.cssselect('.result'))
        fields = result_row.cssselect('td')
        [script_result, _, _, _] = fields
        link = get_one(script_result.cssselect('a'))
        self.assertEqual(
            reverse('nodecommissionresult-view', args=[result.id]),
            link.get('href'))

    def test_groups_by_node(self):
        nodes = [factory.make_node() for _ in range(3)]
        # Create two results per node, but interleave them so the results for
        # any given node are unlikely to occur side by side by accident.
        for _ in range(2):
            for node in nodes:
                factory.make_NodeResult_for_commissioning(node=node)
        sorted_results = self.make_view().get_queryset()
        self.assertEqual(sorted_results[0].node, sorted_results[1].node)
        self.assertEqual(sorted_results[2].node, sorted_results[3].node)
        self.assertEqual(sorted_results[4].node, sorted_results[5].node)

    def test_sorts_by_creation_time_for_same_node(self):
        node = factory.make_node()
        results = [
            factory.make_NodeResult_for_commissioning(node=node)
            for _ in range(3)
            ]
        for result in results:
            result.created -= factory.make_timedelta()
            result.save()

        self.assertEqual(
            sorted(results, key=attrgetter('created'), reverse=True),
            list(self.make_view().get_queryset()))

    def test_sorts_by_name_for_same_node_and_creation_time(self):
        node = factory.make_node()
        results = {
            factory.make_NodeResult_for_commissioning(
                node=node, name=factory.make_name().lower())
            for _ in range(5)
            }
        self.assertEqual(
            sorted(results, key=attrgetter('name')),
            list(self.make_view().get_queryset()))

    def test_filters_by_node(self):
        factory.make_NodeResult_for_commissioning()
        node = factory.make_node()
        node_results = {
            factory.make_NodeResult_for_commissioning(node=node)
            for _ in range(3)
            }
        factory.make_NodeResult_for_commissioning()

        self.assertEqual(
            node_results,
            set(self.make_view(nodes=[node]).get_queryset()))

    def test_combines_node_filters(self):
        # The nodes are passed as GET parameters, which means there is some
        # subtlety to how they are passed to the application.  Reading them
        # naively would ignore all but the first node passed, so make sure we
        # process all of them.
        self.client_log_in(as_admin=True)
        results = [
            factory.make_NodeResult_for_commissioning()
            for _ in range(3)
        ]
        matching_results = results[1:3]
        content = self.request_page(
            nodes=[result.node for result in matching_results])
        rows = content.cssselect('.result')
        self.assertThat(rows, HasLength(len(matching_results)))
        matching_names = set()
        for row in rows:
            [_, name, _, _] = row.cssselect('td')
            matching_names.add(name.text_content().strip())
        self.assertEqual(
            {result.name for result in matching_results},
            matching_names)

    def test_does_not_show_node_if_not_filtering_by_node(self):
        self.client_log_in(as_admin=True)
        doc = self.request_page()
        header = get_one(doc.cssselect('#results_header'))
        self.assertEqual(
            "Commissioning results",
            normalise_whitespace(header.text_content()))

    def test_shows_node_if_filtering_by_node(self):
        self.client_log_in(as_admin=True)
        node = factory.make_node()
        doc = self.request_page(nodes=[node])
        header = get_one(doc.cssselect('#results_header'))
        self.assertEqual(
            "Commissioning results for %s" % node.hostname,
            normalise_whitespace(header.text_content()))

    def test_shows_nodes_if_filtering_by_multiple_nodes(self):
        self.client_log_in(as_admin=True)
        names = [factory.make_name('node').lower() for _ in range(2)]
        nodes = [factory.make_node(hostname=name) for name in names]
        doc = self.request_page(nodes=nodes)
        header = get_one(doc.cssselect('#results_header'))
        self.assertEqual(
            "Commissioning results for %s" % ', '.join(sorted(names)),
            normalise_whitespace(header.text_content()))
