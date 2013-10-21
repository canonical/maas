# Copyright 2012 Canonical Ltd.  This software is licensed under the
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
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.models import (
    NodeGroup,
    NodeGroupInterface,
    )
from maasserver.testing import (
    extract_redirect,
    get_content_links,
    reload_object,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import AdminLoggedInTestCase
from maastesting.matchers import ContainsAll
from testtools.matchers import (
    AllMatch,
    Contains,
    Equals,
    MatchesStructure,
    )


class ClusterListingTest(AdminLoggedInTestCase):

    def test_settings_contains_links_to_edit_and_delete_clusters(self):
        nodegroups = {
            factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED),
            factory.make_node_group(status=NODEGROUP_STATUS.PENDING),
            factory.make_node_group(status=NODEGROUP_STATUS.REJECTED),
            }
        links = get_content_links(self.client.get(reverse('settings')))
        nodegroup_edit_links = [
            reverse('cluster-edit', args=[nodegroup.uuid])
            for nodegroup in nodegroups]
        nodegroup_delete_links = [
            reverse('cluster-delete', args=[nodegroup.uuid])
            for nodegroup in nodegroups]
        self.assertThat(
            links,
            ContainsAll(nodegroup_edit_links + nodegroup_delete_links))


class ClusterDeleteTest(AdminLoggedInTestCase):

    def test_can_delete_cluster(self):
        nodegroup = factory.make_node_group()
        delete_link = reverse('cluster-delete', args=[nodegroup.uuid])
        response = self.client.post(delete_link, {'post': 'yes'})
        self.assertEqual(
            (httplib.FOUND, reverse('settings')),
            (response.status_code, extract_redirect(response)))
        self.assertFalse(
            NodeGroup.objects.filter(uuid=nodegroup.uuid).exists())


class ClusterEditTest(AdminLoggedInTestCase):

    def test_cluster_page_contains_links_to_edit_and_delete_interfaces(self):
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
        nodegroup = factory.make_node_group()
        links = get_content_links(
            self.client.get(reverse('cluster-edit', args=[nodegroup.uuid])))
        self.assertIn(
            reverse('cluster-interface-create', args=[nodegroup.uuid]), links)


class ClusterInterfaceDeleteTest(AdminLoggedInTestCase):

    def test_can_delete_cluster_interface(self):
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


class ClusterInterfaceEditTest(AdminLoggedInTestCase):

    def test_can_edit_cluster_interface(self):
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


class ClusterInterfaceCreateTest(AdminLoggedInTestCase):

    def test_can_create_cluster_interface(self):
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

    def test_rejects_interface_creation_if_cluster_already_managed(self):
        nodegroup = factory.make_node_group(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        create_link = reverse(
            'cluster-interface-create', args=[nodegroup.uuid])
        # nodegroup already has a 'managed' interface, try adding another
        # one, also 'managed'.
        data = factory.get_interface_fields(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        response = self.client.post(create_link, data)
        self.assertEqual(httplib.OK, response.status_code)
        error_message = (
            "Another managed interface already exists for this cluster.")
        self.assertThat(response.content, Contains(error_message))


# XXX: rvb 2012-10-08 bug=1063881: apache transforms '//' into '/' in
# the urls it passes around and this happens when an interface has an empty
# name.
class ClusterInterfaceDoubleSlashBugTest(AdminLoggedInTestCase):

    def test_edit_delete_empty_cluster_interface_when_slash_removed(self):
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
