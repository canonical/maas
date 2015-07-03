# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
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
import provisioningserver.path
from provisioningserver.path import (
    get_path,
    get_tentative_path,
)
from testtools.matchers import (
    DirExists,
    Not,
    StartsWith,
)


class TestGetPathFunctions(MAASTestCase):
    """Tests for `get_path` and `get_tentative_path`."""

    scenarios = (
        ("get_path", {
            "get_path_function": get_path,
            "ensures_directory": True,
        }),
        ("get_tentative_path", {
            "get_path_function": get_tentative_path,
            "ensures_directory": False,
        }),
    )

    def set_root(self, root_path=None):
        """For the duration of this test, set the `MAAS_ROOT` variable`."""
        self.useFixture(EnvironmentVariableFixture('MAAS_ROOT', root_path))

    def test__defaults_to_root(self):
        self.set_root()
        self.patch(provisioningserver.path, 'ensure_dir')
        self.assertEqual('/', self.get_path_function())

    def test__appends_path_elements(self):
        self.set_root('/')
        self.patch(provisioningserver.path, 'ensure_dir')
        part1 = factory.make_name('dir')
        part2 = factory.make_name('file')
        self.assertEqual(
            os.path.join('/', part1, part2),
            self.get_path_function(part1, part2))

    def test__obeys_MAAS_ROOT_variable(self):
        root = factory.make_name('/root')
        self.set_root(root)
        self.patch(provisioningserver.path, 'ensure_dir')
        path = factory.make_name('path')
        self.assertEqual(
            os.path.join(root, path),
            self.get_path_function(path))

    def test__assumes_MAAS_ROOT_is_unset_if_empty(self):
        self.set_root("")
        self.patch(provisioningserver.path, 'ensure_dir')
        path = factory.make_name('path')
        self.assertEqual(
            os.path.join("/", path),
            self.get_path_function(path))

    def test__returns_absolute_path(self):
        self.set_root('.')
        self.patch(provisioningserver.path, 'ensure_dir')
        self.assertThat(self.get_path_function(), StartsWith('/'))
        self.assertEqual(getcwdu(), self.get_path_function())

    def test__concatenates_despite_leading_slash(self):
        root = self.make_dir()
        self.set_root(root)
        self.patch(provisioningserver.path, 'ensure_dir')
        filename = factory.make_name('file')
        self.assertEqual(
            os.path.join(root, filename),
            self.get_path_function('/' + filename))

    def test__normalises(self):
        self.set_root()
        self.patch(provisioningserver.path, 'ensure_dir')
        self.assertEqual(
            '/foo/bar',
            self.get_path_function('foo///szut//..///bar//'))

    def test__maybe_creates_dirpath_if_not_exists(self):
        root_path = self.make_dir()
        self.set_root(root_path)
        self.assertThat(
            os.path.dirname(self.get_path_function('/foo/bar')),
            DirExists() if self.ensures_directory else Not(DirExists()))
