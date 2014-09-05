# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.utils.osystems`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random

from maasserver.testing.factory import factory
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.osystems import (
    get_distro_series_initial,
    get_release_requires_key,
    list_all_releases_requiring_keys,
    list_all_usable_osystems,
    list_all_usable_releases,
    list_osystem_choices,
    list_release_choices,
    )
from maastesting.matchers import MockCalledOnceWith
from provisioningserver.drivers.osystem import OperatingSystemRegistry


def make_usable_boot_images(nodegroup=None, osystem=None, arch=None,
                            subarchitecture=None, release=None):
        """Create a set of boot images."""
        if nodegroup is None:
            nodegroup = factory.make_NodeGroup()
        if osystem is None:
            osystem = factory.make_name('os')
        if arch is None:
            arch = factory.make_name('arch')
        if subarchitecture is None:
            subarchitecture = factory.make_name('subarch')
        if release is None:
            release = factory.make_name('release')
        for purpose in ['install', 'commissioning']:
            factory.make_boot_image(
                nodegroup=nodegroup, osystem=osystem, architecture=arch,
                subarchitecture=subarchitecture, release=release,
                purpose=purpose)


class TestOsystems(MAASServerTestCase):

    def test_list_all_usable_osystems_ignores_boot_images(self):
        expected = set(osystem for _, osystem in OperatingSystemRegistry)
        self.assertItemsEqual(
            expected, list_all_usable_osystems(have_images=False))

    def test_list_all_usable_osystems_sorts_ignores_boot_images(self):
        expected = set(osystem for _, osystem in OperatingSystemRegistry)
        expected = sorted(expected, key=lambda osystem: osystem.title)
        self.assertEqual(
            expected, list_all_usable_osystems(have_images=False))

    def test_list_all_usable_osystems_combines_nodegroups(self):
        osystem_names = [factory.make_name('os') for _ in range(3)]
        expected = []
        for name in osystem_names:
            make_usable_boot_images(osystem=name)
            expected.append(make_usable_osystem(self, name))
        self.assertItemsEqual(expected, list_all_usable_osystems())

    def test_list_all_usable_osystems_sorts_output(self):
        osystem_names = [factory.make_name('os') for _ in range(3)]
        expected = []
        for name in osystem_names:
            make_usable_boot_images(osystem=name)
            expected.append(make_usable_osystem(self, name))
        expected = sorted(expected, key=lambda osystem: osystem.title)
        self.assertEqual(expected, list_all_usable_osystems())

    def test_list_all_usable_osystems_returns_no_duplicates(self):
        os_name = factory.make_name('os')
        make_usable_boot_images(osystem=os_name)
        make_usable_boot_images(osystem=os_name)
        osystem = make_usable_osystem(self, os_name)
        self.assertEqual(
            [osystem], list_all_usable_osystems())

    def test_list_all_usable_osystems_omits_oses_without_boot_images(self):
        usable_os_name = factory.make_name('os')
        unusable_os_name = factory.make_name('os')
        make_usable_boot_images(osystem=usable_os_name)
        usable_os = make_usable_osystem(self, usable_os_name)
        unusable_os = make_usable_osystem(self, unusable_os_name)

        usable_os_list = list_all_usable_osystems()
        self.assertIn(usable_os, usable_os_list)
        self.assertNotIn(unusable_os, usable_os_list)

    def test_list_all_usable_osystems_omits_oses_not_supported(self):
        usable_os_name = factory.make_name('os')
        unusable_os_name = factory.make_name('os')
        make_usable_boot_images(osystem=usable_os_name)
        make_usable_boot_images(osystem=unusable_os_name)
        usable_os = make_usable_osystem(self, usable_os_name)

        usable_os_list = list_all_usable_osystems()
        self.assertIn(usable_os, usable_os_list)
        self.assertNotIn(unusable_os_name, [os.name for os in usable_os_list])

    def test_list_osystem_choices_includes_default(self):
        self.assertEqual(
            [('', 'Default OS')],
            list_osystem_choices([], include_default=True))

    def test_list_osystem_choices_doesnt_include_default(self):
        self.assertEqual([], list_osystem_choices([], include_default=False))

    def test_list_osystem_choices_uses_name_and_title(self):
        name = factory.make_name('os')
        title = factory.make_name('title')
        osystem = make_usable_osystem(self, name)
        osystem.title = title
        self.assertEqual(
            [(name, title)],
            list_osystem_choices([osystem], include_default=False))


