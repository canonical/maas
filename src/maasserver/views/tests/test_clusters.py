# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver clusters views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import random

from django.core.urlresolvers import reverse
from lxml.html import fromstring
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUP_STATUS_CHOICES,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.models import (
    NodeGroup,
    NodeGroupInterface,
    )
from maasserver.testing import (
    extract_redirect,
    get_content_links,
    )
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.views import clusters
from maasserver.views.clusters import ClusterListView
from maastesting.matchers import MockCalledOnceWith
from provisioningserver.boot.tests.test_tftppath import make_osystem
from provisioningserver.utils.enum import map_enum
from testtools.matchers import (
    ContainsAll,
    HasLength,
    MatchesStructure,
    )


class ClusterListingTest(MAASServerTestCase):

    scenarios = [
        ('accepted-clusters', {'status': NODEGROUP_STATUS.ACCEPTED}),
        ('pending-clusters', {'status': NODEGROUP_STATUS.PENDING}),
        ('rejected-clusters', {'status': NODEGROUP_STATUS.REJECTED}),
    ]

    def get_url(self):
        """Return the listing url used in this scenario."""
        return reverse(ClusterListView.status_links[
            self.status])

    def test_cluster_listing_contains_links_to_manipulate_clusters(self):
        self.client_log_in(as_admin=True)
        nodegroups = {
            factory.make_NodeGroup(status=self.status)
            for _ in range(3)
            }
        links = get_content_links(self.client.get(self.get_url()))
        nodegroup_edit_links = [
            reverse('cluster-edit', args=[nodegroup.uuid])
            for nodegroup in nodegroups]
        nodegroup_delete_links = [
            reverse('cluster-delete', args=[nodegroup.uuid])
            for nodegroup in nodegroups]
        self.assertThat(
            links,
            ContainsAll(nodegroup_edit_links + nodegroup_delete_links))

    def make_listing_view(self, status):
        view = ClusterListView()
        view.status = status
        return view

    def test_make_title_entry_returns_link_for_other_status(self):
        # If the entry's status is different from the view's status,
        # the returned entry is a link.
        other_status = factory.pick_choice(
            NODEGROUP_STATUS_CHOICES, but_not=[self.status])
        factory.make_NodeGroup(status=other_status)
        link_name = ClusterListView.status_links[other_status]
        view = self.make_listing_view(self.status)
        entry = view.make_title_entry(other_status, link_name)
        status_name = NODEGROUP_STATUS_CHOICES[other_status][1]
        self.assertEqual(
            '<a href="%s">1 %s cluster</a>' % (
                reverse(link_name), status_name.lower()),
            entry)

    def test_make_title_entry_returns_title_if_no_cluster(self):
        # If no cluster correspond to the entry's status, the returned
        # entry is not a link: it's a simple mention '0 <status> clusters'.
        other_status = factory.pick_choice(
            NODEGROUP_STATUS_CHOICES, but_not=[self.status])
        link_name = ClusterListView.status_links[other_status]
        view = self.make_listing_view(self.status)
        entry = view.make_title_entry(other_status, link_name)
        status_name = NODEGROUP_STATUS_CHOICES[other_status][1]
        self.assertEqual(
            '0 %s clusters' % status_name.lower(), entry)

    def test_title_displays_number_of_clusters(self):
        for _ in range(3):
            factory.make_NodeGroup(status=self.status)
        view = self.make_listing_view(self.status)
        status_name = NODEGROUP_STATUS_CHOICES[self.status][1]
        title = view.make_cluster_listing_title()
        self.assertIn("3 %s clusters" % status_name.lower(), title)

    def test_title_contains_links_to_other_listings(self):
        view = self.make_listing_view(self.status)
        other_statuses = []
        # Compute a list with the statuses of the clusters not being
        # displayed by the 'view'.  Create clusters with these statuses.
        for status in map_enum(NODEGROUP_STATUS).values():
            if status != self.status:
                other_statuses.append(status)
                factory.make_NodeGroup(status=status)
        for status in other_statuses:
            link_name = ClusterListView.status_links[status]
            title = view.make_cluster_listing_title()
            self.assertIn(reverse(link_name), title)

    def test_listing_is_paginated(self):
        self.patch(ClusterListView, "paginate_by", 2)
        self.client_log_in(as_admin=True)
        for _ in range(3):
            factory.make_NodeGroup(status=self.status)
        response = self.client.get(self.get_url())
        self.assertEqual(httplib.OK, response.status_code)
        doc = fromstring(response.content)
        self.assertThat(
            doc.cssselect('div.pagination'),
            HasLength(1),
            "Couldn't find pagination tag.")

    def test_listing_displays_connection_status(self):
        # We're using a little trick here: we create nodegroups
        # whose name end with either '0' or '1' and we then
        # patch nodegroup.is_connected so that it returns
        # True or False based of the name of the nodegroup.
        self.client_log_in(as_admin=True)
        nodegroup_connections = {}
        connection_representation = {
            '&check;': True,
            '&cross;': False,
        }

        def mock_is_connected(self):
            # Return a boolean based on the last character in the
            # nodegroup's name.
            return True if self.name.endswith('0') else False
        self.patch(NodeGroup, 'is_connected', mock_is_connected)

        for _ in range(3):
            # Create a name with a random value of '0' or '1' at the end.
            name = "nodegroup-%s-%s" % (
                factory.make_name(), random.choice(['0', '1']))
            nodegroup = factory.make_NodeGroup(
                status=self.status, name=name)
            nodegroup_connections[nodegroup.uuid] = nodegroup.is_connected()
        response = self.client.get(self.get_url())
        document = fromstring(response.content)
        connection_displayed = {}
        for uuid in nodegroup_connections:
            connection_row = document.xpath(
                "//td[@id='%s_connection']" % uuid)[0]
            connection_displayed[uuid] = connection_representation[
                connection_row.text.strip()]
        self.assertEqual(nodegroup_connections, connection_displayed)


