# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
from random import randint
from xmlrpclib import Fault

from django.conf.urls import patterns
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import Http404
from django.test.client import RequestFactory
from django.utils.html import escape
from lxml.html import fromstring
from maasserver.components import register_persistent_error
from maasserver.testing import extract_redirect
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.views import (
    HelpfulDeleteView,
    PaginatedListView,
)
from testtools.matchers import ContainsAll


class Test404500(MAASServerTestCase):
    """Test pages displayed when an error 404 or an error 500 occur."""

    def test_404(self):
        self.client_log_in()
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
        self.client_log_in()
        from maasserver.urls import urlpatterns
        urlpatterns += patterns(
            '',
            (r'^500/$', 'django.views.defaults.server_error'),
        )
        response = self.client.get('/500/')
        doc = fromstring(response.content)
        self.assertIn(
            "Internal server error",
            doc.cssselect('title')[0].text)
        self.assertSequenceEqual(
            ['Internal server error.'],
            [elem.text.strip() for elem in
                doc.cssselect('h2')])


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

    template_name = 'not-a-real-template'

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


class HelpfulDeleteViewTest(MAASServerTestCase):

    def test_delete_deletes_object(self):
        obj = FakeDeletableModel()
        # HttpResponseRedirect does not allow next_url to be None.
        view = FakeDeleteView(obj, next_url=factory.make_string())
        view.delete()
        self.assertTrue(obj.deleted)
        self.assertEqual([view.compose_feedback_deleted(obj)], view.notices)

    def test_delete_is_gentle_with_missing_objects(self):
        # Deleting a nonexistent object is basically treated as successful.
        # HttpResponseRedirect does not allow next_url to be None.
        view = FakeDeleteView(next_url=factory.make_string())
        response = view.delete()
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual([view.compose_feedback_nonexistent()], view.notices)

    def test_delete_is_not_gentle_with_permission_violations(self):
        view = FakeDeleteView()
        view.get_object = view.raise_permission_denied
        self.assertRaises(PermissionDenied, view.delete)

    def test_get_asks_for_confirmation_and_does_nothing_yet(self):
        obj = FakeDeletableModel()
        next_url = factory.make_string()
        request = RequestFactory().get('/foo')
        view = FakeDeleteView(obj, request=request, next_url=next_url)
        response = view.get(request)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertNotIn(next_url, response.get('Location', ''))
        self.assertFalse(obj.deleted)
        self.assertEqual([], view.notices)

    def test_get_skips_confirmation_for_missing_objects(self):
        next_url = factory.make_string()
        request = RequestFactory().get('/foo')
        view = FakeDeleteView(next_url=next_url, request=request)
        response = view.get(request)
        self.assertEqual(next_url, extract_redirect(response))
        self.assertEqual([view.compose_feedback_nonexistent()], view.notices)

    def test_compose_feedback_nonexistent_names_class(self):
        class_name = factory.make_string()
        self.patch(FakeDeletableModel.Meta, 'verbose_name', class_name)
        view = FakeDeleteView()
        self.assertEqual(
            "Not deleting: %s not found." % class_name,
            view.compose_feedback_nonexistent())

    def test_compose_feedback_deleted_uses_name_object(self):
        object_name = factory.make_string()
        view = FakeDeleteView(FakeDeletableModel())
        view.name_object = lambda _obj: object_name
        self.assertEqual(
            "%s deleted." % object_name.capitalize(),
            view.compose_feedback_deleted(view.obj))


class SimpleFakeModel:
    """Pretend model object for testing"""

    def __init__(self, counter):
        self.id = counter


class SimpleListView(PaginatedListView):
    """Simple paginated view for testing"""

    paginate_by = 2
    query_results = None

    def __init__(self, query_results):
        self.query_results = list(query_results)

    def get_queryset(self):
        """Return precanned list of objects

        Really this should return a QuerySet object, but for basic usage a
        list is close enough.
        """
        return self.query_results


