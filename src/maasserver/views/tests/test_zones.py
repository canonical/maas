# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver zones views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


import httplib
from urllib import urlencode

from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from lxml.html import fromstring
from maasserver.models import Zone
from maasserver.models.zone import DEFAULT_ZONE_NAME
from maasserver.testing import (
    extract_redirect,
    get_content_links,
)
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.views.zones import (
    ZoneAdd,
    ZoneListView,
)
from testtools.matchers import (
    Contains,
    ContainsAll,
    Equals,
    MatchesAll,
    Not,
)


class ZoneListingViewTest(MAASServerTestCase):

    def test_zone_list_link_present_on_homepage(self):
        self.client_log_in()
        response = self.client.get(reverse('index'))
        zone_list_link = reverse('zone-list')
        self.assertIn(
            zone_list_link,
            get_content_links(response, element='#main-nav'))

    def test_zone_list_displays_zone_details(self):
        # Zone listing displays the zone name and the zone description.
        self.client_log_in()
        [factory.make_Zone() for _ in range(3)]
        zones = Zone.objects.all()
        response = self.client.get(reverse('zone-list'))
        zone_names = [zone.name for zone in zones]
        truncated_zone_descriptions = [
            zone.description[:20] for zone in zones]
        self.assertThat(response.content, ContainsAll(zone_names))
        self.assertThat(
            response.content, ContainsAll(truncated_zone_descriptions))

    def test_zone_list_displays_sorted_list_of_zones(self):
        # Zones are alphabetically sorted on the zone list page.
        self.client_log_in()
        [factory.make_Zone(sortable_name=True) for _ in range(3)]
        zones = Zone.objects.all()
        sorted_zones = sorted(zones, key=lambda x: x.name.lower())
        response = self.client.get(reverse('zone-list'))
        zone_links = [
            reverse('zone-view', args=[zone.name])
            for zone in sorted_zones]
        self.assertEqual(
            zone_links,
            [link for link in get_content_links(response)
                if link.startswith('/zones/')])

    def test_zone_list_displays_links_to_zone_query(self):
        """Ensures zone list displays links to the right node/device lists"""
        self.client_log_in()
        [factory.make_Zone(sortable_name=True) for _ in range(3)]
        zones = Zone.objects.all()
        sorted_zones = sorted(zones, key=lambda x: x.name.lower())
        response = self.client.get(reverse('zone-list'))
        zone_node_links = [
            reverse('index') + "#/nodes" + "?" +
            urlencode({'query': 'zone:(%s)' % zone.name})
            for zone in sorted_zones]
        zone_device_links = [reverse('index') + "#/nodes" + "?" +
                             urlencode({'query': 'zone:(%s)' % zone.name,
                                        'tab': 'devices'})
                             for zone in sorted_zones]
        node_links_on_page = [link for link in get_content_links(response)
                              if link.startswith('/#/nodes')
                              and '&tab=devices' not in link]
        device_links_on_page = [link for link in get_content_links(response)
                                if link.startswith('/#/nodes')
                                and '&tab=devices' in link]
        self.assertEqual(zone_device_links, device_links_on_page)
        self.assertEqual(zone_node_links, node_links_on_page)


class ZoneListingViewTestNonAdmin(MAASServerTestCase):

    def test_zone_list_does_not_contain_edit_and_delete_links(self):
        self.client_log_in()
        zones = [factory.make_Zone() for _ in range(3)]
        response = self.client.get(reverse('zone-list'))
        zone_edit_links = [
            reverse('zone-edit', args=[zone.name]) for zone in zones]
        zone_delete_links = [
            reverse('zone-del', args=[zone.name]) for zone in zones]
        all_links = get_content_links(response)
        self.assertThat(
            all_links,
            MatchesAll(*[Not(Equals(link)) for link in zone_edit_links]))
        self.assertThat(
            all_links,
            MatchesAll(*[Not(Equals(link)) for link in zone_delete_links]))

    def test_zone_list_does_not_contain_add_link(self):
        self.client_log_in()
        response = self.client.get(reverse('zone-list'))
        add_link = reverse('zone-add')
        self.assertNotIn(add_link, get_content_links(response))

    def test_zone_listing_is_paginated(self):
        self.patch(ZoneListView, "paginate_by", 3)
        self.client_log_in(as_admin=True)
        # Create 4 zones.
        [factory.make_Zone() for _ in range(4)]
        response = self.client.get(reverse('zone-list'))
        self.assertEqual(httplib.OK, response.status_code)
        doc = fromstring(response.content)
        self.assertEqual(
            1, len(doc.cssselect('div.pagination')),
            "Couldn't find pagination tag.")


