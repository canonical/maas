# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
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

import httplib
from operator import attrgetter
from textwrap import dedent
from unittest import skip
from urlparse import (
    parse_qsl,
    urlparse,
    )

from django.conf import settings
from django.core.urlresolvers import reverse
from lxml.etree import XPath
from lxml.html import fromstring
from maasserver import messages
import maasserver.api
from maasserver.enum import (
    ARCHITECTURE_CHOICES,
    NODE_AFTER_COMMISSIONING_ACTION,
    NODE_STATUS,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.exceptions import NoRabbit
from maasserver.forms import NodeActionForm
from maasserver.models import (
    Config,
    MACAddress,
    Node,
    )
from maasserver.node_action import (
    Commission,
    Delete,
    StartNode,
    )
from maasserver.preseed import (
    get_enlist_preseed,
    get_preseed,
    )
from maasserver.testing import (
    extract_redirect,
    get_content_links,
    reload_object,
    reload_objects,
    )
from maasserver.testing.factory import factory
from maasserver.testing.rabbit import uses_rabbit_fixture
from maasserver.testing.testcase import (
    AdminLoggedInTestCase,
    LoggedInTestCase,
    MAASServerTestCase,
    SeleniumLoggedInTestCase,
    )
from maasserver.utils import map_enum
from maasserver.views import nodes as nodes_views
from maasserver.views.nodes import (
    get_longpoll_context,
    message_from_form_stats,
    )
from maastesting.matchers import ContainsAll
from metadataserver.models.commissioningscript import LLDP_OUTPUT_NAME
from provisioningserver.enum import POWER_TYPE_CHOICES


class NodeViewsTest(LoggedInTestCase):

    def set_up_oauth_token(self):
        """Set up an oauth token to be used for requests."""
        profile = self.logged_in_user.get_profile()
        consumer, token = profile.create_authorisation_token()
        self.patch(maasserver.api, 'get_oauth_token', lambda request: token)

    def test_node_list_contains_link_to_node_view(self):
        node = factory.make_node()
        response = self.client.get(reverse('node-list'))
        node_link = reverse('node-view', args=[node.system_id])
        self.assertIn(node_link, get_content_links(response))

    def test_node_list_contains_link_to_enlist_preseed_view(self):
        response = self.client.get(reverse('node-list'))
        enlist_preseed_link = reverse('enlist-preseed-view')
        self.assertIn(enlist_preseed_link, get_content_links(response))

    def test_node_list_contains_column_sort_links(self):
        # Just create a node to have something in the list
        factory.make_node()
        response = self.client.get(reverse('node-list'))
        sort_hostname = '?sort=hostname&dir=asc'
        sort_status = '?sort=status&dir=asc'
        self.assertIn(sort_hostname, get_content_links(response))
        self.assertIn(sort_status, get_content_links(response))

    def test_node_list_ignores_unknown_sort_param(self):
        factory.make_node()
        response = self.client.get(
            reverse('node-list'), {'sort': 'unknown', 'dir': 'asc'})
        # No error: the unknown sorting parameter was ignored.
        self.assertEqual(httplib.OK, response.status_code)

    def test_node_list_lists_nodes_from_different_nodegroups(self):
        # Bug 1084443.
        nodegroup1 = factory.make_node_group()
        nodegroup2 = factory.make_node_group()
        factory.make_node(nodegroup=nodegroup1)
        factory.make_node(nodegroup=nodegroup2)
        factory.make_node(nodegroup=nodegroup2)
        response = self.client.get(reverse('node-list'))
        self.assertEqual(httplib.OK, response.status_code)

    def test_node_list_sorts_by_hostname(self):
        names = ['zero', 'one', 'five']
        nodes = [factory.make_node(hostname=n) for n in names]

        # First check the ascending sort order
        sorted_nodes = sorted(nodes, key=attrgetter('hostname'))
        response = self.client.get(
            reverse('node-list'), {
                'sort': 'hostname',
                'dir': 'asc'})
        node_links = [
            reverse('node-view', args=[node.system_id])
            for node in sorted_nodes
        ]
        self.assertEqual(
            node_links,
            [link for link in get_content_links(response)
                if link.startswith('/nodes/node')])

        # Now check the reverse order
        node_links = list(reversed(node_links))
        response = self.client.get(
            reverse('node-list'), {
                'sort': 'hostname',
                'dir': 'desc'})
        self.assertEqual(
            node_links,
            [link for link in get_content_links(response)
                if link.startswith('/nodes/node')])

    def test_node_list_sorts_by_status(self):
        statuses = {
            NODE_STATUS.READY,
            NODE_STATUS.DECLARED,
            NODE_STATUS.FAILED_TESTS,
            }
        nodes = [factory.make_node(status=s) for s in statuses]

        # First check the ascending sort order
        sorted_nodes = sorted(nodes, key=attrgetter('status'))
        response = self.client.get(
            reverse('node-list'), {
                'sort': 'status',
                'dir': 'asc'})
        node_links = [
            reverse('node-view', args=[node.system_id])
            for node in sorted_nodes
        ]
        self.assertEqual(
            node_links,
            [link for link in get_content_links(response)
                if link.startswith('/nodes/node')])

        # Now check the reverse order
        node_links = list(reversed(node_links))
        response = self.client.get(
            reverse('node-list'), {
                'sort': 'status',
                'dir': 'desc'})
        self.assertEqual(
            node_links,
            [link for link in get_content_links(response)
                if link.startswith('/nodes/node')])

    def test_node_list_sort_preserves_other_params(self):
        # Set a very small page size to save creating lots of nodes
        page_size = 2
        self.patch(nodes_views.NodeListView, 'paginate_by', page_size)

        nodes = []
        tag = factory.make_tag('shiny')
        for name in ('bbb', 'ccc', 'ddd', 'aaa'):
            node = factory.make_node(hostname=name)
            node.tags = [tag]
            nodes.append(node)

        params = {
            'sort': 'hostname',
            'dir': 'asc',
            'page': '1',
            'query': 'maas-tags=shiny',
        }
        response = self.client.get(reverse('node-list'), params)
        document = fromstring(response.content)
        header_links = document.xpath("//div[@id='nodes']/table//th/a/@href")
        fields = iter(('hostname', 'status'))
        field_dirs = iter(('desc', 'asc'))
        for link in header_links:
            self.assertThat(
                parse_qsl(urlparse(link).query),
                ContainsAll([
                    ('page', '1'),
                    ('query', 'maas-tags=shiny'),
                    ('sort', next(fields)),
                    ('dir', next(field_dirs))]))

    def test_node_list_displays_fqdn_dns_not_managed(self):
        nodes = [factory.make_node() for i in range(3)]
        response = self.client.get(reverse('node-list'))
        node_fqdns = [node.fqdn for node in nodes]
        self.assertThat(response.content, ContainsAll(node_fqdns))

    def test_node_list_displays_fqdn_dns_managed(self):
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        nodes = [factory.make_node(nodegroup=nodegroup) for i in range(3)]
        response = self.client.get(reverse('node-list'))
        node_fqdns = [node.fqdn for node in nodes]
        self.assertThat(response.content, ContainsAll(node_fqdns))

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
                if link.startswith('/nodes/node')])

    def test_node_list_num_queries_is_independent_of_num_nodes(self):
        # Listing nodes takes a constant number of database queries,
        # regardless of how many nodes are in the listing.

        def is_node_link(link):
            """Is `link` (from the view's content links) a link to a node?"""
            return link.startswith('/nodes/node')

        def count_node_links(response):
            """Return the number of node links in a response from the view."""
            return len(filter(is_node_link, get_content_links(response)))

        def make_nodes(nodegroup, number):
            """Create `number` new nodes."""
            for counter in range(number):
                factory.make_node(nodegroup=nodegroup, mac=True)

        nodegroup = factory.make_node_group()
        make_nodes(nodegroup, 10)

        url = reverse('node-list')
        num_queries, response = self.getNumQueries(self.client.get, url)
        # Make sure we counted at least the queries to get the nodes, the
        # nodegroup, and the mac addresses.
        self.assertTrue(num_queries > 3)
        self.assertEqual(10, count_node_links(response))

        # Add 10 more nodes.  Should still have the same number of queries.
        make_nodes(nodegroup, 10)
        num_bonus_queries, response = self.getNumQueries(self.client.get, url)
        # We see more nodes, yet the number of queries is unchanged.
        self.assertEqual(20, count_node_links(response))
        self.assertEqual(num_queries, num_bonus_queries)

    def test_view_node_displays_node_info(self):
        # The node page features the basic information about the node.
        node = factory.make_node(owner=self.logged_in_user)
        node.cpu_count = 123
        node.memory = 512
        node.save()
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        doc = fromstring(response.content)
        content_text = doc.cssselect('#content')[0].text_content()
        self.assertIn(node.hostname, content_text)
        self.assertIn(node.display_status(), content_text)
        self.assertIn(node.architecture, content_text)
        self.assertIn('%d MB' % (node.memory,), content_text)
        self.assertIn('%d' % (node.cpu_count,), content_text)
        self.assertIn(self.logged_in_user.username, content_text)

    def test_view_node_contains_tag_names(self):
        node = factory.make_node(owner=self.logged_in_user)
        tag_a = factory.make_tag()
        tag_b = factory.make_tag()
        node.tags.add(tag_a)
        node.tags.add(tag_b)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        doc = fromstring(response.content)
        tag_text = doc.cssselect('#node_tags')[0].text_content()
        self.assertThat(tag_text, ContainsAll([tag_a.name, tag_b.name]))
        self.assertItemsEqual(
            [reverse('tag-view', args=[t.name]) for t in (tag_a, tag_b)],
            [link for link in get_content_links(response)
                if link.startswith('/tags/')])

    def test_view_node_contains_ip_addresses(self):
        node = factory.make_node(owner=self.logged_in_user)
        nodegroup = node.nodegroup
        macs = [
            factory.make_mac_address(node=node).mac_address for i in range(2)]
        ips = [factory.getRandomIPAddress() for i in range(2)]
        for i in range(2):
            factory.make_dhcp_lease(
                nodegroup=nodegroup, mac=macs[i], ip=ips[i])
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        self.assertThat(response.content, ContainsAll(ips))

    def test_view_node_does_not_contain_ip_addresses_if_no_lease(self):
        node = factory.make_node(owner=self.logged_in_user)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        self.assertNotIn("IP addresses", response.content)

    def test_view_node_displays_node_info_no_owner(self):
        # If the node has no owner, the Owner 'slot' does not exist.
        node = factory.make_node()
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        doc = fromstring(response.content)
        content_text = doc.cssselect('#content')[0].text_content()
        self.assertNotIn('Owner', content_text)

    def test_view_node_displays_link_to_view_preseed(self):
        node = factory.make_node(owner=self.logged_in_user)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        node_preseed_link = reverse('node-preseed-view', args=[node.system_id])
        self.assertIn(node_preseed_link, get_content_links(response))

    def test_view_node_displays_no_routers_if_no_routers_discovered(self):
        node = factory.make_node(owner=self.logged_in_user, routers=[])
        node_link = reverse('node-view', args=[node.system_id])

        response = self.client.get(node_link)
        self.assertEqual(httplib.OK, response.status_code)

        doc = fromstring(response.content)
        routers = doc.cssselect('#routers')
        self.assertItemsEqual([], routers)

    def test_view_node_displays_routers_if_any(self):
        router = factory.make_MAC()
        node = factory.make_node(owner=self.logged_in_user, routers=[router])
        node_link = reverse('node-view', args=[node.system_id])

        response = self.client.get(node_link)
        self.assertEqual(httplib.OK, response.status_code)

        doc = fromstring(response.content)
        routers_display = doc.cssselect('#routers')[0].text_content()
        self.assertIn(router.get_raw(), routers_display)

    def test_view_node_separates_routers_by_comma(self):
        routers = [factory.make_MAC(), factory.make_MAC()]
        node = factory.make_node(owner=self.logged_in_user, routers=routers)
        node_link = reverse('node-view', args=[node.system_id])

        response = self.client.get(node_link)
        self.assertEqual(httplib.OK, response.status_code)

        doc = fromstring(response.content)
        routers_display = doc.cssselect('#routers')[0].text_content()
        self.assertIn(
            ', '.join(mac.get_raw() for mac in routers),
            routers_display)

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
        help_link = "https://maas.ubuntu.com/docs/nodes.html"
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

    def test_user_can_view_someone_elses_node(self):
        node = factory.make_node(owner=factory.make_user())
        node_view_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_view_link)
        self.assertEqual(httplib.OK, response.status_code)

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
            'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
            'after_commissioning_action': factory.getRandomEnum(
                NODE_AFTER_COMMISSIONING_ACTION),
        }
        response = self.client.post(node_edit_link, params)

        node = reload_object(node)
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertAttributes(node, params)

    def test_edit_nodes_contains_list_of_macaddresses(self):
        node = factory.make_node(owner=self.logged_in_user)
        macs = [
            unicode(factory.make_mac_address(node=node).mac_address)
            for i in range(3)
        ]
        node_edit_link = reverse('node-edit', args=[node.system_id])
        response = self.client.get(node_edit_link)
        self.assertThat(response.content, ContainsAll(macs))

    def test_edit_nodes_contains_links_to_delete_the_macaddresses(self):
        node = factory.make_node(owner=self.logged_in_user)
        macs = [
            factory.make_mac_address(node=node).mac_address
            for i in range(3)
        ]
        node_edit_link = reverse('node-edit', args=[node.system_id])
        response = self.client.get(node_edit_link)
        self.assertThat(
            response.content,
            ContainsAll(
                [reverse('mac-delete', args=[node.system_id, mac])
                 for mac in macs]))

    def test_edit_nodes_contains_link_to_add_a_macaddresses(self):
        node = factory.make_node(owner=self.logged_in_user)
        node_edit_link = reverse('node-edit', args=[node.system_id])
        response = self.client.get(node_edit_link)
        self.assertIn(
            reverse('mac-add', args=[node.system_id]), response.content)

    def test_view_node_shows_global_kernel_params(self):
        Config.objects.create(name='kernel_opts', value='--test param')
        node = factory.make_node()
        self.assertEqual(
            node.get_effective_kernel_options(),
            (None, "--test param", )
        )

        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        doc = fromstring(response.content)
        kernel_params = doc.cssselect('#node_kernel_opts')[0]
        self.assertEqual('--test param', kernel_params.text.strip())

        details_link = doc.cssselect('a.kernelopts-global-link')[0].get('href')
        self.assertEqual(reverse('settings'), details_link)

    def test_view_node_shows_tag_kernel_params(self):
        tag = factory.make_tag(name='shiny', kernel_opts="--test params")
        node = factory.make_node()
        node.tags = [tag]
        self.assertEqual(
            (tag, '--test params',),
            node.get_effective_kernel_options())

        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        doc = fromstring(response.content)
        kernel_params = doc.cssselect('#node_kernel_opts')[0]
        self.assertEqual('--test params', kernel_params.text.strip())

        details_link = doc.cssselect('a.kernelopts-tag-link')[0].get('href')
        self.assertEqual(reverse('tag-view', args=[tag.name]), details_link)

    def test_view_node_has_button_to_accept_enlistment_for_user(self):
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

    def test_view_node_POST_performs_action(self):
        factory.make_sshkey(self.logged_in_user)
        self.set_up_oauth_token()
        node = factory.make_node(status=NODE_STATUS.READY)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.post(
            node_link, data={NodeActionForm.input_name: StartNode.name})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(NODE_STATUS.ALLOCATED, reload_object(node).status)

    def test_view_node_skips_probed_details_output_if_none_set(self):
        node = factory.make_node(owner=self.logged_in_user)
        node_link = reverse('node-view', args=[node.system_id])

        response = self.client.get(node_link)
        self.assertEqual(httplib.OK, response.status_code)

        doc = fromstring(response.content)
        self.assertItemsEqual([], doc.cssselect('#details-output'))

    def test_view_node_shows_probed_details_output_if_set(self):
        node = factory.make_node(owner=self.logged_in_user)
        lldp_data = "<foo>bar</foo>".encode("utf-8")
        factory.make_node_commission_result(
            node=node, name=LLDP_OUTPUT_NAME, script_result=0, data=lldp_data)
        node_link = reverse('node-view', args=[node.system_id])

        response = self.client.get(node_link)
        self.assertEqual(httplib.OK, response.status_code)

        doc = fromstring(response.content)
        expected_content = dedent("""\
        <list ...xmlns:lldp="lldp"...>
          <lldp:foo>bar</lldp:foo>
        </list>
        """)
        # We expect only one matched element, so this join is
        # defensive, and gives better output on failure.
        observed_content = "\n---\n".join(
            element.text for element in
            doc.cssselect('#details-output > pre'))
        self.assertDocTestMatches(expected_content, observed_content)

    def test_view_node_POST_commission(self):
        self.become_admin()
        node = factory.make_node(status=NODE_STATUS.READY)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.post(
            node_link, data={NodeActionForm.input_name: Commission.name})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(NODE_STATUS.COMMISSIONING, reload_object(node).status)

    def perform_action_and_get_node_page(self, node, action_name):
        """POST to perform a node action, then load the resulting page."""
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.post(
            node_link, data={NodeActionForm.input_name: action_name})
        redirect = extract_redirect(response)
        if redirect != node_link:
            self.fail("Odd: %s redirected to %s." % (node_link, redirect))
        return self.client.get(redirect)

    def test_view_node_POST_action_displays_message(self):
        factory.make_sshkey(self.logged_in_user)
        self.set_up_oauth_token()
        node = factory.make_node(status=NODE_STATUS.READY)
        response = self.perform_action_and_get_node_page(
            node, StartNode.name)
        self.assertIn(
            "This node is now allocated to you.",
            '\n'.join(msg.message for msg in response.context['messages']))

    def test_node_list_query_includes_current(self):
        qs = factory.getRandomString()
        response = self.client.get(reverse('node-list'), {"query": qs})
        query_value = fromstring(response.content).xpath(
            "string(//div[@id='nodes']//input[@name='query']/@value)")
        self.assertIn(qs, query_value)

    def test_node_list_query_error_on_missing_tag(self):
        response = self.client.get(
            reverse('node-list'), {"query": "maas-tags=missing"})
        error_string = fromstring(response.content).xpath(
            "string(//div[@id='nodes']//p[@class='form-errors'])")
        self.assertIn("No such tag(s): 'missing'", error_string)

    def test_node_list_query_error_on_unknown_constraint(self):
        response = self.client.get(
            reverse('node-list'), {"query": "color=red"})
        error_string = fromstring(response.content).xpath(
            "string(//div[@id='nodes']//p[@class='form-errors'])")
        self.assertEqual("color: No such constraint.", error_string.strip())

    def test_node_list_query_selects_subset(self):
        tag = factory.make_tag("shiny")
        node1 = factory.make_node(cpu_count=1)
        node2 = factory.make_node(cpu_count=2)
        node3 = factory.make_node(cpu_count=2)
        node1.tags = [tag]
        node2.tags = [tag]
        node3.tags = []
        response = self.client.get(
            reverse('node-list'), {"query": "maas-tags=shiny cpu=2"})
        node2_link = reverse('node-view', args=[node2.system_id])
        document = fromstring(response.content)
        node_links = document.xpath(
            "//div[@id='nodes']/form/table/tr/td[2]/a/@href")
        self.assertEqual([node2_link], node_links)

    def test_node_list_paginates(self):
        """Node listing is split across multiple pages with links"""
        # Set a very small page size to save creating lots of nodes
        page_size = 2
        self.patch(nodes_views.NodeListView, 'paginate_by', page_size)
        nodes = [
            factory.make_node(created="2012-10-12 12:00:%02d" % i)
            for i in range(page_size * 2 + 1)
        ]
        # Order node links with newest first as the view is expected to
        node_links = [
            reverse('node-view', args=[node.system_id])
            for node in reversed(nodes)
        ]
        expr_node_links = XPath(
            "//div[@id='nodes']/form/table/tr/td[2]/a/@href")
        expr_page_anchors = XPath("//div[@class='pagination']//a")
        # Fetch first page, should link newest two nodes and page 2
        response = self.client.get(reverse('node-list'))
        page1 = fromstring(response.content)
        self.assertEqual(node_links[:page_size], expr_node_links(page1))
        self.assertEqual(
            [("next", "?page=2"), ("last", "?page=3")],
            [(a.text.lower(), a.get("href"))
             for a in expr_page_anchors(page1)])
        # Fetch second page, should link next nodes and adjacent pages
        response = self.client.get(reverse('node-list'), {"page": 2})
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
        response = self.client.get(reverse('node-list'), {"page": 3})
        page3 = fromstring(response.content)
        self.assertEqual(node_links[page_size * 2:], expr_node_links(page3))
        self.assertEqual(
            [("first", "."), ("previous", "?page=2")],
            [(a.text.lower(), a.get("href"))
             for a in expr_page_anchors(page3)])

    def test_node_list_query_paginates(self):
        """Node list query subset is split across multiple pages with links"""
        # Set a very small page size to save creating lots of nodes
        self.patch(nodes_views.NodeListView, 'paginate_by', 2)
        nodes = [
            factory.make_node(created="2012-10-12 12:00:%02d" % i)
            for i in range(10)]
        tag = factory.make_tag("odd")
        for node in nodes[::2]:
            node.tags = [tag]
        last_node_link = reverse('node-view', args=[nodes[0].system_id])
        response = self.client.get(
            reverse('node-list'),
            {"query": "maas-tags=odd", "page": 3})
        document = fromstring(response.content)
        self.assertIn("5 matching nodes", document.xpath("string(//h1)"))
        self.assertEqual(
            [last_node_link],
            document.xpath("//div[@id='nodes']/form/table/tr/td[2]/a/@href"))
        self.assertEqual(
            [
                ("first", "?query=maas-tags%3Dodd"),
                ("previous", "?query=maas-tags%3Dodd&page=2")
            ],
            [
                (a.text.lower(), a.get("href"))
                for a in document.xpath("//div[@class='pagination']//a")
            ])

    def test_node_list_performs_bulk_action(self):
        self.become_admin()
        node1 = factory.make_node()
        node2 = factory.make_node()
        node3 = factory.make_node()
        system_id_to_delete = [node1.system_id, node2.system_id]
        response = self.client.post(
            reverse('node-list'),
            {"action": Delete.name, "system_id": system_id_to_delete})
        redirect = extract_redirect(response)
        response = self.client.get(redirect)
        document = fromstring(response.content)
        self.assertIn("1 node in", document.xpath("string(//h1)"))
        message = (
            'The action "%s" was successfully performed on 2 nodes'
            % Delete.display_bulk)
        self.assertIn(
            message,
            document.xpath(
                "string(//div[@id='body']/ul/li[@class='info'])").strip())
        existing_nodes = list(Node.objects.filter(
            system_id__in=system_id_to_delete))
        node3_system_id = node3.system_id
        self.assertEqual(
            [[], node3.system_id], [existing_nodes, node3_system_id])

    def test_node_list_post_form_preserves_get_params(self):
        factory.make_node()
        params = {
            "dir": "desc",
            "query": factory.make_name("query"),
            "page": "1",
            "sort": factory.make_name(""),
        }
        response = self.client.get(reverse('node-list'), params)
        document = fromstring(response.content)
        [form_action] = document.xpath(
            "//form[@id='node_listing_form']/@action")
        query_string_params = parse_qsl(urlparse(form_action).query)
        self.assertEqual(params.items(), query_string_params)


