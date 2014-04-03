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

from django.core.urlresolvers import reverse
from lxml.html import fromstring
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUP_STATUS_CHOICES,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.models import (
    NodeGroup,
    nodegroup as nodegroup_module,
    NodeGroupInterface,
    )
from maasserver.testing import (
    extract_redirect,
    get_content_links,
    reload_object,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import map_enum
from maasserver.views.clusters import ClusterListView
from mock import (
    ANY,
    call,
    )
from testtools.matchers import (
    AllMatch,
    Contains,
    ContainsAll,
    Equals,
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
            factory.make_node_group(status=self.status)
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
        other_status = factory.getRandomChoice(
            NODEGROUP_STATUS_CHOICES, but_not=[self.status])
        factory.make_node_group(status=other_status)
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
        other_status = factory.getRandomChoice(
            NODEGROUP_STATUS_CHOICES, but_not=[self.status])
        link_name = ClusterListView.status_links[other_status]
        view = self.make_listing_view(self.status)
        entry = view.make_title_entry(other_status, link_name)
        status_name = NODEGROUP_STATUS_CHOICES[other_status][1]
        self.assertEqual(
            '0 %s clusters' % status_name.lower(), entry)

    def test_title_displays_number_of_clusters(self):
        for _ in range(3):
            factory.make_node_group(status=self.status)
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
                factory.make_node_group(status=status)
        for status in other_statuses:
            link_name = ClusterListView.status_links[status]
            title = view.make_cluster_listing_title()
            self.assertIn(reverse(link_name), title)

    def test_listing_is_paginated(self):
        self.patch(ClusterListView, "paginate_by", 2)
        self.client_log_in(as_admin=True)
        for _ in range(3):
            factory.make_node_group(status=self.status)
        response = self.client.get(self.get_url())
        self.assertEqual(httplib.OK, response.status_code)
        doc = fromstring(response.content)
        self.assertThat(
            doc.cssselect('div.pagination'),
            HasLength(1),
            "Couldn't find pagination tag.")


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
        factory.make_node_group(status=NODEGROUP_STATUS.PENDING),
        response = self.client.get(reverse('cluster-list-pending'))
        doc = fromstring(response.content)
        forms = doc.cssselect('form#accept_all_pending_nodegroups')
        self.assertEqual(1, len(forms))

    def test_pending_listing_contains_form_to_reject_all_nodegroups(self):
        self.client_log_in(as_admin=True)
        factory.make_node_group(status=NODEGROUP_STATUS.PENDING),
        response = self.client.get(reverse('cluster-list-pending'))
        doc = fromstring(response.content)
        forms = doc.cssselect('form#reject_all_pending_nodegroups')
        self.assertEqual(1, len(forms))

    def test_pending_listing_accepts_all_pending_nodegroups_POST(self):
        self.client_log_in(as_admin=True)
        nodegroups = {
            factory.make_node_group(status=NODEGROUP_STATUS.PENDING),
            factory.make_node_group(status=NODEGROUP_STATUS.PENDING),
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
            factory.make_node_group(status=NODEGROUP_STATUS.PENDING),
            factory.make_node_group(status=NODEGROUP_STATUS.PENDING),
        }
        response = self.client.post(
            reverse('cluster-list-pending'), {'mass_reject_submit': 1})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(
            [reload_object(nodegroup).status for nodegroup in nodegroups],
            [NODEGROUP_STATUS.REJECTED] * 2)


class ClusterAcceptedListingTest(MAASServerTestCase):

    def test_accepted_listing_import_boot_images_calls_tasks(self):
        self.client_log_in(as_admin=True)
        recorder = self.patch(nodegroup_module, 'import_boot_images')
        accepted_nodegroups = [
            factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED),
            factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED),
        ]
        response = self.client.post(
            reverse('cluster-list'), {'import_all_boot_images': 1})
        self.assertEqual(httplib.FOUND, response.status_code)
        calls = [
            call(queue=nodegroup.work_queue, kwargs=ANY)
            for nodegroup in accepted_nodegroups
        ]
        self.assertItemsEqual(calls, recorder.apply_async.call_args_list)

    def test_a_warning_is_displayed_if_the_cluster_has_no_boot_images(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED)
        response = self.client.get(reverse('cluster-list'))
        document = fromstring(response.content)
        nodegroup_row = document.xpath("//tr[@id='%s']" % nodegroup.uuid)[0]
        self.assertIn('warning', nodegroup_row.get('class'))
        warning_elems = (
            nodegroup_row.xpath(
                "//img[@title='Warning: this cluster has no boot images.']"))
        self.assertEqual(
            1, len(warning_elems), "No warning about missing boot images.")


