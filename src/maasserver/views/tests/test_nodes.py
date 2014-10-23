# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
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

from cgi import escape
import httplib
import logging
from operator import attrgetter
import os
from random import (
    choice,
    randint,
    )
from textwrap import dedent
from unittest import skip
from urlparse import (
    parse_qsl,
    urlparse,
    )

from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import transaction
from django.utils import html
from lxml.etree import XPath
from lxml.html import fromstring
from maasserver import preseed as preseed_module
import maasserver.api
from maasserver.clusterrpc.testing.boot_images import make_rpc_boot_image
from maasserver.enum import (
    NODE_BOOT,
    NODE_STATUS,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.forms import NodeActionForm
from maasserver.models import (
    Config,
    MACAddress,
    Node,
    node as node_module,
    )
from maasserver.node_action import (
    AcquireNode,
    Commission,
    Delete,
    StartNode,
    )
from maasserver.preseed import (
    get_enlist_preseed,
    get_preseed,
    )
from maasserver.rpc.testing.mixins import PreseedRPCMixin
from maasserver.testing import (
    extract_redirect,
    get_content_links,
    )
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.orm import (
    reload_object,
    reload_objects,
    )
from maasserver.testing.testcase import (
    MAASServerTestCase,
    SeleniumTestCase,
    )
from maasserver.third_party_drivers import get_third_party_driver
from maasserver.utils.orm import get_one
from maasserver.views import nodes as nodes_views
from maasserver.views.nodes import (
    message_from_form_stats,
    NodeEventListView,
    NodeView,
    )
from maastesting.djangotestcase import count_queries
from metadataserver.enum import RESULT_TYPE
from metadataserver.models.commissioningscript import (
    LIST_MODALIASES_OUTPUT_NAME,
    LLDP_OUTPUT_NAME,
    )
from provisioningserver.utils.enum import map_enum
from provisioningserver.utils.text import normalise_whitespace
from testtools.matchers import (
    ContainsAll,
    HasLength,
    Not,
    )


def normalize_text(text):
    return ' '.join(text.split())


class TestGenerateJSPowerTypes(MAASServerTestCase):
    def patch_power_types(self, enum):
        """Make `get_power_types` return the given `enum` dict."""
        self.patch(nodes_views, 'get_power_types').return_value = enum

    def test_lists_power_types_as_JS_array(self):
        power_type = factory.make_name('power')
        self.patch_power_types({power_type: power_type})
        self.assertEqual(
            '[\n"%s"\n]' % power_type,
            nodes_views.generate_js_power_types())

    def test_uses_power_type_names_not_descriptions(self):
        name = factory.make_name('name')
        description = factory.make_name('description')
        self.patch_power_types({name: description})
        output = nodes_views.generate_js_power_types()
        self.assertIn(name, output)
        self.assertNotIn(description, output)

    def test_works_with_real_get_power_types(self):
        self.assertIn('ipmi', nodes_views.generate_js_power_types())

    def test_uses_comma_as_item_separator_not_as_terminator(self):
        self.patch(nodes_views, 'get_power_types').return_value = {
            'a': factory.make_name('a'),
            'b': factory.make_name('b'),
            }
        self.assertEqual(
            ['[', '"a",', '"b"', ']'],
            nodes_views.generate_js_power_types().strip().split())

    def test_sorts_entries(self):
        power_types = {
            factory.make_name('power'): factory.make_name('desc')
            for _ in range(3)
            }
        self.patch_power_types(power_types)
        output = nodes_views.generate_js_power_types()
        self.assertEqual(
            sorted(power_types.keys()),
            [
                item.rstrip(',').strip('"\'')
                for item in output.strip('[]').strip().split()
            ])


class NodeViewsTest(MAASServerTestCase):

    def set_up_oauth_token(self):
        """Set up an oauth token to be used for requests."""
        profile = self.logged_in_user.get_profile()
        consumer, token = profile.create_authorisation_token()
        self.patch(maasserver.api, 'get_oauth_token', lambda request: token)

    def test_node_list_contains_link_to_node_view(self):
        self.client_log_in()
        node = factory.make_Node()
        response = self.client.get(reverse('node-list'))
        node_link = reverse('node-view', args=[node.system_id])
        self.assertIn(node_link, get_content_links(response))

    def test_node_list_contains_link_to_enlist_preseed_view(self):
        self.client_log_in()
        response = self.client.get(reverse('node-list'))
        enlist_preseed_link = reverse('enlist-preseed-view')
        self.assertIn(enlist_preseed_link, get_content_links(response))

    def test_node_list_contains_column_sort_links(self):
        # Just create a node to have something in the list
        self.client_log_in()
        factory.make_Node()
        response = self.client.get(reverse('node-list'))
        sort_hostname = '?sort=hostname&dir=asc'
        sort_status = '?sort=status&dir=asc'
        sort_owner = '?sort=owner&dir=asc'
        sort_cpu_count = '?sort=cpu_count&dir=asc'
        sort_memory = '?sort=memory&dir=asc'
        sort_storage = '?sort=storage&dir=asc'
        sort_primary_mac = '?sort=primary_mac&dir=asc'
        sort_zone = '?sort=zone&dir=asc'
        self.assertIn(sort_hostname, get_content_links(response))
        self.assertIn(sort_status, get_content_links(response))
        self.assertIn(sort_owner, get_content_links(response))
        self.assertIn(sort_cpu_count, get_content_links(response))
        self.assertIn(sort_memory, get_content_links(response))
        self.assertIn(sort_storage, get_content_links(response))
        self.assertIn(sort_primary_mac, get_content_links(response))
        self.assertIn(sort_zone, get_content_links(response))

    def test_node_list_ignores_unknown_sort_param(self):
        self.client_log_in()
        factory.make_Node()
        response = self.client.get(
            reverse('node-list'), {'sort': 'unknown', 'dir': 'asc'})
        # No error: the unknown sorting parameter was ignored.
        self.assertEqual(httplib.OK, response.status_code)

    def test_node_list_lists_nodes_from_different_nodegroups(self):
        # Bug 1084443.
        self.client_log_in()
        nodegroup1 = factory.make_NodeGroup()
        nodegroup2 = factory.make_NodeGroup()
        factory.make_Node(nodegroup=nodegroup1)
        factory.make_Node(nodegroup=nodegroup2)
        factory.make_Node(nodegroup=nodegroup2)
        response = self.client.get(reverse('node-list'))
        self.assertEqual(httplib.OK, response.status_code)

    def test_node_list_sorts_by_hostname(self):
        self.client_log_in()
        names = ['zero', 'one', 'five']
        nodes = [factory.make_Node(hostname=n) for n in names]

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
        self.client_log_in()
        statuses = {
            NODE_STATUS.READY,
            NODE_STATUS.NEW,
            NODE_STATUS.FAILED_COMMISSIONING,
            }
        nodes = [factory.make_Node(status=s) for s in statuses]

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

    def test_node_list_sorts_by_zone(self):
        self.client_log_in()
        zones = [factory.make_Zone(sortable_name=True) for _ in range(5)]
        nodes = [factory.make_Node(zone=zone) for zone in zones]

        # We use PostgreSQL's case-insensitive text sorting algorithm.
        sorted_nodes = sorted(
            nodes, key=lambda node: node.zone.name.lower())
        node_links = [
            reverse('node-view', args=[node.system_id])
            for node in sorted_nodes
        ]

        # First check the ascending sort order.
        response = self.client.get(
            reverse('node-list'), {
                'sort': 'zone',
                'dir': 'asc',
            })
        self.assertEqual(
            node_links,
            get_content_links(response, '.node-column'))

        # Now check the reverse order.
        node_links = list(reversed(node_links))
        response = self.client.get(
            reverse('node-list'), {
                'sort': 'zone',
                'dir': 'desc',
            })
        self.assertEqual(
            node_links,
            get_content_links(response, '.node-column'))

    def test_node_list_sort_preserves_other_params(self):
        self.client_log_in()
        # Set a very small page size to save creating lots of nodes
        page_size = 2
        self.patch(nodes_views.NodeListView, 'paginate_by', page_size)

        nodes = []
        tag = factory.make_Tag('shiny')
        for name in ('bbb', 'ccc', 'ddd', 'aaa'):
            node = factory.make_Node(hostname=name)
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
        self.client_log_in()
        nodes = [factory.make_Node() for _ in range(3)]
        response = self.client.get(reverse('node-list'))
        node_fqdns = [node.fqdn for node in nodes]
        self.assertThat(response.content, ContainsAll(node_fqdns))

    def test_node_list_displays_fqdn_dns_managed(self):
        self.client_log_in()
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        nodes = [factory.make_Node(nodegroup=nodegroup) for _ in range(3)]
        response = self.client.get(reverse('node-list'))
        node_fqdns = [node.fqdn for node in nodes]
        self.assertThat(response.content, ContainsAll(node_fqdns))

    def test_node_list_displays_zone(self):
        self.client_log_in()
        node = factory.make_Node()
        response = self.client.get(reverse('node-list'))
        [zone_field] = fromstring(response.content).cssselect('.zone-column')
        self.assertEqual(node.zone.name, zone_field.text_content().strip())

    def test_node_list_links_to_zone(self):
        self.client_log_in()
        node = factory.make_Node()
        response = self.client.get(reverse('node-list'))
        zone_link = reverse('zone-view', args=[node.zone.name])
        self.assertEqual(
            [zone_link],
            get_content_links(response, '.zone-column'))

    def test_node_list_displays_sorted_list_of_nodes(self):
        # Nodes are sorted on the node list page, newest first.
        self.client_log_in()
        nodes = [factory.make_Node() for _ in range(3)]
        # Explicitely set node.created since all of these node will
        # be created in the same transaction and thus have the same
        # 'created' value by default.
        for node in nodes:
            created = factory.make_date()
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
        # XXX: GavinPanella 2014-10-03 bug=1377335
        self.skip("Unreliable; something is causing varying counts.")

        # Listing nodes takes a constant number of database queries,
        # regardless of how many nodes are in the listing.
        self.client_log_in()

        def is_node_link(link):
            """Is `link` (from the view's content links) a link to a node?"""
            return link.startswith('/nodes/node')

        def count_node_links(response):
            """Return the number of node links in a response from the view."""
            return len(filter(is_node_link, get_content_links(response)))

        def make_nodes(nodegroup, number):
            """Create `number` new nodes."""
            for counter in range(number):
                factory.make_Node(nodegroup=nodegroup, mac=True)

        nodegroup = factory.make_NodeGroup()
        make_nodes(nodegroup, 10)

        url = reverse('node-list')
        num_queries, response = count_queries(self.client.get, url)
        # Make sure we counted at least the queries to get the nodes, the
        # nodegroup, and the mac addresses.
        self.assertTrue(num_queries > 3)
        self.assertEqual(10, count_node_links(response))

        # Add 10 more nodes.  Should still have the same number of queries.
        make_nodes(nodegroup, 10)
        num_bonus_queries, response = count_queries(self.client.get, url)
        # We see more nodes, yet the number of queries is unchanged.
        self.assertEqual(20, count_node_links(response))
        self.assertEqual(num_queries, num_bonus_queries)

    def test_view_node_displays_node_info(self):
        # The node page features the basic information about the node.
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
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
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        tag_a = factory.make_Tag()
        tag_b = factory.make_Tag()
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
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user, disable_ipv4=False)
        nodegroup = node.nodegroup
        macs = [
            factory.make_MACAddress(node=node).mac_address
            for _ in range(2)
            ]
        ips = [factory.make_ipv4_address() for _ in range(2)]
        for mac, ip in zip(macs, ips):
            factory.make_DHCPLease(nodegroup=nodegroup, mac=mac, ip=ip)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        self.assertThat(response.content, ContainsAll(ips))

    def test_view_node_does_not_contain_ip_addresses_if_no_lease(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user, disable_ipv4=False)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        self.assertNotIn("IP addresses", response.content)

    def test_view_node_warns_about_unconfigured_IPv6_addresses(self):
        self.client_log_in()
        ipv6_network = factory.make_ipv6_network()
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            owner=self.logged_in_user, network=ipv6_network,
            osystem='windows')
        factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_network(ipv6_network),
            mac=node.get_primary_mac())
        node_link = reverse('node-view', args=[node.system_id])
        page = fromstring(self.client.get(node_link).content)
        [addresses_section] = page.cssselect('#ip-addresses')
        self.expectThat(
            addresses_section.cssselect('#unconfigured-ips-warning'),
            Not(HasLength(0)))

    def test_view_node_does_not_warn_if_no_unconfigured_IPv6_addresses(self):
        self.client_log_in()
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            owner=self.logged_in_user)
        factory.make_StaticIPAddress(mac=node.get_primary_mac())
        node_link = reverse('node-view', args=[node.system_id])
        page = fromstring(self.client.get(node_link).content)
        [addresses_section] = page.cssselect('#ip-addresses')
        self.assertEqual(
            [],
            addresses_section.cssselect('#unconfigured-ip-warning'))

    def test_view_node_displays_node_info_no_owner(self):
        # If the node has no owner, the Owner 'slot' does not exist.
        self.client_log_in()
        node = factory.make_Node()
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        doc = fromstring(response.content)
        content_text = doc.cssselect('#content')[0].text_content()
        self.assertNotIn('Owner', content_text)

    def test_view_node_displays_link_to_view_preseed(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        node_preseed_link = reverse('node-preseed-view', args=[node.system_id])
        self.assertIn(node_preseed_link, get_content_links(response))

    def test_view_node_displays_no_routers_if_no_routers_discovered(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user, routers=[])
        node_link = reverse('node-view', args=[node.system_id])

        response = self.client.get(node_link)
        self.assertEqual(httplib.OK, response.status_code)

        doc = fromstring(response.content)
        routers = doc.cssselect('#routers')
        self.assertItemsEqual([], routers)

    def test_view_node_displays_routers_if_any(self):
        self.client_log_in()
        router = factory.make_MAC()
        node = factory.make_Node(owner=self.logged_in_user, routers=[router])
        node_link = reverse('node-view', args=[node.system_id])

        response = self.client.get(node_link)
        self.assertEqual(httplib.OK, response.status_code)

        doc = fromstring(response.content)
        routers_display = doc.cssselect('#routers')[0].text_content()
        self.assertIn(router.get_raw(), routers_display)

    def test_view_node_separates_routers_by_comma(self):
        self.client_log_in()
        routers = [factory.make_MAC(), factory.make_MAC()]
        node = factory.make_Node(owner=self.logged_in_user, routers=routers)
        node_link = reverse('node-view', args=[node.system_id])

        response = self.client.get(node_link)
        self.assertEqual(httplib.OK, response.status_code)

        doc = fromstring(response.content)
        routers_display = doc.cssselect('#routers')[0].text_content()
        self.assertIn(
            ', '.join(mac.get_raw() for mac in routers),
            routers_display)

    def test_view_node_links_to_physical_zone(self):
        self.client_log_in()
        node = factory.make_Node()
        node_link = reverse('node-view', args=[node.system_id])

        response = self.client.get(node_link)
        self.assertEqual(httplib.OK, response.status_code)

        [zone_section] = fromstring(response.content).cssselect('#zone')
        self.assertThat(
            zone_section.text_content(),
            ContainsAll(["Physical zone", node.zone.name]))
        self.assertEqual(
            [reverse('zone-view', args=[node.zone.name])],
            get_content_links(response, '#zone'))

    def test_view_node_shows_macs(self):
        self.client_log_in()
        mac = factory.make_MACAddress()

        response = self.client.get(
            reverse('node-view', args=[mac.node.system_id]))
        self.assertEqual(httplib.OK, response.status_code)

        [interfaces_section] = fromstring(response.content).cssselect(
            '#network-interfaces')
        [listing] = get_one(interfaces_section.cssselect('span'))
        self.assertEqual(mac.mac_address, listing.text_content().strip())

    def test_view_node_lists_macs_as_list_items(self):
        self.client_log_in()
        node = factory.make_Node()
        factory.make_MACAddress('11:11:11:11:11:11', node=node)
        factory.make_MACAddress('22:22:22:22:22:22', node=node)

        response = self.client.get(reverse('node-view', args=[node.system_id]))
        self.assertEqual(httplib.OK, response.status_code)

        [interfaces_section] = fromstring(response.content).cssselect(
            '#network-interfaces')
        [interfaces_list] = interfaces_section.cssselect('ul')
        interfaces = interfaces_list.cssselect('li')
        self.assertEqual(
            ['11:11:11:11:11:11', '22:22:22:22:22:22'],
            [interface.text_content().strip() for interface in interfaces])

    def test_view_node_links_network_interfaces_to_networks(self):
        self.client_log_in()
        network = factory.make_Network()
        mac = factory.make_MACAddress(networks=[network])

        response = self.client.get(
            reverse('node-view', args=[mac.node.system_id]))
        self.assertEqual(httplib.OK, response.status_code)

        [interfaces_section] = fromstring(response.content).cssselect(
            '#network-interfaces')
        [interfaces_list] = interfaces_section.cssselect('ul')
        [interface] = interfaces_list.cssselect('li')
        self.assertEqual(
            "%s (on %s)" % (mac.mac_address, network.name),
            normalise_whitespace(interface.text_content()))
        [link] = interface.cssselect('a')
        self.assertEqual(network.name, link.text_content().strip())
        self.assertEqual(
            reverse('network-view', args=[network.name]),
            link.get('href'))

    def test_view_node_sorts_networks_by_name(self):
        self.client_log_in()
        networks = factory.make_Networks(3, sortable_name=True)
        mac = factory.make_MACAddress(networks=networks)

        response = self.client.get(
            reverse('node-view', args=[mac.node.system_id]))
        self.assertEqual(httplib.OK, response.status_code)

        sorted_names = sorted(network.name for network in networks)
        [interfaces_section] = fromstring(response.content).cssselect(
            '#network-interfaces')
        [interfaces_list] = interfaces_section.cssselect('ul')
        [interface] = interfaces_list.cssselect('li')
        self.assertEqual(
            "%s (on %s)" % (mac.mac_address, ', '.join(sorted_names)),
            normalise_whitespace(interface.text_content()))

    def test_view_node_displays_link_to_edit_if_user_owns_node(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        node_edit_link = reverse('node-edit', args=[node.system_id])
        self.assertIn(node_edit_link, get_content_links(response))

    def test_view_node_does_not_show_link_to_delete_node(self):
        # Only admin users can delete nodes.
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        node_delete_link = reverse('node-delete', args=[node.system_id])
        self.assertNotIn(node_delete_link, get_content_links(response))

    def test_user_cannot_delete_node(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        node_delete_link = reverse('node-delete', args=[node.system_id])
        response = self.client.get(node_delete_link)
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_view_node_shows_message_for_commissioning_node(self):
        self.client_log_in()
        statuses_with_message = (
            NODE_STATUS.READY, NODE_STATUS.COMMISSIONING)
        help_link = "https://maas.ubuntu.com/docs/nodes.html"
        for status in map_enum(NODE_STATUS).values():
            node = factory.make_Node(status=status)
            node_link = reverse('node-view', args=[node.system_id])
            response = self.client.get(node_link)
            links = get_content_links(response, '#flash-messages')
            if status in statuses_with_message:
                self.assertIn(help_link, links)
            else:
                self.assertNotIn(help_link, links)

    def test_admin_can_delete_nodes(self):
        self.client_log_in(as_admin=True)
        node = factory.make_Node()
        node_delete_link = reverse('node-delete', args=[node.system_id])
        response = self.client.post(node_delete_link, {'post': 'yes'})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertFalse(Node.objects.filter(id=node.id).exists())

    def test_allocated_node_view_page_says_node_cannot_be_deleted(self):
        self.client_log_in(as_admin=True)
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        node_view_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_view_link)
        node_delete_link = reverse('node-delete', args=[node.system_id])

        self.assertEqual(httplib.OK, response.status_code)
        self.assertNotIn(node_delete_link, get_content_links(response))
        self.assertIn(
            "You cannot delete this node because",
            response.content)

    def test_allocated_node_cannot_be_deleted(self):
        self.client_log_in(as_admin=True)
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        node_delete_link = reverse('node-delete', args=[node.system_id])
        response = self.client.get(node_delete_link)

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_user_can_view_someone_elses_node(self):
        self.client_log_in()
        node = factory.make_Node(owner=factory.make_User())
        node_view_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_view_link)
        self.assertEqual(httplib.OK, response.status_code)

    def test_user_cannot_edit_someone_elses_node(self):
        self.client_log_in()
        node = factory.make_Node(owner=factory.make_User())
        node_edit_link = reverse('node-edit', args=[node.system_id])
        response = self.client.get(node_edit_link)
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_admin_can_view_someonelses_node(self):
        self.client_log_in(as_admin=True)
        node = factory.make_Node(owner=factory.make_User())
        node_view_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_view_link)
        self.assertEqual(httplib.OK, response.status_code)

    def test_admin_can_edit_someonelses_node(self):
        self.client_log_in(as_admin=True)
        node = factory.make_Node(owner=factory.make_User())
        node_edit_link = reverse('node-edit', args=[node.system_id])
        response = self.client.get(node_edit_link)
        self.assertEqual(httplib.OK, response.status_code)

    def test_user_can_access_the_edition_page_for_his_nodes(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        node_edit_link = reverse('node-edit', args=[node.system_id])
        response = self.client.get(node_edit_link)
        self.assertEqual(httplib.OK, response.status_code)

    def test_user_can_edit_his_nodes(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        node_edit_link = reverse('node-edit', args=[node.system_id])
        params = {
            'hostname': factory.make_string(),
            'architecture': make_usable_architecture(self),
        }
        response = self.client.post(node_edit_link, params)

        node = reload_object(node)
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertAttributes(node, params)

    def test_user_can_change_disable_ipv4_flag(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user, disable_ipv4=True)
        node_edit_link = reverse('node-edit', args=[node.system_id])
        params = {
            'hostname': factory.make_string(),
            'architecture': make_usable_architecture(self),
            'ui_submission': True,
            # Omitting the 'disable_ipv4' parameters means setting it
            # to false because this is a UI submission.
        }
        response = self.client.post(node_edit_link, params)

        node = reload_object(node)
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(False, node.disable_ipv4)

    def test_edit_nodes_contains_list_of_macaddresses(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        macs = [
            unicode(factory.make_MACAddress(node=node).mac_address)
            for _ in range(3)
        ]
        node_edit_link = reverse('node-edit', args=[node.system_id])
        response = self.client.get(node_edit_link)
        self.assertThat(response.content, ContainsAll(macs))

    def test_edit_nodes_contains_links_to_delete_the_macaddresses(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        macs = [
            factory.make_MACAddress(node=node).mac_address
            for _ in range(3)
        ]
        node_edit_link = reverse('node-edit', args=[node.system_id])
        response = self.client.get(node_edit_link)
        self.assertThat(
            response.content,
            ContainsAll(
                [reverse('mac-delete', args=[node.system_id, mac])
                 for mac in macs]))

    def test_edit_nodes_contains_link_to_add_a_macaddresses(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        node_edit_link = reverse('node-edit', args=[node.system_id])
        response = self.client.get(node_edit_link)
        self.assertIn(
            reverse('mac-add', args=[node.system_id]), response.content)

    def test_view_node_shows_global_kernel_params(self):
        self.client_log_in()
        Config.objects.create(name='kernel_opts', value='--test param')
        node = factory.make_Node()
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
        self.client_log_in()
        tag = factory.make_Tag(name='shiny', kernel_opts="--test params")
        node = factory.make_Node()
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
        self.client_log_in()
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        doc = fromstring(response.content)

        self.assertEqual(0, len(doc.cssselect('form#node_actions input')))

    def test_view_node_shows_console_output_if_error_set(self):
        # When node.error is set but the node's status does not indicate an
        # error condition, the contents of node.error are displayed as console
        # output.
        self.client_log_in()
        node = factory.make_Node(
            owner=self.logged_in_user, error=factory.make_string(),
            status=NODE_STATUS.READY)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        console_output = fromstring(response.content).xpath(
            '//h4[text()="Console output"]/following-sibling::span/text()')
        self.assertEqual([node.error], console_output)

    def test_view_node_shows_error_output_if_error_set(self):
        # When node.error is set and the node's status indicates an error
        # condition, the contents of node.error are displayed as error output.
        self.client_log_in()
        node = factory.make_Node(
            owner=self.logged_in_user, error=factory.make_string(),
            status=NODE_STATUS.FAILED_COMMISSIONING)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        error_output = fromstring(response.content).xpath(
            '//h4[text()="Error output"]/following-sibling::span/text()')
        self.assertEqual([node.error], error_output)

    def test_view_node_shows_no_error_if_no_error_set(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        doc = fromstring(response.content)
        content_text = doc.cssselect('#content')[0].text_content()
        self.assertNotIn("Error output", content_text)

    def test_view_node_POST_performs_action(self):
        # Don't start the monitoring thread.
        self.patch(node_module, "getClientFor")

        # Stub-out real-world RPC calls.
        self.patch(node_module, "update_host_maps").return_value = []
        self.patch(node_module, "power_on_nodes").return_value = {}

        self.client_log_in()
        factory.make_SSHKey(self.logged_in_user)
        self.set_up_oauth_token()
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            status=NODE_STATUS.ALLOCATED, power_type='ether_wake',
            owner=self.logged_in_user)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.post(
            node_link, data={NodeActionForm.input_name: StartNode.name})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(NODE_STATUS.DEPLOYING, reload_object(node).status)

    def test_view_node_skips_probed_details_output_if_none_set(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        node_link = reverse('node-view', args=[node.system_id])

        response = self.client.get(node_link)
        self.assertEqual(httplib.OK, response.status_code)

        doc = fromstring(response.content)
        self.assertItemsEqual([], doc.cssselect('#details-output'))

    def test_view_node_shows_probed_details_xml_output_if_set(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        lldp_data = "<foo>bar</foo>".encode("utf-8")
        factory.make_NodeResult_for_commissioning(
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
            doc.cssselect('#xml > pre'))
        self.assertDocTestMatches(expected_content, observed_content)

    def test_view_node_shows_probed_details_yaml_output_if_set(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        lldp_data = "<foo>bar</foo>".encode("utf-8")
        factory.make_NodeResult_for_commissioning(
            node=node, name=LLDP_OUTPUT_NAME, script_result=0, data=lldp_data)
        node_link = reverse('node-view', args=[node.system_id])

        response = self.client.get(node_link)
        self.assertEqual(httplib.OK, response.status_code)

        doc = fromstring(response.content)
        expected_content = dedent("""\
        - list:
          - lldp:foo:
            bar
        """)
        # We expect only one matched element, so this join is
        # defensive, and gives better output on failure.
        observed_content = "\n---\n".join(
            element.text for element in
            doc.cssselect('#yaml > pre'))
        self.assertDocTestMatches(expected_content, observed_content)

    def test_view_node_POST_commission(self):
        self.client_log_in(as_admin=True)
        node = factory.make_Node(status=NODE_STATUS.READY)
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
        self.client_log_in()
        factory.make_SSHKey(self.logged_in_user)
        self.set_up_oauth_token()
        node = factory.make_Node(status=NODE_STATUS.READY)
        response = self.perform_action_and_get_node_page(
            node, AcquireNode.name)
        self.assertIn(
            "This node is now allocated to you.",
            '\n'.join(msg.message for msg in response.context['messages']))

    def test_node_list_query_includes_current(self):
        self.client_log_in()
        qs = factory.make_string()
        response = self.client.get(reverse('node-list'), {"query": qs})
        query_value = fromstring(response.content).xpath(
            "string(//div[@id='nodes']//input[@name='query']/@value)")
        self.assertIn(qs, query_value)

    def test_node_list_query_error_on_missing_tag(self):
        self.client_log_in()
        response = self.client.get(
            reverse('node-list'), {"query": "maas-tags=missing"})
        error_string = fromstring(response.content).xpath(
            "string(//div[@id='nodes']//p[@class='form-errors'])")
        self.assertIn("No such tag(s): 'missing'", error_string)

    def test_node_list_query_error_on_unknown_constraint(self):
        self.client_log_in()
        response = self.client.get(
            reverse('node-list'), {"query": "color=red"})
        error_string = fromstring(response.content).xpath(
            "string(//div[@id='nodes']//p[@class='form-errors'])")
        self.assertEqual("color: No such constraint.", error_string.strip())

    def test_node_list_query_selects_subset(self):
        self.client_log_in()
        tag = factory.make_Tag("shiny")
        node1 = factory.make_Node(cpu_count=1)
        node2 = factory.make_Node(cpu_count=2)
        node3 = factory.make_Node(cpu_count=2)
        node1.tags = [tag]
        node2.tags = [tag]
        node3.tags = []
        response = self.client.get(
            reverse('node-list'), {"query": "maas-tags=shiny cpu=2"})
        node2_link = reverse('node-view', args=[node2.system_id])
        document = fromstring(response.content)
        node_links = document.xpath(
            "//div[@id='nodes']/form/table/tr/td[3]/a/@href")
        self.assertEqual([node2_link], node_links)

    def test_node_list_paginates(self):
        """Node listing is split across multiple pages with links"""
        self.client_log_in()
        # Set a very small page size to save creating lots of nodes
        page_size = 2
        self.patch(nodes_views.NodeListView, 'paginate_by', page_size)
        nodes = [
            factory.make_Node(created="2012-10-12 12:00:%02d" % i)
            for i in range(page_size * 2 + 1)
        ]
        # Order node links with newest first as the view is expected to
        node_links = [
            reverse('node-view', args=[node.system_id])
            for node in reversed(nodes)
        ]
        expr_node_links = XPath(
            "//div[@id='nodes']/form/table/tr/td[3]/a/@href")
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
        self.client_log_in()
        # Set a very small page size to save creating lots of nodes
        self.patch(nodes_views.NodeListView, 'paginate_by', 2)
        nodes = [
            factory.make_Node(created="2012-10-12 12:00:%02d" % i)
            for i in range(10)]
        tag = factory.make_Tag("odd")
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
            document.xpath("//div[@id='nodes']/form/table/tr/td[3]/a/@href"))
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
        self.client_log_in(as_admin=True)
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        node3 = factory.make_Node()
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
                "string(//div[@id='body']/div/div/"
                "ul/li[@class='info'])").strip())
        existing_nodes = list(Node.objects.filter(
            system_id__in=system_id_to_delete))
        node3_system_id = node3.system_id
        self.assertEqual(
            [[], node3.system_id], [existing_nodes, node3_system_id])

    def test_node_list_post_form_preserves_get_params(self):
        self.client_log_in()
        factory.make_Node()
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

    def test_node_list_view_shows_third_party_drivers_warning(self):
        self.client_log_in()
        factory.make_Node()
        Config.objects.set_config(
            name='enable_third_party_drivers', value=True)
        response = self.client.get(reverse('node-list'))
        document = fromstring(response.content)
        self.assertIn(
            nodes_views.construct_third_party_drivers_notice(False).strip(),
            document.xpath(
                "string(//div[@id='body']/div/div/"
                "ul/li[@class='info'])").strip())

    def test_node_list_view_shows_third_party_drivers_admin_warning(self):
        self.client_log_in(as_admin=True)
        factory.make_Node()
        Config.objects.set_config(
            name='enable_third_party_drivers', value=True)
        response = self.client.get(reverse('node-list'))
        # We'll check in response.content directly here. It's not ideal
        # but using fromstring() strips out the link-y goodness and
        # causes the test to fail.
        self.assertIn(
            nodes_views.construct_third_party_drivers_notice(True).strip(),
            response.content)

    def test_node_list_view_hides_drivers_warning_if_drivers_disabled(self):
        self.client_log_in()
        factory.make_Node()
        Config.objects.set_config(
            name='enable_third_party_drivers', value=False)
        response = self.client.get(reverse('node-list'))
        self.assertNotIn(
            nodes_views.construct_third_party_drivers_notice(False).strip(),
            response.content)

    def test_node_view_hides_third_party_drivers_section_if_no_drivers(self):
        self.client_log_in()
        Config.objects.set_config(
            name='enable_third_party_drivers', value=True)
        node = factory.make_Node(status=NODE_STATUS.READY)
        response = self.client.get(reverse('node-view', args=[node.system_id]))
        self.assertNotIn("Third Party Drivers", response.content)

    def test_node_view_shows_third_party_drivers(self):
        self.client_log_in()
        Config.objects.set_config(
            name='enable_third_party_drivers', value=True)
        node = factory.make_Node(status=NODE_STATUS.READY)
        data = "pci:v00001590d00000047sv00001590sd00000047bc*sc*i*"
        factory.make_NodeResult_for_commissioning(
            node=node, name=LIST_MODALIASES_OUTPUT_NAME, script_result=0,
            data=data.encode("utf-8"))
        response = self.client.get(reverse('node-view', args=[node.system_id]))
        document = fromstring(response.content)
        driver = get_third_party_driver(node)
        self.assertIn(
            "%s (%s)" % (driver['module'], driver['comment']),
            document.xpath("string(//span[@id='third_party_drivers'])"))

    def test_node_view_hides_drivers_section_if_drivers_disabled(self):
        self.client_log_in()
        Config.objects.set_config(
            name='enable_third_party_drivers', value=False)
        node = factory.make_Node(status=NODE_STATUS.READY)
        data = "pci:v00001590d00000047sv00001590sd00000047bc*sc*i*"
        factory.make_NodeResult_for_commissioning(
            node=node, name=LIST_MODALIASES_OUTPUT_NAME, script_result=0,
            data=data.encode("utf-8"))
        response = self.client.get(reverse('node-view', args=[node.system_id]))
        self.assertNotIn("Third Party Drivers", response.content)

    def test_node_view_show_latest_node_events(self):
        self.client_log_in()
        node = factory.make_Node()
        # Create old events.
        [
            factory.make_Event(
                node=node, type=factory.make_EventType(
                    level=logging.INFO))
            for _ in range(4)
        ]
        # Create NodeView.number_of_events_shown events.
        events = [
            factory.make_Event(
                node=node, type=factory.make_EventType(
                    level=logging.INFO))
            for _ in range(NodeView.number_of_events_shown)
        ]
        response = self.client.get(reverse('node-view', args=[node.system_id]))
        self.assertIn("Latest node events", response.content.decode('utf8'))
        document = fromstring(response.content)
        events_displayed = document.xpath(
            "//div[@id='node_event_list']//td[@class='event_description']")
        self.assertItemsEqual(
            [
                event.type.description + ' \u2014 ' + event.description
                for event in events
            ],
            [
                normalize_text(display.text_content())
                for display in events_displayed
            ]
        )

    def test_node_view_doesnt_show_events_with_debug_level(self):
        self.client_log_in()
        node = factory.make_Node()
        # Create an event with debug level
        event = factory.make_Event(
            node=node, type=factory.make_EventType(
                level=logging.DEBUG))
        response = self.client.get(
            reverse('node-view', args=[node.system_id]))
        self.assertIn("Latest node events", response.content)
        document = fromstring(response.content)
        events_displayed = document.xpath("//div[@id='node_event_list']")
        self.assertNotIn(
            event.type.description,
            events_displayed[0].text_content().strip(),
        )

    def test_node_view_doesnt_show_events_from_other_nodes(self):
        self.client_log_in()
        node = factory.make_Node()
        # Create an event related to another node.
        event = factory.make_Event()
        response = self.client.get(
            reverse('node-view', args=[node.system_id]))
        self.assertIn("Latest node events", response.content)
        document = fromstring(response.content)
        events_displayed = document.xpath("//div[@id='node_event_list']")
        self.assertNotIn(
            event.type.description,
            events_displayed[0].text_content().strip(),
        )

    def test_node_view_links_to_node_event_log(self):
        self.client_log_in()
        node = factory.make_Node()
        factory.make_Event(node=node)
        response = self.client.get(
            reverse('node-view', args=[node.system_id]))
        self.assertIn("Latest node events", response.content.decode('utf8'))
        document = fromstring(response.content)
        [events_section] = document.xpath("//li[@id='node-events']")
        self.assertIn(
            "Full node event log (1 event).",
            ' '.join(events_section.text_content().split()))

    def test_node_view_pluralises_link_to_node_event_log(self):
        self.client_log_in()
        node = factory.make_Node()
        num_events = randint(2, 3)
        for _ in range(num_events):
            factory.make_Event(node=node)
        response = self.client.get(
            reverse('node-view', args=[node.system_id]))
        self.assertIn("Latest node events", response.content.decode('utf8'))
        document = fromstring(response.content)
        [events_section] = document.xpath("//li[@id='node-events']")
        self.assertIn(
            "Full node event log (%d events)." % num_events,
            ' '.join(events_section.text_content().split()))

    def test_node_view_contains_link_to_node_event_log(self):
        self.client_log_in()
        node = factory.make_Node()
        # Create an event related to another node.
        [
            factory.make_Event(node=node)
            for _ in range(4)
        ]
        response = self.client.get(
            reverse('node-view', args=[node.system_id]))
        node_event_list = reverse(
            'node-event-list-view', args=[node.system_id])
        self.assertIn(node_event_list, get_content_links(response))


class TestWarnUnconfiguredIPAddresses(MAASServerTestCase):

    def test__warns_for_IPv6_address_on_non_ubuntu_OS(self):
        network = factory.make_ipv6_network()
        osystem = choice(['windows', 'centos', 'suse'])
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            osystem=osystem, network=network)
        factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_network(network), mac=node.get_primary_mac())
        self.assertTrue(NodeView().warn_unconfigured_ip_addresses(node))

    def test__warns_for_IPv6_address_on_debian_installer(self):
        network = factory.make_ipv6_network()
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            osystem='ubuntu', network=network, boot_type=NODE_BOOT.DEBIAN)
        factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_network(network), mac=node.get_primary_mac())
        self.assertTrue(NodeView().warn_unconfigured_ip_addresses(node))

    def test__does_not_warn_for_ubuntu_fast_installer(self):
        network = factory.make_ipv6_network()
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            osystem='ubuntu', network=network, boot_type=NODE_BOOT.FASTPATH)
        factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_network(network), mac=node.get_primary_mac())
        self.assertFalse(NodeView().warn_unconfigured_ip_addresses(node))

    def test__does_not_warn_for_default_ubuntu_with_fast_installer(self):
        network = factory.make_ipv6_network()
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            osystem='ubuntu', network=network, boot_type=NODE_BOOT.FASTPATH)
        node.osystem = ''
        node.save()
        factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_network(network), mac=node.get_primary_mac())
        self.assertFalse(NodeView().warn_unconfigured_ip_addresses(node))

    def test__does_not_warn_for_just_IPv4_address(self):
        network = factory.make_ipv4_network()
        osystem = choice(['windows', 'centos', 'suse'])
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            osystem=osystem, network=network)
        factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_network(network), mac=node.get_primary_mac())
        self.assertFalse(NodeView().warn_unconfigured_ip_addresses(node))

    def test__does_not_warn_without_static_address(self):
        osystem = choice(['windows', 'centos', 'suse'])
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            osystem=osystem)
        self.assertFalse(NodeView().warn_unconfigured_ip_addresses(node))


