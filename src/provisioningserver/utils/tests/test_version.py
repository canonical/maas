# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test version utilities."""


import dataclasses
import os.path
from unittest import skipUnless
from unittest.mock import MagicMock, sentinel

from fixtures import EnvironmentVariableFixture
from pkg_resources import parse_version

from maastesting import root
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.utils import shell, snappy, version
from provisioningserver.utils.version import (
    _get_version_from_python_package,
    get_version_tuple,
    MAASVersion,
)


class TestGetVersionFromPythonPackage(MAASTestCase):

    scenarios = [
        (
            "final",
            {
                "version": "1.2.3",
                "output": "1.2.3",
            },
        ),
        (
            "alpha",
            {
                "version": "2.3.4a1",
                "output": "2.3.4~alpha1",
            },
        ),
        (
            "beta",
            {
                "version": "2.3.4b2",
                "output": "2.3.4~beta2",
            },
        ),
        (
            "rc",
            {
                "version": "2.3.4rc4",
                "output": "2.3.4~rc4",
            },
        ),
    ]

    def test_version(self):
        self.patch(version, "DISTRIBUTION").parsed_version = parse_version(
            self.version
        )
        self.assertEqual(_get_version_from_python_package(), self.output)


class TestGetVersionFromAPT(MAASTestCase):
    def test_creates_cache_with_None_progress(self):
        mock_Cache = self.patch(version.apt_pkg, "Cache")
        version._get_version_from_apt(version.REGION_PACKAGE_NAME)
        self.assertThat(mock_Cache, MockCalledOnceWith(None))

    def test_returns_empty_string_if_package_not_in_cache(self):
        self.patch(version.apt_pkg, "Cache").return_value = {}

        self.assertEqual(
            "", version._get_version_from_apt(version.REGION_PACKAGE_NAME)
        )

    def test_returns_empty_string_if_not_current_ver_from_package(self):
        package = MagicMock()
        package.current_ver = None
        mock_cache = {version.REGION_PACKAGE_NAME: package}
        self.patch(version.apt_pkg, "Cache").return_value = mock_cache
        self.assertEqual(
            "", version._get_version_from_apt(version.REGION_PACKAGE_NAME)
        )

    def test_returns_ver_str_from_package(self):
        package = MagicMock()
        package.current_ver.ver_str = "1.2.3~rc4-567-ubuntu0"
        mock_cache = {version.RACK_PACKAGE_NAME: package}
        self.patch(version.apt_pkg, "Cache").return_value = mock_cache
        self.assertEqual(
            version._get_version_from_apt(version.RACK_PACKAGE_NAME),
            "1.2.3~rc4-567-ubuntu0",
        )

    def test_returns_ver_str_from_package_without_epoch(self):
        package = MagicMock()
        package.current_ver.ver_str = "99:1.2.3~rc4-567-ubuntu0"
        mock_cache = {version.RACK_PACKAGE_NAME: package}
        self.patch(version.apt_pkg, "Cache").return_value = mock_cache
        self.assertEqual(
            version._get_version_from_apt(version.RACK_PACKAGE_NAME),
            "1.2.3~rc4-567-ubuntu0",
        )

    def test_returns_ver_str_from_second_package_if_first_not_found(self):
        package = MagicMock()
        package.current_ver.ver_str = "1.2.3~rc4-567-ubuntu0"
        mock_cache = {version.REGION_PACKAGE_NAME: package}
        self.patch(version.apt_pkg, "Cache").return_value = mock_cache
        self.assertEqual(
            version._get_version_from_apt(
                version.RACK_PACKAGE_NAME, version.REGION_PACKAGE_NAME
            ),
            "1.2.3~rc4-567-ubuntu0",
        )

    def test_returns_ver_str_from_second_package_if_first_is_empty(self):
        rack = MagicMock()
        rack.current_ver = ""
        region = MagicMock()
        region.current_ver.ver_str = "1.2.3~rc4-567-ubuntu0"
        mock_cache = {
            version.RACK_PACKAGE_NAME: rack,
            version.REGION_PACKAGE_NAME: region,
        }
        self.patch(version.apt_pkg, "Cache").return_value = mock_cache
        self.assertEqual(
            version._get_version_from_apt(
                version.RACK_PACKAGE_NAME, version.REGION_PACKAGE_NAME
            ),
            "1.2.3~rc4-567-ubuntu0",
        )


