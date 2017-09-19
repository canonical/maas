# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test version utilities."""

__all__ = []


import os.path
import random
from unittest import skipUnless
from unittest.mock import (
    MagicMock,
    sentinel,
)

from maastesting import root
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.utils import (
    shell,
    snappy,
    version,
)
from provisioningserver.utils.version import (
    DEFAULT_VERSION as old_version,
    get_version_tuple,
)
from testtools.matchers import (
    Equals,
    GreaterThan,
    Is,
    IsInstance,
)


class TestGetVersionFromAPT(MAASTestCase):

    def test__creates_cache_with_None_progress(self):
        mock_Cache = self.patch(version.apt_pkg, "Cache")
        version.get_version_from_apt(version.REGION_PACKAGE_NAME)
        self.assertThat(mock_Cache, MockCalledOnceWith(None))

    def test__returns_empty_string_if_package_not_in_cache(self):
        self.patch(version.apt_pkg, "Cache")
        self.assertEqual(
            "",
            version.get_version_from_apt(version.REGION_PACKAGE_NAME))

    def test__returns_empty_string_if_not_current_ver_from_package(self):
        package = MagicMock()
        package.current_ver = None
        mock_cache = {
            version.REGION_PACKAGE_NAME: package,
            }
        self.patch(version.apt_pkg, "Cache").return_value = mock_cache
        self.assertEqual(
            "",
            version.get_version_from_apt(version.REGION_PACKAGE_NAME))

    def test__returns_ver_str_from_package(self):
        package = MagicMock()
        package.current_ver.ver_str = sentinel.ver_str
        mock_cache = {
            version.RACK_PACKAGE_NAME: package
            }
        self.patch(version.apt_pkg, "Cache").return_value = mock_cache
        self.assertIs(
            sentinel.ver_str,
            version.get_version_from_apt(version.RACK_PACKAGE_NAME))

    def test__returns_ver_str_from_second_package_if_first_not_found(self):
        package = MagicMock()
        package.current_ver.ver_str = sentinel.ver_str
        mock_cache = {
            version.REGION_PACKAGE_NAME: package,
        }
        self.patch(version.apt_pkg, "Cache").return_value = mock_cache
        self.assertIs(
            sentinel.ver_str,
            version.get_version_from_apt(
                version.RACK_PACKAGE_NAME, version.REGION_PACKAGE_NAME))

    def test__returns_ver_str_from_second_package_if_first_is_empty(self):
        rack = MagicMock()
        rack.current_ver = ''
        region = MagicMock()
        region.current_ver.ver_str = sentinel.ver_str
        mock_cache = {
            version.RACK_PACKAGE_NAME: rack,
            version.REGION_PACKAGE_NAME: region,
        }
        self.patch(version.apt_pkg, "Cache").return_value = mock_cache
        self.assertIs(
            sentinel.ver_str,
            version.get_version_from_apt(
                version.RACK_PACKAGE_NAME, version.REGION_PACKAGE_NAME))


class TestGetMAASBranchVersion(MAASTestCase):

    def test__returns_None_if_this_is_not_a_branch(self):
        self.patch(version, "__file__", "/")
        self.assertIsNone(version.get_maas_branch_version())

    def test__returns_None_if_bzr_crashes(self):
        call_and_check = self.patch(shell, "call_and_check")
        call_and_check.side_effect = shell.ExternalProcessError(2, "cmd")
        self.assertIsNone(version.get_maas_branch_version())

    def test__returns_None_if_bzr_not_found(self):
        call_and_check = self.patch(shell, "call_and_check")
        call_and_check.side_effect = FileNotFoundError()
        self.assertIsNone(version.get_maas_branch_version())

    def test__returns_None_if_bzr_emits_something_thats_not_a_number(self):
        call_and_check = self.patch(shell, "call_and_check")
        call_and_check.return_value = b"???"
        self.assertIsNone(version.get_maas_branch_version())

    @skipUnless(os.path.isdir(os.path.join(root, ".bzr")), "Not a branch")
    def test__returns_revno_for_this_branch(self):
        revno = version.get_maas_branch_version()
        self.assertThat(revno, IsInstance(int))
        self.assertThat(revno, GreaterThan(0))


class TestExtractVersionSubversion(MAASTestCase):

    scenarios = [
        ("with ~", {
            "version": "2.2.0~beta4+bzr5856-0ubuntu1",
            "output": ("2.2.0~beta4", "bzr5856-0ubuntu1"),
            }),
        ("without ~", {
            "version": "2.1.0+bzr5480-0ubuntu1",
            "output": ("2.1.0", "bzr5480-0ubuntu1"),
            }),
        ("without ~ or +", {
            "version": "2.1.0-0ubuntu1",
            "output": ("2.1.0", "0ubuntu1"),
            }),
    ]

    def test__returns_version_subversion(self):
        self.assertEqual(
            self.output, version.extract_version_subversion(self.version))


