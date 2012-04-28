# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import httplib
from xmlrpclib import Fault

from django.conf.urls.defaults import patterns
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import Http404
from django.test.client import RequestFactory
from django.utils.html import escape
from lxml.html import fromstring
from maasserver import components
from maasserver.components import register_persistent_error
from maasserver.exceptions import ExternalComponentException
from maasserver.testing import extract_redirect
from maasserver.testing.enum import map_enum
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    LoggedInTestCase,
    TestCase,
    )
from maasserver.views import HelpfulDeleteView
from maasserver.views.nodes import NodeEdit
from provisioningserver.enum import PSERV_FAULT
from testtools.matchers import (
    Contains,
    MatchesAll,
    )


class Test404500(LoggedInTestCase):
    """Test pages displayed when an error 404 or an error 500 occur."""

    def test_404(self):
        response = self.client.get('/no-found-page/')
        doc = fromstring(response.content)
        self.assertIn(
            "Error: Page not found",
            doc.cssselect('title')[0].text)
        self.assertSequenceEqual(
            ['The requested URL /no-found-page/ was not found on this '
             'server.'],
            [elem.text.strip() for elem in
                doc.cssselect('h2')])

    def test_500(self):
        from maasserver.urls import urlpatterns
        urlpatterns += patterns('',
            (r'^500/$', 'django.views.defaults.server_error'),)
        response = self.client.get('/500/')
        doc = fromstring(response.content)
        self.assertIn(
            "Internal server error",
            doc.cssselect('title')[0].text)
        self.assertSequenceEqual(
            ['Internal server error.'],
            [elem.text.strip() for elem in
                doc.cssselect('h2')])


class TestSnippets(LoggedInTestCase):

    def assertTemplateExistsAndContains(self, content, template_selector,
                                        contains_selector):
        """Assert that the provided html 'content' contains a snippet as
        selected by 'template_selector' which in turn contains an element
        selected by 'contains_selector'.
        """
        doc = fromstring(content)
        snippets = doc.cssselect(template_selector)
        # The snippet exists.
        self.assertEqual(1, len(snippets))
        # It contains the required element.
        selects = fromstring(snippets[0].text).cssselect(contains_selector)
        self.assertEqual(1, len(selects))

    def test_architecture_snippet(self):
        response = self.client.get('/')
        self.assertTemplateExistsAndContains(
            response.content, '#add-architecture', 'select#id_architecture')

    def test_hostname(self):
        response = self.client.get('/')
        self.assertTemplateExistsAndContains(
            response.content, '#add-node', 'input#id_hostname')

    def test_after_commissioning_action_snippet(self):
        response = self.client.get('/')
        self.assertTemplateExistsAndContains(
            response.content, '#add-node',
            'select#id_after_commissioning_action')


class FakeDeletableModel:
    """A fake model class, with a delete method."""

    class Meta:
        app_label = 'maasserver'
        object_name = 'fake'
        verbose_name = "fake object"

    _meta = Meta
    deleted = False

    def delete(self):
        self.deleted = True


class FakeDeleteView(HelpfulDeleteView):
    """A fake `HelpfulDeleteView` instance.  Goes through most of the motions.

    There are a few special features to help testing along:
     - If there's no object, get_object() raises Http404.
     - Info messages are captured in self.notices.
    """

    model = FakeDeletableModel

    def __init__(self, obj=None, next_url=None, request=None):
        self.obj = obj
        self.next_url = next_url
        self.request = request
        self.notices = []

    def get_object(self):
        if self.obj is None:
            raise Http404()
        else:
            return self.obj

    def get_next_url(self):
        return self.next_url

    def raise_permission_denied(self):
        """Helper to substitute for get_object."""
        raise PermissionDenied()

    def show_notice(self, notice):
        self.notices.append(notice)


