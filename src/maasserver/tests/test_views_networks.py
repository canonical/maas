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


from django.core.urlresolvers import reverse
from maasserver.models import Network
import itertools
from maasserver.testing import get_content_links
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import (
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
        [factory.make_network() for i in range(3)]
        networks = Network.objects.all()
        response = self.client.get(reverse('network-list'))
        details_list = [
            [
                network.name,
                network.description[:20],
                '%s' % network.get_network(),
                '%s' % network.vlan_tag if network.vlan_tag else '',
            ]
            for network in networks]
        details = list(itertools.chain(*details_list))
        self.assertThat(response.content, ContainsAll(details))

    def test_network_list_displays_sorted_list_of_networks(self):
        # Networks are alphabetically sorted on the network list page.
        self.client_log_in()
        [factory.make_network() for i in range(3)]
        networks = Network.objects.all()
        sorted_networks = sorted(networks, key=lambda x: x.name.lower())
        response = self.client.get(reverse('network-list'))
        network_links = [
            reverse('network-view', args=[network.name])
            for network in sorted_networks]
        self.assertEqual(
            network_links,
            [link for link in get_content_links(response)
                if link.startswith('/networks/')])


class NetworkListingViewTestNonAdmin(MAASServerTestCase):

    def test_network_list_does_not_contain_edit_and_delete_links(self):
        self.client_log_in()
        networks = [factory.make_network() for i in range(3)]
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
        networks = [factory.make_network() for i in range(3)]
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
