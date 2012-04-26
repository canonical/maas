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

import httplib
from urlparse import urlparse

from django.conf import settings
from django.core.urlresolvers import reverse
from lxml.html import fromstring
from maasserver import messages
import maasserver.api
from maasserver.enum import (
    NODE_AFTER_COMMISSIONING_ACTION,
    NODE_STATUS,
    )
from maasserver.exceptions import NoRabbit
from maasserver.forms import NodeActionForm
from maasserver.models import Node
from maasserver.testing import (
    get_content_links,
    reload_object,
    reload_objects,
    )
from maasserver.testing.enum import map_enum
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    AdminLoggedInTestCase,
    LoggedInTestCase,
    TestCase,
    )
from maasserver.views import nodes as nodes_views
from maasserver.views.nodes import get_longpoll_context
from maastesting.rabbit import uses_rabbit_fixture
from provisioningserver.enum import POWER_TYPE_CHOICES


class NodeViewsTest(LoggedInTestCase):

    def test_node_list_contains_link_to_node_view(self):
        node = factory.make_node()
        response = self.client.get(reverse('node-list'))
        node_link = reverse('node-view', args=[node.system_id])
        self.assertIn(node_link, get_content_links(response))

    def test_node_list_displays_sorted_list_of_nodes(self):
        # Nodes are sorted on the node list page, newest first.
        nodes = [factory.make_node() for i in range(3)]
        # Explicitely set node.created since all of these node will
        # be created in the same transaction and thus have the same
        # 'created' value by default.
        for node in nodes:
            created = factory.getRandomDate()
            # Update node.created without calling node.save().
            Node.objects.filter(id=node.id).update(created=created)
        nodes = reload_objects(Node, nodes)
        sorted_nodes = sorted(nodes, key=lambda x: x.created, reverse=True)
        response = self.client.get(reverse('node-list'))
        node_links = [
            reverse('node-view', args=[node.system_id])
            for node in sorted_nodes]
        self.assertEqual(
            node_links,
            [link for link in get_content_links(response)
                if link.startswith('/nodes')])

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

    def test_view_node_shows_message_for_commissioning_node(self):
        statuses_with_message = (
            NODE_STATUS.READY, NODE_STATUS.COMMISSIONING)
        help_link = "https://wiki.ubuntu.com/ServerTeam/MAAS/AvahiBoot"
        for status in map_enum(NODE_STATUS).values():
            node = factory.make_node(status=status)
            node_link = reverse('node-view', args=[node.system_id])
            response = self.client.get(node_link)
            links = get_content_links(response, '#flash-messages')
            if status in statuses_with_message:
                self.assertIn(help_link, links)
            else:
                self.assertNotIn(help_link, links)

    def test_admin_can_delete_nodes(self):
        self.become_admin()
        node = factory.make_node()
        node_delete_link = reverse('node-delete', args=[node.system_id])
        response = self.client.post(node_delete_link, {'post': 'yes'})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertFalse(Node.objects.filter(id=node.id).exists())

    def test_allocated_node_view_page_says_node_cannot_be_deleted(self):
        self.become_admin()
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        node_view_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_view_link)
        node_delete_link = reverse('node-delete', args=[node.system_id])

        self.assertEqual(httplib.OK, response.status_code)
        self.assertNotIn(node_delete_link, get_content_links(response))
        self.assertIn(
            "You cannot delete this node because",
            response.content)

    def test_allocated_node_cannot_be_deleted(self):
        self.become_admin()
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        node_delete_link = reverse('node-delete', args=[node.system_id])
        response = self.client.get(node_delete_link)

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

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

    def test_view_node_has_button_to_accept_enlistement_for_user(self):
        # A simple user can't see the button to enlist a declared node.
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        doc = fromstring(response.content)

        self.assertEqual(0, len(doc.cssselect('form#node_actions input')))

    def test_view_node_shows_console_output_if_error_set(self):
        # When node.error is set but the node's status does not indicate an
        # error condition, the contents of node.error are displayed as console
        # output.
        node = factory.make_node(
            owner=self.logged_in_user, error=factory.getRandomString(),
            status=NODE_STATUS.READY)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        console_output = fromstring(response.content).xpath(
            '//h4[text()="Console output"]/following-sibling::span/text()')
        self.assertEqual([node.error], console_output)

    def test_view_node_shows_error_output_if_error_set(self):
        # When node.error is set and the node's status indicates an error
        # condition, the contents of node.error are displayed as error output.
        node = factory.make_node(
            owner=self.logged_in_user, error=factory.getRandomString(),
            status=NODE_STATUS.FAILED_TESTS)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        error_output = fromstring(response.content).xpath(
            '//h4[text()="Error output"]/following-sibling::span/text()')
        self.assertEqual([node.error], error_output)

    def test_view_node_shows_no_error_if_no_error_set(self):
        node = factory.make_node(owner=self.logged_in_user)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        doc = fromstring(response.content)
        content_text = doc.cssselect('#content')[0].text_content()
        self.assertNotIn("Error output", content_text)

    def test_view_node_POST_admin_can_delete_unused_node(self):
        self.become_admin()
        node = factory.make_node(status=NODE_STATUS.READY)
        response = self.client.post(
            reverse('node-view', args=[node.system_id]),
            data={NodeActionForm.input_name: "Delete node"})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(
            reverse('node-delete', args=[node.system_id]),
            urlparse(response['Location']).path)

    def test_view_node_POST_admin_cannot_delete_used_node(self):
        self.become_admin()
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        response = self.client.post(
            reverse('node-view', args=[node.system_id]),
            data={NodeActionForm.input_name: "Delete node"})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_view_node_POST_admin_can_start_commissioning_node(self):
        self.become_admin()
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.post(
            node_link,
            data={
                NodeActionForm.input_name: "Accept & commission",
            })
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(
            NODE_STATUS.COMMISSIONING, reload_object(node).status)

    def test_view_node_POST_admin_can_retry_failed_commissioning(self):
        self.become_admin()
        node = factory.make_node(status=NODE_STATUS.FAILED_TESTS)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.post(
            node_link,
            data={NodeActionForm.input_name: "Retry commissioning"})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(
            NODE_STATUS.COMMISSIONING, reload_object(node).status)

    def perform_action_and_get_node_page(self, node, action_name):
        """POST to perform a node action, then load the resulting page."""
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.post(
            node_link,
            data={
                NodeActionForm.input_name: action_name,
            })
        if response.status_code != httplib.FOUND:
            self.fail(
                "POST failed with code %d: '%s'"
                % (response.status_code, response.content))
        redirect = urlparse(response['Location']).path
        if redirect != node_link:
            self.fail(
                "Odd: POST on %s redirected to %s." % (node_link, redirect))
        return self.client.get(redirect)

    def test_start_commisioning_displays_message(self):
        self.become_admin()
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        response = self.perform_action_and_get_node_page(
            node, "Accept & commission")
        self.assertIn(
            "Node commissioning started.",
            [message.message for message in response.context['messages']])

    def test_start_node_displays_message(self):
        profile = self.logged_in_user.get_profile()
        consumer, token = profile.create_authorisation_token()
        self.patch(maasserver.api, 'get_oauth_token', lambda request: token)
        node = factory.make_node(status=NODE_STATUS.READY)
        response = self.perform_action_and_get_node_page(node, "Start node")
        notices = '\n'.join(
            message.message for message in response.context['messages'])
        self.assertIn("This node is now allocated to you.", notices)
        self.assertIn("asked to start up.", notices)

    def test_start_node_without_auth_returns_Unauthorized(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        response = self.client.post(
            reverse('node-view', args=[node.system_id]),
            data={NodeActionForm.input_name: "Start node"})
        self.assertEqual(httplib.UNAUTHORIZED, response.status_code)


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


class TestGetLongpollContext(TestCase):

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
