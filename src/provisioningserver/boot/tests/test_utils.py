# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.boot.utils`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
)
from maastesting.testcase import MAASTestCase
from mock import call
from provisioningserver.boot import utils


class TestBootMethodUtils(MAASTestCase):
    """Test for `BootMethod` in `provisioningserver.boot.utils`."""

    def test_get_packages(self):
        archive = factory.make_name("archive")
        comp, arch, release = factory.make_names("comp", "arch", "release")
        release_gpg = factory.make_string()
        packages_gz = factory.make_string()

        url = utils.urljoin(archive, 'dists', release)
        release_url = utils.urljoin(url, 'Release')
        release_gpg_url = utils.urljoin(url, 'Release.gpg')
        packages_path = '%s/binary-%s/Packages.gz' % (comp, arch)
        packages_url = utils.urljoin(url, packages_path)
        packages_gz_md5 = utils.get_md5sum(packages_gz)
        release_data = "  %s  012 %s" % (packages_gz_md5, packages_path)

        get_file = self.patch(utils, "get_file")
        get_file.side_effect = [release_data, release_gpg, packages_gz]
        verify_data = self.patch(utils, "gpg_verify_data")
        decompress = self.patch(utils, "decompress_packages")

        utils.get_packages(archive, comp, arch, release)

        self.assertThat(
            verify_data,
            MockCalledOnceWith(release_gpg, release_data))
        self.assertThat(
            decompress,
            MockCalledOnceWith(packages_gz))
        self.assertThat(
            get_file,
            MockCallsMatch(
                call(release_url),
                call(release_gpg_url),
                call(packages_url)))

    def test_get_packages_errors_on_invalid_checksum(self):
        archive = factory.make_name("archive")
        comp, arch, release = factory.make_names("comp", "arch", "release")
        release_gpg = factory.make_string()
        packages_gz = factory.make_string()

        packages_path = '%s/binary-%s/Packages.gz' % (comp, arch)
        packages_gz_md5 = utils.get_md5sum(packages_gz + '0')
        release_data = "  %s  012 %s" % (packages_gz_md5, packages_path)

        get_file = self.patch(utils, "get_file")
        get_file.side_effect = [release_data, release_gpg, packages_gz]
        self.patch(utils, "gpg_verify_data")
        self.patch(utils, "decompress_packages")

        self.assertRaises(
            ValueError, utils.get_packages, archive,
            comp, arch, release)

    def test_get_package_info(self):
        package = factory.make_name("package")
        archive = factory.make_name("archive")
        comp, arch, release = factory.make_names("comp", "arch", "release")

        package_items = {}
        package_list = "Package: %s\n" % package
        for _ in range(5):
            key, value = factory.make_names("key", "value")
            package_items[key] = value
            package_list += "%s: %s\n" % (key, value)
        package_list += "\n"

        get_packages = self.patch(utils, "get_packages")
        get_packages.return_value = package_list

        output = utils.get_package_info(
            package, archive, comp, arch, release)

        self.assertEqual(package, output['Package'])
        for key, value in package_items.items():
            self.assertEqual(value, output[key])

    def test_get_package(self):
        package = factory.make_name("package")
        filename = factory.make_name("filename")
        archive = factory.make_name("archive")
        comp, arch, release = factory.make_names("comp", "arch", "release")

        package_data = factory.make_string()
        package_md5 = utils.get_md5sum(package_data)
        package_info = {
            'Package': package,
            'Filename': filename,
            'MD5sum': package_md5
        }

        get_package_info = self.patch(utils, "get_package_info")
        get_package_info.return_value = package_info

        get_file = self.patch(utils, "get_file")
        get_file.return_value = package_data

        data, fn = utils.get_package(
            package, archive, comp, arch, release)

        url = utils.urljoin(archive, filename)
        self.assertThat(get_file, MockCalledOnceWith(url))
        self.assertEqual(package_data, data)
        self.assertEqual(filename, fn)

    def test_get_package_errors_on_invalid_checksum(self):
        package = factory.make_name("package")
        filename = factory.make_name("filename")
        archive = factory.make_name("archive")
        comp, arch, release = factory.make_names("comp", "arch", "release")

        package_data = factory.make_string()
        package_md5 = utils.get_md5sum(package_data + '0')
        package_info = {
            'Package': package,
            'Filename': filename,
            'MD5sum': package_md5
        }

        get_package_info = self.patch(utils, "get_package_info")
        get_package_info.return_value = package_info

        get_file = self.patch(utils, "get_file")
        get_file.return_value = package_data

        self.assertRaises(
            ValueError, utils.get_package, package,
            archive, comp, arch, release)

    def test_get_updates_package(self):
        package = factory.make_name("package")
        archive = factory.make_name("archive")
        comp, arch, release = factory.make_names("comp", "arch", "release")

        get_package = self.patch(utils, "get_package")
        get_package.return_value = (None, None)

        utils.get_updates_package(package, archive, comp, arch, release)

        updates = '%s-updates' % release
        self.assertThat(
            get_package,
            MockCallsMatch(
                call(package, archive, comp, arch, release=updates),
                call(package, archive, comp, arch, release=release)))