class NodeEventLogTest(MAASServerTestCase):

    def test_event_log_shows_event_list(self):
        self.client_log_in()
        node = factory.make_Node()
        events = [
            factory.make_Event(node=node)
            for _ in range(NodeView.number_of_events_shown)
        ]
        response = self.client.get(
            reverse('node-event-list-view', args=[node.system_id]))
        document = fromstring(response.content)
        events_displayed = document.xpath(
            "//div[@id='node_event_list']//td[@class='event_description']")
        self.assertItemsEqual(
            [
                event.type.description + ' \u2014 ' + event.description
                for event in events
            ],
            [
                normalize_text(display.text_content())
                for display in events_displayed
            ]
        )

    def test_event_log_is_paginated(self):
        self.client_log_in()
        self.patch(NodeEventListView, "paginate_by", 3)
        node = factory.make_Node()
        # Create 4 events.
        [factory.make_Event(node=node) for _ in range(4)]

        response = self.client.get(
            reverse('node-event-list-view', args=[node.system_id]))
        self.assertEqual(httplib.OK, response.status_code)
        doc = fromstring(response.content)
        self.assertEqual(
            1, len(doc.cssselect('div.pagination')),
            "Couldn't find pagination tag.")


class ConstructThirdPartyDriversNoticeTest(MAASServerTestCase):

    def test_constructs_notice_without_link_for_normal_users(self):
        expected_notice = nodes_views.THIRD_PARTY_DRIVERS_NOTICE
        self.assertEqual(
            expected_notice.strip(),
            nodes_views.construct_third_party_drivers_notice(False).strip())

    def test_constructs_notice_with_link_for_admin_users(self):
        expected_notice = (
            nodes_views.THIRD_PARTY_DRIVERS_NOTICE +
            nodes_views.THIRD_PARTY_DRIVERS_ADMIN_NOTICE % escape(
                reverse('settings')))
        self.assertEqual(
            expected_notice.strip(),
            nodes_views.construct_third_party_drivers_notice(True).strip())