class ClusterListingAccess(MAASServerTestCase):

    def test_admin_sees_cluster_tab(self):
        self.client_log_in(as_admin=True)
        links = get_content_links(
            self.client.get(reverse('index')), element='#main-nav')
        self.assertIn(reverse('cluster-list'), links)

    def test_non_admin_doesnt_see_cluster_tab(self):
        self.client_log_in(as_admin=False)
        links = get_content_links(
            self.client.get(reverse('index')), element='#main-nav')
        self.assertNotIn(reverse('cluster-list'), links)


class ClusterPendingListingTest(MAASServerTestCase):

    def test_pending_listing_contains_form_to_accept_all_nodegroups(self):
        self.client_log_in(as_admin=True)
        factory.make_NodeGroup(status=NODEGROUP_STATUS.PENDING),
        response = self.client.get(reverse('cluster-list-pending'))
        doc = fromstring(response.content)
        forms = doc.cssselect('form#accept_all_pending_nodegroups')
        self.assertEqual(1, len(forms))

    def test_pending_listing_contains_form_to_reject_all_nodegroups(self):
        self.client_log_in(as_admin=True)
        factory.make_NodeGroup(status=NODEGROUP_STATUS.PENDING),
        response = self.client.get(reverse('cluster-list-pending'))
        doc = fromstring(response.content)
        forms = doc.cssselect('form#reject_all_pending_nodegroups')
        self.assertEqual(1, len(forms))

    def test_pending_listing_accepts_all_pending_nodegroups_POST(self):
        self.client_log_in(as_admin=True)
        nodegroups = {
            factory.make_NodeGroup(status=NODEGROUP_STATUS.PENDING),
            factory.make_NodeGroup(status=NODEGROUP_STATUS.PENDING),
        }
        response = self.client.post(
            reverse('cluster-list-pending'), {'mass_accept_submit': 1})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(
            [reload_object(nodegroup).status for nodegroup in nodegroups],
            [NODEGROUP_STATUS.ACCEPTED] * 2)

    def test_pending_listing_rejects_all_pending_nodegroups_POST(self):
        self.client_log_in(as_admin=True)
        nodegroups = {
            factory.make_NodeGroup(status=NODEGROUP_STATUS.PENDING),
            factory.make_NodeGroup(status=NODEGROUP_STATUS.PENDING),
        }
        response = self.client.post(
            reverse('cluster-list-pending'), {'mass_reject_submit': 1})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(
            [reload_object(nodegroup).status for nodegroup in nodegroups],
            [NODEGROUP_STATUS.REJECTED] * 2)


