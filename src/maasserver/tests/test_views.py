# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver API."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from collections import namedtuple
import httplib
import os
import urllib2

from django.conf import settings
from django.conf.urls.defaults import patterns
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from lxml.html import fromstring
from maasserver import views
from maasserver.messages import get_messaging
from maasserver.models import (
    Config,
    NODE_AFTER_COMMISSIONING_ACTION,
    SSHKeys,
    UserProfile,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    LoggedInTestCase,
    TestCase,
    )
from maasserver.urls import (
    get_proxy_longpoll_enabled,
    make_path_relative,
    )
from maasserver.views import (
    get_longpoll_context,
    get_yui_location,
    proxy_to_longpoll,
    )
from maastesting.rabbit import uses_rabbit_fixture


def get_prefixed_form_data(prefix, data):
    result = {'%s-%s' % (prefix, key): value for key, value in data.items()}
    result.update({'%s_submit' % prefix: 1})
    return result


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


class TestProxyView(LoggedInTestCase):
    """Test the (dev) view used to proxy request to a txlongpoll server."""

    def test_proxy_to_longpoll(self):
        # Set LONGPOLL_SERVER_URL (to a random string).
        longpoll_server_url = factory.getRandomString()
        self.patch(settings, 'LONGPOLL_SERVER_URL', longpoll_server_url)

        # Create content of the fake reponse.
        query_string = factory.getRandomString()
        mimetype = factory.getRandomString()
        content = factory.getRandomString()
        status_code = factory.getRandomStatusCode()

        # Monkey patch urllib2.urlopen to make it return a (fake) response
        # with status_code=code, headers.typeheader=mimetype and a
        # 'read' method that will return 'content'.
        def urlopen(url):
            # Assert that urlopen is called on the longpoll url (plus
            # additional parameters taken from the original request's
            # query string).
            self.assertEqual(
                '%s?%s' % (longpoll_server_url, query_string), url)
            FakeProxiedResponse = namedtuple(
                'FakeProxiedResponse', 'code headers read')
            headers = namedtuple('Headers', 'typeheader')(mimetype)
            return FakeProxiedResponse(status_code, headers, lambda: content)
        self.patch(urllib2, 'urlopen', urlopen)

        # Create a fake request.
        request = namedtuple(
            'FakeRequest', ['META'])({'QUERY_STRING': query_string})
        response = proxy_to_longpoll(request)

        self.assertEqual(content, response.content)
        self.assertEqual(mimetype, response['Content-Type'])
        self.assertEqual(status_code, response.status_code)


class TestGetLongpollenabled(TestCase):

    def test_longpoll_not_included_if_LONGPOLL_SERVER_URL_None(self):
        self.patch(settings, 'LONGPOLL_PATH', factory.getRandomString())
        self.patch(settings, 'LONGPOLL_SERVER_URL', None)
        self.assertFalse(get_proxy_longpoll_enabled())

    def test_longpoll_not_included_if_LONGPOLL_PATH_None(self):
        self.patch(settings, 'LONGPOLL_PATH', None)
        self.patch(settings, 'LONGPOLL_SERVER_URL', factory.getRandomString())
        self.assertFalse(get_proxy_longpoll_enabled())

    def test_longpoll_included_if_LONGPOLL_PATH_and_LONGPOLL_SERVER_URL(self):
        self.patch(settings, 'LONGPOLL_PATH', factory.getRandomString())
        self.patch(settings, 'LONGPOLL_SERVER_URL', factory.getRandomString())
        self.assertTrue(get_proxy_longpoll_enabled())


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
        self.patch(views, 'messaging', get_messaging())
        self.assertEqual({}, get_longpoll_context())

    def test_get_longpoll_context_empty_if_longpoll_url_is_None(self):
        self.patch(settings, 'LONGPOLL_PATH', None)
        self.patch(views, 'messaging', get_messaging())
        self.assertEqual({}, get_longpoll_context())

    @uses_rabbit_fixture
    def test_get_longpoll_context(self):
        longpoll = factory.getRandomString()
        self.patch(settings, 'LONGPOLL_PATH', longpoll)
        self.patch(settings, 'RABBITMQ_PUBLISH', True)
        self.patch(views, 'messaging', get_messaging())
        context = get_longpoll_context()
        self.assertItemsEqual(
            ['LONGPOLL_PATH', 'longpoll_queue'], list(context))
        self.assertEqual(longpoll, context['LONGPOLL_PATH'])

    def test_make_path_relative_if_prefix(self):
        url_without_prefix = factory.getRandomString()
        url = '/%s' % url_without_prefix
        self.assertEqual(url_without_prefix, make_path_relative(url))

    def test_make_path_relative_if_no_prefix(self):
        url_without_prefix = factory.getRandomString()
        self.assertEqual(
            url_without_prefix, make_path_relative(url_without_prefix))