class NodeResultsDisplayTest(MAASServerTestCase):
    """Tests for the link to node commissioning/installing
    results on the Node page.
    """

    def request_results_display(self, node, result_type):
        """Request the page for `node`, and extract the results display.

        Fails if generating, loading or parsing the page failed; or if
        there was more than one section of commissioning results.

        :return: An `lxml.html.HtmlElement` representing the commissioning
            results portion of the page; or `None` if it was not present on
            the page.
        """
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        self.assertEqual(httplib.OK, response.status_code, response.content)
        doc = fromstring(response.content)
        if result_type == RESULT_TYPE.COMMISSIONING:
            results_display = doc.cssselect('#nodecommissionresults')
        elif result_type == RESULT_TYPE.INSTALLING:
            results_display = doc.cssselect('#nodeinstallresults')
        if len(results_display) == 0:
            return None
        elif len(results_display) == 1:
            return results_display[0]
        else:
            self.fail("Found more than one matching tag: %s" % results_display)

    def get_commissioning_results_link(self, display):
        """Find the results link in `display`.

        :param display: Results display section for a node, as returned by
            `request_results_display`.
        :return: `lxml.html.HtmlElement` for the link to the node's
            commissioning results, as found in `display`; or `None` if it was
            not present.
        """
        links = display.cssselect('a')
        if len(links) == 0:
            return None
        elif len(links) == 1:
            return links[0]
        else:
            self.fail("Found more than one link: %s" % links)

    def get_installing_results_link(self, display):
        """Find the results link in `display`.

        :param display: Results display section for a node, as returned by
            `request_results_display`.
        :return: `lxml.html.HtmlElement` for the link to the node's
            installation results, as found in `display`; or `None` if it was
            not present.
        """
        links = display.cssselect('a')
        if len(links) == 0:
            return None
        elif len(links) == 1:
            return links[0]
        elif len(links) > 1:
            return links

    def test_view_node_links_to_commissioning_results_if_appropriate(self):
        self.client_log_in(as_admin=True)
        result = factory.make_NodeResult_for_commissioning()
        section = self.request_results_display(
            result.node, RESULT_TYPE.COMMISSIONING)
        link = self.get_commissioning_results_link(section)
        results_list = reverse('nodecommissionresult-list')
        self.assertEqual(
            results_list + '?node=%s' % result.node.system_id,
            link.get('href'))

    def test_view_node_shows_commissioning_results_only_if_present(self):
        self.client_log_in(as_admin=True)
        node = factory.make_Node()
        self.assertIsNone(
            self.request_results_display(node, RESULT_TYPE.COMMISSIONING))

    def test_view_node_shows_commissioning_results_with_edit_perm(self):
        password = 'test'
        user = factory.make_User(password=password)
        node = factory.make_Node(owner=user)
        self.client.login(username=user.username, password=password)
        self.logged_in_user = user
        result = factory.make_NodeResult_for_commissioning(node=node)
        section = self.request_results_display(
            result.node, RESULT_TYPE.COMMISSIONING)
        link = self.get_commissioning_results_link(section)
        self.assertEqual(
            "1 output file",
            normalise_whitespace(link.text_content()))

    def test_view_node_shows_commissioning_results_requires_edit_perm(self):
        password = 'test'
        user = factory.make_User(password=password)
        node = factory.make_Node()
        self.client.login(username=user.username, password=password)
        self.logged_in_user = user
        result = factory.make_NodeResult_for_commissioning(node=node)
        self.assertIsNone(
            self.request_results_display(
                result.node, RESULT_TYPE.COMMISSIONING))

    def test_view_node_shows_single_commissioning_result(self):
        self.client_log_in(as_admin=True)
        result = factory.make_NodeResult_for_commissioning()
        section = self.request_results_display(
            result.node, RESULT_TYPE.COMMISSIONING)
        link = self.get_commissioning_results_link(section)
        self.assertEqual(
            "1 output file",
            normalise_whitespace(link.text_content()))

    def test_view_node_shows_multiple_commissioning_results(self):
        self.client_log_in(as_admin=True)
        node = factory.make_Node()
        num_results = randint(2, 5)
        for _ in range(num_results):
            factory.make_NodeResult_for_commissioning(node=node)
        section = self.request_results_display(
            node, RESULT_TYPE.COMMISSIONING)
        link = self.get_commissioning_results_link(section)
        self.assertEqual(
            "%d output files" % num_results,
            normalise_whitespace(link.text_content()))

    def test_view_node_shows_installing_results_only_if_present(self):
        self.client_log_in(as_admin=True)
        node = factory.make_Node()
        self.assertIsNone(
            self.request_results_display(node, RESULT_TYPE.INSTALLING))

    def test_view_node_shows_installing_results_with_edit_perm(self):
        password = 'test'
        user = factory.make_User(password=password)
        node = factory.make_Node(owner=user)
        self.client.login(username=user.username, password=password)
        self.logged_in_user = user
        result = factory.make_NodeResult_for_installing(node=node)
        section = self.request_results_display(
            result.node, RESULT_TYPE.INSTALLING)
        link = self.get_installing_results_link(section)
        self.assertNotIn(
            normalise_whitespace(link.text_content()),
            ('', None))

    def test_view_node_shows_installing_results_requires_edit_perm(self):
        password = 'test'
        user = factory.make_User(password=password)
        node = factory.make_Node()
        self.client.login(username=user.username, password=password)
        self.logged_in_user = user
        result = factory.make_NodeResult_for_installing(node=node)
        self.assertIsNone(
            self.request_results_display(
                result.node, RESULT_TYPE.INSTALLING))

    def test_view_node_shows_single_installing_result(self):
        self.client_log_in(as_admin=True)
        result = factory.make_NodeResult_for_installing()
        section = self.request_results_display(
            result.node, RESULT_TYPE.INSTALLING)
        link = self.get_installing_results_link(section)
        self.assertEqual(
            "install log",
            normalise_whitespace(link.text_content()))

    def test_view_node_shows_multiple_installing_results(self):
        self.client_log_in(as_admin=True)
        node = factory.make_Node()
        num_results = randint(2, 5)
        results_names = []
        for _ in range(num_results):
            node_result = factory.make_NodeResult_for_installing(node=node)
            results_names.append(node_result.name)
        section = self.request_results_display(
            node, RESULT_TYPE.INSTALLING)
        links = self.get_installing_results_link(section)
        self.assertEqual(
            ' '.join(reversed(results_names)),
            ' '.join([
                normalise_whitespace(link.text_content()) for link in links]))


