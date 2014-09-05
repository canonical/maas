# Copyright 2013-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver networks views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import itertools
from operator import attrgetter
from urllib import urlencode

from django.core.urlresolvers import reverse
from lxml.html import fromstring
from maasserver.models import Network
from maasserver.testing import (
    extract_redirect,
    get_content_links,
    )
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import get_one
from maasserver.views.networks import (
    NetworkAdd,
    NetworkListView,
    )
from testtools.matchers import (
    Contains,
    ContainsAll,
    Equals,
    MatchesAll,
    Not,
    )


class NetworkListingViewTest(MAASServerTestCase):

    def test_network_list_link_present_on_homepage(self):
        self.client_log_in()
        response = self.client.get(reverse('index'))
        network_list_link = reverse('network-list')
        self.assertIn(
            network_list_link,
            get_content_links(response, element='#main-nav'))

    def test_network_list_displays_network_details(self):
        # Network listing displays the network name, description,
        # network information and VLAN tag.
        self.client_log_in()
        factory.make_networks(3)
        networks = Network.objects.all()
        # Attach some NICs to some of the networks.
        [factory.make_mac_address(networks=networks[1:3]) for _ in range(12)]
        response = self.client.get(reverse('network-list'))
        details_list = [
            [
                network.name,
                network.description[:20],
                '%s' % network.get_network(),
                '%s' % network.vlan_tag if network.vlan_tag else '',
                '%s' % (
                    network.default_gateway if network.default_gateway
                    else ''),
                '%d' % network.get_connected_nodes().count(),
            ]
            for network in networks]
        details = list(itertools.chain(*details_list))
        self.assertThat(response.content, ContainsAll(details))

    def test_network_list_displays_sorted_list_of_networks(self):
        # Networks are alphabetically sorted on the network list page.
        self.client_log_in()
        factory.make_networks(3, sortable_name=True)
        networks = Network.objects.all()
        sorted_networks = sorted(networks, key=attrgetter('name'))
        response = self.client.get(reverse('network-list'))
        network_links = [
            reverse('network-view', args=[network.name])
            for network in sorted_networks]
        self.assertEqual(
            network_links,
            [link for link in get_content_links(response)
                if link.startswith('/networks/')])

    def test_network_list_displays_links_to_network_node(self):
        self.client_log_in()
        factory.make_networks(3, sortable_name=True)
        networks = Network.objects.all()
        sorted_networks = sorted(networks, key=attrgetter('name'))
        response = self.client.get(reverse('network-list'))
        network_node_links = [
            reverse('node-list') + "?" +
            urlencode({'query': 'networks=%s' % network.name})
            for network in sorted_networks]
        self.assertEqual(
            network_node_links,
            [link for link in get_content_links(response)
                if link.startswith('/nodes/')])

    def test_network_listing_is_paginated(self):
        self.patch(NetworkListView, "paginate_by", 3)
        self.client_log_in(as_admin=True)
        factory.make_networks(4)
        response = self.client.get(reverse('network-list'))
        self.assertEqual(httplib.OK, response.status_code)
        doc = fromstring(response.content)
        self.assertEqual(
            1, len(doc.cssselect('div.pagination')),
            "Couldn't find pagination tag.")


class NetworkListingViewTestNonAdmin(MAASServerTestCase):

    def test_network_list_does_not_contain_edit_and_delete_links(self):
        self.client_log_in()
        networks = factory.make_networks(3)
        response = self.client.get(reverse('network-list'))
        network_edit_links = [
            reverse('network-edit', args=[network.name])
            for network in networks
            ]
        network_delete_links = [
            reverse('network-del', args=[network.name])
            for network in networks
            ]
        all_links = get_content_links(response)
        self.assertThat(
            all_links,
            MatchesAll(*[Not(Equals(link)) for link in network_edit_links]))
        self.assertThat(
            all_links,
            MatchesAll(*[Not(Equals(link)) for link in network_delete_links]))

    def test_network_list_does_not_contain_add_link(self):
        self.client_log_in()
        response = self.client.get(reverse('network-list'))
        add_link = reverse('network-add')
        self.assertNotIn(add_link, get_content_links(response))