class TestGetMAASRepoHash(MAASTestCase):
    def test_returns_None_if_this_is_not_a_git_repo(self):
        call_and_check = self.patch(shell, "call_and_check")
        call_and_check.side_effect = shell.ExternalProcessError(127, "cmd")
        self.assertIsNone(version._get_maas_repo_hash())

    def test_returns_None_if_git_crashes(self):
        call_and_check = self.patch(shell, "call_and_check")
        call_and_check.side_effect = shell.ExternalProcessError(2, "cmd")
        self.assertIsNone(version._get_maas_repo_hash())

    def test_returns_None_if_git_not_found(self):
        call_and_check = self.patch(shell, "call_and_check")
        call_and_check.side_effect = FileNotFoundError()
        self.assertIsNone(version._get_maas_repo_hash())

    @skipUnless(os.path.isdir(os.path.join(root, ".git")), "Not a branch")
    def test_returns_hash_for_this_branch(self):
        commit_hash = version._get_maas_repo_hash()
        self.assertIsInstance(commit_hash, str)
        self.assertEqual(40, len(commit_hash))


class TestExtractVersionSubversion(MAASTestCase):

    scenarios = [
        (
            "with ~",
            {
                "version": "2.2.0~beta4+bzr5856-0ubuntu1",
                "output": ("2.2.0~beta4", "bzr5856-0ubuntu1"),
            },
        ),
        (
            "without ~",
            {
                "version": "2.1.0+bzr5480-0ubuntu1",
                "output": ("2.1.0", "bzr5480-0ubuntu1"),
            },
        ),
        (
            "without ~ or +",
            {"version": "2.1.0-0ubuntu1", "output": ("2.1.0", "0ubuntu1")},
        ),
    ]

    def test_returns_version_subversion(self):
        self.assertEqual(
            self.output, version._extract_version_subversion(self.version)
        )


class TestGetVersionTuple(MAASTestCase):

    scenarios = (
        (
            "empty string",
            {
                "version": "",
                "maas_version": MAASVersion(
                    0, 0, 0, 0, 0, 0, "", "", "", None, False
                ),
            },
        ),
        (
            "single digit",
            {
                "version": "2",
                "maas_version": MAASVersion(
                    2, 0, 0, 0, 0, 0, "", "2", "", None, False
                ),
            },
        ),
        (
            "double digit",
            {
                "version": "2.2",
                "maas_version": MAASVersion(
                    2,
                    2,
                    0,
                    0,
                    0,
                    0,
                    "",
                    "2.2",
                    "",
                    None,
                    False,
                ),
            },
        ),
        (
            "triple digits",
            {
                "version": "11.22.33",
                "maas_version": MAASVersion(
                    11,
                    22,
                    33,
                    0,
                    0,
                    0,
                    "",
                    "11.22.33",
                    "",
                    None,
                    False,
                ),
            },
        ),
        (
            "single digit with qualifier",
            {
                "version": "2~alpha4",
                "maas_version": MAASVersion(
                    2,
                    0,
                    0,
                    -3,
                    4,
                    0,
                    "",
                    "2~alpha4",
                    "",
                    "alpha",
                    False,
                ),
            },
        ),
        (
            "triple digit with qualifier",
            {
                "version": "11.22.33~rc3",
                "maas_version": MAASVersion(
                    11,
                    22,
                    33,
                    -1,
                    3,
                    0,
                    "",
                    "11.22.33~rc3",
                    "",
                    "rc",
                    False,
                ),
            },
        ),
        (
            "full version",
            {
                "version": "2.3.0~alpha3-6202-g54f83de-0ubuntu1~16.04.1",
                "maas_version": MAASVersion(
                    2,
                    3,
                    0,
                    -3,
                    3,
                    6202,
                    "54f83de",
                    "2.3.0~alpha3",
                    "6202-g54f83de",
                    "alpha",
                    False,
                ),
            },
        ),
        (
            "full version with dotted git hash prefix",
            {
                "version": "2.3.0~alpha3-6202-g.54f83de-0ubuntu1~16.04.1",
                "maas_version": MAASVersion(
                    2,
                    3,
                    0,
                    -3,
                    3,
                    6202,
                    "54f83de",
                    "2.3.0~alpha3",
                    "6202-g.54f83de",
                    "alpha",
                    False,
                ),
            },
        ),
        (
            "full version with garbage revisions",
            {
                "version": "2.3.0~experimental3-xxxxxxx-xxxxxx",
                "maas_version": MAASVersion(
                    2,
                    3,
                    0,
                    0,
                    3,
                    0,
                    "",
                    "2.3.0~experimental3",
                    "xxxxxxx-xxxxxx",
                    "experimental",
                    False,
                ),
            },
        ),
        (
            "garbage integers",
            {
                "version": "2x.x3.x5x~alpha5Y-xxx-g1",
                "maas_version": MAASVersion(
                    2,
                    3,
                    5,
                    0,
                    5,
                    0,
                    "1",
                    "2x.x3.x5x~alpha5Y",
                    "xxx-g1",
                    "alphaY",
                    False,
                ),
            },
        ),
        (
            "ci version",
            {
                "version": "2.4.0+6981.g011e51b+ci-0ubuntu1",
                "maas_version": MAASVersion(
                    2,
                    4,
                    0,
                    0,
                    0,
                    6981,
                    "011e51b",
                    "2.4.0",
                    "6981.g011e51b+ci-0ubuntu1",
                    None,
                    False,
                ),
            },
        ),
        (
            "ci version with epoch",
            {
                "version": "1:2.9.0~beta3-8950-g.b5ea2ab1b-0ubuntu1",
                "maas_version": MAASVersion(
                    2,
                    9,
                    0,
                    -2,
                    3,
                    8950,
                    "b5ea2ab1b",
                    "2.9.0~beta3",
                    "8950-g.b5ea2ab1b",
                    "beta",
                    False,
                ),
            },
        ),
    )

    def test_returns_expected_version(self):
        self.useFixture(EnvironmentVariableFixture("SNAP", None))
        self.assertEqual(get_version_tuple(self.version), self.maas_version)

        maas_version_snap = dataclasses.replace(
            self.maas_version, is_snap=True
        )
        self.useFixture(
            EnvironmentVariableFixture("SNAP", "/var/snap/maas/123")
        )
        self.assertEqual(get_version_tuple(self.version), maas_version_snap)


