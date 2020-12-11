# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test version utilities."""


import os.path
from unittest import skipUnless
from unittest.mock import MagicMock

from pkg_resources import parse_version

from maastesting import root
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.utils import shell, snappy, version
from provisioningserver.utils.version import (
    _get_version_from_python_package,
    get_running_version,
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


class TestMAASVersion(MAASTestCase):

    scenarios = (
        (
            "version only",
            {
                "version": "1.2.3",
                "maas_version": MAASVersion(
                    major=1,
                    minor=2,
                    point=3,
                    qualifier_type_version=0,
                    qualifier_version=0,
                    revno=0,
                    git_rev="",
                    short_version="1.2.3",
                    extended_info="",
                    qualifier_type=None,
                ),
                "str_version": "1.2.3",
            },
        ),
        (
            "version with qualifier",
            {
                "version": "11.22.33~rc3",
                "maas_version": MAASVersion(
                    major=11,
                    minor=22,
                    point=33,
                    qualifier_type_version=-1,
                    qualifier_version=3,
                    revno=0,
                    git_rev="",
                    short_version="11.22.33~rc3",
                    extended_info="",
                    qualifier_type="rc",
                ),
                "str_version": "11.22.33~rc3",
            },
        ),
        (
            "full version",
            {
                "version": "2.3.0~alpha3-6202-g54f83de-0ubuntu1~16.04.1",
                "maas_version": MAASVersion(
                    major=2,
                    minor=3,
                    point=0,
                    qualifier_type_version=-3,
                    qualifier_version=3,
                    revno=6202,
                    git_rev="54f83de",
                    short_version="2.3.0~alpha3",
                    extended_info="6202-g54f83de",
                    qualifier_type="alpha",
                ),
                "str_version": "2.3.0~alpha3-6202-g.54f83de",
            },
        ),
        (
            "full version with snap suffix",
            {
                "version": "2.3.0~alpha3-6202-g54f83de-0ubuntu1~16.04.1-snap",
                "maas_version": MAASVersion(
                    major=2,
                    minor=3,
                    point=0,
                    qualifier_type_version=-3,
                    qualifier_version=3,
                    revno=6202,
                    git_rev="54f83de",
                    short_version="2.3.0~alpha3",
                    extended_info="6202-g54f83de",
                    qualifier_type="alpha",
                ),
                "str_version": "2.3.0~alpha3-6202-g.54f83de",
            },
        ),
        (
            "full version with dotted git hash prefix",
            {
                "version": "2.3.0~alpha3-6202-g.54f83de-0ubuntu1~16.04.1",
                "maas_version": MAASVersion(
                    major=2,
                    minor=3,
                    point=0,
                    qualifier_type_version=-3,
                    qualifier_version=3,
                    revno=6202,
                    git_rev="54f83de",
                    short_version="2.3.0~alpha3",
                    extended_info="6202-g.54f83de",
                    qualifier_type="alpha",
                ),
                "str_version": "2.3.0~alpha3-6202-g.54f83de",
            },
        ),
        (
            "full version with epoch",
            {
                "version": "1:2.3.0~alpha3-6202-g54f83de-0ubuntu1~16.04.1",
                "maas_version": MAASVersion(
                    major=2,
                    minor=3,
                    point=0,
                    qualifier_type_version=-3,
                    qualifier_version=3,
                    revno=6202,
                    git_rev="54f83de",
                    short_version="2.3.0~alpha3",
                    extended_info="6202-g54f83de",
                    qualifier_type="alpha",
                ),
                "str_version": "2.3.0~alpha3-6202-g.54f83de",
            },
        ),
    )

    def test_parse(self):
        self.assertEqual(
            MAASVersion.from_string(self.version), self.maas_version
        )

    def test_string(self):
        self.assertEqual(
            str(MAASVersion.from_string(self.version)), self.str_version
        )


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
        mock_apt.return_value = "2.10.0-456-g.deadbeef-0ubuntu1"
        maas_version = get_running_version()
        self.assertEqual(maas_version.short_version, "2.10.0")
        self.assertEqual(maas_version.extended_info, "456-g.deadbeef")
        self.expectThat(
            mock_apt,
            MockCalledOnceWith(
                version.RACK_PACKAGE_NAME, version.REGION_PACKAGE_NAME
            ),
        )

    def test_uses_snappy_get_snap_version(self):
        self.patch(snappy, "running_in_snap").return_value = True
        self.patch(
            snappy, "get_snap_version"
        ).return_value = "2.10.0-456-g.deadbeef"
        maas_version = get_running_version()
        self.assertEqual(maas_version.short_version, "2.10.0")
        self.assertEqual(maas_version.extended_info, "456-g.deadbeef")

    def test_uses_version_from_python(self):
        self.patch(version, "_get_version_from_apt").return_value = None
        self.patch(version, "DISTRIBUTION").parsed_version = parse_version(
            "2.10.0b1"
        )
        maas_version = get_running_version()
        self.assertEqual(maas_version.short_version, "2.10.0~beta1")
        self.assertEqual(maas_version.extended_info, "")

    def test_uses_version_from_python_with_git_hash(self):
        self.patch(version, "_get_version_from_apt").return_value = None
        self.patch(version, "DISTRIBUTION").parsed_version = parse_version(
            "2.10.0b1"
        )
        self.patch(version, "_get_maas_repo_hash").return_value = "deadbeef"
        maas_version = get_running_version()
        self.assertEqual(maas_version.short_version, "2.10.0~beta1")
        self.assertEqual(maas_version.git_rev, "deadbeef")

    def test_method_is_cached(self):
        mock_apt = self.patch(version, "_get_version_from_apt")
        mock_apt.return_value = "1.8.0~alpha4+bzr356-0ubuntu1"
        version.get_running_version.cache_clear()

        first_return_value = version.get_running_version()
        second_return_value = version.get_running_version()
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
        self.patch(
            version, "get_running_version"
        ).return_value = MAASVersion.from_string(self.version)
        result = version.get_maas_version_track_channel()
        self.assertEqual(result, self.output)