class TestReleases(MAASServerTestCase):

    def test_list_all_usable_releases_ignores_releases_without_images(self):
        expected = {}
        osystems = []
        os_names = [factory.make_name('os') for _ in range(3)]
        for name in os_names:
            releases = [factory.make_name('release') for _ in range(3)]
            osystems.append(
                make_usable_osystem(self, name, releases=releases))
            expected[name] = releases
        self.assertItemsEqual(
            expected, list_all_usable_releases(osystems, have_images=False))

    def test_list_all_usable_releases_ignores_releases_wo_images_sorted(self):
        expected = {}
        osystems = []
        os_names = [factory.make_name('os') for _ in range(3)]
        for name in os_names:
            releases = [factory.make_name('release') for _ in range(3)]
            osystems.append(
                make_usable_osystem(self, name, releases=releases))
            expected[name] = sorted(releases)
        self.assertEqual(
            expected, list_all_usable_releases(osystems, have_images=False))

    def test_list_all_usable_releases_combines_nodegroups(self):
        expected = {}
        osystems = []
        os_names = [factory.make_name('os') for _ in range(3)]
        for name in os_names:
            releases = [factory.make_name('release') for _ in range(3)]
            for release in releases:
                # Each create call also creates a new nodegroup for the image,
                # testing that the result combines all nodegroups. Which is one
                # nodegroup per boot image, in this test.
                make_usable_boot_images(osystem=name, release=release)
            osystems.append(
                make_usable_osystem(self, name, releases=releases))
            expected[name] = releases
        self.assertItemsEqual(expected, list_all_usable_releases(osystems))

    def test_list_all_usable_releases_sorts_output(self):
        expected = {}
        osystems = []
        os_names = [factory.make_name('os') for _ in range(3)]
        for name in os_names:
            releases = [factory.make_name('release') for _ in range(3)]
            for release in releases:
                make_usable_boot_images(osystem=name, release=release)
            osystems.append(
                make_usable_osystem(self, name, releases=releases))
            expected[name] = sorted(releases)
        self.assertEqual(expected, list_all_usable_releases(osystems))

    def test_list_all_usable_releases_returns_no_duplicates(self):
        os_name = factory.make_name('os')
        release = factory.make_name('release')
        make_usable_boot_images(osystem=os_name, release=release)
        make_usable_boot_images(osystem=os_name, release=release)
        osystem = make_usable_osystem(self, os_name, releases=[release])
        expected = {}
        expected[os_name] = [release]
        self.assertEqual(expected, list_all_usable_releases([osystem]))

    def test_list_all_releases_requiring_keys(self):
        # Create osystem with multiple releases
        osystem = make_usable_osystem(self)
        assert len(osystem.get_supported_releases()) > 0
        self.patch(osystem, 'requires_license_key').return_value = True
        expected = {
            osystem.name: osystem.get_supported_releases()
            }
        self.assertItemsEqual(
            expected, list_all_releases_requiring_keys([osystem]))

    def test_list_all_releases_requiring_keys_sorts_releases(self):
        # Create osystem with multiple releases
        osystem = make_usable_osystem(self)
        assert len(osystem.get_supported_releases()) > 0
        self.patch(osystem, 'requires_license_key').return_value = True
        expected = {
            osystem.name: sorted(osystem.get_supported_releases())
            }
        self.assertEqual(
            expected, list_all_releases_requiring_keys([osystem]))

    def test_list_all_releases_requiring_keys_ignores_releases_without(self):
        osystem = make_usable_osystem(self)
        self.patch(osystem, 'requires_license_key').return_value = True
        osystem_not = make_usable_osystem(self)
        self.patch(osystem_not, 'requires_license_key').return_value = False
        expected = {
            osystem.name: osystem.get_supported_releases(),
            }
        self.assertItemsEqual(
            expected, list_all_releases_requiring_keys([osystem, osystem_not]))

    def test_get_release_requires_key(self):
        releases = [
            (factory.make_name('release'), random.choice(['', '*']))
            for _ in range(3)
            ]
        names = [name for name, _ in releases]
        output = [key for _, key in releases]
        osystem = make_usable_osystem(self, releases=[names])
        self.patch(osystem, 'requires_license_key').side_effect = output
        for release, expected in releases:
            self.assertEqual(
                expected, get_release_requires_key(osystem, release))

    def test_list_release_choices_includes_default(self):
        self.assertEqual(
            [('', 'Default OS Release')],
            list_release_choices({}, include_default=True))

    def test_list_release_choices_doesnt_include_default(self):
        self.assertEqual([], list_release_choices({}, include_default=False))

    def test_list_release_choices_includes_default_and_latest(self):
        os_name = factory.make_name('os')
        osystem = make_usable_osystem(
            self, osystem_name=os_name, releases=[])
        mapping = {
            os_name: [],
            }
        expected = [
            ('', 'Default OS Release'),
            ('%s/' % os_name, 'Latest %s Release' % osystem.title),
            ]
        self.assertEqual(
            expected,
            list_release_choices(
                mapping, include_default=True, include_latest=True))

    def test_list_release_choices_includes_only_latest(self):
        os_name = factory.make_name('os')
        osystem = make_usable_osystem(
            self, osystem_name=os_name, releases=[])
        mapping = {
            os_name: [],
            }
        self.assertEqual(
            [('%s/' % os_name, 'Latest %s Release' % osystem.title)],
            list_release_choices(
                mapping, include_default=False, include_latest=True))

    def test_list_release_choices_calls_format_release_choices(self):
        os_name = factory.make_name('os')
        releases = [factory.make_name('release') for _ in range(3)]
        osystem = make_usable_osystem(
            self, osystem_name=os_name, releases=releases)
        mapping = {
            os_name: releases,
            }
        mock_format = self.patch(osystem, 'format_release_choices')
        mock_format.return_value = []
        list_release_choices(mapping)
        self.assertThat(mock_format, MockCalledOnceWith(releases))

    def test_list_release_choices_formats_releases(self):
        os_name = factory.make_name('os')
        releases = [factory.make_name('release') for _ in range(3)]
        make_usable_osystem(
            self, osystem_name=os_name, releases=releases)
        mapping = {
            os_name: releases,
            }
        expected = [
            ('%s/%s' % (os_name, release), release)
            for release in sorted(releases, reverse=True)
            ]
        self.assertEqual(
            expected,
            list_release_choices(
                mapping, include_default=False, include_latest=False))

    def test_list_release_choices_includes_requires_key_astrisk(self):
        os_name = factory.make_name('os')
        releases = [factory.make_name('release') for _ in range(3)]
        osystem = make_usable_osystem(
            self, osystem_name=os_name, releases=releases)
        self.patch(osystem, 'requires_license_key').return_value = True
        mapping = {
            os_name: releases,
            }
        expected = [('%s/*' % os_name, 'Latest %s Release' % os_name)]
        expected.extend(
            ('%s/%s*' % (os_name, release), release)
            for release in sorted(releases, reverse=True)
            )
        self.assertEqual(
            expected,
            list_release_choices(
                mapping, include_default=False, include_latest=True))

    def test_get_distro_series_initial(self):
        osystem = make_usable_osystem(self)
        series = factory.pick_release(osystem)
        node = factory.make_Node(osystem=osystem.name, distro_series=series)
        self.assertEqual(
            '%s/%s' % (osystem.name, series),
            get_distro_series_initial(node, with_key_required=False))

    def test_get_distro_series_initial_without_key_required(self):
        osystem = make_usable_osystem(self)
        self.patch(osystem, 'requires_license_key').return_value = True
        series = factory.pick_release(osystem)
        node = factory.make_Node(osystem=osystem.name, distro_series=series)
        self.assertEqual(
            '%s/%s' % (osystem.name, series),
            get_distro_series_initial(node, with_key_required=False))

    def test_get_distro_series_initial_with_key_required(self):
        osystem = make_usable_osystem(self)
        self.patch(osystem, 'requires_license_key').return_value = True
        series = factory.pick_release(osystem)
        node = factory.make_Node(osystem=osystem.name, distro_series=series)
        self.assertEqual(
            '%s/%s*' % (osystem.name, series),
            get_distro_series_initial(node, with_key_required=True))
