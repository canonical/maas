# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for filesystem paths."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from os import getcwdu
import os.path

from fixtures import EnvironmentVariableFixture
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.path import get_path
from testtools.matchers import StartsWith


class TestGetPath(MAASTestCase):

    def set_root(self, root_path=None):
        """For the duration of this test, set the `MAAS_ROOT` variable`."""
        self.useFixture(EnvironmentVariableFixture('MAAS_ROOT', root_path))

    def test__defaults_to_root(self):
        self.set_root()
        self.assertEqual('/', get_path())

    def test__appends_path_elements(self):
        self.set_root()
        part1 = factory.make_name('dir')
        part2 = factory.make_name('file')
        self.assertEqual(
            os.path.join('/', part1, part2),
            get_path(part1, part2))

    def test__obeys_MAAS_ROOT_variable(self):
        root = factory.make_name('/root')
        self.set_root(root)
        path = factory.make_name('path')
        self.assertEqual(os.path.join(root, path), get_path(path))

    def test__returns_absolute_path(self):
        self.set_root('.')
        self.assertThat(get_path(), StartsWith('/'))
        self.assertEqual(getcwdu(), get_path())

    def test__concatenates_despite_leading_slash(self):
        root = self.make_dir()
        self.set_root(root)
        filename = factory.make_name('file')
        self.assertEqual(
            os.path.join(root, filename),
            get_path('/' + filename))

    def test__normalises(self):
        self.set_root()
        self.assertEqual('/foo/bar', get_path('foo///szut//..///bar//'))
