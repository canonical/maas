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

from collections import Callable
import httplib
import os

from django.conf import settings
from django.core.urlresolvers import reverse
from django.test.client import RequestFactory
from maasserver.testing import extract_redirect
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from maasserver.views.combo import (
    get_absolute_location,
    get_combo_view,
    )


class TestUtilities(TestCase):

    def test_get_abs_location_returns_absolute_location_if_not_None(self):
        abs_location = '%s%s' % (os.path.sep, factory.getRandomString())
        self.assertEqual(
            abs_location, get_absolute_location(location=abs_location))

    def test_get_abs_location_returns_rel_loc_if_static_root_not_none(self):
        static_root = factory.getRandomString()
        self.patch(settings, 'STATIC_ROOT', static_root)
        rel_location = os.path.join(
            factory.getRandomString(), factory.getRandomString())
        expected_location = os.path.join(static_root, rel_location)
        self.assertEqual(
            expected_location, get_absolute_location(location=rel_location))

    def test_get_abs_location_returns_rel_loc_if_static_root_is_none(self):
        self.patch(settings, 'STATIC_ROOT', None)
        rel_location = os.path.join(
            factory.getRandomString(), factory.getRandomString())
        rel_location_base = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'static')
        expected_location = os.path.join(rel_location_base, rel_location)
        self.assertEqual(
            expected_location, get_absolute_location(location=rel_location))

    def test_get_combo_view_returns_callable(self):
        rel_location = os.path.join(
            factory.getRandomString(), factory.getRandomString())
        view = get_combo_view(rel_location)
        self.assertIsInstance(view, Callable)

    def test_get_combo_view_loads_from_disk(self):
        test_file_contents = factory.getRandomString()
        # Create a valid file with a proper extension (the combo loader only
        # serves JS or CSS files)
        test_file_name = "%s.js" % factory.getRandomString()
        test_file = self.make_file(
            name=test_file_name, contents=test_file_contents)
        directory = os.path.dirname(test_file)
        view = get_combo_view(directory)
        # Create a request for test file.
        rf = RequestFactory()
        request = rf.get("/test/?%s" % test_file_name)
        response = view(request)
        expected_content = '/* %s */\n%s\n' % (
            test_file_name, test_file_contents)
        self.assertEqual(
             (httplib.OK, expected_content),
             (response.status_code, response.content))

    def test_get_combo_redirects_if_unknown_type(self):
        # The optional parameter 'default_redirect' allows to configure
        # a default address where requests for files of unknown types will be
        # redirected.
        # Create a test file with an unknown extension.
        test_file_name = "%s.%s" % (
            factory.getRandomString(), factory.getRandomString())
        redirect_root = factory.getRandomString()
        view = get_combo_view(
            factory.getRandomString(), default_redirect=redirect_root)
        rf = RequestFactory()
        request = rf.get("/test/?%s" % test_file_name)
        response = view(request)
        self.assertEqual(
            '%s%s' % (redirect_root, test_file_name),
            extract_redirect(response))


# String used by convoy to replace missing files.
CONVOY_MISSING_FILE = "/* [missing] */"


class TestComboLoaderView(TestCase):
    """Test combo loader views."""

    def test_yui_load_js(self):
        requested_files = [
            'oop/oop.js',
            'event-custom-base/event-custom-base.js'
            ]
        url = '%s?%s' % (reverse('combo-yui'), '&'.join(requested_files))
        response = self.client.get(url)
        self.assertIn('text/javascript', response['Content-Type'])
        for requested_file in requested_files:
            self.assertIn(requested_file, response.content)
        # No sign of a missing js file.
        self.assertNotIn(CONVOY_MISSING_FILE, response.content)
        # The file contains a link to YUI's licence.
        self.assertIn('http://yuilibrary.com/license/', response.content)

    def test_yui_load_css(self):
        requested_files = [
            'widget-base/assets/skins/sam/widget-base.css',
            'widget-stack/assets/skins/sam/widget-stack.css',
            ]
        url = '%s?%s' % (reverse('combo-yui'), '&'.join(requested_files))
        response = self.client.get(url)
        self.assertIn('text/css', response['Content-Type'])
        for requested_file in requested_files:
            self.assertIn(requested_file, response.content)
        # No sign of a missing css file.
        self.assertNotIn(CONVOY_MISSING_FILE, response.content)
        # The file contains a link to YUI's licence.
        self.assertIn('http://yuilibrary.com/license/', response.content)

    def test_yui_combo_no_file_returns_not_found(self):
        response = self.client.get(reverse('combo-yui'))
        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_yui_combo_other_file_extension_returns_bad_request(self):
        url = '%s?%s' % (reverse('combo-yui'), 'file.wrongextension')
        response = self.client.get(url)
        self.assertEqual(
                (httplib.BAD_REQUEST, "Invalid file type requested."),
                (response.status_code, response.content))

    def test_maas_load_js(self):
        requested_files = ['js/node.js', 'js/enums.js']
        url = '%s?%s' % (reverse('combo-maas'), '&'.join(requested_files))
        response = self.client.get(url)
        # No sign of a missing js file.
        self.assertNotIn(CONVOY_MISSING_FILE, response.content)

    def test_maas_load_css(self):
        requested_files = ['css/base.css', 'css/forms.css']
        url = '%s?%s' % (reverse('combo-maas'), '&'.join(requested_files))
        response = self.client.get(url)
        # No sign of a missing css file.
        self.assertNotIn(CONVOY_MISSING_FILE, response.content)

    def test_maas_load_image(self):
        img_path = 'img/bg_dots.png'
        url = '%s?%s' % (reverse('combo-maas'), img_path)
        response = self.client.get(url)
        self.assertEqual(
            '%s%s' % (settings.STATIC_URL, img_path),
            extract_redirect(response))

    def test_raphael_load_js(self):
        requested_files = ['raphael-min.js']
        url = '%s?%s' % (reverse('combo-raphael'), '&'.join(requested_files))
        response = self.client.get(url)
        # No sign of a missing js file.
        self.assertNotIn(CONVOY_MISSING_FILE, response.content.decode('utf8'))
