# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver boot image list view."""

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

from django.core.urlresolvers import reverse
from lxml.html import fromstring
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.views.clusters import BootImagesListView
from provisioningserver.boot.tests.test_tftppath import make_osystem
from testtools.matchers import ContainsAll


class BootImageListTest(MAASServerTestCase):

    def setUp(self):
        super(BootImageListTest, self).setUp()

    def test_contains_boot_image_list(self):
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_NodeGroup()
        boot_images = [
            factory.make_BootImage(nodegroup=nodegroup) for _ in range(3)]
        for bi in boot_images:
            make_osystem(self, bi.osystem, ['install'])
        response = self.client.get(
            reverse('cluster-bootimages-list', args=[nodegroup.uuid]))
        self.assertEqual(
            httplib.OK, response.status_code, response.content)
        items_in_page = [
            [
                '%s' % image.id,
                image.label,
                image.purpose,
                image.release,
                image.subarchitecture,
                image.architecture,
                image.osystem,
                '%s' % image.updated.year,
            ] for image in boot_images]
        self.assertThat(
            response.content, ContainsAll(itertools.chain(*items_in_page)))

    def test_listing_is_paginated(self):
        self.patch(BootImagesListView, "paginate_by", 3)
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_NodeGroup()
        # Create 4 images.
        boot_images = [
            factory.make_BootImage(nodegroup=nodegroup)
            for _ in range(4)
            ]
        for bi in boot_images:
            make_osystem(self, bi.osystem, ['install'])
        response = self.client.get(
            reverse('cluster-bootimages-list', args=[nodegroup.uuid]))
        self.assertEqual(httplib.OK, response.status_code)
        doc = fromstring(response.content)
        self.assertEqual(
            1, len(doc.cssselect('div.pagination')),
            "Couldn't find pagination tag.")

    def test_displays_warning_if_boot_image_list_is_empty(self):
        # Create boot images in another nodegroup.
        boot_images = [factory.make_BootImage() for _ in range(3)]
        for bi in boot_images:
            make_osystem(self, bi.osystem, ['install'])
        self.client_log_in(as_admin=True)
        nodegroup = factory.make_NodeGroup()
        response = self.client.get(
            reverse('cluster-bootimages-list', args=[nodegroup.uuid]))
        self.assertEqual(httplib.OK, response.status_code)
        doc = fromstring(response.content)
        self.assertEqual(
            1, len(doc.cssselect('#no_boot_images_warning')),
            "Warning about missing images not present")