class UserPrefsViewTest(LoggedInTestCase):

    def test_prefs_GET_profile(self):
        # The preferences page displays a form with the user's personal
        # information.
        user = self.logged_in_user
        user.last_name = 'Steve Bam'
        user.save()
        response = self.client.get('/account/prefs/')
        doc = fromstring(response.content)
        self.assertSequenceEqual(
            ['Steve Bam'],
            [elem.value for elem in
                doc.cssselect('input#id_profile-last_name')])

    def test_prefs_GET_api(self):
        # The preferences page displays the API access tokens.
        user = self.logged_in_user
        # Create a few tokens.
        for i in range(3):
            user.get_profile().create_authorisation_token()
        response = self.client.get('/account/prefs/')
        doc = fromstring(response.content)
        # The OAuth tokens are displayed.
        for token in user.get_profile().get_authorisation_tokens():
            consumer = token.consumer
            # The token string is a compact representation of the keys.
            token_string = '%s:%s:%s' % (consumer.key, token.key, token.secret)
            self.assertSequenceEqual(
                [token_string],
                [elem.value.strip() for elem in
                    doc.cssselect('input#%s' % token.key)])

    def test_prefs_POST_profile(self):
        # The preferences page allows the user the update its profile
        # information.
        response = self.client.post(
            '/account/prefs/',
            get_prefixed_form_data(
                'profile',
                {
                    'last_name': 'John Doe',
                    'email': 'jon@example.com',
                }))

        self.assertEqual(httplib.FOUND, response.status_code)
        user = User.objects.get(id=self.logged_in_user.id)
        self.assertEqual('John Doe', user.last_name)
        self.assertEqual('jon@example.com', user.email)

    def test_prefs_POST_password(self):
        # The preferences page allows the user to change his password.
        self.logged_in_user.set_password('password')
        old_pw = self.logged_in_user.password
        response = self.client.post(
            '/account/prefs/',
            get_prefixed_form_data(
                'password',
                {
                    'old_password': 'test',
                    'new_password1': 'new',
                    'new_password2': 'new',
                }))

        self.assertEqual(httplib.FOUND, response.status_code)
        user = User.objects.get(id=self.logged_in_user.id)
        # The password is SHA1ized, we just make sure that it has changed.
        self.assertNotEqual(old_pw, user.password)


class AdminLoggedInTestCase(LoggedInTestCase):

    def setUp(self):
        super(AdminLoggedInTestCase, self).setUp()
        # Promote the logged-in user to admin.
        self.logged_in_user.is_superuser = True
        self.logged_in_user.save()


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
        new_provide_dhcp = factory.getRandomBoolean()
        response = self.client.post(
            '/settings/',
            get_prefixed_form_data(
                prefix='maas_and_network',
                data={
                    'maas_name': new_name,
                    'provide_dhcp': new_provide_dhcp,
                }))

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(new_name, Config.objects.get_config('maas_name'))
        self.assertEqual(
            new_provide_dhcp, Config.objects.get_config('provide_dhcp'))

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


class UserManagementTest(AdminLoggedInTestCase):

    def test_add_user_POST(self):
        new_last_name = factory.getRandomString(30)
        new_password = factory.getRandomString()
        new_email = factory.getRandomEmail()
        new_admin_status = factory.getRandomBoolean()
        response = self.client.post(
            reverse('accounts-add'),
            {
                'username': 'my_user',
                'last_name': new_last_name,
                'password1': new_password,
                'password2': new_password,
                'is_superuser': new_admin_status,
                'email': new_email,
            })
        self.assertEqual(httplib.FOUND, response.status_code)
        users = list(User.objects.filter(username='my_user'))
        self.assertEqual(1, len(users))
        self.assertEqual(new_last_name, users[0].last_name)
        self.assertEqual(new_admin_status, users[0].is_superuser)
        self.assertEqual(new_email, users[0].email)
        self.assertTrue(users[0].check_password(new_password))

    def test_edit_user_POST(self):
        user = factory.make_user(username='user')
        user_id = user.id
        new_last_name = factory.getRandomString(30)
        new_admin_status = factory.getRandomBoolean()
        response = self.client.post(
            reverse('accounts-edit', args=['user']),
            {
                'username': 'new_user',
                'last_name': new_last_name,
                'email': 'new_test@example.com',
                'is_superuser': new_admin_status,
            })
        self.assertEqual(httplib.FOUND, response.status_code)
        users = list(User.objects.filter(username='new_user'))
        self.assertEqual(1, len(users))
        self.assertEqual(user_id, users[0].id)
        self.assertEqual(new_last_name, users[0].last_name)
        self.assertEqual(new_admin_status, users[0].is_superuser)

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
        response = self.client.post(
            del_link,
            {
                'post': 'yes',
            })
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertFalse(User.objects.filter(id=user_id).exists())

    def test_view_user(self):
        # The user page feature the basic information about the user.
        user = factory.make_user()
        del_link = reverse('accounts-view', args=[user.username])
        response = self.client.get(del_link)
        doc = fromstring(response.content)
        content_text = doc.cssselect('#content')[0].text_content()
        self.assertIn(user.username, content_text)
        self.assertIn(user.email, content_text)


class SSHKeyServerTest(TestCase):

    def setUp(self):
        super(SSHKeyServerTest, self).setUp()
        self.user = factory.make_user()
        self.sshkey = SSHKeys.objects.create(
            user=self.user.get_profile(),
            key=("ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAYQDmQLTto0BUB2+Ayj9rwuE",
                 "iwd/IyY9YU7qUzqgJBqRp+3FDhZYQqI6aG9sLmPccP+gka1Ia5wlJODpXeu",
                 "cQVqPsKW9Moj/XP1spIuYh6ZrhHElyPB7aPjqoTtpX1+lx6mJU=",
                 "maas@example")
            )

    def test_get_user_sshkey(self):
        response = self.client.get('/accounts/%s/sshkeys/' % self.user)
        self.assertIn(str(self.sshkey.key), response.content)

    def test_get_null_sshkey(self):
        response = self.client.get('/accounts/nulluser/sshkeys/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual('\n'.encode('utf-8'), response.content)
