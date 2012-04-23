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
import os
from urlparse import urlparse
from xmlrpclib import Fault

from django.conf import settings
from django.conf.urls.defaults import patterns
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import Http404
from django.test.client import RequestFactory
from django.utils.html import escape
from lxml.html import fromstring
from maasserver import (
    components,
    messages,
    )
from maasserver.components import register_persistent_error
from maasserver.enum import NODE_AFTER_COMMISSIONING_ACTION
from maasserver.exceptions import (
    ExternalComponentException,
    NoRabbit,
    )
from maasserver.models import (
    Config,
    UserProfile,
    )
from maasserver.testing import (
    get_prefixed_form_data,
    reload_object,
    )
from maasserver.testing.enum import map_enum
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    LoggedInTestCase,
    TestCase,
    )
from maasserver.views import (
    get_yui_location,
    HelpfulDeleteView,
    nodes as nodes_views,
    )
from maasserver.views.nodes import (
    get_longpoll_context,
    NodeEdit,
    )
from maastesting.rabbit import uses_rabbit_fixture
from provisioningserver.enum import (
    POWER_TYPE_CHOICES,
    PSERV_FAULT,
    )
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


class TestComboLoaderView(TestCase):
    """Test combo loader view."""

    def test_load_js(self):
        requested_files = [
            'tests/build/oop/oop.js',
            'tests/build/event-custom-base/event-custom-base.js'
            ]
        response = self.client.get('/combo/?%s' % '&'.join(requested_files))
        self.assertIn('text/javascript', response['Content-Type'])
        for requested_file in requested_files:
            self.assertIn(requested_file, response.content)
        # No sign of a missing js file.
        self.assertNotIn("/* [missing] */", response.content)
        # The file contains a link to YUI's licence.
        self.assertIn('http://yuilibrary.com/license/', response.content)

    def test_load_css(self):
        requested_files = [
            'tests/build/widget-base/assets/skins/sam/widget-base.css',
            'tests/build/widget-stack/assets/skins/sam/widget-stack.css',
            ]
        response = self.client.get('/combo/?%s' % '&'.join(requested_files))
        self.assertIn('text/css', response['Content-Type'])
        for requested_file in requested_files:
            self.assertIn(requested_file, response.content)
        # No sign of a missing css file.
        self.assertNotIn("/* [missing] */", response.content)
        # The file contains a link to YUI's licence.
        self.assertIn('http://yuilibrary.com/license/', response.content)

    def test_combo_no_file_returns_not_found(self):
        response = self.client.get('/combo/')
        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_combo_wrong_file_extension_returns_bad_request(self):
        response = self.client.get('/combo/?file.wrongextension')
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual("Invalid file type requested.", response.content)


class TestUtilities(TestCase):

    def test_get_yui_location_if_static_root_is_none(self):
        self.patch(settings, 'STATIC_ROOT', None)
        yui_location = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'static', 'jslibs', 'yui')
        self.assertEqual(yui_location, get_yui_location())

    def test_get_yui_location(self):
        static_root = factory.getRandomString()
        self.patch(settings, 'STATIC_ROOT', static_root)
        yui_location = os.path.join(static_root, 'jslibs', 'yui')
        self.assertEqual(yui_location, get_yui_location())

    def test_get_longpoll_context_empty_if_rabbitmq_publish_is_none(self):
        self.patch(settings, 'RABBITMQ_PUBLISH', None)
        self.patch(nodes_views, 'messaging', messages.get_messaging())
        self.assertEqual({}, get_longpoll_context())

    def test_get_longpoll_context_returns_empty_if_rabbit_not_running(self):

        class FakeMessaging:
            """Fake :class:`RabbitMessaging`: fail with `NoRabbit`."""

            def getQueue(self, *args, **kwargs):
                raise NoRabbit("Pretending not to have a rabbit.")

        self.patch(messages, 'messaging', FakeMessaging())
        self.assertEqual({}, get_longpoll_context())

    def test_get_longpoll_context_empty_if_longpoll_url_is_None(self):
        self.patch(settings, 'LONGPOLL_PATH', None)
        self.patch(nodes_views, 'messaging', messages.get_messaging())
        self.assertEqual({}, get_longpoll_context())

    @uses_rabbit_fixture
    def test_get_longpoll_context(self):
        longpoll = factory.getRandomString()
        self.patch(settings, 'LONGPOLL_PATH', longpoll)
        self.patch(settings, 'RABBITMQ_PUBLISH', True)
        self.patch(nodes_views, 'messaging', messages.get_messaging())
        context = get_longpoll_context()
        self.assertItemsEqual(
            ['LONGPOLL_PATH', 'longpoll_queue'], context)
        self.assertEqual(longpoll, context['LONGPOLL_PATH'])


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
        self.assertEqual(
            (httplib.FOUND, next_url),
            (response.status_code, response['Location']))
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