class NodeListingSelectionJSControls(SeleniumTestCase):

    @skip(
        "XXX: blake_r 2014-10-02 bug=1376977: Causes intermittent failures")
    def test_node_list_js_control_select_all(self):
        self.log_in()
        self.get_page('node-list')
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


class NodeListingBulkActionSelectionTest(SeleniumTestCase):
    """Tests for JS event handling on the "bulk action" selection widget."""

    def select_action(self, action_name):
        """Select the given node action."""
        action_dropdown = self.selenium.find_element_by_id('id_action')
        # Loop through the options and click on the one we want.  There's
        # supposed to be a select_by_value() on the Select item, but for some
        # reason we're getting a plain WebElement here.
        actions = action_dropdown.find_elements_by_tag_name('option')
        for action in actions:
            if action.get_attribute('value') == action_name:
                action.click()

    @skip(
        "XXX: blake_r 2014-10-02 bug=1376977: Causes intermittent failures")
    def test_zone_widget_is_visible_only_when_set_zone_selected(self):
        self.log_in('admin')
        self.get_page('node-list')
        zone_widget = self.selenium.find_element_by_id('zone_widget')

        self.assertFalse(zone_widget.is_displayed())

        self.select_action('set_zone')
        self.assertTrue(zone_widget.is_displayed())

        self.select_action('delete')
        self.assertFalse(zone_widget.is_displayed())


