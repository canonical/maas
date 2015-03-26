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

from operator import itemgetter
import random

from maasserver.clusterrpc.testing.osystems import (
    make_rpc_osystem,
    make_rpc_release,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import osystems as osystems_module
from maasserver.utils.osystems import (
    get_distro_series_initial,
    get_release_requires_key,
    list_all_releases_requiring_keys,
    list_all_usable_osystems,
    list_all_usable_releases,
    list_commissioning_choices,
    list_osystem_choices,
    list_release_choices,
)


class TestOsystems(MAASServerTestCase):

    def patch_gen_all_known_operating_systems(self, osystems):
        self.patch(
            osystems_module,
            'gen_all_known_operating_systems').return_value = osystems

    def test_list_all_usable_osystems(self):
        osystems = [make_rpc_osystem() for _ in range(3)]
        self.patch_gen_all_known_operating_systems(osystems)
        self.assertItemsEqual(osystems, list_all_usable_osystems())

    def test_list_all_usable_osystems_sorts_title(self):
        osystems = [make_rpc_osystem() for _ in range(3)]
        self.patch_gen_all_known_operating_systems(osystems)
        self.assertEqual(
            sorted(osystems, key=itemgetter('title')),
            list_all_usable_osystems())

    def test_list_all_usable_osystems_removes_os_without_releases(self):
        osystems = [make_rpc_osystem() for _ in range(3)]
        without_releases = make_rpc_osystem(releases=[])
        self.patch_gen_all_known_operating_systems(
            osystems + [without_releases])
        self.assertItemsEqual(osystems, list_all_usable_osystems())

    def test_list_osystem_choices_includes_default(self):
        self.assertEqual(
            [('', 'Default OS')],
            list_osystem_choices([], include_default=True))

    def test_list_osystem_choices_doesnt_include_default(self):
        self.assertEqual([], list_osystem_choices([], include_default=False))

    def test_list_osystem_choices_uses_name_and_title(self):
        osystem = make_rpc_osystem()
        self.assertEqual(
            [(osystem['name'], osystem['title'])],
            list_osystem_choices([osystem], include_default=False))


class TestReleases(MAASServerTestCase):

    def make_release_choice(self, osystem, release, include_asterisk=False):
        key = '%s/%s' % (osystem['name'], release['name'])
        if include_asterisk:
            return ('%s*' % key, release['title'])
        return (key, release['title'])

    def test_list_all_usable_releases(self):
        releases = [make_rpc_release() for _ in range(3)]
        osystem = make_rpc_osystem(releases=releases)
        self.assertItemsEqual(
            releases, list_all_usable_releases([osystem])[osystem['name']])

    def test_list_all_usable_releases_sorts(self):
        releases = [make_rpc_release() for _ in range(3)]
        osystem = make_rpc_osystem(releases=releases)
        releases = sorted(releases, key=itemgetter('title'))
        self.assertEqual(
            releases, list_all_usable_releases([osystem])[osystem['name']])

    def test_list_all_releases_requiring_keys(self):
        releases = [
            make_rpc_release(requires_license_key=True) for _ in range(3)]
        release_without_license_key = make_rpc_release(
            requires_license_key=False)
        osystem = make_rpc_osystem(
            releases=releases + [release_without_license_key])
        self.assertItemsEqual(
            releases,
            list_all_releases_requiring_keys([osystem])[osystem['name']])

    def test_list_all_releases_requiring_keys_sorts(self):
        releases = [
            make_rpc_release(requires_license_key=True) for _ in range(3)]
        release_without_license_key = make_rpc_release(
            requires_license_key=False)
        osystem = make_rpc_osystem(
            releases=releases + [release_without_license_key])
        releases = sorted(releases, key=itemgetter('title'))
        self.assertEqual(
            releases,
            list_all_releases_requiring_keys([osystem])[osystem['name']])

    def test_get_release_requires_key_returns_asterisk_when_required(self):
        release = make_rpc_release(requires_license_key=True)
        self.assertEqual('*', get_release_requires_key(release))

    def test_get_release_requires_key_returns_empty_when_not_required(self):
        release = make_rpc_release(requires_license_key=False)
        self.assertEqual('', get_release_requires_key(release))

    def test_list_release_choices_includes_default(self):
        self.assertEqual(
            [('', 'Default OS Release')],
            list_release_choices({}, include_default=True))

    def test_list_release_choices_doesnt_include_default(self):
        self.assertEqual([], list_release_choices({}, include_default=False))

    def test_list_release_choices(self):
        releases = [make_rpc_release() for _ in range(3)]
        osystem = make_rpc_osystem(releases=releases)
        choices = [
            self.make_release_choice(osystem, release)
            for release in releases
            ]
        self.assertItemsEqual(
            choices,
            list_release_choices(
                list_all_usable_releases([osystem]),
                include_default=False))

    def test_list_release_choices_sorts(self):
        releases = [make_rpc_release() for _ in range(3)]
        osystem = make_rpc_osystem(releases=releases)
        choices = [
            self.make_release_choice(osystem, release)
            for release in sorted(releases, key=itemgetter('title'))
            ]
        self.assertEqual(
            choices,
            list_release_choices(
                list_all_usable_releases([osystem]),
                include_default=False))

    def test_list_release_choices_includes_requires_key_asterisk(self):
        releases = [
            make_rpc_release(requires_license_key=True) for _ in range(3)]
        osystem = make_rpc_osystem(releases=releases)
        choices = [
            self.make_release_choice(osystem, release, include_asterisk=True)
            for release in releases
            ]
        self.assertItemsEqual(
            choices,
            list_release_choices(
                list_all_usable_releases([osystem]),
                include_default=False))

    def test_get_distro_series_initial(self):
        releases = [make_rpc_release() for _ in range(3)]
        osystem = make_rpc_osystem(releases=releases)
        release = random.choice(releases)
        node = factory.make_Node(
            osystem=osystem['name'], distro_series=release['name'])
        self.assertEqual(
            '%s/%s' % (osystem['name'], release['name']),
            get_distro_series_initial(
                [osystem], node, with_key_required=False))

    def test_get_distro_series_initial_without_key_required(self):
        releases = [
            make_rpc_release(requires_license_key=True) for _ in range(3)]
        osystem = make_rpc_osystem(releases=releases)
        release = random.choice(releases)
        node = factory.make_Node(
            osystem=osystem['name'], distro_series=release['name'])
        self.assertEqual(
            '%s/%s' % (osystem['name'], release['name']),
            get_distro_series_initial(
                [osystem], node, with_key_required=False))

    def test_get_distro_series_initial_with_key_required(self):
        releases = [
            make_rpc_release(requires_license_key=True) for _ in range(3)]
        osystem = make_rpc_osystem(releases=releases)
        release = random.choice(releases)
        node = factory.make_Node(
            osystem=osystem['name'], distro_series=release['name'])
        self.assertEqual(
            '%s/%s*' % (osystem['name'], release['name']),
            get_distro_series_initial(
                [osystem], node, with_key_required=True))

    def test_list_commissioning_choices_returns_empty_list_if_not_ubuntu(self):
        osystem = make_rpc_osystem()
        self.assertEqual([], list_commissioning_choices([osystem]))

    def test_list_commissioning_choices_returns_commissioning_releases(self):
        comm_releases = [
            make_rpc_release(can_commission=True) for _ in range(3)]
        no_comm_release = make_rpc_release()
        osystem = make_rpc_osystem(
            'ubuntu', releases=comm_releases + [no_comm_release])
        choices = [
            (release['name'], release['title'])
            for release in comm_releases
            ]
        self.assertItemsEqual(choices, list_commissioning_choices([osystem]))

    def test_list_commissioning_choices_returns_sorted(self):
        comm_releases = [
            make_rpc_release(can_commission=True) for _ in range(3)]
        osystem = make_rpc_osystem(
            'ubuntu', releases=comm_releases)
        comm_releases = sorted(
            comm_releases, key=itemgetter('title'))
        choices = [
            (release['name'], release['title'])
            for release in comm_releases
            ]
        self.assertEqual(choices, list_commissioning_choices([osystem]))
