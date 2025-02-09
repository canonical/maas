# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from maastesting.testcase import MAASTestCase
from provisioningserver.utils import deb, shell, snap, version
from provisioningserver.utils.version import (
    _get_version_from_python_package,
    get_running_version,
    get_versions_info,
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
        self.patch(version, "DISTRIBUTION").version = self.version
        self.assertEqual(_get_version_from_python_package(), self.output)


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

    def test_returns_hash_for_this_branch(self):
        commit_hash = version._get_maas_repo_hash()
        self.assertIsInstance(commit_hash, str)


class TestMAASVersionScenarios(MAASTestCase):
    scenarios = (
        (
            "version only",
            {
                "version": "1.2.3",
                "maas_version": MAASVersion(
                    major=1,
                    minor=2,
                    point=3,
                    qualifier_type=None,
                    qualifier_version=0,
                    revno=0,
                    git_rev="",
                ),
                "str_version": "1.2.3",
                "short_version": "1.2.3",
                "extended_info": "",
                "qualifier_type_order": 0,
                "main_version": MAASVersion(
                    major=1,
                    minor=2,
                    point=3,
                    qualifier_type=None,
                    qualifier_version=0,
                ),
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
                    qualifier_type="rc",
                    qualifier_version=3,
                    revno=0,
                    git_rev="",
                ),
                "str_version": "11.22.33~rc3",
                "short_version": "11.22.33~rc3",
                "extended_info": "",
                "qualifier_type_order": -1,
                "main_version": MAASVersion(
                    major=11,
                    minor=22,
                    point=33,
                    qualifier_type="rc",
                    qualifier_version=3,
                ),
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
                    qualifier_type="alpha",
                    qualifier_version=3,
                    revno=6202,
                    git_rev="54f83de",
                ),
                "str_version": "2.3.0~alpha3-6202-g.54f83de",
                "short_version": "2.3.0~alpha3",
                "extended_info": "6202-g.54f83de",
                "qualifier_type_order": -3,
                "main_version": MAASVersion(
                    major=2,
                    minor=3,
                    point=0,
                    qualifier_type="alpha",
                    qualifier_version=3,
                ),
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
                    qualifier_type="alpha",
                    qualifier_version=3,
                    revno=6202,
                    git_rev="54f83de",
                ),
                "str_version": "2.3.0~alpha3-6202-g.54f83de",
                "short_version": "2.3.0~alpha3",
                "extended_info": "6202-g.54f83de",
                "qualifier_type_order": -3,
                "main_version": MAASVersion(
                    major=2,
                    minor=3,
                    point=0,
                    qualifier_type="alpha",
                    qualifier_version=3,
                ),
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
                    qualifier_type="alpha",
                    qualifier_version=3,
                    revno=6202,
                    git_rev="54f83de",
                ),
                "str_version": "2.3.0~alpha3-6202-g.54f83de",
                "short_version": "2.3.0~alpha3",
                "extended_info": "6202-g.54f83de",
                "qualifier_type_order": -3,
                "main_version": MAASVersion(
                    major=2,
                    minor=3,
                    point=0,
                    qualifier_type="alpha",
                    qualifier_version=3,
                ),
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
                    qualifier_type="alpha",
                    qualifier_version=3,
                    revno=6202,
                    git_rev="54f83de",
                ),
                "str_version": "2.3.0~alpha3-6202-g.54f83de",
                "short_version": "2.3.0~alpha3",
                "extended_info": "6202-g.54f83de",
                "qualifier_type_order": -3,
                "main_version": MAASVersion(
                    major=2,
                    minor=3,
                    point=0,
                    qualifier_type="alpha",
                    qualifier_version=3,
                ),
            },
        ),
    )

    def test_parse(self):
        maas_version = MAASVersion.from_string(self.version)
        self.assertEqual(maas_version, self.maas_version)
        self.assertEqual(maas_version.short_version, self.short_version)
        self.assertEqual(maas_version.extended_info, self.extended_info)
        self.assertEqual(
            maas_version._qualifier_type_order, self.qualifier_type_order
        )

    def test_string(self):
        self.assertEqual(
            str(MAASVersion.from_string(self.version)), self.str_version
        )

    def test_short_version(self):
        maas_version = MAASVersion.from_string(self.version)
        self.assertEqual(maas_version.main_version, self.main_version)