class NetworkListingViewTestAdmin(MAASServerTestCase):

    def test_network_list_contains_edit_links(self):
        self.client_log_in(as_admin=True)
        networks = factory.make_networks(3)
        network_edit_links = [
            reverse('network-edit', args=[network.name])
            for network in networks
            ]
        network_delete_links = [
            reverse('network-del', args=[network.name])
            for network in networks
            ]

        response = self.client.get(reverse('network-list'))
        all_links = get_content_links(response)

        self.assertThat(all_links, ContainsAll(
            network_edit_links + network_delete_links))

    def test_network_list_contains_add_link(self):
        self.client_log_in(as_admin=True)
        response = self.client.get(reverse('network-list'))
        add_link = reverse('network-add')
        self.assertIn(add_link, get_content_links(response))


class NetworkAddTestNonAdmin(MAASServerTestCase):

    def test_cannot_add_network(self):
        self.client_log_in()
        name = factory.make_name('network')
        response = self.client.post(reverse('network-add'), {'name': name})
        # This returns an inappropriate response (302 FOUND, redirect to the
        # login page; should be 403 FORBIDDEN) but does not actually create the
        # network, and that's the main thing.
        self.assertEqual(reverse('login'), extract_redirect(response))
        self.assertEqual([], list(Network.objects.filter(name=name)))


class NetworkAddTestAdmin(MAASServerTestCase):

    def test_adds_network(self):
        self.client_log_in(as_admin=True)
        network = factory.getRandomNetwork()
        definition = {
            'name': factory.make_name('network'),
            'description': factory.make_string(),
            'ip': "%s" % network.cidr.ip,
            'netmask': "%s" % network.netmask,
            'vlan_tag': factory.make_vlan_tag(),
            'default_gateway': factory.getRandomIPAddress(),
        }
        response = self.client.post(reverse('network-add'), definition)
        self.assertEqual(httplib.FOUND, response.status_code)
        network = Network.objects.get(name=definition['name'])
        self.assertEqual(
            [definition[key] for key in sorted(definition)],
            [getattr(network, key) for key in sorted(definition)])
        self.assertEqual(reverse('network-list'), extract_redirect(response))

    def test_get_success_url_returns_valid_url(self):
        self.client_log_in(as_admin=True)
        url = NetworkAdd().get_success_url()
        self.assertIn("/networks", url)


class NetworkDetailViewTest(MAASServerTestCase):

    def test_network_detail_displays_network_detail(self):
        # The Network detail view displays the network name and the network
        # description.
        self.client_log_in()
        network = factory.make_network()
        response = self.client.get(
            reverse('network-view', args=[network.name]))
        self.assertThat(
            response.content,
            ContainsAll([
                network.name,
                network.description,
                reverse('node-list') + "?" + urlencode(
                    {'query': 'networks=%s' % network.name}),
            ])
        )

    def test_network_detail_displays_node_count(self):
        self.client_log_in()
        network = factory.make_network()
        [factory.make_mac_address(networks=[network]) for i in range(5)]
        response = self.client.get(
            reverse('network-view', args=[network.name]))
        document = fromstring(response.content)
        count_text = document.get_element_by_id("nodecount").text_content()
        self.assertThat(count_text, Contains('5'))

    def test_network_detail_escapes_description(self):
        nasty_description = 'A<B>C&D'
        self.client_log_in()
        network = factory.make_network(description=nasty_description)
        response = self.client.get(
            reverse('network-view', args=[network.name]))
        doc = fromstring(response.content)
        description_field = get_one(doc.cssselect('.network-description'))
        pre_tag = get_one(description_field.cssselect('pre'))
        self.assertEqual(nasty_description, pre_tag.text_content().strip())