class ClusterAcceptedListingTest(MAASServerTestCase):

    def test_accepted_listing_import_boot_images_calls_import_resources(self):
        self.client_log_in(as_admin=True)
        fake_import = self.patch(clusters, 'import_resources')
        factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED),
        response = self.client.post(
            reverse('cluster-list'), {'import_all_boot_images': 1})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertThat(fake_import, MockCalledOnceWith())

    def test_a_warning_is_displayed_if_the_cluster_has_no_boot_images(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ACCEPTED)
        response = self.client.get(reverse('cluster-list'))
        document = fromstring(response.content)
        nodegroup_row = document.xpath("//tr[@id='%s']" % nodegroup.uuid)[0]
        self.assertIn('warning', nodegroup_row.get('class'))
        warning_elems = (
            nodegroup_row.xpath(
                "//img[@title='Warning: this cluster has no boot images.']"))
        self.assertThat(
            warning_elems, HasLength(1),
            "No warning about missing boot images.")

    def test_warning_is_displayed_if_a_cluster_is_not_connected(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ACCEPTED)
        # Create a boot image so that the warning about the missing boot images
        # isn't displayed.
        factory.make_BootImage(nodegroup=nodegroup)

        self.patch(NodeGroup, 'is_connected', lambda _: False)
        response = self.client.get(reverse('cluster-list'))
        document = fromstring(response.content)
        nodegroup_row = document.xpath("//tr[@id='%s']" % nodegroup.uuid)[0]
        self.assertIn('warning', nodegroup_row.get('class'))
        warning_elems = (
            nodegroup_row.xpath(
                """//img[@title="Warning: this cluster isn't connected."]"""))
        self.assertThat(
            warning_elems, HasLength(1),
            "No warning about disconnected cluster.")