class ZoneListingViewTestAdmin(MAASServerTestCase):

    def test_zone_list_contains_edit_links(self):
        self.client_log_in(as_admin=True)
        zones = [factory.make_Zone() for _ in range(3)]
        default_zone = Zone.objects.get_default_zone()
        zone_edit_links = [
            reverse('zone-edit', args=[zone.name]) for zone in zones]
        zone_delete_links = [
            reverse('zone-del', args=[zone.name]) for zone in zones]
        zone_default_edit = reverse('zone-edit', args=[default_zone])
        zone_default_delete = reverse('zone-del', args=[default_zone])

        response = self.client.get(reverse('zone-list'))
        all_links = get_content_links(response)

        self.assertThat(all_links, ContainsAll(
            zone_edit_links + zone_delete_links))
        self.assertThat(all_links, Not(Contains(zone_default_edit)))
        self.assertThat(all_links, Not(Contains(zone_default_delete)))

    def test_zone_list_contains_add_link(self):
        self.client_log_in(as_admin=True)
        response = self.client.get(reverse('zone-list'))
        add_link = reverse('zone-add')
        self.assertIn(add_link, get_content_links(response))


class ZoneAddTestNonAdmin(MAASServerTestCase):

    def test_cannot_add_zone(self):
        self.client_log_in()
        name = factory.make_name('zone')
        response = self.client.post(reverse('zone-add'), {'name': name})
        # This returns an inappropriate response (302 FOUND, redirect to the
        # login page; should be 403 FORBIDDEN) but does not actually create the
        # zone, and that's the main thing.
        self.assertEqual(reverse('login'), extract_redirect(response))
        self.assertEqual([], list(Zone.objects.filter(name=name)))


class ZoneAddTestAdmin(MAASServerTestCase):

    def test_adds_zone(self):
        self.client_log_in(as_admin=True)
        definition = {
            'name': factory.make_name('zone'),
            'description': factory.make_string(),
        }
        response = self.client.post(reverse('zone-add'), definition)
        self.assertEqual(httplib.FOUND, response.status_code)
        zone = Zone.objects.get(name=definition['name'])
        self.assertEqual(definition['description'], zone.description)
        self.assertEqual(reverse('zone-list'), extract_redirect(response))

    def test_description_is_optional(self):
        self.client_log_in(as_admin=True)
        name = factory.make_name('zone')
        response = self.client.post(reverse('zone-add'), {'name': name})
        self.assertEqual(httplib.FOUND, response.status_code)
        zone = Zone.objects.get(name=name)
        self.assertEqual('', zone.description)

    def test_get_success_url_returns_valid_url(self):
        self.client_log_in(as_admin=True)
        url = ZoneAdd().get_success_url()
        self.assertIn("/zones", url)


class ZoneDetailViewTest(MAASServerTestCase):

    def test_zone_detail_displays_zone_detail(self):
        # The Zone detail view displays the zone name and the zone
        # description.
        self.client_log_in()
        zone = factory.make_Zone()
        response = self.client.get(reverse('zone-view', args=[zone.name]))
        self.assertThat(response.content, Contains(zone.name))
        self.assertThat(
            response.content, Contains(zone.description))

    def test_zone_detail_displays_node_count(self):
        self.client_log_in()
        zone = factory.make_Zone()
        node = factory.make_Node()
        node.zone = zone
        response = self.client.get(reverse('zone-view', args=[zone.name]))
        document = fromstring(response.content)
        count_text = document.get_element_by_id("#nodecount").text_content()
        self.assertThat(
            count_text, Contains(unicode(zone.node_set.count())))

    def test_zone_detail_links_to_node_list(self):
        self.client_log_in()
        zone = factory.make_Zone()
        node = factory.make_Node()
        node.zone = zone
        response = self.client.get(reverse('zone-view', args=[zone.name]))
        zone_node_link = (
            reverse('index') + "#/nodes" + "?" +
            urlencode({'query': 'zone:(%s)' % zone.name}))
        all_links = get_content_links(response)
        self.assertIn(zone_node_link, all_links)