class NodeListingSelectionJSControls(SeleniumLoggedInTestCase):

    def test_node_list_js_control_select_all(self):
        self.selenium.get(
            '%s%s' % (self.live_server_url, reverse('node-list')))
        master_selector = self.selenium.find_element_by_id(
            'all_system_id_control')
        nodes_selector = self.selenium.find_elements_by_name('system_id')

        # All the checkboxes are initially unselected.
        self.assertFalse(master_selector.is_selected())
        self.assertFalse(nodes_selector[0].is_selected())
        self.assertFalse(nodes_selector[1].is_selected())
        # Select all.
        master_selector.click()
        self.assertTrue(nodes_selector[0].is_selected())
        self.assertTrue(nodes_selector[1].is_selected())
        # Unselect all.
        master_selector.click()
        self.assertFalse(nodes_selector[0].is_selected())
        self.assertFalse(nodes_selector[1].is_selected())
        # Re-select all.
        master_selector.click()
        # Unselect one of the nodes.
        nodes_selector[1].click()
        # The master selector gets unselected.
        self.assertFalse(master_selector.is_selected())
        # Re-select the previously un-selected node.
        nodes_selector[1].click()
        # The master selector gets selected.
        self.assertTrue(master_selector.is_selected())


class NodeProbedDetailsExpanderTest(SeleniumLoggedInTestCase):

    def make_node_with_lldp_output(self):
        node = factory.make_node()
        factory.make_node_commission_result(
            node=node, name=LLDP_OUTPUT_NAME,
            data="<foo>bar</foo>".encode("utf-8"),
            script_result=0)
        return node

    def load_node_page(self, node):
        """Load the given node's page in Selenium."""
        self.selenium.get(
            self.live_server_url + reverse('node-view', args=[node.system_id]))

    def find_content_div(self):
        """Find the details content div in the page Selenium has rendered."""
        return self.selenium.find_element_by_id('details-output')

    def find_button_link(self):
        """Find the details button link in the page Selenium has rendered."""
        return self.selenium.find_element_by_id('details-trigger')

    def find_tag_by_class(self, class_name):
        """Find DOM node by its CSS class."""
        return self.selenium.find_element_by_class_name(class_name)

    def test_details_output_expands(self):
        # Loading just once.  Creating a second node in a separate test causes
        # an integrity error in the database; clearly that's not working too
        # well in a Selenium test case.
        self.load_node_page(self.make_node_with_lldp_output())

        # The ProbedDetails output is in its hidden state.
        self.assertEqual(
            "Show discovered details", self.find_button_link().text)
        self.assertEqual(0, self.find_content_div().size['height'])
        # The button link has the expander-hidden class, meaning that it
        # sports a "collapsed-items" icon.  (There seems to be no way to
        # query the tag's classes directly).
        self.assertEquals(
            self.find_button_link(),
            self.find_tag_by_class('expander-hidden'))

        # When we click the link, the ProbedDetails output expands.
        self.find_button_link().click()

        # The ProbedDetails output is now in its visible state.
        self.assertEqual(
            "Hide discovered details", self.find_button_link().text)
        self.assertNotEqual(0, self.find_content_div().size['height'])
        # The button link has the expander-shown class, meaning that it
        # now sports an "expanded-items" icon.
        self.assertEqual(
            self.find_button_link(),
            self.find_tag_by_class('expander-shown'))