class PaginatedListViewTests(MAASServerTestCase):
    """Check PaginatedListView page links inserted into context are correct"""

    def test_single_page(self):
        view = SimpleListView.as_view(query_results=[SimpleFakeModel(1)])
        request = RequestFactory().get('/index')
        response = view(request)
        context = response.context_data
        self.assertEqual("", context["first_page_link"])
        self.assertEqual("", context["previous_page_link"])
        self.assertEqual("", context["next_page_link"])
        self.assertEqual("", context["last_page_link"])

    def test_on_first_page(self):
        view = SimpleListView.as_view(
            query_results=[SimpleFakeModel(i) for i in range(5)])
        request = RequestFactory().get('/index')
        response = view(request)
        context = response.context_data
        self.assertEqual("", context["first_page_link"])
        self.assertEqual("", context["previous_page_link"])
        self.assertEqual("?page=2", context["next_page_link"])
        self.assertEqual("?page=3", context["last_page_link"])

    def test_on_second_page(self):
        view = SimpleListView.as_view(
            query_results=[SimpleFakeModel(i) for i in range(7)])
        request = RequestFactory().get('/index?page=2')
        response = view(request)
        context = response.context_data
        self.assertEqual("index", context["first_page_link"])
        self.assertEqual("index", context["previous_page_link"])
        self.assertEqual("?page=3", context["next_page_link"])
        self.assertEqual("?page=4", context["last_page_link"])

    def test_on_final_page(self):
        view = SimpleListView.as_view(
            query_results=[SimpleFakeModel(i) for i in range(5)])
        request = RequestFactory().get('/index?page=3')
        response = view(request)
        context = response.context_data
        self.assertEqual("index", context["first_page_link"])
        self.assertEqual("?page=2", context["previous_page_link"])
        self.assertEqual("", context["next_page_link"])
        self.assertEqual("", context["last_page_link"])

    def test_relative_to_directory(self):
        view = SimpleListView.as_view(
            query_results=[SimpleFakeModel(i) for i in range(6)])
        request = RequestFactory().get('/index/?page=2')
        response = view(request)
        context = response.context_data
        self.assertEqual(".", context["first_page_link"])
        self.assertEqual(".", context["previous_page_link"])
        self.assertEqual("?page=3", context["next_page_link"])
        self.assertEqual("?page=3", context["last_page_link"])

    def test_preserves_query_string(self):
        view = SimpleListView.as_view(
            query_results=[SimpleFakeModel(i) for i in range(6)])
        request = RequestFactory().get('/index?lookup=value')
        response = view(request)
        context = response.context_data
        self.assertEqual("", context["first_page_link"])
        self.assertEqual("", context["previous_page_link"])
        # Does this depend on dict hash values for order or does django sort?
        self.assertEqual("?lookup=value&page=2", context["next_page_link"])
        self.assertEqual("?lookup=value&page=3", context["last_page_link"])

    def test_preserves_query_string_with_page(self):
        view = SimpleListView.as_view(
            query_results=[SimpleFakeModel(i) for i in range(8)])
        request = RequestFactory().get('/index?page=3&lookup=value')
        response = view(request)
        context = response.context_data
        self.assertEqual("?lookup=value", context["first_page_link"])
        # Does this depend on dict hash values for order or does django sort?
        self.assertEqual("?lookup=value&page=2", context["previous_page_link"])
        self.assertEqual("?lookup=value&page=4", context["next_page_link"])
        self.assertEqual("?lookup=value&page=4", context["last_page_link"])


class PermanentErrorDisplayTest(MAASServerTestCase):

    def test_permanent_error_displayed(self):
        self.client_log_in()
        fault_codes = [
            randint(1, 100),
            randint(101, 200),
            ]
        errors = []
        for fault in fault_codes:
            # Create component with make_string to be sure to display all
            # the errors.
            component = factory.make_name('component')
            error_message = factory.make_name('error')
            errors.append(Fault(fault, error_message))
            register_persistent_error(component, error_message)
        links = [
            reverse('index'),
            reverse('prefs'),
        ]
        for link in links:
            response = self.client.get(link)
            self.assertThat(
                response.content,
                ContainsAll(
                    [escape(error.faultString) for error in errors]))