class AdminLoggedInTestCase(LoggedInTestCase):

    def setUp(self):
        super(AdminLoggedInTestCase, self).setUp()
        # Promote the logged-in user to admin.
        self.logged_in_user.is_superuser = True
        self.logged_in_user.save()


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
        redirect_url = urlparse(response['Location']).path
        self.assertEqual(
            (httplib.FOUND, redirect_url),
            (response.status_code, node_edit_link))

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


class AdminNodeViewsTest(AdminLoggedInTestCase):

    def test_admin_can_edit_nodes(self):
        node = factory.make_node(owner=factory.make_user())
        node_edit_link = reverse('node-edit', args=[node.system_id])
        params = {
            'hostname': factory.getRandomString(),
            'after_commissioning_action': factory.getRandomEnum(
                NODE_AFTER_COMMISSIONING_ACTION),
            'power_type': factory.getRandomChoice(POWER_TYPE_CHOICES),
        }
        response = self.client.post(node_edit_link, params)

        node = reload_object(node)
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertAttributes(node, params)


class SettingsTest(AdminLoggedInTestCase):

    def test_settings_list_users(self):
        # The settings page displays a list of the users with links to view,
        # delete or edit each user. Note that the link to delete the the
        # logged-in user is not display.
        [factory.make_user() for i in range(3)]
        users = UserProfile.objects.all_users()
        response = self.client.get('/settings/')
        doc = fromstring(response.content)
        tab = doc.cssselect('#users')[0]
        all_links = [elem.get('href') for elem in tab.cssselect('a')]
        # "Add a user" link.
        self.assertIn(reverse('accounts-add'), all_links)
        for user in users:
            rows = tab.cssselect('tr#%s' % user.username)
            # Only one row for the user.
            self.assertEqual(1, len(rows))
            row = rows[0]
            links = [elem.get('href') for elem in row.cssselect('a')]
            # The username is shown...
            self.assertSequenceEqual(
                [user.username],
                [link.text.strip() for link in row.cssselect('a.user')])
            # ...with a link to view the user's profile.
            self.assertSequenceEqual(
                [reverse('accounts-view', args=[user.username])],
                [link.get('href') for link in row.cssselect('a.user')])
            # A link to edit the user is shown.
            self.assertIn(
                reverse('accounts-edit', args=[user.username]), links)
            if user != self.logged_in_user:
                # A link to delete the user is shown.
                self.assertIn(
                    reverse('accounts-del', args=[user.username]), links)
            else:
                # No link to delete the user is shown if the user is the
                # logged-in user.
                self.assertNotIn(
                    reverse('accounts-del', args=[user.username]), links)

    def test_settings_maas_and_network_POST(self):
        new_name = factory.getRandomString()
        new_domain = factory.getRandomString()
        response = self.client.post(
            '/settings/',
            get_prefixed_form_data(
                prefix='maas_and_network',
                data={
                    'maas_name': new_name,
                    'enlistment_domain': new_domain,
                }))

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(new_name, Config.objects.get_config('maas_name'))
        self.assertEqual(
            new_domain, Config.objects.get_config('enlistment_domain'))

    def test_settings_commissioning_POST(self):
        new_after_commissioning = factory.getRandomEnum(
            NODE_AFTER_COMMISSIONING_ACTION)
        new_check_compatibility = factory.getRandomBoolean()
        response = self.client.post(
            '/settings/',
            get_prefixed_form_data(
                prefix='commissioning',
                data={
                    'after_commissioning': new_after_commissioning,
                    'check_compatibility': new_check_compatibility,
                }))

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(
            new_after_commissioning,
            Config.objects.get_config('after_commissioning'))
        self.assertEqual(
            new_check_compatibility,
            Config.objects.get_config('check_compatibility'))

    def test_settings_ubuntu_POST(self):
        new_fallback_master_archive = factory.getRandomBoolean()
        new_keep_mirror_list_uptodate = factory.getRandomBoolean()
        new_fetch_new_releases = factory.getRandomBoolean()
        choices = Config.objects.get_config('update_from_choice')
        new_update_from = factory.getRandomChoice(choices)
        response = self.client.post(
            '/settings/',
            get_prefixed_form_data(
                prefix='ubuntu',
                data={
                    'fallback_master_archive': new_fallback_master_archive,
                    'keep_mirror_list_uptodate': new_keep_mirror_list_uptodate,
                    'fetch_new_releases': new_fetch_new_releases,
                    'update_from': new_update_from,
                }))

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(
            new_fallback_master_archive,
            Config.objects.get_config('fallback_master_archive'))
        self.assertEqual(
            new_keep_mirror_list_uptodate,
            Config.objects.get_config('keep_mirror_list_uptodate'))
        self.assertEqual(
            new_fetch_new_releases,
            Config.objects.get_config('fetch_new_releases'))
        self.assertEqual(
            new_update_from, Config.objects.get_config('update_from'))

    def test_settings_add_archive_POST(self):
        choices = Config.objects.get_config('update_from_choice')
        response = self.client.post(
            '/settings/archives/add/',
            data={'archive_name': 'my.hostname.com'}
        )
        new_choices = Config.objects.get_config('update_from_choice')

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertItemsEqual(
            choices + [['my.hostname.com', 'my.hostname.com']],
            new_choices)