class MessageFromFormStatsTest(MAASServerTestCase):

    def test_message_from_form_stats(self):
        params_and_snippets = [
            (
                (Delete, 0, 1, 1),
                (
                    'could not be performed on 1 node because its state',
                    "could not be performed on 1 node because that action",
                )
            ),
            (
                (Delete, 2, 0, 0),
                ('The action "%s" was successfully performed on 2 nodes'
                 % Delete.display_bulk,),
            ),
            (
                (Delete, 1, 4, 2),
                (
                    'The action "%s" was successfully performed on 1 node'
                    % Delete.display_bulk,
                    'It could not be performed on 4 nodes because their '
                    'state does not allow that action.',
                    "It could not be performed on 2 nodes because that "
                    "action is not permitted on these nodes.",
                ),
            ),
            (
                (Delete, 0, 0, 3),
                ('The action "%s" could not be performed on 3 nodes '
                 "because that action is not permitted on these nodes."
                 % Delete.display_bulk,),
            ),
        ]
        for params, snippets in params_and_snippets:
            message = message_from_form_stats(*params)
            for snippet in snippets:
                self.assertIn(snippet, message)


class NodeEnlistmentPreseedViewTest(LoggedInTestCase):

    def test_enlistpreseedview_displays_preseed_data(self):
        response = self.client.get(reverse('enlist-preseed-view'))
        # Simply test that the preseed looks ok.
        self.assertIn('metadata_url', response.content)

    def test_enlistpreseedview_display_warning_about_url(self):
        response = self.client.get(reverse('enlist-preseed-view'))
        message_chunk = (
            "The URL mentioned in the following enlistment preseed will "
            "be different depending on"
            )
        self.assertIn(message_chunk, response.content)


