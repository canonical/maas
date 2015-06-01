# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for blockdevice API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import json

from django.core.urlresolvers import reverse
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object


def get_blockdevice_uri(device):
    """Return a BlockDevice's URI on the API."""
    return reverse('blockdevice_handler', args=[device.id])


class TestBlockDeviceAPI(APITestCase):

    def test_add_tag_to_block_device(self):
        self.become_admin()
        device = factory.make_BlockDevice()
        tag_to_be_added = factory.make_name('tag')
        uri = get_blockdevice_uri(device)
        response = self.client.get(
            uri, {'op': 'add_tag', 'tag': tag_to_be_added})

        # Ensure the response status is OK
        self.assertEqual(httplib.OK, response.status_code, response.content)

        # Ensure the change was persisted
        device = reload_object(device)
        self.assertIn(tag_to_be_added, device.tags)

        # Check whether the returned data reflects the change
        parsed_device = json.loads(response.content)
        self.assertIn(tag_to_be_added, parsed_device['tags'])

    def test_remove_tag_from_block_device(self):
        self.become_admin()
        device = factory.make_BlockDevice()
        tag_to_be_removed = device.tags[0]
        uri = get_blockdevice_uri(device)
        response = self.client.get(
            uri, {'op': 'remove_tag', 'tag': tag_to_be_removed})

        # Ensure the response status is OK
        self.assertEqual(httplib.OK, response.status_code, response.content)

        # Ensure the change was persisted
        device = reload_object(device)
        self.assertNotIn(tag_to_be_removed, device.tags)

        # Check whether the returned data reflects the change
        parsed_device = json.loads(response.content)
        self.assertNotIn(tag_to_be_removed, parsed_device['tags'])