class ZoneDetailViewNonAdmin(MAASServerTestCase):

    def test_zone_detail_does_not_contain_edit_link(self):
        self.client_log_in()
        zone = factory.make_Zone()
        response = self.client.get(reverse('zone-view', args=[zone.name]))
        zone_edit_link = reverse('zone-edit', args=[zone.name])
        self.assertNotIn(zone_edit_link, get_content_links(response))

    def test_zone_detail_does_not_contain_delete_link(self):
        self.client_log_in()
        zone = factory.make_Zone()
        response = self.client.get(reverse('zone-view', args=[zone.name]))
        zone_delete_link = reverse('zone-del', args=[zone.name])
        self.assertNotIn(zone_delete_link, get_content_links(response))


class ZoneDetailViewAdmin(MAASServerTestCase):

    def test_zone_detail_contains_edit_link(self):
        self.client_log_in(as_admin=True)
        zone = factory.make_Zone()
        response = self.client.get(reverse('zone-view', args=[zone.name]))
        zone_edit_link = reverse('zone-edit', args=[zone.name])
        self.assertIn(zone_edit_link, get_content_links(response))

    def test_zone_detail_contains_delete_link(self):
        self.client_log_in(as_admin=True)
        zone = factory.make_Zone()
        response = self.client.get(reverse('zone-view', args=[zone.name]))
        zone_delete_link = reverse('zone-del', args=[zone.name])
        self.assertIn(zone_delete_link, get_content_links(response))

    def test_zone_detail_for_default_zone_does_not_contain_delete_link(self):
        self.client_log_in(as_admin=True)
        response = self.client.get(
            reverse('zone-view', args=[DEFAULT_ZONE_NAME]))
        zone_delete_link = reverse('zone-del', args=[DEFAULT_ZONE_NAME])
        self.assertNotIn(zone_delete_link, get_content_links(response))


class ZoneEditNonAdminTest(MAASServerTestCase):

    def test_cannot_access_zone_edit(self):
        self.client_log_in()
        zone = factory.make_Zone()
        response = self.client.post(reverse('zone-edit', args=[zone.name]))
        self.assertEqual(reverse('login'), extract_redirect(response))


class ZoneEditAdminTest(MAASServerTestCase):

    def test_zone_edit(self):
        self.client_log_in(as_admin=True)
        zone = factory.make_Zone()
        new_name = factory.make_name('name')
        new_description = factory.make_name('description')
        response = self.client.post(
            reverse('zone-edit', args=[zone.name]),
            data={
                'name': new_name,
                'description': new_description,
            })
        self.assertEqual(
            reverse('zone-list'), extract_redirect(response),
            response.content)
        zone = reload_object(zone)
        self.assertEqual(
            (new_name, new_description),
            (zone.name, zone.description),
        )


class ZoneDeleteNonAdminTest(MAASServerTestCase):

    def test_cannot_delete(self):
        self.client_log_in()
        zone = factory.make_Zone()
        response = self.client.post(reverse('zone-del', args=[zone.name]))
        self.assertEqual(reverse('login'), extract_redirect(response))
        self.assertIsNotNone(reload_object(zone))


class ZoneDeleteAdminTest(MAASServerTestCase):

    def test_deletes_zone(self):
        self.client_log_in(as_admin=True)
        zone = factory.make_Zone()
        response = self.client.post(
            reverse('zone-del', args=[zone.name]),
            {'post': 'yes'})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertIsNone(reload_object(zone))

    def test_rejects_deletion_of_default_zone(self):
        self.client_log_in(as_admin=True)
        try:
            self.client.post(
                reverse('zone-del', args=[DEFAULT_ZONE_NAME]),
                {'post': 'yes'})
        except ValidationError:
            # Right now, this generates an error because the deletion
            # is prevented in the model code and not at the form level.
            # This is not so bad because we make sure that the deletion link
            # for the default zone isn't shown anywhere.
            # If we move validation to the form level, this exception goes
            # away and we'll have to check the HTTP response for a validation
            # failure.
            pass

        # The default zone is still there.
        self.assertIsNotNone(Zone.objects.get_default_zone())

    def test_redirects_to_listing(self):
        self.client_log_in(as_admin=True)
        zone = factory.make_Zone()
        response = self.client.post(
            reverse('zone-del', args=[zone.name]),
            {'post': 'yes'})
        self.assertEqual(reverse('zone-list'), extract_redirect(response))

    def test_does_not_delete_nodes(self):
        self.client_log_in(as_admin=True)
        zone = factory.make_Zone()
        node = factory.make_Node(zone=zone)
        response = self.client.post(
            reverse('zone-del', args=[zone.name]),
            {'post': 'yes'})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertIsNone(reload_object(zone))
        node = reload_object(node)
        self.assertIsNotNone(node)
        self.assertEqual(Zone.objects.get_default_zone(), node.zone)