class NetworkDetailViewNonAdmin(MAASServerTestCase):

    def test_network_detail_does_not_contain_edit_link(self):
        self.client_log_in()
        network = factory.make_network()
        response = self.client.get(
            reverse('network-view', args=[network.name]))
        network_edit_link = reverse('network-edit', args=[network.name])
        self.assertNotIn(network_edit_link, get_content_links(response))

    def test_network_detail_does_not_contain_delete_link(self):
        self.client_log_in()
        network = factory.make_network()
        response = self.client.get(
            reverse('network-view', args=[network.name]))
        network_delete_link = reverse('network-del', args=[network.name])
        self.assertNotIn(network_delete_link, get_content_links(response))


class NetworkDetailViewAdmin(MAASServerTestCase):

    def test_network_detail_contains_edit_link(self):
        self.client_log_in(as_admin=True)
        network = factory.make_network()
        response = self.client.get(
            reverse('network-view', args=[network.name]))
        network_edit_link = reverse('network-edit', args=[network.name])
        self.assertIn(network_edit_link, get_content_links(response))

    def test_network_detail_contains_delete_link(self):
        self.client_log_in(as_admin=True)
        network = factory.make_network()
        response = self.client.get(
            reverse('network-view', args=[network.name]))
        network_delete_link = reverse('network-del', args=[network.name])
        self.assertIn(network_delete_link, get_content_links(response))


class NetworkEditNonAdminTest(MAASServerTestCase):

    def test_cannot_access_network_edit(self):
        self.client_log_in()
        network = factory.make_network()
        response = self.client.post(
            reverse('network-edit', args=[network.name]))
        self.assertEqual(reverse('login'), extract_redirect(response))


class NetworkEditAdminTest(MAASServerTestCase):

    def test_network_edit(self):
        self.client_log_in(as_admin=True)
        network = factory.make_network()
        new_name = factory.make_name('name')
        new_description = factory.make_name('description')
        new_macs = [
            factory.make_mac_address()
            for _ in range(3)]
        new_gateway = factory.getRandomIPAddress()
        response = self.client.post(
            reverse('network-edit', args=[network.name]),
            data={
                'name': new_name,
                'description': new_description,
                'default_gateway': new_gateway,
                'mac_addresses': new_macs,
            })
        self.assertEqual(
            reverse('network-list'), extract_redirect(response),
            response.content)
        network = reload_object(network)
        self.assertEqual(
            (new_name, new_description),
            (network.name, network.description),
        )
        self.assertItemsEqual(new_macs, network.macaddress_set.all())


class NetworkDeleteNonAdminTest(MAASServerTestCase):

    def test_cannot_delete(self):
        self.client_log_in()
        network = factory.make_network()
        response = self.client.post(
            reverse('network-del', args=[network.name]))
        self.assertEqual(reverse('login'), extract_redirect(response))
        self.assertIsNotNone(reload_object(network))


class NetworkDeleteAdminTest(MAASServerTestCase):

    def test_deletes_network(self):
        self.client_log_in(as_admin=True)
        network = factory.make_network()
        response = self.client.post(
            reverse('network-del', args=[network.name]),
            {'post': 'yes'})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertIsNone(reload_object(network))

    def test_redirects_to_listing(self):
        self.client_log_in(as_admin=True)
        network = factory.make_network()
        response = self.client.post(
            reverse('network-del', args=[network.name]),
            {'post': 'yes'})
        self.assertEqual(reverse('network-list'), extract_redirect(response))

    def test_disconnects_macs(self):
        self.client_log_in(as_admin=True)
        network = factory.make_network()
        mac = factory.make_mac_address(networks=[network])
        response = self.client.post(
            reverse('network-del', args=[network.name]),
            {'post': 'yes'})
        self.assertEqual(httplib.FOUND, response.status_code)
        mac = reload_object(mac)
        self.assertIsNotNone(mac)
        self.assertEqual([], list(mac.networks.all()))