class TestVersionTestCase(MAASTestCase):
    """MAASTestCase that resets the cache used by utility methods."""

    def setUp(self):
        super().setUp()
        self._clear_caches()

    def tearDown(self):
        super().tearDown()
        self._clear_caches()

    def _clear_caches(self):
        for attribute in vars(version).values():
            if hasattr(attribute, "cache_clear"):
                attribute.cache_clear()


class TestGetRunningVersion(TestVersionTestCase):
    def test_calls__get_version_from_apt(self):
        mock_apt = self.patch(version, "_get_version_from_apt")
        mock_apt.return_value = sentinel.version
        self.assertIs(version.get_running_version(), sentinel.version)
        self.expectThat(
            mock_apt,
            MockCalledOnceWith(
                version.RACK_PACKAGE_NAME, version.REGION_PACKAGE_NAME
            ),
        )

    def test_uses_snappy_get_snap_version(self):
        self.patch(snappy, "running_in_snap").return_value = True
        self.patch(snappy, "get_snap_version").return_value = sentinel.version
        self.assertEqual(sentinel.version, version.get_running_version())


class TestGetMAASVersionSubversion(TestVersionTestCase):
    def test_returns_package_version(self):
        mock_apt = self.patch(version, "_get_version_from_apt")
        mock_apt.return_value = "1.8.0~alpha4+bzr356-0ubuntu1"
        self.assertEqual(
            ("1.8.0~alpha4", "bzr356-0ubuntu1"),
            version.get_maas_version_subversion(),
        )

    def test_returns_unknown_if_version_is_empty_and_not_git_repo(self):
        mock_version = self.patch(version, "_get_version_from_apt")
        mock_version.return_value = ""
        mock_repo_hash = self.patch(version, "_get_maas_repo_hash")
        mock_repo_hash.return_value = None
        self.assertEqual(
            (_get_version_from_python_package(), "unknown"),
            version.get_maas_version_subversion(),
        )

    def test_returns_from_source_and_revno_from_branch(self):
        mock_version = self.patch(version, "_get_version_from_apt")
        mock_version.return_value = ""
        mock_repo_hash = self.patch(version, "_get_maas_repo_hash")
        mock_repo_hash.return_value = "deadbeef"
        self.assertEqual(
            (
                "%s from source" % _get_version_from_python_package(),
                "git+deadbeef",
            ),
            version.get_maas_version_subversion(),
        )