class ClusterDeleteTest(MAASServerTestCase):

    def test_can_delete_cluster(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_NodeGroup()
        delete_link = reverse('cluster-delete', args=[nodegroup.uuid])
        response = self.client.post(delete_link, {'post': 'yes'})
        self.assertEqual(
            (httplib.FOUND, reverse('cluster-list')),
            (response.status_code, extract_redirect(response)))
        self.assertFalse(
            NodeGroup.objects.filter(uuid=nodegroup.uuid).exists())


class ClusterEditTest(MAASServerTestCase):

    def test_cluster_page_contains_links_to_edit_and_delete_interfaces(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_NodeGroup()
        interfaces = set()
        for _ in range(3):
            interfaces.add(
                factory.make_NodeGroupInterface(
                    nodegroup=nodegroup,
                    management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED))
        links = get_content_links(
            self.client.get(reverse('cluster-edit', args=[nodegroup.uuid])))
        interface_edit_links = [
            reverse(
                'cluster-interface-edit',
                args=[nodegroup.uuid, interface.name])
            for interface in interfaces]
        interface_delete_links = [
            reverse(
                'cluster-interface-delete',
                args=[nodegroup.uuid, interface.name])
            for interface in interfaces]
        self.assertThat(
            links,
            ContainsAll(interface_edit_links + interface_delete_links))

    def test_can_edit_cluster(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_NodeGroup()
        edit_link = reverse('cluster-edit', args=[nodegroup.uuid])
        data = {
            'cluster_name': factory.make_name('cluster_name'),
            'name': factory.make_name('name'),
            'status': factory.pick_enum(NODEGROUP_STATUS),
            }
        response = self.client.post(edit_link, data)
        self.assertEqual(httplib.FOUND, response.status_code, response.content)
        self.assertThat(
            reload_object(nodegroup),
            MatchesStructure.byEquality(**data))

    def test_contains_link_to_add_interface(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_NodeGroup()
        links = get_content_links(
            self.client.get(reverse('cluster-edit', args=[nodegroup.uuid])))
        self.assertIn(
            reverse('cluster-interface-create', args=[nodegroup.uuid]), links)

    def test_contains_link_to_boot_image_list(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_NodeGroup()
        boot_images = [
            factory.make_BootImage(nodegroup=nodegroup)
            for _ in range(3)
            ]
        for bi in boot_images:
            make_osystem(self, bi.osystem, ['install'])
        response = self.client.get(
            reverse('cluster-edit', args=[nodegroup.uuid]))
        self.assertEqual(
            httplib.OK, response.status_code, response.content)
        links = get_content_links(response)
        self.assertIn(
            reverse('cluster-bootimages-list', args=[nodegroup.uuid]), links)

    def test_displays_warning_if_boot_image_list_is_empty(self):
        # Create boot images in another nodegroup.
        boot_images = [factory.make_BootImage() for _ in range(3)]
        for bi in boot_images:
            make_osystem(self, bi.osystem, ['install'])
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_NodeGroup()
        response = self.client.get(
            reverse('cluster-edit', args=[nodegroup.uuid]))
        self.assertEqual(httplib.OK, response.status_code)
        doc = fromstring(response.content)
        self.assertEqual(
            1, len(doc.cssselect('#no_boot_images_warning')),
            "Warning about missing images not present")
        links = get_content_links(response)
        self.assertNotIn(
            reverse('cluster-bootimages-list', args=[nodegroup.uuid]), links)


class ClusterInterfaceDeleteTest(MAASServerTestCase):

    def test_can_delete_cluster_interface(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_NodeGroup()
        interface = factory.make_NodeGroupInterface(
            nodegroup=nodegroup,
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        delete_link = reverse(
            'cluster-interface-delete',
            args=[nodegroup.uuid, interface.name])
        response = self.client.post(delete_link, {'post': 'yes'})
        self.assertEqual(
            (httplib.FOUND, reverse('cluster-edit', args=[nodegroup.uuid])),
            (response.status_code, extract_redirect(response)))
        self.assertFalse(
            NodeGroupInterface.objects.filter(id=interface.id).exists())

    def test_interface_delete_supports_interface_alias(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_NodeGroup(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        interface = factory.make_NodeGroupInterface(
            nodegroup=nodegroup, name="eth0:0")
        delete_link = reverse(
            'cluster-interface-delete',
            args=[nodegroup.uuid, interface.name])
        # The real test is that reverse() does not blow up when the
        # interface's name contains an alias.
        self.assertIsInstance(delete_link, (bytes, unicode))


class ClusterInterfaceEditTest(MAASServerTestCase):

    def test_can_edit_cluster_interface(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_NodeGroup(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        interface = factory.make_NodeGroupInterface(
            nodegroup=nodegroup)
        edit_link = reverse(
            'cluster-interface-edit',
            args=[nodegroup.uuid, interface.name])
        data = factory.get_interface_fields()
        response = self.client.post(edit_link, data)
        self.assertEqual(
            (httplib.FOUND, reverse('cluster-edit', args=[nodegroup.uuid])),
            (response.status_code, extract_redirect(response)))
        self.assertThat(
            reload_object(interface),
            MatchesStructure.byEquality(**data))

    def test_interface_edit_supports_interface_alias(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_NodeGroup(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        interface = factory.make_NodeGroupInterface(
            nodegroup=nodegroup, name="eth0:0")
        edit_link = reverse(
            'cluster-interface-edit',
            args=[nodegroup.uuid, interface.name])
        # The real test is that reverse() does not blow up when the
        # interface's name contains an alias.
        self.assertIsInstance(edit_link, (bytes, unicode))


class ClusterInterfaceCreateTest(MAASServerTestCase):

    def test_can_create_cluster_interface(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_NodeGroup(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        create_link = reverse(
            'cluster-interface-create', args=[nodegroup.uuid])
        data = factory.get_interface_fields()
        response = self.client.post(create_link, data)
        self.assertEqual(
            (httplib.FOUND, reverse('cluster-edit', args=[nodegroup.uuid])),
            (response.status_code, extract_redirect(response)))
        interface = NodeGroupInterface.objects.get(
            nodegroup__uuid=nodegroup.uuid, name=data['name'])
        self.assertThat(
            reload_object(interface),
            MatchesStructure.byEquality(**data))