class TestGetVersionTuple(MAASTestCase):

    scenarios = (
        ('empty string', {
            'version': '',
            'expected_tuple': (0, 0, 0, 0, 0, 0, '', '', '', None, False)
        }),
        ('single digit', {
            'version': '2',
            'expected_tuple': (2, 0, 0, 0, 0, 0, '', '2', '', None, False)
        }),
        ('double digit', {
            'version': '2.2',
            'expected_tuple': (2, 2, 0, 0, 0, 0, '', '2.2', '', None, False)
        }),
        ('triple digits', {
            'version': '11.22.33',
            'expected_tuple': (
                11, 22, 33, 0, 0, 0, '', '11.22.33', '', None, False)
        }),
        ('single digit with qualifier', {
            'version': '2~alpha4',
            'expected_tuple': (
                2, 0, 0, -3, 4, 0, '', '2~alpha4', '', 'alpha', False)
        }),
        ('triple digit with qualifier', {
            'version': '11.22.33~rc3',
            'expected_tuple': (
                11, 22, 33, -1, 3, 0, '', '11.22.33~rc3', '', 'rc', False)
        }),
        ('full version', {
            'version': '2.3.0~alpha3-6202-g54f83de-0ubuntu1~16.04.1',
            'expected_tuple': (
                2, 3, 0, -3, 3, 6202, '54f83de', '2.3.0~alpha3',
                '6202-g54f83de', 'alpha', False)
        }),
        ('full version with garbage revisions', {
            'version': '2.3.0~experimental3-xxxxxxx-xxxxxx',
            'expected_tuple': (
                2, 3, 0, 0, 3, 0, '', '2.3.0~experimental3', 'xxxxxxx-xxxxxx',
                'experimental', False)
        }),
        ('garbage integers', {
            'version': '2x.x3.x5x~alpha5Y-xxx-g1',
            'expected_tuple': (
                2, 3, 5, 0, 5, 0, '1', '2x.x3.x5x~alpha5Y', 'xxx-g1',
                'alphaY', False)
        }),
    )

    def test__returns_expected_tuple(self):
        version = self.version
        actual_tuple = get_version_tuple(version)
        self.assertThat(actual_tuple, Equals(self.expected_tuple), version)
        expected_tuple__snap = list(self.expected_tuple)
        expected_tuple__snap[-1] = True
        expected_tuple__snap = tuple(expected_tuple__snap)
        version += "-snap"
        actual_tuple__snap = get_version_tuple(version)
        self.assertThat(
            actual_tuple__snap, Equals(expected_tuple__snap), version)


class TestVersionTestCase(MAASTestCase):
    """MAASTestCase that resets the cache used by utility methods."""

    def setUp(self):
        super(TestVersionTestCase, self).setUp()
        for attribute in vars(version).values():
            if hasattr(attribute, "cache_clear"):
                attribute.cache_clear()


class TestGetMAASVersion(TestVersionTestCase):

    def test__calls_get_version_from_apt(self):
        mock_apt = self.patch(version, "get_version_from_apt")
        mock_apt.return_value = sentinel.version
        self.expectThat(
            version.get_maas_version(), Is(sentinel.version))
        self.expectThat(
            mock_apt, MockCalledOnceWith(
                version.RACK_PACKAGE_NAME, version.REGION_PACKAGE_NAME))

    def test__uses_snappy_get_snap_version(self):
        self.patch(snappy, 'running_in_snap').return_value = True
        self.patch(snappy, 'get_snap_version').return_value = sentinel.version
        self.assertEqual(sentinel.version, version.get_maas_version())


class TestGetMAASVersionSubversion(TestVersionTestCase):

    def test__returns_package_version(self):
        mock_apt = self.patch(version, "get_version_from_apt")
        mock_apt.return_value = "1.8.0~alpha4+bzr356-0ubuntu1"
        self.assertEqual(
            ("1.8.0~alpha4", "bzr356-0ubuntu1"),
            version.get_maas_version_subversion())

    def test__returns_unknown_if_version_is_empty_and_not_bzr_branch(self):
        mock_version = self.patch(version, "get_version_from_apt")
        mock_version.return_value = ""
        mock_branch_version = self.patch(version, "get_maas_branch_version")
        mock_branch_version.return_value = None
        self.assertEqual(
            (old_version, "unknown"),
            version.get_maas_version_subversion())

    def test__returns_from_source_and_revno_from_branch(self):
        mock_version = self.patch(version, "get_version_from_apt")
        mock_version.return_value = ""
        revno = random.randint(1, 5000)
        mock_branch_version = self.patch(version, "get_maas_branch_version")
        mock_branch_version.return_value = revno
        self.assertEqual(
            ("%s from source" % old_version, "bzr%d" % revno),
            version.get_maas_version_subversion())


