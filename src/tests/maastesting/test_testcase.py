# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `MAASTestCase`."""


import os.path
from shutil import rmtree
from tempfile import mkdtemp
from unittest import mock as mock_module
from unittest.mock import call, MagicMock, sentinel

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase


class TestTestCase(MAASTestCase):
    """Tests the base `MAASTestCase` facilities."""

    def test_make_dir_creates_directory(self):
        self.assertTrue(os.path.isdir(self.make_dir()))

    def test_make_dir_creates_temporary_directory(self):
        other_temp_dir = mkdtemp()
        self.addCleanup(rmtree, other_temp_dir)
        other_temp_root, other_subdir = os.path.split(other_temp_dir)
        temp_root, subdir = os.path.split(self.make_dir())
        self.assertEqual(other_temp_root, temp_root)
        self.assertNotIn(subdir, [b"", "", None])

    def test_make_dir_creates_one_directory_per_call(self):
        self.assertNotEqual(self.make_dir(), self.make_dir())

    def test_make_file_creates_file(self):
        self.assertTrue(os.path.isfile(self.make_file()))

    def test_make_file_uses_temporary_directory(self):
        directory = self.make_dir()
        self.patch(self, "make_dir", lambda: directory)
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

    def method_to_be_patched(self, a, b):
        return sentinel.method_to_be_patched

    def test_patch_autospec_creates_autospec_from_target(self):
        # Grab a reference to this now.
        method_to_be_patched = self.method_to_be_patched

        # It's simpler to test that create_autospec has been called than it is
        # to test the result of calling it; mock does some clever things to do
        # what it does that make comparisons hard.
        create_autospec = self.patch(mock_module, "create_autospec")
        create_autospec.return_value = sentinel.autospec

        method_to_be_patched_autospec = self.patch_autospec(
            self,
            "method_to_be_patched",
            spec_set=sentinel.spec_set,
            instance=sentinel.instance,
        )

        self.assertIs(sentinel.autospec, method_to_be_patched_autospec)
        self.assertIs(sentinel.autospec, self.method_to_be_patched)
        create_autospec.assert_called_once_with(
            method_to_be_patched, sentinel.spec_set, sentinel.instance
        )

    def test_patch_autospec_really_leaves_an_autospec_behind(self):
        self.patch_autospec(self, "method_to_be_patched")
        # The patched method can be called with positional or keyword
        # arguments.
        self.method_to_be_patched(1, 2)
        self.method_to_be_patched(3, b=4)
        self.method_to_be_patched(a=5, b=6)
        self.method_to_be_patched.assert_has_calls(
            [call(1, 2), call(3, b=4), call(a=5, b=6)]
        )
        # Calling the patched method with unrecognised arguments or not
        # enough arguments results in an exception.
        self.assertRaises(TypeError, self.method_to_be_patched, c=7)
        self.assertRaises(TypeError, self.method_to_be_patched, 8)
        self.assertRaises(TypeError, self.method_to_be_patched, b=9)

    def test_assertSequenceEqual_rejects_mappings(self):
        self.assertRaises(AssertionError, self.assertSequenceEqual, {}, [])
        self.assertRaises(AssertionError, self.assertSequenceEqual, [], {})
        self.assertRaises(AssertionError, self.assertSequenceEqual, {}, {})
        self.assertSequenceEqual([], [])

    def test_assertSequenceEqual_ignores_mappings_if_seq_type_is_set(self):
        self.assertSequenceEqual({}, {}, seq_type=dict)

    def test_assertSequenceEqual_forwards_message(self):
        message = factory.make_name("message")
        error = self.assertRaises(
            AssertionError, self.assertSequenceEqual, [1], [2], message
        )
        self.assertIn(message, str(error))
