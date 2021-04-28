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
                "version": "3.0.0~alpha1-111-g.deadbeef",
            },
            update={
                "version": "3.0.0~alpha2-222-g.cafecafe",
            },
        )
        self.assertEqual(
            info.current,
            DebVersion(version="3.0.0~alpha1-111-g.deadbeef"),
        )
        self.assertEqual(
            info.update,
            DebVersion(version="3.0.0~alpha2-222-g.cafecafe"),
        )


class MockAptPkg:
    def __init__(self):
        self._cache = {}
        self._dep_cache = defaultdict(None)
        self._package_file_indexes = defaultdict(None)
        self._priorities = {}

        self.Cache = Mock(return_value=self._cache)
        self.DepCache = Mock()
        self.SourceList = Mock()
        self.Policy = Mock()

        depcache = self.DepCache.return_value
        depcache.get_candidate_ver = self._dep_cache.get
        sourcelist = self.SourceList.return_value
        sourcelist.find_index = self._package_file_indexes.get
        policy = self.Policy.return_value
        policy.get_priority = self._priorities.get

    def _add_package(self, name, current=None, update=None):
        package = Mock()
        package.configure_mock(name=name, current_ver=current)

        self._cache[name] = package
        if update:
            self._dep_cache[package] = update

        return package

    def _make_package_version(self, version, origins=()):
        package_version = Mock(ver_str=version)
        package_version.file_list = [
            (package_file, None)  # the index is unused
            for package_file in self._make_package_files(origins)
        ]
        return package_version

    def _make_package_files(self, origins):
        package_files = []
        for priority, uri, codename, component in origins:
            package_file = Mock(codename=codename, component=component)
            if uri:
                index = Mock()
                index.archive_uri.return_value = uri
                self._package_file_indexes[package_file] = index
            self._priorities[package_file] = priority
            package_files.append(package_file)
        return package_files


class TestGetDebVersionsInfo(MAASTestCase):
    def test_no_package_known(self):
        apt_pkg = MockAptPkg()
        self.assertIsNone(get_deb_versions_info(apt_pkg=apt_pkg))

    def test_no_package_installed(self):
        apt_pkg = MockAptPkg()
        apt_pkg._add_package("maas-region-api")
        self.assertIsNone(get_deb_versions_info(apt_pkg=apt_pkg))

    def test_region_installed(self):
        apt_pkg = MockAptPkg()
        current = apt_pkg._make_package_version("3.0.0~alpha1-111-g.deadbeef")
        apt_pkg._add_package("maas-region-api", current=current)
        self.assertEqual(
            get_deb_versions_info(apt_pkg=apt_pkg),
            DebVersionsInfo(
                current=DebVersion(
                    version="3.0.0~alpha1-111-g.deadbeef", origin=""
                ),
                update=None,
            ),
        )

    def test_rack_installed(self):
        apt_pkg = MockAptPkg()
        current = apt_pkg._make_package_version("3.0.0~alpha1-111-g.deadbeef")
        apt_pkg._add_package("maas-rack-controller", current=current)
        self.assertEqual(
            get_deb_versions_info(apt_pkg=apt_pkg),
            DebVersionsInfo(
                current=DebVersion(
                    version="3.0.0~alpha1-111-g.deadbeef", origin=""
                ),
                update=None,
            ),
        )

    def test_origin(self):
        apt_pkg = MockAptPkg()
        current = apt_pkg._make_package_version(
            "3.0.0~alpha1-111-g.deadbeef",
            origins=(
                (500, "http://archive.ubuntu.com", "focal", "main"),
                (900, "http://mirror.example.com", "focal", "other"),
            ),
        )
        apt_pkg._add_package("maas-region-api", current=current)
        self.assertEqual(
            get_deb_versions_info(apt_pkg=apt_pkg),
            DebVersionsInfo(
                current=DebVersion(
                    version="3.0.0~alpha1-111-g.deadbeef",
                    origin="http://mirror.example.com focal/other",
                ),
                update=None,
            ),
        )

    def test_update(self):
        apt_pkg = MockAptPkg()
        current = apt_pkg._make_package_version("3.0.0~alpha1-111-g.deadbeef")
        update = apt_pkg._make_package_version(
            "3.0.0~alpha2-222-g.cafecafe",
            origins=(
                (500, "http://archive.ubuntu.com", "focal", "main"),
                (900, "http://mirror.example.com", "focal", "other"),
            ),
        )
        apt_pkg._add_package("maas-region-api", current=current, update=update)
        self.assertEqual(
            get_deb_versions_info(apt_pkg=apt_pkg),
            DebVersionsInfo(
                current=DebVersion(
                    version="3.0.0~alpha1-111-g.deadbeef",
                ),
                update=DebVersion(
                    version="3.0.0~alpha2-222-g.cafecafe",
                    origin="http://mirror.example.com focal/other",
                ),
            ),
        )

    def test_no_update_if_candidate_same_as_installed(self):
        apt_pkg = MockAptPkg()
        current = apt_pkg._make_package_version("3.0.0~alpha1-111-g.deadbeef")
        apt_pkg._add_package(
            "maas-region-api", current=current, update=current
        )
        self.assertEqual(
            get_deb_versions_info(apt_pkg=apt_pkg),
            DebVersionsInfo(
                current=DebVersion(
                    version="3.0.0~alpha1-111-g.deadbeef",
                ),
                update=None,
            ),
        )