class ClusterDeleteTest(MAASServerTestCase):

    def test_can_delete_cluster(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_node_group()
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
        nodegroup = factory.make_node_group()
        interfaces = set()
        for i in range(3):
            interface = factory.make_node_group_interface(
                nodegroup=nodegroup,
                management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
            interfaces.add(interface)
        links = get_content_links(
            self.client.get(reverse('cluster-edit', args=[nodegroup.uuid])))
        interface_edit_links = [
            reverse(
                'cluster-interface-edit',
                args=[nodegroup.uuid, interface.interface])
            for interface in interfaces]
        interface_delete_links = [
            reverse(
                'cluster-interface-delete',
                args=[nodegroup.uuid, interface.interface])
            for interface in interfaces]
        self.assertThat(
            links,
            ContainsAll(interface_edit_links + interface_delete_links))

    def test_can_edit_cluster(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_node_group()
        edit_link = reverse('cluster-edit', args=[nodegroup.uuid])
        data = {
            'cluster_name': factory.make_name('cluster_name'),
            'name': factory.make_name('name'),
            'status': factory.getRandomEnum(NODEGROUP_STATUS),
            }
        response = self.client.post(edit_link, data)
        self.assertEqual(httplib.FOUND, response.status_code, response.content)
        self.assertThat(
            reload_object(nodegroup),
            MatchesStructure.byEquality(**data))

    def test_contains_link_to_add_interface(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_node_group()
        links = get_content_links(
            self.client.get(reverse('cluster-edit', args=[nodegroup.uuid])))
        self.assertIn(
            reverse('cluster-interface-create', args=[nodegroup.uuid]), links)

    def test_contains_link_to_boot_image_list(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_node_group()
        [factory.make_boot_image(nodegroup=nodegroup) for _ in range(3)]
        response = self.client.get(
            reverse('cluster-edit', args=[nodegroup.uuid]))
        self.assertEqual(
            httplib.OK, response.status_code, response.content)
        links = get_content_links(response)
        self.assertIn(
            reverse('cluster-bootimages-list', args=[nodegroup.uuid]), links)

    def test_displays_warning_if_boot_image_list_is_empty(self):
        # Create boot images in another nodegroup.
        [factory.make_boot_image() for _ in range(3)]
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_node_group()
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
        nodegroup = factory.make_node_group()
        interface = factory.make_node_group_interface(
            nodegroup=nodegroup,
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        delete_link = reverse(
            'cluster-interface-delete',
            args=[nodegroup.uuid, interface.interface])
        response = self.client.post(delete_link, {'post': 'yes'})
        self.assertEqual(
            (httplib.FOUND, reverse('cluster-edit', args=[nodegroup.uuid])),
            (response.status_code, extract_redirect(response)))
        self.assertFalse(
            NodeGroupInterface.objects.filter(id=interface.id).exists())

    def test_interface_delete_supports_interface_alias(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_node_group(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        interface = factory.make_node_group_interface(
            nodegroup=nodegroup, interface="eth0:0")
        delete_link = reverse(
            'cluster-interface-delete',
            args=[nodegroup.uuid, interface.interface])
        # The real test is that reverse() does not blow up when the
        # interface's name contains an alias.
        self.assertIsInstance(delete_link, (bytes, unicode))


class ClusterInterfaceEditTest(MAASServerTestCase):

    def test_can_edit_cluster_interface(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_node_group(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        interface = factory.make_node_group_interface(
            nodegroup=nodegroup)
        edit_link = reverse(
            'cluster-interface-edit',
            args=[nodegroup.uuid, interface.interface])
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
        nodegroup = factory.make_node_group(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        interface = factory.make_node_group_interface(
            nodegroup=nodegroup, interface="eth0:0")
        edit_link = reverse(
            'cluster-interface-edit',
            args=[nodegroup.uuid, interface.interface])
        # The real test is that reverse() does not blow up when the
        # interface's name contains an alias.
        self.assertIsInstance(edit_link, (bytes, unicode))


class ClusterInterfaceCreateTest(MAASServerTestCase):

    def test_can_create_cluster_interface(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_node_group(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        create_link = reverse(
            'cluster-interface-create', args=[nodegroup.uuid])
        data = factory.get_interface_fields()
        response = self.client.post(create_link, data)
        self.assertEqual(
            (httplib.FOUND, reverse('cluster-edit', args=[nodegroup.uuid])),
            (response.status_code, extract_redirect(response)))
        interface = NodeGroupInterface.objects.get(
            nodegroup__uuid=nodegroup.uuid, interface=data['interface'])
        self.assertThat(
            reload_object(interface),
            MatchesStructure.byEquality(**data))


# XXX: rvb 2012-10-08 bug=1063881: apache transforms '//' into '/' in
# the urls it passes around and this happens when an interface has an empty
# name.
class ClusterInterfaceDoubleSlashBugTest(MAASServerTestCase):

    def test_edit_delete_empty_cluster_interface_when_slash_removed(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_node_group()
        interface = factory.make_node_group_interface(
            nodegroup=nodegroup, interface='',
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        edit_link = reverse(
            'cluster-interface-edit',
            args=[nodegroup.uuid, interface.interface])
        delete_link = reverse(
            'cluster-interface-delete',
            args=[nodegroup.uuid, interface.interface])
        links = [edit_link, delete_link]
        # Just make sure that the urls contains '//'.  If this is not
        # true anymore, because we've refactored the urls, this test can
        # problably be removed.
        self.assertThat(links, AllMatch(Contains('//')))
        # Simulate what apache (when used as a frontend) does to the
        # urls.
        new_links = [link.replace('//', '/') for link in links]
        response_statuses = [
            self.client.get(link).status_code for link in new_links]
        self.assertThat(response_statuses, AllMatch(Equals(httplib.OK)))
