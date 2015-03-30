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
import json
import logging
import os
from random import (
    choice,
    randint,
)
from textwrap import dedent
import time
from unittest import SkipTest

from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import transaction
from django.utils import html
from lxml.html import fromstring
from maasserver import preseed as preseed_module
import maasserver.api
from maasserver.clusterrpc import power as power_module
from maasserver.clusterrpc.testing.boot_images import make_rpc_boot_image
from maasserver.enum import (
    NODE_BOOT,
    NODE_STATUS,
)
from maasserver.forms import NodeActionForm
from maasserver.models import (
    Config,
    Event,
    MACAddress,
    Node,
    node as node_module,
)
from maasserver.node_action import (
    Acquire,
    Commission,
    Delete,
    Deploy,
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
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import (
    MAASServerTestCase,
    SeleniumTestCase,
)
from maasserver.third_party_drivers import get_third_party_driver
from maasserver.utils.orm import get_one
from maasserver.views import nodes as nodes_views
from maasserver.views.nodes import (
    event_to_dict,
    message_from_form_stats,
    node_to_dict,
    NodeEventListView,
    NodeView,
)
from metadataserver.enum import RESULT_TYPE
from metadataserver.models.commissioningscript import (
    LIST_MODALIASES_OUTPUT_NAME,
    LLDP_OUTPUT_NAME,
)
from provisioningserver.utils.enum import map_enum
from provisioningserver.utils.text import normalise_whitespace
from testtools.matchers import (
    Contains,
    ContainsAll,
    Equals,
    HasLength,
    Not,
)


def normalize_text(text):
    return ' '.join(text.split())


class TestHelpers(MAASServerTestCase):

    def test_node_to_dict_keys(self):
        node = factory.make_Node(mac=True)
        self.assertThat(
            node_to_dict(node),
            ContainsAll([
                'id', 'system_id', 'url', 'hostname', 'fqdn',
                'status', 'owner', 'cpu_count', 'memory', 'storage',
                'power_state', 'zone', 'zone_url', 'mac', 'vendor', 'macs']))

    def test_node_to_dict_values(self):
        node = factory.make_Node(mac=True)
        dict_node = node_to_dict(node)
        self.expectThat(dict_node['id'], Equals(node.id))
        self.expectThat(dict_node['system_id'], Equals(node.system_id))
        self.expectThat(
            dict_node['url'],
            Equals(reverse('node-view', args=[node.system_id])))
        self.expectThat(dict_node['hostname'], Equals(node.hostname))
        self.expectThat(dict_node['fqdn'], Equals(node.fqdn))
        self.expectThat(dict_node['status'], Equals(node.display_status()))
        self.expectThat(dict_node['owner'], Equals(''))
        self.expectThat(dict_node['cpu_count'], Equals(node.cpu_count))
        self.expectThat(dict_node['memory'], Equals(node.display_memory()))
        self.expectThat(dict_node['storage'], Equals(node.display_storage()))
        self.expectThat(dict_node['power_state'], Equals(node.power_state))
        self.expectThat(dict_node['zone'], Equals(node.zone.name))
        self.expectThat(
            dict_node['zone_url'],
            Equals(reverse('zone-view', args=[node.zone.name])))
        self.expectThat(
            dict_node['mac'],
            Equals(node.get_pxe_mac().mac_address.get_raw()))
        self.expectThat(dict_node['vendor'], Equals(node.get_pxe_mac_vendor()))
        self.assertItemsEqual(
            dict_node['macs'],
            [mac.mac_address.get_raw() for mac in node.get_extra_macs()])

    def test_node_to_dict_include_events(self):
        node = factory.make_Node()
        etype = factory.make_EventType(level=logging.INFO)
        events = [factory.make_Event(node, etype) for _ in range(4)]
        dict_node = node_to_dict(node, event_log_count=2)
        self.expectThat(dict_node['events']['total'], Equals(len(events)))
        self.expectThat(dict_node['events']['count'], Equals(2))
        self.expectThat(len(dict_node['events']['events']), Equals(2))
        self.expectThat(
            dict_node['events']['more_url'],
            Equals(reverse('node-event-list-view', args=[node.system_id])))

    def test_event_to_dict_keys(self):
        event = factory.make_Event()
        self.assertThat(
            event_to_dict(event),
            ContainsAll([
                'id', 'level', 'created', 'type', 'description']))

    def test_event_to_dict_values(self):
        event = factory.make_Event()
        dict_event = event_to_dict(event)
        self.expectThat(dict_event['id'], Equals(event.id))
        self.expectThat(dict_event['level'], Equals(event.type.level_str))
        self.expectThat(
            dict_event['created'],
            Equals(event.created.strftime('%a, %d %b. %Y %H:%M:%S')))
        self.expectThat(dict_event['type'], Equals(event.type.description))
        self.expectThat(dict_event['description'], Equals(event.description))


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
        profile = self.logged_in_user.userprofile
        consumer, token = profile.create_authorisation_token()
        self.patch(maasserver.api, 'get_oauth_token', lambda request: token)

    def get_node_view_ajax(self, node):
        """Get result of AJAX request for node view."""
        url = reverse('node-view', args=[node.system_id])
        return self.client.get(
            url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

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
        self.assertIn('%s GiB' % (node.display_memory(),), content_text)
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
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
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
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            owner=self.logged_in_user)
        factory.make_StaticIPAddress(mac=node.get_primary_mac())
        node_link = reverse('node-view', args=[node.system_id])
        page = fromstring(self.client.get(node_link).content)
        [addresses_section] = page.cssselect('#ip-addresses')
        self.assertEqual(
            [],
            addresses_section.cssselect('#unconfigured-ip-warning'))

    def test_view_node_displays_node_info_no_owner(self):
        # If the node has no owner, the Owner 'slot' is hidden.
        self.client_log_in()
        node = factory.make_Node()
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        doc = fromstring(response.content)
        [owner_div] = doc.cssselect('#owner')
        self.assertIn('hidden', owner_div.attrib['class'])

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
        mac = factory.make_MACAddress_with_Node()

        response = self.client.get(
            reverse('node-view', args=[mac.node.system_id]))
        self.assertEqual(httplib.OK, response.status_code)

        [interfaces_section] = fromstring(response.content).cssselect(
            '#network-interfaces')
        [listing] = get_one(interfaces_section.cssselect('span'))
        self.assertEqual(mac.mac_address, listing.text_content().strip())

    def test_view_node_lists_macs_as_sorted_list_items(self):
        # The PXE mac is listed first on the node view page.
        self.client_log_in()
        node = factory.make_Node()

        macs = [
            factory.make_MACAddress(node=node)
            for _ in range(4)
        ]
        pxe_mac_index = 2
        node.pxe_mac = macs[pxe_mac_index]
        node.save()

        response = self.client.get(reverse('node-view', args=[node.system_id]))
        self.assertEqual(httplib.OK, response.status_code)

        [interfaces_section] = fromstring(response.content).cssselect(
            '#network-interfaces')
        [interfaces_list] = interfaces_section.cssselect('ul')
        interfaces = interfaces_list.cssselect('li')
        sorted_macs = (
            [macs[pxe_mac_index]] +
            macs[:pxe_mac_index] + macs[pxe_mac_index + 1:]
        )
        self.assertEqual(
            [mac.mac_address.get_raw() for mac in sorted_macs],
            [interface.text_content().strip() for interface in interfaces])

    def test_view_node_links_network_interfaces_to_networks(self):
        self.client_log_in()
        network = factory.make_Network()
        mac = factory.make_MACAddress_with_Node(networks=[network])

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
        mac = factory.make_MACAddress_with_Node(networks=networks)

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

    def test_view_node_ajax_returns_json(self):
        self.client_log_in()
        node = factory.make_Node()
        response = self.get_node_view_ajax(node)
        self.assertEqual('application/json', response['Content-Type'])

    def test_view_node_ajax_returns_node_info(self):
        self.client_log_in()
        node = factory.make_Node()
        response = self.get_node_view_ajax(node)
        json_obj = json.loads(response.content)
        del json_obj['action_view']
        self.assertEquals(
            node_to_dict(
                node,
                event_log_count=NodeView.number_of_events_shown),
            json_obj)

    def test_view_node_ajax_returns_action_view(self):
        self.client_log_in()
        node = factory.make_Node()
        response = self.get_node_view_ajax(node)
        json_obj = json.loads(response.content)
        self.assertThat(
            json_obj['action_view'],
            Contains('<h3>Node details</h3'))

    def test_view_node_ajax_returns_latest_node_events(self):
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
        response = self.get_node_view_ajax(node)
        json_obj = json.loads(response.content)
        self.assertItemsEqual(
            [
                (event.type.description, event.description)
                for event in events
            ],
            [
                (event['type'], event['description'])
                for event in json_obj['events']['events']
            ]
        )

    def test_view_node_ajax_doesnt_return_events_with_debug_level(self):
        self.client_log_in()
        node = factory.make_Node()
        # Create an event with debug level
        factory.make_Event(
            node=node, type=factory.make_EventType(
                level=logging.DEBUG))
        response = self.get_node_view_ajax(node)
        json_obj = json.loads(response.content)
        self.expectThat(json_obj['events']['total'], Equals(1))
        self.expectThat(json_obj['events']['count'], Equals(0))

    def test_view_node_ajax_doesnt_return_events_from_other_nodes(self):
        self.client_log_in()
        node = factory.make_Node()
        # Create an event related to another node.
        factory.make_Event()
        response = self.get_node_view_ajax(node)
        json_obj = json.loads(response.content)
        self.expectThat(json_obj['events']['total'], Equals(0))
        self.expectThat(json_obj['events']['count'], Equals(0))

    def test_view_node_hides_storage_section_if_no_physical_devices(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        node_link = reverse('node-view', args=[node.system_id])

        response = self.client.get(node_link)
        self.assertEqual(httplib.OK, response.status_code)

        doc = fromstring(response.content)
        self.assertItemsEqual([], doc.cssselect('#storage'))

    def test_view_node_lists_physical_devices(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        devices = [
            factory.make_PhysicalBlockDevice(node=node)
            for _ in range(3)
            ]
        expected_data = [
            [
                device.name,
                device.path,
                device.display_size(),
                device.model,
                device.serial,
                ', '.join(device.tags)
            ]
            for device in devices
            ]

        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.get(node_link)
        self.assertEqual(httplib.OK, response.status_code)

        doc = fromstring(response.content)
        table_rows = doc.cssselect('#storage > table > tbody > tr')
        rows_data = [
            [col.text.strip() for col in rows.findall('td')]
            for rows in table_rows
            ]
        self.assertItemsEqual(expected_data, rows_data)

    def test_admin_can_delete_nodes(self):
        self.client_log_in(as_admin=True)
        node = factory.make_Node()
        node_delete_link = reverse('node-delete', args=[node.system_id])
        response = self.client.post(node_delete_link, {'post': 'yes'})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertFalse(Node.objects.filter(id=node.id).exists())

    def test_allocated_node_can_be_deleted(self):
        self.client_log_in(as_admin=True)
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())

        node_delete_link = reverse('node-delete', args=[node.system_id])
        response = self.client.get(node_delete_link)

        self.assertEqual(httplib.OK, response.status_code)

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
        # Don't call through to the cluster to turn the power on.
        self.patch(power_module, "getClientFor")

        # Stub-out real-world RPC calls.
        self.patch(node_module, "update_host_maps").return_value = []

        self.client_log_in()
        factory.make_SSHKey(self.logged_in_user)
        self.set_up_oauth_token()
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            status=NODE_STATUS.ALLOCATED, power_type='ether_wake',
            owner=self.logged_in_user)
        node_link = reverse('node-view', args=[node.system_id])
        response = self.client.post(
            node_link, data={NodeActionForm.input_name: Deploy.name})
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
            node, Acquire.name)
        self.assertIn(
            "This node is now allocated to you.",
            '\n'.join(msg.message for msg in response.context['messages']))

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


