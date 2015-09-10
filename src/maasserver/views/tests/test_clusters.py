# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
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
    NODEGROUP_STATE,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
)
from maasserver.models import (
    BootResource,
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
from maasserver.views.clusters import ClusterListView
from netaddr import IPNetwork
from testtools.matchers import (
    ContainsAll,
    HasLength,
    MatchesStructure,
)


class ClusterListingTest(MAASServerTestCase):

    def get_url(self):
        """Return the listing url used in this scenario."""
        return reverse('cluster-list')

    def make_listing_view(self, status):
        view = ClusterListView()
        view.status = status
        return view

    def test_listing_is_paginated(self):
        self.patch(ClusterListView, "paginate_by", 2)
        self.client_log_in(as_admin=True)
        for _ in range(3):
            factory.make_NodeGroup()
        response = self.client.get(self.get_url())
        self.assertEqual(httplib.OK, response.status_code)
        doc = fromstring(response.content)
        self.assertThat(
            doc.cssselect('div.pagination'),
            HasLength(1),
            "Couldn't find pagination tag.")


class ClusterListingStateTest(MAASServerTestCase):

    scenarios = [
        ('disconnected', {
            'state': NODEGROUP_STATE.DISCONNECTED,
            'text': '-',
            'connection': '&cross;',
            }),
        ('out-of-sync', {
            'state': NODEGROUP_STATE.OUT_OF_SYNC,
            'text': NODEGROUP_STATE.OUT_OF_SYNC,
            'connection': '&check;',
            }),
        ('syncing', {
            'state': NODEGROUP_STATE.SYNCING,
            'text': NODEGROUP_STATE.SYNCING,
            'connection': '&check;',
            }),
        ('synced', {
            'state': NODEGROUP_STATE.SYNCED,
            'text': NODEGROUP_STATE.SYNCED,
            'connection': '&check;',
            }),
    ]

    def test_listing_displays_connected_image_status(self):
        self.client_log_in(as_admin=True)
        factory.make_BootResource()
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED, name=self.state)

        def mock_get_state(self):
            # Return a state, which is set to the name of the node.
            return self.name
        self.patch(NodeGroup, 'get_state', mock_get_state)

        response = self.client.get(
            reverse('cluster-list'))
        document = fromstring(response.content)
        images_col = document.xpath(
            "//td[@id='%s_images']" % nodegroup.uuid)[0]
        connection_col = document.xpath(
            "//td[@id='%s_connection']" % nodegroup.uuid)[0]
        self.assertEqual(
            self.text, images_col.text_content().strip())
        self.assertEqual(
            self.connection, connection_col.text_content().strip())


class ClusterListingNoImagesTest(MAASServerTestCase):

    def test_listing_displays_no_images_available(self):
        self.client_log_in(as_admin=True)
        BootResource.objects.all().delete()
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED)

        def mock_get_state(self):
            return NODEGROUP_STATE.OUT_OF_SYNC
        self.patch(NodeGroup, 'get_state', mock_get_state)

        response = self.client.get(
            reverse('cluster-list'))
        document = fromstring(response.content)
        images_col = document.xpath(
            "//td[@id='%s_images']" % nodegroup.uuid)[0]
        self.assertEqual(
            "No images available", images_col.text_content().strip())


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

    def test_admin_can_disable_default_disable_ipv4_flag(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_NodeGroup(default_disable_ipv4=True)
        edit_link = reverse('cluster-edit', args=[nodegroup.uuid])
        # In a UI submission, omitting a boolean means setting it to False.
        data = {
            'ui_submission': True,
            }
        response = self.client.post(edit_link, data)
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertFalse(reload_object(nodegroup).default_disable_ipv4)


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
        del data['subnet']
        response = self.client.post(edit_link, data)
        self.assertEqual(
            (httplib.FOUND, reverse('cluster-edit', args=[nodegroup.uuid])),
            (response.status_code, extract_redirect(response)))
        interface = reload_object(interface)
        self.assertThat(
            interface,
            MatchesStructure.byEquality(**data))
        cidr = unicode(
            IPNetwork("%s/%s" % (data['ip'], data['subnet_mask'])).cidr)
        self.assertThat(
            interface.subnet,
            MatchesStructure.byEquality(cidr=cidr))

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
        del data['subnet']
        response = self.client.post(create_link, data)
        self.assertEqual(
            (httplib.FOUND, reverse('cluster-edit', args=[nodegroup.uuid])),
            (response.status_code, extract_redirect(response)))
        interface = NodeGroupInterface.objects.get(
            nodegroup__uuid=nodegroup.uuid, name=data['name'])
        self.assertThat(
            reload_object(interface),
            MatchesStructure.byEquality(**data))