# Settable attributes on User.
user_attributes = [
    'email',
    'is_superuser',
    'last_name',
    'username',
    ]


def make_user_attribute_params(user):
    """Compose a dict of form parameters for a user's account data.

    By default, each attribute in the dict maps to the user's existing value
    for that atrribute.
    """
    return {
        attr: getattr(user, attr)
        for attr in user_attributes
        }


def make_password_params(password):
    """Create a dict of parameters for setting a given password."""
    return {
        'password1': password,
        'password2': password,
    }


def subset_dict(input_dict, keys_subset):
    """Return a subset of `input_dict` restricted to `keys_subset`.

    All keys in `keys_subset` must be in `input_dict`.
    """
    return {key: input_dict[key] for key in keys_subset}


class UserManagementTest(AdminLoggedInTestCase):

    def test_add_user_POST(self):
        params = {
            'username': factory.getRandomString(),
            'last_name': factory.getRandomString(30),
            'email': factory.getRandomEmail(),
            'is_superuser': factory.getRandomBoolean(),
        }
        password = factory.getRandomString()
        params.update(make_password_params(password))

        response = self.client.post(reverse('accounts-add'), params)
        self.assertEqual(httplib.FOUND, response.status_code)
        user = User.objects.get(username=params['username'])
        self.assertAttributes(user, subset_dict(params, user_attributes))
        self.assertTrue(user.check_password(password))

    def test_edit_user_POST_profile_updates_attributes(self):
        user = factory.make_user()
        params = make_user_attribute_params(user)
        params.update({
            'last_name': 'Newname-%s' % factory.getRandomString(),
            'email': 'new-%s@example.com' % factory.getRandomString(),
            'is_superuser': True,
            'username': 'newname-%s' % factory.getRandomString(),
            })

        response = self.client.post(
            reverse('accounts-edit', args=[user.username]),
            get_prefixed_form_data('profile', params))

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertAttributes(
            reload_object(user), subset_dict(params, user_attributes))

    def test_edit_user_POST_updates_password(self):
        user = factory.make_user()
        new_password = factory.getRandomString()
        params = make_password_params(new_password)
        response = self.client.post(
            reverse('accounts-edit', args=[user.username]),
            get_prefixed_form_data('password', params))
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertTrue(reload_object(user).check_password(new_password))

    def test_delete_user_GET(self):
        # The user delete page displays a confirmation page with a form.
        user = factory.make_user()
        del_link = reverse('accounts-del', args=[user.username])
        response = self.client.get(del_link)
        doc = fromstring(response.content)
        confirmation_message = (
            'Are you sure you want to delete the user "%s"?' %
            user.username)
        self.assertSequenceEqual(
            [confirmation_message],
            [elem.text.strip() for elem in doc.cssselect('h2')])
        # The page features a form that submits to itself.
        self.assertSequenceEqual(
            ['.'],
            [elem.get('action').strip() for elem in doc.cssselect(
                '#content form')])

    def test_delete_user_POST(self):
        # A POST request to the user delete finally deletes the user.
        user = factory.make_user()
        user_id = user.id
        del_link = reverse('accounts-del', args=[user.username])
        response = self.client.post(del_link, {'post': 'yes'})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertItemsEqual([], User.objects.filter(id=user_id))

    def test_view_user(self):
        # The user page feature the basic information about the user.
        user = factory.make_user()
        del_link = reverse('accounts-view', args=[user.username])
        response = self.client.get(del_link)
        doc = fromstring(response.content)
        content_text = doc.cssselect('#content')[0].text_content()
        self.assertIn(user.username, content_text)
        self.assertIn(user.email, content_text)


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