class NodeProbedDetailsExpanderTest(SeleniumTestCase):

    def make_node_with_lldp_output(self):
        node = factory.make_Node()
        factory.make_NodeResult_for_commissioning(
            node=node, name=LLDP_OUTPUT_NAME,
            data="<foo>bar</foo>".encode("utf-8"),
            script_result=0)
        return node

    def load_node_page(self, node):
        """Load the given node's page in Selenium."""
        self.get_page('node-view', args=[node.system_id])

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
        self.log_in()
        # Loading just once.  Creating a second node in a separate test causes
        # an integrity error in the database; clearly that's not working too
        # well in a Selenium test case.
        with transaction.atomic():
            node = self.make_node_with_lldp_output()
        self.load_node_page(node)

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


class NodeEnlistmentPreseedViewTest(MAASServerTestCase):

    def test_enlistpreseedview_displays_preseed_data(self):
        self.client_log_in()
        response = self.client.get(reverse('enlist-preseed-view'))
        # Simply test that the preseed looks ok.
        self.assertIn('metadata_url', response.content)

    def test_enlistpreseedview_catches_template_error(self):
        self.client_log_in()
        path = self.make_file(name="enlist", contents="{{invalid}}")
        self.patch(
            settings, 'PRESEED_TEMPLATE_LOCATIONS', [os.path.dirname(path)])
        response = self.client.get(reverse('enlist-preseed-view'))
        self.assertIn('ERROR RENDERING PRESEED', response.content)

    def test_enlistpreseedview_displays_warning_about_url(self):
        self.client_log_in()
        response = self.client.get(reverse('enlist-preseed-view'))
        message_chunk = (
            "The URL mentioned in the following enlistment preseed will "
            "be different depending on"
            )
        self.assertIn(message_chunk, response.content)