class NodePreseedViewTest(LoggedInTestCase):

    def test_preseedview_node_displays_preseed_data(self):
        node = factory.make_node(owner=self.logged_in_user)
        node_preseed_link = reverse('node-preseed-view', args=[node.system_id])
        response = self.client.get(node_preseed_link)
        self.assertIn(get_preseed(node), response.content)

    def test_preseedview_node_displays_message_if_commissioning(self):
        node = factory.make_node(
            owner=self.logged_in_user, status=NODE_STATUS.COMMISSIONING,
            )
        node_preseed_link = reverse('node-preseed-view', args=[node.system_id])
        response = self.client.get(node_preseed_link)
        self.assertThat(
            response.content,
            ContainsAll([get_preseed(node), "This node is commissioning."]))

    def test_preseedview_node_displays_link_to_view_node(self):
        node = factory.make_node(owner=self.logged_in_user)
        node_preseed_link = reverse('node-preseed-view', args=[node.system_id])
        response = self.client.get(node_preseed_link)
        node_link = reverse('node-view', args=[node.system_id])
        self.assertIn(node_link, get_content_links(response))

    def test_enlist_preseed_displays_enlist_preseed(self):
        enlist_preseed_link = reverse('enlist-preseed-view')
        response = self.client.get(enlist_preseed_link)
        self.assertIn(get_enlist_preseed(), response.content)


