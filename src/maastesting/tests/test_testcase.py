# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `TestCase`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import os.path
from shutil import rmtree
from tempfile import mkdtemp

from maastesting.factory import factory
from maastesting.testcase import TestCase
from mock import MagicMock
from testtools.matchers import (
    DirExists,
    FileExists,
    )


class TestTestCase(TestCase):
    """Tests the base `TestCase` facilities."""

    def test_make_dir_creates_directory(self):
        self.assertThat(self.make_dir(), DirExists())

    def test_make_dir_creates_temporary_directory(self):
        other_temp_dir = mkdtemp()
        self.addCleanup(rmtree, other_temp_dir)
        other_temp_root, other_subdir = os.path.split(other_temp_dir)
        temp_root, subdir = os.path.split(self.make_dir())
        self.assertEqual(other_temp_root, temp_root)
        self.assertNotIn(subdir, [b'', u'', None])

    def test_make_dir_creates_one_directory_per_call(self):
        self.assertNotEqual(self.make_dir(), self.make_dir())

    def test_make_file_creates_file(self):
        self.assertThat(self.make_file(), FileExists())

    def test_make_file_uses_temporary_directory(self):
        directory = self.make_dir()
        self.patch(self, 'make_dir', lambda: directory)
        dir_part, file_part = os.path.split(self.make_file())
        self.assertEqual(directory, dir_part)

    def test_patch_can_mock(self):
        # The patch method patches-in and returns a new MagicMock() instance
        # if no attribute value is given.
        attribute_name = factory.make_name("attribute")
        self.assertRaises(AttributeError, getattr, self, attribute_name)
        attribute = self.patch(self, attribute_name)
        self.assertIs(getattr(self, attribute_name), attribute)
        self.assertIsInstance(attribute, MagicMock)