class NodePreseedViewTest(PreseedRPCMixin, MAASServerTestCase):

    def test_preseedview_node_displays_preseed_data(self):
        self.client_log_in()
        node = factory.make_Node(
            nodegroup=self.rpc_nodegroup, owner=self.logged_in_user)
        boot_image = make_rpc_boot_image(purpose='install')
        self.patch(
            preseed_module, 'get_boot_images_for').return_value = [boot_image]
        node_preseed_link = reverse('node-preseed-view', args=[node.system_id])
        response = self.client.get(node_preseed_link)
        escaped = html.escape(get_preseed(node))
        self.assertIn(escaped, response.content)

    def test_preseedview_node_catches_template_error(self):
        self.client_log_in()
        node = factory.make_Node(
            nodegroup=self.rpc_nodegroup, owner=self.logged_in_user)
        boot_image = make_rpc_boot_image(purpose='install')
        self.patch(
            preseed_module, 'get_boot_images_for').return_value = [boot_image]
        node_preseed_link = reverse('node-preseed-view', args=[node.system_id])
        path = self.make_file(name="generic", contents="{{invalid}}")
        self.patch(
            settings, 'PRESEED_TEMPLATE_LOCATIONS', [os.path.dirname(path)])
        response = self.client.get(node_preseed_link)
        self.assertIn('ERROR RENDERING PRESEED', response.content)

    def test_preseedview_node_displays_message_if_commissioning(self):
        self.client_log_in()
        node = factory.make_Node(
            nodegroup=self.rpc_nodegroup, owner=self.logged_in_user,
            status=NODE_STATUS.COMMISSIONING,
            )
        node_preseed_link = reverse('node-preseed-view', args=[node.system_id])
        response = self.client.get(node_preseed_link)
        escaped = html.escape(get_preseed(node))
        self.assertThat(
            response.content,
            ContainsAll([escaped, "This node is commissioning."]))

    def test_preseedview_node_displays_link_to_view_node(self):
        self.client_log_in()
        node = factory.make_Node(
            nodegroup=self.rpc_nodegroup, owner=self.logged_in_user)
        boot_image = make_rpc_boot_image(purpose='install')
        self.patch(
            preseed_module, 'get_boot_images_for').return_value = [boot_image]
        node_preseed_link = reverse('node-preseed-view', args=[node.system_id])
        response = self.client.get(node_preseed_link)
        node_link = reverse('node-view', args=[node.system_id])
        self.assertIn(node_link, get_content_links(response))

    def test_enlist_preseed_displays_enlist_preseed(self):
        self.client_log_in()
        enlist_preseed_link = reverse('enlist-preseed-view')
        response = self.client.get(enlist_preseed_link)
        self.assertIn(get_enlist_preseed(), response.content)


