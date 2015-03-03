# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test version utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random

from bzrlib.errors import NotBranchError
from maasserver.utils import version
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import (
    MagicMock,
    sentinel,
    )
from testtools.matchers import Is


class TestGetVersionFromAPT(MAASTestCase):

    def test__returns_empty_string_if_package_not_in_cache(self):
        self.patch(version.apt_pkg, "Cache")
        self.assertEquals(
            "",
            version.get_version_from_apt(version.REGION_PACKAGE_NAME))

    def test__returns_empty_string_if_not_current_ver_from_package(self):
        package = MagicMock()
        package.current_ver = None
        mock_cache = {
            version.REGION_PACKAGE_NAME: package,
            }
        self.patch(version.apt_pkg, "Cache").return_value = mock_cache
        self.assertEquals(
            "",
            version.get_version_from_apt(version.REGION_PACKAGE_NAME))

    def test__returns_ver_str_from_package(self):
        package = MagicMock()
        package.current_ver.ver_str = sentinel.ver_str
        mock_cache = {
            version.REGION_PACKAGE_NAME: package,
            }
        self.patch(version.apt_pkg, "Cache").return_value = mock_cache
        self.assertIs(
            sentinel.ver_str,
            version.get_version_from_apt(version.REGION_PACKAGE_NAME))


class TestFormatVersion(MAASTestCase):

    scenarios = [
        ("with ~", {
            "version": "1.8.0~alpha4+bzr356-0ubuntu1",
            "output": "1.8.0 (alpha4+bzr356)",
            }),
        ("without ~", {
            "version": "1.8.0+bzr356-0ubuntu1",
            "output": "1.8.0 (+bzr356)",
            }),
        ("without ~ or +", {
            "version": "1.8.0-0ubuntu1",
            "output": "1.8.0",
            }),
    ]

    def test__returns_formatted_version(self):
        self.assertEquals(self.output, version.format_version(self.version))


class TestGetMAASRegionPackageVersion(MAASTestCase):

    def test__returns_value_from_global(self):
        self.patch(version, "MAAS_VERSION", sentinel.maas_version)
        self.assertIs(
            sentinel.maas_version, version.get_maas_region_package_version())

    def test__calls_get_version_from_apt_if_global_not_set(self):
        self.patch(version, "MAAS_VERSION", None)
        mock_apt = self.patch(version, "get_version_from_apt")
        version.get_maas_region_package_version()
        self.assertThat(
            mock_apt, MockCalledOnceWith(version.REGION_PACKAGE_NAME))

    def test__calls_format_version_with_version_from_apt(self):
        self.patch(version, "MAAS_VERSION", None)
        current_ver = "1.8.0~alpha4+bzr356-0ubuntu1"
        mock_apt = self.patch(version, "get_version_from_apt")
        mock_apt.return_value = current_ver
        mock_format = self.patch(version, "format_version")
        mock_format.return_value = sentinel.format
        self.expectThat(
            version.get_maas_region_package_version(), Is(sentinel.format))
        self.expectThat(
            mock_format, MockCalledOnceWith(current_ver))

    def test__sets_global_value(self):
        self.patch(version, "MAAS_VERSION", None)
        current_ver = "1.8.0~alpha4+bzr356-0ubuntu1"
        mock_apt = self.patch(version, "get_version_from_apt")
        mock_apt.return_value = current_ver
        mock_format = self.patch(version, "format_version")
        mock_format.return_value = sentinel.format
        version.get_maas_region_package_version()
        self.assertIs(sentinel.format, version.MAAS_VERSION)


class TestGetMAASBranch(MAASTestCase):

    def test__returns_None_if_Branch_is_None(self):
        self.patch(version, "Branch", None)
        self.assertIsNone(version.get_maas_branch())

    def test__calls_Branch_open_with_current_dir(self):
        mock_open = self.patch(version.Branch, "open")
        mock_open.return_value = sentinel.branch
        self.expectThat(version.get_maas_branch(), Is(sentinel.branch))
        self.expectThat(mock_open, MockCalledOnceWith("."))

    def test__returns_None_on_NotBranchError(self):
        mock_open = self.patch(version.Branch, "open")
        mock_open.side_effect = NotBranchError("")
        self.assertIsNone(version.get_maas_branch())


class TestGetMAASVersion(MAASTestCase):

    def test__returns_version_from_get_maas_region_package_version(self):
        mock_version = self.patch(version, "get_maas_region_package_version")
        mock_version.return_value = sentinel.version
        self.assertIs(sentinel.version, version.get_maas_version())

    def test__returns_unknown_if_version_is_empty_and_not_bzr_branch(self):
        mock_version = self.patch(version, "get_maas_region_package_version")
        mock_version.return_value = ""
        mock_branch = self.patch(version, "get_maas_branch")
        mock_branch.return_value = None
        self.assertEquals("unknown", version.get_maas_version())

    def test__returns_from_source_and_revno_from_branch(self):
        mock_version = self.patch(version, "get_maas_region_package_version")
        mock_version.return_value = ""
        revno = random.randint(1, 5000)
        mock_branch = self.patch(version, "get_maas_branch")
        mock_branch.return_value.revno.return_value = revno
        self.assertEquals(
            "from source (+bzr%s)" % revno, version.get_maas_version())


class TestGetMAASMainVersion(MAASTestCase):

    def test__returns_main_version_from_package_version_with_space(self):
        mock_version = self.patch(version, "get_maas_region_package_version")
        mock_version.return_value = "1.8.0 (alpha4+bzr356)"
        self.assertEquals("1.8.0", version.get_maas_main_version())

    def test__returns_main_version_from_package_version_without_space(self):
        mock_version = self.patch(version, "get_maas_region_package_version")
        mock_version.return_value = "1.8.0"
        self.assertEquals("1.8.0", version.get_maas_main_version())

    def test__returns_empty_if_version_is_empty(self):
        mock_version = self.patch(version, "get_maas_region_package_version")
        mock_version.return_value = ""
        self.assertEquals("", version.get_maas_main_version())


class TestGetMAASDocVersion(MAASTestCase):

    def test__returns_doc_version_with_greater_than_1_decimals(self):
        mock_version = self.patch(version, "get_maas_main_version")
        mock_version.return_value = "1.8.0"
        self.assertEquals("doc1.8", version.get_maas_doc_version())

    def test__returns_doc_version_with_equal_to_1_decimals(self):
        mock_version = self.patch(version, "get_maas_main_version")
        mock_version.return_value = "1.8"
        self.assertEquals("doc1.8", version.get_maas_doc_version())

    def test__returns_just_doc_if_version_is_empty(self):
        mock_version = self.patch(version, "get_maas_main_version")
        mock_version.return_value = ""
        self.assertEquals("doc", version.get_maas_doc_version())
