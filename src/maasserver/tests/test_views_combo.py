# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test combo view."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import httplib
import os

from django.conf import settings
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from maasserver.views.combo import get_yui_location


class TestUtilities(TestCase):

    def test_get_yui_location_if_static_root_is_none(self):
        self.patch(settings, 'STATIC_ROOT', None)
        yui_location = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'static', 'jslibs', 'yui')
        self.assertEqual(yui_location, get_yui_location())

    def test_get_yui_location(self):
        static_root = factory.getRandomString()
        self.patch(settings, 'STATIC_ROOT', static_root)
        yui_location = os.path.join(static_root, 'jslibs', 'yui')
        self.assertEqual(yui_location, get_yui_location())


class TestComboLoaderView(TestCase):
    """Test combo loader view."""

    def test_load_js(self):
        requested_files = [
            'tests/build/oop/oop.js',
            'tests/build/event-custom-base/event-custom-base.js'
            ]
        response = self.client.get('/combo/?%s' % '&'.join(requested_files))
        self.assertIn('text/javascript', response['Content-Type'])
        for requested_file in requested_files:
            self.assertIn(requested_file, response.content)
        # No sign of a missing js file.
        self.assertNotIn("/* [missing] */", response.content)
        # The file contains a link to YUI's licence.
        self.assertIn('http://yuilibrary.com/license/', response.content)

    def test_load_css(self):
        requested_files = [
            'tests/build/widget-base/assets/skins/sam/widget-base.css',
            'tests/build/widget-stack/assets/skins/sam/widget-stack.css',
            ]
        response = self.client.get('/combo/?%s' % '&'.join(requested_files))
        self.assertIn('text/css', response['Content-Type'])
        for requested_file in requested_files:
            self.assertIn(requested_file, response.content)
        # No sign of a missing css file.
        self.assertNotIn("/* [missing] */", response.content)
        # The file contains a link to YUI's licence.
        self.assertIn('http://yuilibrary.com/license/', response.content)

    def test_combo_no_file_returns_not_found(self):
        response = self.client.get('/combo/')
        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_combo_wrong_file_extension_returns_bad_request(self):
        response = self.client.get('/combo/?file.wrongextension')
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual("Invalid file type requested.", response.content)