class NodeDeleteMacTest(LoggedInTestCase):

    def test_node_delete_not_found_if_node_does_not_exist(self):
        # This returns a 404 rather than returning to the node page
        # with a nice error message because the node could not be found.
        node_id = factory.getRandomString()
        mac = factory.getRandomMACAddress()
        mac_delete_link = reverse('mac-delete', args=[node_id, mac])
        response = self.client.get(mac_delete_link)
        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_node_delete_redirects_if_mac_does_not_exist(self):
        # If the MAC address does not exist, the user is redirected
        # to the node edit page.
        node = factory.make_node(owner=self.logged_in_user)
        mac = factory.getRandomMACAddress()
        mac_delete_link = reverse('mac-delete', args=[node.system_id, mac])
        response = self.client.get(mac_delete_link)
        self.assertEqual(
            reverse('node-edit', args=[node.system_id]),
            extract_redirect(response))

    def test_node_delete_access_denied_if_user_cannot_edit_node(self):
        node = factory.make_node(owner=factory.make_user())
        mac = factory.make_mac_address(node=node)
        mac_delete_link = reverse('mac-delete', args=[node.system_id, mac])
        response = self.client.get(mac_delete_link)
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_node_delete_mac_contains_mac(self):
        node = factory.make_node(owner=self.logged_in_user)
        mac = factory.make_mac_address(node=node)
        mac_delete_link = reverse('mac-delete', args=[node.system_id, mac])
        response = self.client.get(mac_delete_link)
        self.assertIn(
            'Are you sure you want to delete the MAC address "%s"' %
            mac.mac_address,
            response.content)

    def test_node_delete_mac_POST_deletes_mac(self):
        node = factory.make_node(owner=self.logged_in_user)
        mac = factory.make_mac_address(node=node)
        mac_delete_link = reverse('mac-delete', args=[node.system_id, mac])
        response = self.client.post(mac_delete_link, {'post': 'yes'})
        self.assertEqual(
            reverse('node-edit', args=[node.system_id]),
            extract_redirect(response))
        self.assertFalse(MACAddress.objects.filter(id=mac.id).exists())

    def test_node_delete_mac_POST_displays_message(self):
        node = factory.make_node(owner=self.logged_in_user)
        mac = factory.make_mac_address(node=node)
        mac_delete_link = reverse('mac-delete', args=[node.system_id, mac])
        response = self.client.post(mac_delete_link, {'post': 'yes'})
        redirect = extract_redirect(response)
        response = self.client.get(redirect)
        self.assertEqual(
            ["Mac address %s deleted." % mac.mac_address],
            [message.message for message in response.context['messages']])