class TestGetMAASVersionUI(TestVersionTestCase):
    def test_returns_package_version(self):
        mock_apt = self.patch(version, "_get_version_from_apt")
        mock_apt.return_value = "1.8.0~alpha4+git+deadbeef-0ubuntu1"
        self.assertEqual(
            "1.8.0~alpha4 (git+deadbeef-0ubuntu1)",
            version.get_maas_version_ui(),
        )

    def test_returns_unknown_if_version_is_empty_and_not_git_repo(self):
        mock_version = self.patch(version, "_get_version_from_apt")
        mock_version.return_value = ""
        mock_repo_hash = self.patch(version, "_get_maas_repo_hash")
        mock_repo_hash.return_value = None
        self.assertEqual(
            "%s (unknown)" % _get_version_from_python_package(),
            version.get_maas_version_ui(),
        )

    def test_returns_from_source_and_revno_from_branch(self):
        mock_version = self.patch(version, "_get_version_from_apt")
        mock_version.return_value = ""
        mock_repo_hash = self.patch(version, "_get_maas_repo_hash")
        mock_repo_hash.return_value = "deadbeef"

        self.assertEqual(
            "{} from source (git+deadbeef)".format(
                _get_version_from_python_package()
            ),
            version.get_maas_version_ui(),
        )


class TestGetMAASVersionUserAgent(TestVersionTestCase):
    def test_returns_package_version(self):
        mock_apt = self.patch(version, "_get_version_from_apt")
        mock_apt.return_value = "1.8.0~alpha4+bzr356-0ubuntu1"
        self.assertEqual(
            "maas/1.8.0~alpha4/bzr356-0ubuntu1",
            version.get_maas_version_user_agent(),
        )

    def test_returns_unknown_if_version_is_empty_and_not_git_repo(self):
        mock_version = self.patch(version, "_get_version_from_apt")
        mock_version.return_value = ""
        mock_repo_hash = self.patch(version, "_get_maas_repo_hash")
        mock_repo_hash.return_value = None
        self.assertEqual(
            "maas/%s/unknown" % _get_version_from_python_package(),
            version.get_maas_version_user_agent(),
        )

    def test_returns_from_source_and_hashfrom_repo(self):
        mock_version = self.patch(version, "_get_version_from_apt")
        mock_version.return_value = ""
        mock_repo_hash = self.patch(version, "_get_maas_repo_hash")
        mock_repo_hash.return_value = "deadbeef"
        self.assertEqual(
            "maas/%s from source/git+%s"
            % (_get_version_from_python_package(), "deadbeef"),
            version.get_maas_version_user_agent(),
        )


class TestVersionMethodsCached(TestVersionTestCase):

    scenarios = [
        ("get_running_version", dict(method="get_running_version")),
        (
            "get_maas_version_subversion",
            dict(method="get_maas_version_subversion"),
        ),
        ("get_maas_version_ui", dict(method="get_maas_version_ui")),
    ]

    def test_method_is_cached(self):
        mock_apt = self.patch(version, "_get_version_from_apt")
        mock_apt.return_value = "1.8.0~alpha4+bzr356-0ubuntu1"
        cached_method = getattr(version, self.method)
        cached_method.cache_clear()

        first_return_value = cached_method()
        second_return_value = cached_method()
        # The return value is not empty (full unit tests have been performed
        # earlier).
        self.assertNotIn(first_return_value, [b"", "", None])
        self.assertEqual(first_return_value, second_return_value)
        # Apt has only been called once.
        self.expectThat(
            mock_apt,
            MockCalledOnceWith(
                version.RACK_PACKAGE_NAME, version.REGION_PACKAGE_NAME
            ),
        )


class TestGetMAASVersionTrackChannel(TestVersionTestCase):

    scenarios = [
        (
            "alpha",
            {
                "version": "2.7.0~alpha1-6192-g.10a4565-0ubuntu1",
                "output": "2.7/edge",
            },
        ),
        (
            "beta",
            {"version": "2.7.0~beta1-6192-g.10a4565", "output": "2.7/beta"},
        ),
        (
            "rc",
            {"version": "2.7.0~rc1-6192-g10a4565", "output": "2.7/candidate"},
        ),
        (
            "final",
            {
                "version": "2.7.0-6192-g10a4565-0ubuntu1",
                "output": "2.7/stable",
            },
        ),
    ]

    def test_get_maas_version_track_channel(self):
        mock = self.patch(version, "get_running_version")
        mock.return_value = self.version
        result = version.get_maas_version_track_channel()
        self.assertEqual(result, self.output)
