# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `ephemerals_script`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import os.path

from maastesting.factory import factory
from provisioningserver.import_images.ephemerals_script import (
    copy_file_by_glob,
    )
from provisioningserver.testing.testcase import PservTestCase
from testtools.matchers import FileContains


def split_path(path):
    """Return directory and filename component of a file path."""
    return os.path.dirname(path), os.path.basename(path)


class TestHelpers(PservTestCase):
    def make_target(self):
        """Return an existing directory, and nonexistent filename."""
        return self.make_dir(), factory.make_name()

    def test_copy_file_by_glob_copies_file(self):
        content = factory.getRandomString()
        source_dir, source_name = split_path(self.make_file(contents=content))
        target_dir, target_name = self.make_target()

        copy_file_by_glob(
            source_dir, source_name[:3] + '*',
            target_dir, target_name)

        self.assertThat(
            os.path.join(source_dir, source_name),
            FileContains(content))
        self.assertThat(
            os.path.join(target_dir, target_name),
            FileContains(content))

    def test_copy_by_file_returns_target_path(self):
        source_dir, source_name = split_path(self.make_file())
        target_dir, target_name = self.make_target()

        target = copy_file_by_glob(
            source_dir, source_name, target_dir, target_name)

        self.assertEqual(os.path.join(target_dir, target_name), target)

    def test_copy_file_by_glob_ignores_nonmatching_files(self):
        content = factory.getRandomString()
        source_dir, source_name = split_path(self.make_file(contents=content))
        other_content = factory.getRandomString()
        other_file = factory.make_file(source_dir, contents=other_content)
        target_dir, target_name = self.make_target()

        copy_file_by_glob(source_dir, source_name, target_dir, target_name)

        self.assertThat(other_file, FileContains(other_content))
        self.assertThat(
            os.path.join(target_dir, target_name),
            FileContains(content))
        self.assertItemsEqual(
            [source_name, os.path.basename(other_file)],
            os.listdir(source_dir))
        self.assertItemsEqual([target_name], os.listdir(target_dir))

    def test_copy_file_by_glob_fails_if_no_files_match(self):
        self.assertRaises(
            AssertionError,
            copy_file_by_glob,
            self.make_dir(), factory.make_name() + '*',
            self.make_dir(), factory.make_name())

    def test_copy_file_by_glob_fails_if_multiple_files_match(self):
        source_dir = self.make_dir()
        factory.make_file(source_dir)
        factory.make_file(source_dir)

        self.assertRaises(
            AssertionError,
            copy_file_by_glob,
            source_dir, '*', self.make_dir(), factory.make_name())
