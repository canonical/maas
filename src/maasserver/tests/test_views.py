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
from maasserver import (
    messages,
    views,
    )
from maasserver.exceptions import NoRabbit
from maasserver.forms import NodeActionForm
from maasserver.models import (
    Config,
    NODE_AFTER_COMMISSIONING_ACTION,
    NODE_STATUS,
    POWER_TYPE_CHOICES,
    SSHKey,
    UserProfile,
    )
from maasserver.testing import (
    get_data,
    reload_object,
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
    """Prefix entries in a dict of form parameters with a form prefix.

    Also, add a parameter "<prefix>_submit" to indicate that the form with
    the given prefix is being submitted.

    Use this to construct a form submission if the form uses a prefix (as it
    would if there are multiple forms on the page).

    :param prefix: Form prefix string.
    :param data: A dict of form parameters.
    :return: A new dict of prefixed form parameters.
    """
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


class TestLogin(TestCase):

    def test_login_contains_input_tags_if_user(self):
        factory.make_user()
        response = self.client.get('/accounts/login/')
        doc = fromstring(response.content)
        self.assertFalse(response.context['no_users'])
        self.assertEqual(1, len(doc.cssselect('input#id_username')))
        self.assertEqual(1, len(doc.cssselect('input#id_password')))

    def test_login_displays_createsuperuser_message_if_no_user(self):
        path = factory.getRandomString()
        self.patch(settings, 'MAAS_CLI', path)
        response = self.client.get('/accounts/login/')
        self.assertTrue(response.context['no_users'])
        self.assertEqual(path, response.context['create_command'])


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
        self.patch(views, 'messaging', messages.get_messaging())
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
        self.patch(views, 'messaging', messages.get_messaging())
        self.assertEqual({}, get_longpoll_context())

    @uses_rabbit_fixture
    def test_get_longpoll_context(self):
        longpoll = factory.getRandomString()
        self.patch(settings, 'LONGPOLL_PATH', longpoll)
        self.patch(settings, 'RABBITMQ_PUBLISH', True)
        self.patch(views, 'messaging', messages.get_messaging())
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
        params = {
            'last_name': 'John Doe',
            'email': 'jon@example.com',
        }
        response = self.client.post(
            '/account/prefs/', get_prefixed_form_data('profile', params))

        self.assertEqual(httplib.FOUND, response.status_code)
        user = User.objects.get(id=self.logged_in_user.id)
        self.assertAttributes(user, params)

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

    def test_prefs_displays_message_when_no_public_keys_are_configured(self):
        response = self.client.get('/account/prefs/')
        self.assertIn("No SSH key configured.", response.content)

    def test_prefs_displays_add_ssh_key_button(self):
        response = self.client.get('/account/prefs/')
        add_key_link = reverse('prefs-add-sshkey')
        self.assertIn(add_key_link, get_content_links(response))

    def create_keys_for_user(self, user):
        return [factory.make_sshkey(self.logged_in_user) for i in range(3)]

    def test_prefs_displays_compact_representation_of_users_keys(self):
        keys = self.create_keys_for_user(self.logged_in_user)
        response = self.client.get('/account/prefs/')
        for key in keys:
            self.assertIn(key.display_html(), response.content)

    def test_prefs_displays_link_to_delete_ssh_keys(self):
        keys = self.create_keys_for_user(self.logged_in_user)
        response = self.client.get('/account/prefs/')
        links = get_content_links(response)
        for key in keys:
            del_key_link = reverse('prefs-delete-sshkey', args=[key.id])
            self.assertIn(del_key_link, links)


class KeyManagementTest(LoggedInTestCase):

    def test_add_key_GET(self):
        # The 'Add key' page displays a form to add a key.
        response = self.client.get(reverse('prefs-add-sshkey'))
        doc = fromstring(response.content)

        self.assertEqual(1, len(doc.cssselect('textarea#id_key')))
        # The page features a form that submits to itself.
        self.assertSequenceEqual(
            ['.'],
            [elem.get('action').strip() for elem in doc.cssselect(
                '#content form')])

    def test_add_key_POST_adds_key(self):
        key_string = get_data('data/test_rsa.pub')
        response = self.client.post(
            reverse('prefs-add-sshkey'), {'key': key_string})

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertTrue(SSHKey.objects.filter(key=key_string).exists())

    def test_delete_key_GET(self):
        # The 'Delete key' page displays a confirmation page with a form.
        key = factory.make_sshkey(self.logged_in_user)
        del_link = reverse('prefs-delete-sshkey', args=[key.id])
        response = self.client.get(del_link)
        doc = fromstring(response.content)

        self.assertIn(
            "Are you sure you want to delete the following key?",
            response.content)
        # The page features a form that submits to itself.
        self.assertSequenceEqual(
            ['.'],
            [elem.get('action').strip() for elem in doc.cssselect(
                '#content form')])

    def test_delete_key_GET_cannot_access_someoneelses_key(self):
        key = factory.make_sshkey(factory.make_user())
        del_link = reverse('prefs-delete-sshkey', args=[key.id])
        response = self.client.get(del_link)

        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_delete_key_POST(self):
        # A POST request deletes the key.
        key = factory.make_sshkey(self.logged_in_user)
        del_link = reverse('prefs-delete-sshkey', args=[key.id])
        response = self.client.post(del_link, {'post': 'yes'})

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertFalse(SSHKey.objects.filter(id=key.id).exists())


class AdminLoggedInTestCase(LoggedInTestCase):

    def setUp(self):
        super(AdminLoggedInTestCase, self).setUp()
        # Promote the logged-in user to admin.
        self.logged_in_user.is_superuser = True
        self.logged_in_user.save()


def get_content_links(response):
    """Extract links from :class:`HttpResponse` HTML body."""
    doc = fromstring(response.content)
    [content_node] = doc.cssselect('#content')
    return [elem.get('href') for elem in content_node.cssselect('a')]


class NodeViewsTest(LoggedInTestCase):

    def test_node_list_contains_link_to_node_view(self):
        node = factory.make_node()
        response = self.client.get(reverse('node-list'))
        node_link = reverse('node-view', args=[node.system_id])
        self.assertIn(node_link, get_content_links(response))

    def test_view_node_displays_node_info(self):
        # The node page features the basic information about the node.
        node = factory.make_node(owner=self.logged_in_user)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        doc = fromstring(response.content)
        content_text = doc.cssselect('#content')[0].text_content()
        self.assertIn(node.hostname, content_text)
        self.assertIn(node.display_status(), content_text)
        self.assertIn(self.logged_in_user.username, content_text)

    def test_view_node_displays_node_info_no_owner(self):
        # If the node has no owner, the Owner 'slot' does not exist.
        node = factory.make_node()
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        doc = fromstring(response.content)
        content_text = doc.cssselect('#content')[0].text_content()
        self.assertNotIn('Owner', content_text)

    def test_view_node_displays_link_to_edit_if_user_owns_node(self):
        node = factory.make_node(owner=self.logged_in_user)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        node_edit_link = reverse('node-edit', args=[node.system_id])
        self.assertIn(node_edit_link, get_content_links(response))

    def test_view_node_does_not_show_link_to_delete_node(self):
        # Only admin users can delete nodes.
        node = factory.make_node(owner=self.logged_in_user)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        node_delete_link = reverse('node-delete', args=[node.system_id])
        self.assertNotIn(node_delete_link, get_content_links(response))

    def test_user_cannot_delete_node(self):
        node = factory.make_node(owner=self.logged_in_user)
        node_delete_link = reverse('node-delete', args=[node.system_id])
        response = self.client.get(node_delete_link)
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_view_node_shows_link_to_delete_node_for_admin(self):
        self.become_admin()
        node = factory.make_node(owner=factory.make_user())
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        node_delete_link = reverse('node-delete', args=[node.system_id])
        self.assertIn(node_delete_link, get_content_links(response))

    def test_admin_can_delete_nodes(self):
        self.become_admin()
        node = factory.make_node(owner=factory.make_user())
        node_delete_link = reverse('node-delete', args=[node.system_id])
        response = self.client.post(node_delete_link, {'post': 'yes'})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertFalse(User.objects.filter(id=node.id).exists())

    def test_user_cannot_view_someone_elses_node(self):
        node = factory.make_node(owner=factory.make_user())
        node_view_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_view_link)
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_user_cannot_edit_someone_elses_node(self):
        node = factory.make_node(owner=factory.make_user())
        node_edit_link = reverse('node-edit', args=[node.system_id])
        response = self.client.get(node_edit_link)
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_admin_can_view_someonelses_node(self):
        self.become_admin()
        node = factory.make_node(owner=factory.make_user())
        node_view_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_view_link)
        self.assertEqual(httplib.OK, response.status_code)

    def test_admin_can_edit_someonelses_node(self):
        self.become_admin()
        node = factory.make_node(owner=factory.make_user())
        node_edit_link = reverse('node-edit', args=[node.system_id])
        response = self.client.get(node_edit_link)
        self.assertEqual(httplib.OK, response.status_code)

    def test_user_can_access_the_edition_page_for_his_nodes(self):
        node = factory.make_node(owner=self.logged_in_user)
        node_edit_link = reverse('node-edit', args=[node.system_id])
        response = self.client.get(node_edit_link)
        self.assertEqual(httplib.OK, response.status_code)

    def test_user_can_edit_his_nodes(self):
        node = factory.make_node(owner=self.logged_in_user)
        node_edit_link = reverse('node-edit', args=[node.system_id])
        params = {
            'hostname': factory.getRandomString(),
            'after_commissioning_action': factory.getRandomEnum(
                NODE_AFTER_COMMISSIONING_ACTION),
        }
        response = self.client.post(node_edit_link, params)

        node = reload_object(node)
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertAttributes(node, params)

    def test_view_node_admin_has_button_to_accept_enlistement(self):
        self.logged_in_user.is_superuser = True
        self.logged_in_user.save()
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        doc = fromstring(response.content)
        inputs = [
            input for input in doc.cssselect('form#node_actions input')
            if input.name == NodeActionForm.input_name]

        self.assertSequenceEqual(
            ["Accept Enlisted node"], [input.value for input in inputs])

    def test_view_node_POST_admin_can_enlist_node(self):
        self.logged_in_user.is_superuser = True
        self.logged_in_user.save()
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.post(
            node_link,
            data={
                NodeActionForm.input_name: "Accept Enlisted node",
            })

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(
            NODE_STATUS.READY, reload_object(node).status)

    def test_view_node_has_button_to_accept_enlistement_for_user(self):
        # A simple user can't see the button to enlist a declared node.
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        doc = fromstring(response.content)

        self.assertEqual(0, len(doc.cssselect('form#node_actions input')))


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