class NodeAddMacTest(LoggedInTestCase):

    def test_node_add_mac_contains_form(self):
        node = factory.make_node(owner=self.logged_in_user)
        mac_add_link = reverse('mac-add', args=[node.system_id])
        response = self.client.get(mac_add_link)
        doc = fromstring(response.content)
        self.assertEqual(1, len(doc.cssselect('form input#id_mac_address')))

    def test_node_add_mac_POST_adds_mac(self):
        node = factory.make_node(owner=self.logged_in_user)
        mac_add_link = reverse('mac-add', args=[node.system_id])
        mac = factory.getRandomMACAddress()
        response = self.client.post(mac_add_link, {'mac_address': mac})
        self.assertEqual(
            reverse('node-edit', args=[node.system_id]),
            extract_redirect(response))
        self.assertTrue(
            MACAddress.objects.filter(node=node, mac_address=mac).exists())

    def test_node_add_mac_POST_displays_message(self):
        node = factory.make_node(owner=self.logged_in_user)
        mac_add_link = reverse('mac-add', args=[node.system_id])
        mac = factory.getRandomMACAddress()
        response = self.client.post(mac_add_link, {'mac_address': mac})
        redirect = extract_redirect(response)
        response = self.client.get(redirect)
        self.assertEqual(
            ["MAC address added."],
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
            'architecture': factory.getRandomChoice(ARCHITECTURE_CHOICES),
        }
        response = self.client.post(node_edit_link, params)

        node = reload_object(node)
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertAttributes(node, params)