class NodeDeleteMacTest(MAASServerTestCase):

    def test_node_delete_not_found_if_node_does_not_exist(self):
        # This returns a 404 rather than returning to the node page
        # with a nice error message because the node could not be found.
        self.client_log_in()
        node_id = factory.make_string()
        mac = factory.make_mac_address()
        mac_delete_link = reverse('mac-delete', args=[node_id, mac])
        response = self.client.get(mac_delete_link)
        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_node_delete_redirects_if_mac_does_not_exist(self):
        # If the MAC address does not exist, the user is redirected
        # to the node edit page.
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        mac = factory.make_mac_address()
        mac_delete_link = reverse('mac-delete', args=[node.system_id, mac])
        response = self.client.get(mac_delete_link)
        self.assertEqual(
            reverse('node-edit', args=[node.system_id]),
            extract_redirect(response))

    def test_node_delete_access_denied_if_user_cannot_edit_node(self):
        self.client_log_in()
        node = factory.make_Node(owner=factory.make_User())
        mac = factory.make_MACAddress(node=node)
        mac_delete_link = reverse('mac-delete', args=[node.system_id, mac])
        response = self.client.get(mac_delete_link)
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_node_delete_mac_contains_mac(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        mac = factory.make_MACAddress(node=node)
        mac_delete_link = reverse('mac-delete', args=[node.system_id, mac])
        response = self.client.get(mac_delete_link)
        self.assertIn(
            'Are you sure you want to delete network interface "%s"' %
            mac.mac_address,
            response.content)

    def test_node_delete_mac_POST_deletes_mac(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        mac = factory.make_MACAddress(node=node)
        mac_delete_link = reverse('mac-delete', args=[node.system_id, mac])
        response = self.client.post(mac_delete_link, {'post': 'yes'})
        self.assertEqual(
            reverse('node-edit', args=[node.system_id]),
            extract_redirect(response))
        self.assertFalse(MACAddress.objects.filter(id=mac.id).exists())

    def test_node_delete_mac_POST_displays_message(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        mac = factory.make_MACAddress(node=node)
        mac_delete_link = reverse('mac-delete', args=[node.system_id, mac])
        response = self.client.post(mac_delete_link, {'post': 'yes'})
        redirect = extract_redirect(response)
        response = self.client.get(redirect)
        self.assertEqual(
            ["Mac address %s deleted." % mac.mac_address],
            [message.message for message in response.context['messages']])

    def test_node_delete_mac_POST_disconnects_MAC_from_network(self):
        self.client_log_in()
        network = factory.make_Network()
        node = factory.make_Node(owner=self.logged_in_user)
        mac = factory.make_MACAddress(node=node, networks=[network])
        response = self.client.post(
            reverse('mac-delete', args=[node.system_id, mac]), {'post': 'yes'})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertIsNotNone(reload_object(network))


class NodeAddMacTest(MAASServerTestCase):

    def test_node_add_mac_contains_form(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        mac_add_link = reverse('mac-add', args=[node.system_id])
        response = self.client.get(mac_add_link)
        doc = fromstring(response.content)
        self.assertEqual(1, len(doc.cssselect('form input#id_mac_address')))

    def test_node_add_mac_POST_adds_mac(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        mac_add_link = reverse('mac-add', args=[node.system_id])
        mac = factory.make_mac_address()
        response = self.client.post(mac_add_link, {'mac_address': mac})
        self.assertEqual(
            reverse('node-edit', args=[node.system_id]),
            extract_redirect(response))
        self.assertTrue(
            MACAddress.objects.filter(node=node, mac_address=mac).exists())

    def test_node_add_mac_POST_displays_message(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        mac_add_link = reverse('mac-add', args=[node.system_id])
        mac = factory.make_mac_address()
        response = self.client.post(mac_add_link, {'mac_address': mac})
        redirect = extract_redirect(response)
        response = self.client.get(redirect)
        self.assertEqual(
            ["MAC address added."],
            [message.message for message in response.context['messages']])


class AdminNodeViewsTest(MAASServerTestCase):

    def test_admin_can_edit_nodes(self):
        self.client_log_in(as_admin=True)
        node = factory.make_Node(owner=factory.make_User())
        node_edit_link = reverse('node-edit', args=[node.system_id])
        params = {
            'hostname': factory.make_string(),
            'power_type': factory.pick_power_type(),
            'architecture': make_usable_architecture(self),
        }
        response = self.client.post(node_edit_link, params)

        node = reload_object(node)
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertAttributes(node, params)


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
