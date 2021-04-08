# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from collections import defaultdict
from unittest.mock import Mock

from maastesting.testcase import MAASTestCase
from provisioningserver.utils.deb import (
    DebVersion,
    DebVersionsInfo,
    get_deb_versions_info,
)


class TestDebVersionsInfo(MAASTestCase):
    def test_deserialize(self):
        info = DebVersionsInfo(
            current={
                "version": "3.0.0-alpha1-111-g.deadbeef",
            },
            update={
                "version": "3.0.0-alpha2-222-g.cafecafe",
            },
        )
        self.assertEqual(
            info.current,
            DebVersion(version="3.0.0-alpha1-111-g.deadbeef"),
        )
        self.assertEqual(
            info.update,
            DebVersion(version="3.0.0-alpha2-222-g.cafecafe"),
        )


class TestGetDebVersionsInfo(MAASTestCase):
    def mock_apt_pkg(self, packages_info=()):
        apt_pkg = Mock()

        cache = {}
        dep_cache = defaultdict(None)
        apt_pkg.Cache.return_value = cache
        depcache = apt_pkg.DepCache.return_value
        depcache.get_candidate_ver = lambda package: dep_cache.get(
            package.name
        )
        for name, current_version, update_version in packages_info:
            package = Mock()
            package.configure_mock(name=name)
            if current_version:
                package.current_ver.ver_str = current_version
            else:
                package.current_ver = None
            cache[name] = package

            if update_version:
                dep_cache[name] = Mock(ver_str=update_version)

        return apt_pkg

    def test_no_package_installed(self):
        apt_pkg = self.mock_apt_pkg()
        self.assertIsNone(get_deb_versions_info(apt_pkg=apt_pkg))

    def test_region_installed(self):
        apt_pkg = self.mock_apt_pkg(
            [("maas-region-api", "3.0.0-alpha1-111-g.deadbeef", None)]
        )
        self.assertEqual(
            get_deb_versions_info(apt_pkg=apt_pkg),
            DebVersionsInfo(
                current=DebVersion(version="3.0.0-alpha1-111-g.deadbeef"),
                update=None,
            ),
        )

    def test_rack_installed(self):
        apt_pkg = self.mock_apt_pkg(
            [("maas-rack-controller", "3.0.0-alpha1-111-g.deadbeef", None)]
        )
        self.assertEqual(
            get_deb_versions_info(apt_pkg=apt_pkg),
            DebVersionsInfo(
                current=DebVersion(version="3.0.0-alpha1-111-g.deadbeef"),
                update=None,
            ),
        )

    def test_update(self):
        apt_pkg = self.mock_apt_pkg(
            [
                (
                    "maas-region-api",
                    "3.0.0-alpha1-111-g.deadbeef",
                    "3.0.0-alpha2-222-g.cafecafe",
                )
            ]
        )
        self.assertEqual(
            get_deb_versions_info(apt_pkg=apt_pkg),
            DebVersionsInfo(
                current=DebVersion(version="3.0.0-alpha1-111-g.deadbeef"),
                update=DebVersion(version="3.0.0-alpha2-222-g.cafecafe"),
            ),
        )