class TestMAASVersion(MAASTestCase):
    def test_extended_info_no_git_hash_ignore_count(self):
        version = MAASVersion(
            major=2,
            minor=3,
            point=2,
            qualifier_type="alpha",
            qualifier_version=3,
            git_rev="54f83de",
        )
        self.assertEqual(version.extended_info, "g.54f83de")


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
    def test_uses_get_deb_versions_info(self):
        self.patch(
            version.deb, "get_deb_versions_info"
        ).return_value = deb.DebVersionsInfo(
            current=deb.DebVersion(
                version="2.10.0-456-g.deadbeef-0ubuntu1",
            )
        )
        maas_version = get_running_version()
        self.assertEqual(maas_version.short_version, "2.10.0")
        self.assertEqual(maas_version.extended_info, "456-g.deadbeef")

    def test_uses_snap_get_snap_version(self):
        self.patch(snap, "running_in_snap").return_value = True
        self.patch(snap, "get_snap_version").return_value = snap.SnapVersion(
            version="2.10.0-456-g.deadbeef",
            revision="1234",
        )
        maas_version = get_running_version()
        self.assertEqual(maas_version.short_version, "2.10.0")
        self.assertEqual(maas_version.extended_info, "456-g.deadbeef")

    def test_uses_version_from_python(self):
        self.patch(version, "_get_version_from_apt").return_value = None
        self.patch(version, "DISTRIBUTION").version = "2.10.0b1"
        self.patch(version, "_get_maas_repo_hash").return_value = None
        self.patch(version, "_get_maas_repo_commit_count").return_value = 0
        maas_version = get_running_version()
        self.assertEqual(maas_version.short_version, "2.10.0~beta1")
        self.assertEqual(maas_version.extended_info, "")

    def test_uses_version_from_python_with_git_info(self):
        self.patch(version, "_get_version_from_apt").return_value = None
        self.patch(version, "DISTRIBUTION").version = "2.10.0b1"
        self.patch(version, "_get_maas_repo_commit_count").return_value = 1234
        self.patch(version, "_get_maas_repo_hash").return_value = "deadbeef"
        maas_version = get_running_version()
        self.assertEqual(maas_version.short_version, "2.10.0~beta1")
        self.assertEqual(maas_version.extended_info, "1234-g.deadbeef")

    def test_method_is_cached(self):
        self.patch(snap, "running_in_snap").return_value = True
        mock_get_snap_versions = self.patch(snap, "get_snap_version")
        mock_get_snap_versions.return_value = snap.SnapVersion(
            version="2.10.0-456-g.deadbeef",
            revision="1234",
        )
        version.get_running_version.cache_clear()

        first_return_value = version.get_running_version()
        second_return_value = version.get_running_version()
        # The return value is not empty (full unit tests have been performed
        # earlier).
        self.assertNotIn(first_return_value, [b"", "", None])
        self.assertEqual(first_return_value, second_return_value)
        mock_get_snap_versions.assert_called_once()


class TestGetVersionsInfo(MAASTestCase):
    def test_get_versions_info_empty(self):
        self.patch(snap, "get_snap_versions_info").return_value = None
        self.patch(deb, "get_deb_versions_info").return_value = None
        self.assertIsNone(get_versions_info())

    def test_get_versions_state_snap_over_deb(self):
        versions_info = snap.SnapVersionsInfo(
            current=snap.SnapVersion(
                revision="1234", version="3.0.0~alpha1-111-g.deadbeef"
            ),
        )
        mock_get_snap_versions = self.patch(snap, "get_snap_versions_info")
        mock_get_snap_versions.return_value = versions_info
        mock_get_deb_versions = self.patch(deb, "get_deb_versions_info")
        mock_get_deb_versions.return_value = None
        self.assertEqual(get_versions_info(), versions_info)
        # if running in the snap, deb info is not collected
        mock_get_snap_versions.assert_called_once()
        mock_get_deb_versions.assert_not_called()