class TestGetLongpollContext(MAASServerTestCase):

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

    @skip(
        "XXX: GavinPanella 2012-09-27 bug=1057250: Causes test "
        "failures in unrelated parts of the test suite.")
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


class ParseConstraintsTests(MAASServerTestCase):
    """Tests for helper that parses user search text into constraints

    Constraints are checked when evaulated, so the function just needs to
    create some sort of sane output on any input string, rather than raise
    clear errors itself.
    """

    def test_empty(self):
        constraints = nodes_views._parse_constraints("")
        self.assertEqual({}, constraints.dict())

    def test_whitespace_only(self):
        constraints = nodes_views._parse_constraints("  ")
        self.assertEqual({}, constraints.dict())

    def test_leading_whitespace(self):
        constraints = nodes_views._parse_constraints("\tmaas-tags=tag")
        self.assertEqual({"maas-tags": "tag"}, constraints.dict())

    def test_trailing_whitespace(self):
        constraints = nodes_views._parse_constraints("maas-tags=tag\r\n")
        self.assertEqual({"maas-tags": "tag"}, constraints.dict())

    def test_unicode(self):
        constraints = nodes_views._parse_constraints("maas-tags=\xa7")
        self.assertEqual({"maas-tags": "\xa7"}, constraints.dict())

    def test_discards_constraints_with__any__value(self):
        constraints = nodes_views._parse_constraints("maas-name=any")
        self.assertEqual({}, constraints.dict())

    def test_empty_param(self):
        constraints = nodes_views._parse_constraints("arch=")
        self.assertEqual({'arch': ''}, constraints.dict())

    def test_multiple_params(self):
        constraints = nodes_views._parse_constraints("maas-tags=a,b cpu=2")
        self.assertEqual(
            {"cpu": "2", "maas-tags": "a,b"}, constraints.dict())