class TestGetMAASVersionUI(TestVersionTestCase):

    def test__returns_package_version(self):
        mock_apt = self.patch(version, "get_version_from_apt")
        mock_apt.return_value = "1.8.0~alpha4+bzr356-0ubuntu1"
        self.assertEqual(
            "1.8.0~alpha4 (bzr356-0ubuntu1)", version.get_maas_version_ui())

    def test__returns_unknown_if_version_is_empty_and_not_bzr_branch(self):
        mock_version = self.patch(version, "get_version_from_apt")
        mock_version.return_value = ""
        mock_branch_version = self.patch(version, "get_maas_branch_version")
        mock_branch_version.return_value = None
        self.assertEqual(
            "%s (unknown)" % old_version,
            version.get_maas_version_ui())

    def test__returns_from_source_and_revno_from_branch(self):
        mock_version = self.patch(version, "get_version_from_apt")
        mock_version.return_value = ""
        revno = random.randint(1, 5000)
        mock_branch_version = self.patch(version, "get_maas_branch_version")
        mock_branch_version.return_value = revno
        self.assertEqual(
            "%s from source (bzr%d)" % (old_version, revno),
            version.get_maas_version_ui())


class TestGetMAASVersionUserAgent(TestVersionTestCase):

    def test__returns_package_version(self):
        mock_apt = self.patch(version, "get_version_from_apt")
        mock_apt.return_value = "1.8.0~alpha4+bzr356-0ubuntu1"
        self.assertEqual(
            "maas/1.8.0~alpha4/bzr356-0ubuntu1",
            version.get_maas_version_user_agent())

    def test__returns_unknown_if_version_is_empty_and_not_bzr_branch(self):
        mock_version = self.patch(version, "get_version_from_apt")
        mock_version.return_value = ""
        mock_branch_version = self.patch(version, "get_maas_branch_version")
        mock_branch_version.return_value = None
        self.assertEqual(
            "maas/%s/unknown" % old_version,
            version.get_maas_version_user_agent())

    def test__returns_from_source_and_revno_from_branch(self):
        mock_version = self.patch(version, "get_version_from_apt")
        mock_version.return_value = ""
        revno = random.randint(1, 5000)
        mock_branch_version = self.patch(version, "get_maas_branch_version")
        mock_branch_version.return_value = revno
        self.assertEqual(
            "maas/%s from source/bzr%d" % (old_version, revno),
            version.get_maas_version_user_agent())


class TestGetMAASDocVersion(TestVersionTestCase):

    def test__returns_doc_version_with_greater_than_1_decimals(self):
        mock_apt = self.patch(version, "get_version_from_apt")
        mock_apt.return_value = "1.8.0~alpha4+bzr356-0ubuntu1"
        self.assertEqual("1.8", version.get_maas_doc_version())

    def test__returns_doc_version_with_equal_to_1_decimals(self):
        mock_apt = self.patch(version, "get_version_from_apt")
        mock_apt.return_value = "1.8~alpha4+bzr356-0ubuntu1"
        self.assertEqual("1.8", version.get_maas_doc_version())

    def test__returns_empty_if_version_is_empty(self):
        mock_apt = self.patch(version, "get_version_from_apt")
        mock_apt.return_value = ""
        self.assertEqual("", version.get_maas_doc_version())


class TestVersionMethodsCached(TestVersionTestCase):

    scenarios = [
        ("get_maas_version", dict(method="get_maas_version")),
        ("get_maas_version_subversion", dict(
            method="get_maas_version_subversion")),
        ("get_maas_version_ui", dict(method="get_maas_version_ui")),
        ("get_maas_doc_version", dict(method="get_maas_doc_version")),
        ]

    def test_method_is_cached(self):
        mock_apt = self.patch(version, "get_version_from_apt")
        mock_apt.return_value = "1.8.0~alpha4+bzr356-0ubuntu1"
        cached_method = getattr(version, self.method)
        first_return_value = cached_method()
        second_return_value = cached_method()
        # The return value is not empty (full unit tests have been performed
        # earlier).
        self.assertNotIn(first_return_value, [b'', '', None])
        self.assertEqual(first_return_value, second_return_value)
        # Apt has only been called once.
        self.expectThat(
            mock_apt, MockCalledOnceWith(
                version.RACK_PACKAGE_NAME, version.REGION_PACKAGE_NAME))


class TestGetMAASVersionTuple(MAASTestCase):

    def test_get_maas_version_tuple(self):
        self.assertEquals(
            '.'.join([str(i) for i in version.get_maas_version_tuple()]),
            version.get_maas_version_subversion()[0])


class TestGetMAASVersionTrackChannel(MAASTestCase):

    scenarios = [
        ("alpha", {
            "version": "2.3.0~alpha1-6192-g10a4565-0ubuntu1",
            "output": ("latest/edge"),
            }),
        ("beta", {
            "version": "2.3.0~beta1-6192-g10a4565-snap",
            "output": ("latest/edge"),
            }),
        ("rc4", {
            "version": "2.3.0~rc1-6192-g10a4565",
            "output": ("latest/edge"),
            }),
        ("stable", {
            "version": "2.3.0-6192-g10a4565-0ubuntu1",
            "output": ("2.3/stable"),
            }),
        ("stable", {
            "version": "",
            "output": ("%s/stable" % '.'.join(old_version.split('.')[0:2])),
            }),
    ]

    def test_get_maas_version_track_channel(self):
        mock = self.patch(version, "get_maas_version")
        mock.return_value = self.version
        result = version.get_maas_version_track_channel()
        self.assertEqual(result, self.output)
