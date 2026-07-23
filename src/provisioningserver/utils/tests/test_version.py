# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from maastesting.testcase import MAASTestCase
from provisioningserver.utils import snap, version
from provisioningserver.utils.version import (
    get_running_version,
    get_versions_info,
    MAASVersion,
)


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
    def test_uses_snap_get_snap_version(self):
        self.patch(snap, "get_snap_version").return_value = snap.SnapVersion(
            version="2.10.0-456-g.deadbeef",
            revision="1234",
        )
        maas_version = get_running_version()
        self.assertEqual(maas_version.short_version, "2.10.0")
        self.assertEqual(maas_version.extended_info, "456-g.deadbeef")

    def test_method_is_cached(self):
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
        self.assertIsNone(get_versions_info())

    def test_get_versions_info_snap(self):
        versions_info = snap.SnapVersionsInfo(
            current=snap.SnapVersion(
                revision="1234", version="3.0.0~alpha1-111-g.deadbeef"
            ),
        )
        mock_get_snap_versions = self.patch(snap, "get_snap_versions_info")
        mock_get_snap_versions.return_value = versions_info
        self.assertEqual(get_versions_info(), versions_info)
        mock_get_snap_versions.assert_called_once()