class HelpfulDeleteViewTest(TestCase):

    def test_delete_deletes_object(self):
        obj = FakeDeletableModel()
        view = FakeDeleteView(obj)
        view.delete()
        self.assertTrue(obj.deleted)
        self.assertEqual([view.compose_feedback_deleted(obj)], view.notices)

    def test_delete_is_gentle_with_missing_objects(self):
        # Deleting a nonexistent object is basically treated as successful.
        view = FakeDeleteView()
        response = view.delete()
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual([view.compose_feedback_nonexistent()], view.notices)

    def test_delete_is_not_gentle_with_permission_violations(self):
        view = FakeDeleteView()
        view.get_object = view.raise_permission_denied
        self.assertRaises(PermissionDenied, view.delete)

    def test_get_asks_for_confirmation_and_does_nothing_yet(self):
        obj = FakeDeletableModel()
        next_url = factory.getRandomString()
        request = RequestFactory().get('/foo')
        view = FakeDeleteView(obj, request=request, next_url=next_url)
        response = view.get(request)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertNotIn(next_url, response.get('Location', ''))
        self.assertFalse(obj.deleted)
        self.assertEqual([], view.notices)

    def test_get_skips_confirmation_for_missing_objects(self):
        next_url = factory.getRandomString()
        request = RequestFactory().get('/foo')
        view = FakeDeleteView(next_url=next_url, request=request)
        response = view.get(request)
        self.assertEqual(next_url, extract_redirect(response))
        self.assertEqual([view.compose_feedback_nonexistent()], view.notices)

    def test_compose_feedback_nonexistent_names_class(self):
        class_name = factory.getRandomString()
        self.patch(FakeDeletableModel.Meta, 'verbose_name', class_name)
        view = FakeDeleteView()
        self.assertEqual(
            "Not deleting: %s not found." % class_name,
            view.compose_feedback_nonexistent())

    def test_compose_feedback_deleted_uses_name_object(self):
        object_name = factory.getRandomString()
        view = FakeDeleteView(FakeDeletableModel())
        view.name_object = lambda _obj: object_name
        self.assertEqual(
            "%s deleted." % object_name.capitalize(),
            view.compose_feedback_deleted(view.obj))


class MAASExceptionHandledInView(LoggedInTestCase):

    def test_raised_MAASException_redirects(self):
        # When a ExternalComponentException is raised in a POST request, the
        # response is a redirect to the same page.

        # Patch NodeEdit to error on post.
        def post(self, request, *args, **kwargs):
            raise ExternalComponentException()
        self.patch(NodeEdit, 'post', post)
        node = factory.make_node(owner=self.logged_in_user)
        node_edit_link = reverse('node-edit', args=[node.system_id])
        response = self.client.post(node_edit_link, {})
        self.assertEqual(node_edit_link, extract_redirect(response))

    def test_raised_ExternalComponentException_publishes_message(self):
        # When a ExternalComponentException is raised in a POST request, a
        # message is published with the error message.
        error_message = factory.getRandomString()

        # Patch NodeEdit to error on post.
        def post(self, request, *args, **kwargs):
            raise ExternalComponentException(error_message)
        self.patch(NodeEdit, 'post', post)
        node = factory.make_node(owner=self.logged_in_user)
        node_edit_link = reverse('node-edit', args=[node.system_id])
        self.client.post(node_edit_link, {})
        # Manually perform the redirect: i.e. get the same page.
        response = self.client.get(node_edit_link, {})
        self.assertEqual(
            [error_message],
            [message.message for message in response.context['messages']])


class PermanentErrorDisplayTest(LoggedInTestCase):

    def test_permanent_error_displayed(self):
        self.patch(components, '_PERSISTENT_ERRORS', {})
        pserv_fault = set(map_enum(PSERV_FAULT).values())
        errors = []
        for fault in pserv_fault:
            # Create component with getRandomString to be sure
            # to display all the errors.
            component = factory.getRandomString()
            error_message = factory.getRandomString()
            error = Fault(fault, error_message)
            errors.append(error)
            register_persistent_error(component, error_message)
        links = [
            reverse('index'),
            reverse('node-list'),
            reverse('prefs'),
        ]
        for link in links:
            response = self.client.get(link)
            self.assertThat(
                response.content,
                MatchesAll(
                    *[Contains(
                          escape(error.faultString))
                     for error in errors]))
