# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver images views."""

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
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.views import images as images_view
from maastesting.matchers import MockCalledOnceWith


class UbuntuImagesTest(MAASServerTestCase):

    def test_shows_missing_images_warning_if_not_ubuntu_boot_resources(self):
        self.client_log_in()
        response = self.client.get(reverse('images'))
        doc = fromstring(response.content)
        warnings = doc.cssselect('div#missing-ubuntu-images')
        self.assertEqual(1, len(warnings))

    def test_post_returns_forbidden_if_not_admin(self):
        self.client_log_in()
        response = self.client.post(
            reverse('images'), {'ubuntu_images': 1})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_import_button_calls_import_resources(self):
        self.client_log_in(as_admin=True)
        mock_import = self.patch(images_view, 'import_resources')
        response = self.client.post(
            reverse('images'), {'ubuntu_images': 1})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertThat(mock_import, MockCalledOnceWith())