class TestWarnUnconfiguredIPAddresses(MAASServerTestCase):

    def test__warns_for_IPv6_address_on_non_ubuntu_OS(self):
        network = factory.make_ipv6_network()
        osystem = choice(['windows', 'centos', 'suse'])
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            osystem=osystem, network=network)
        factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_network(network), mac=node.get_primary_mac())
        self.assertTrue(NodeView().warn_unconfigured_ip_addresses(node))

    def test__warns_for_IPv6_address_on_debian_installer(self):
        network = factory.make_ipv6_network()
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            osystem='ubuntu', network=network, boot_type=NODE_BOOT.DEBIAN)
        factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_network(network), mac=node.get_primary_mac())
        self.assertTrue(NodeView().warn_unconfigured_ip_addresses(node))

    def test__does_not_warn_for_ubuntu_fast_installer(self):
        network = factory.make_ipv6_network()
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            osystem='ubuntu', network=network, boot_type=NODE_BOOT.FASTPATH)
        factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_network(network), mac=node.get_primary_mac())
        self.assertFalse(NodeView().warn_unconfigured_ip_addresses(node))

    def test__does_not_warn_for_default_ubuntu_with_fast_installer(self):
        network = factory.make_ipv6_network()
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            osystem='ubuntu', network=network, boot_type=NODE_BOOT.FASTPATH)
        node.osystem = ''
        node.save()
        factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_network(network), mac=node.get_primary_mac())
        self.assertFalse(NodeView().warn_unconfigured_ip_addresses(node))

    def test__does_not_warn_for_just_IPv4_address(self):
        network = factory.make_ipv4_network()
        osystem = choice(['windows', 'centos', 'suse'])
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            osystem=osystem, network=network)
        factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_network(network), mac=node.get_primary_mac())
        self.assertFalse(NodeView().warn_unconfigured_ip_addresses(node))

    def test__does_not_warn_without_static_address(self):
        osystem = choice(['windows', 'centos', 'suse'])
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
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
    """Tests for the link to node commissioning/installation
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
        elif result_type == RESULT_TYPE.INSTALLATION:
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

    def get_installation_results_link(self, display):
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

    def test_view_node_shows_installation_results_only_if_present(self):
        self.client_log_in(as_admin=True)
        node = factory.make_Node()
        self.assertIsNone(
            self.request_results_display(node, RESULT_TYPE.INSTALLATION))

    def test_view_node_shows_installation_results_with_edit_perm(self):
        password = 'test'
        user = factory.make_User(password=password)
        node = factory.make_Node(owner=user)
        self.client.login(username=user.username, password=password)
        self.logged_in_user = user
        result = factory.make_NodeResult_for_installation(node=node)
        section = self.request_results_display(
            result.node, RESULT_TYPE.INSTALLATION)
        link = self.get_installation_results_link(section)
        self.assertNotIn(
            normalise_whitespace(link.text_content()),
            ('', None))

    def test_view_node_shows_installation_results_requires_edit_perm(self):
        password = 'test'
        user = factory.make_User(password=password)
        node = factory.make_Node()
        self.client.login(username=user.username, password=password)
        self.logged_in_user = user
        result = factory.make_NodeResult_for_installation(node=node)
        self.assertIsNone(
            self.request_results_display(
                result.node, RESULT_TYPE.INSTALLATION))

    def test_view_node_shows_single_installation_result(self):
        self.client_log_in(as_admin=True)
        result = factory.make_NodeResult_for_installation()
        section = self.request_results_display(
            result.node, RESULT_TYPE.INSTALLATION)
        link = self.get_installation_results_link(section)
        self.assertEqual(
            "install log",
            normalise_whitespace(link.text_content()))

    def test_view_node_shows_multiple_installation_results(self):
        self.client_log_in(as_admin=True)
        node = factory.make_Node()
        num_results = randint(2, 5)
        results_names = []
        for _ in range(num_results):
            node_result = factory.make_NodeResult_for_installation(node=node)
            results_names.append(node_result.name)
        section = self.request_results_display(
            node, RESULT_TYPE.INSTALLATION)
        links = self.get_installation_results_link(section)
        self.assertThat(
            results_names,
            ContainsAll(
                [normalise_whitespace(link.text_content()) for link in links]))


class TestJSNodeView(SeleniumTestCase):

    @classmethod
    def setUpClass(cls):
        raise SkipTest(
            "XXX: Gavin Panella 2015-02-26 bug=1426010: "
            "All tests using Selenium are breaking.")

    # JS Script that will load a new NodeView, placing the
    # object on the global window.
    VIEW_SCRIPT = dedent("""\
        YUI().use(
            'maas.node', 'maas.node_views', 'maas.shortpoll',
            function (Y) {
              Y.on('domready', function() {
                // Place the view on the window, giving the ability for
                // selenium to access it.
                window.node_view = new Y.maas.node_views.NodeView({
                  srcNode: 'body',
                  eventList: '#node_event_list',
                  actionView: '#sidebar'
                });
                var poller = new Y.maas.shortpoll.ShortPollManager({
                  uri: "%s"
                });
                window.node_view.addLoader(poller.get("io"));
                poller.poll();
            });
        });
        """)

    def get_js_node(self, node):
        """Return the loaded node from JS NodeView."""
        self.get_page('node-view', args=[node.system_id])

        # We execute a script to create a new view. This needs to
        # be done to get access to the view. As the view code does not place
        # the object on a global variable, which is a good thing.
        self.selenium.execute_script(
            self.VIEW_SCRIPT % reverse('node-view', args=[node.system_id]))

        # Extract the load node from javascript, to check that it loads the
        # correct information. Due to the nature of JS and the
        # poller requesting the node, we cannot assume that the result
        # will be their immediately. We will try for a maximum of
        # 5 seconds before giving up.
        for _ in range(10):
            js_node = self.selenium.execute_script(
                "return window.node_view.node;")
            if js_node is not None:
                break
            time.sleep(0.5)
        if js_node is None:
            self.fail("Unable to retrieve the loaded node from selenium.")
        return js_node

    def make_node_with_events(self):
        node = factory.make_Node()
        [factory.make_Event(node=node) for _ in range(3)]
        return node

    def test_node_view_loads_node_with_correct_attributes(self):
        self.log_in()
        with transaction.atomic():
            node = self.make_node_with_events()
        js_node = self.get_js_node(node)
        self.expectThat(js_node, ContainsAll([
            'id',
            'system_id',
            'url',
            'hostname',
            'architecture',
            'fqdn',
            'status',
            'owner',
            'cpu_count',
            'memory',
            'storage',
            'power_state',
            'zone',
            'zone_url',
            'mac',
            'vendor',
            'macs',
            'events',
            ]))

    def test_node_view_loads_node_with_events(self):
        self.log_in()
        with transaction.atomic():
            node = self.make_node_with_events()
            all_node_events = Event.objects.filter(node=node)
            total_events = all_node_events.count()
            viewable_events_count = (
                all_node_events.exclude(type__level=logging.DEBUG).count())
        js_node = self.get_js_node(node)
        self.expectThat(
            js_node['events']['total'], Equals(total_events))
        self.expectThat(
            js_node['events']['count'], Equals(viewable_events_count))
        self.expectThat(
            js_node['events']['more_url'],
            Equals(reverse('node-event-list-view', args=[node.system_id])))
        for event in js_node['events']['events']:
            self.expectThat(event, ContainsAll([
                'id',
                'level',
                'created',
                'type',
                'description',
                ]))


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
                 % Delete.display,),
            ),
            (
                (Delete, 1, 4, 2),
                (
                    'The action "%s" was successfully performed on 1 node'
                    % Delete.display,
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
                 % Delete.display,),
            ),
        ]
        # level precedence is worst-case for the concantenation of messages
        levels = ['error', 'info', 'error', 'error']
        for index, (params, snippets) in enumerate(params_and_snippets):
            message, level = message_from_form_stats(*params)
            for snippet in snippets:
                self.assertIn(snippet, message)
            self.assertEqual(level, levels[index])


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
