# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.utils.osystems`."""

__all__ = []

from operator import itemgetter
import random

from distro_info import UbuntuDistroInfo
from django.core.exceptions import ValidationError
from maasserver.clusterrpc.testing.osystems import (
    make_rpc_osystem,
    make_rpc_release,
)
from maasserver.models import (
    BootResource,
    BootSourceCache,
    Config,
)
from maasserver.testing.factory import factory
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import osystems as osystems_module
from maasserver.utils.orm import post_commit_hooks
from maasserver.utils.osystems import (
    get_distro_series_initial,
    get_release_requires_key,
    list_all_releases_requiring_keys,
    list_all_usable_osystems,
    list_all_usable_releases,
    list_commissioning_choices,
    list_osystem_choices,
    list_release_choices,
    make_hwe_kernel_ui_text,
    release_a_newer_than_b,
    validate_hwe_kernel,
    validate_osystem_and_distro_series,
)
from maastesting.matchers import MockAnyCall


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

    def test_get_distro_series_initial_works_around_conflicting_os(self):
        # Test for bug 1456892.
        releases = [
            make_rpc_release(requires_license_key=True) for _ in range(3)]
        osystem = make_rpc_osystem(releases=releases)
        release = random.choice(releases)
        node = factory.make_Node(
            osystem=osystem['name'], distro_series=release['name'])
        self.assertEqual(
            '%s/%s' % (osystem['name'], release['name']),
            get_distro_series_initial(
                [], node, with_key_required=True))

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

    def test_make_hwe_kernel_ui_text_finds_release_from_bootsourcecache(self):
        release = factory.pick_ubuntu_release()
        kernel = 'hwe-' + release[0]
        # Stub out the post commit tasks otherwise the test fails due to
        # unrun post-commit tasks at the end of the test.
        self.patch(BootSourceCache, "post_commit_do")
        # Force run the post commit tasks as we make new boot sources
        with post_commit_hooks:
            factory.make_BootSourceCache(
                os="ubuntu/%s" % release,
                subarch=kernel,
                release=release)
        self.assertEqual(
            '%s (%s)' % (release, kernel),
            make_hwe_kernel_ui_text(kernel))

    def test_make_hwe_kernel_ui_finds_release_from_ubuntudistroinfo(self):
        self.assertEqual('trusty (hwe-t)', make_hwe_kernel_ui_text('hwe-t'))

    def test_make_hwe_kernel_ui_returns_kernel_when_none_found(self):
        # Since this is testing that our fall final fall back returns just the
        # kernel name when the release isn't found in BootSourceCache or
        # UbuntuDistroInfo we patch out UbuntuDistroInfo so nothing is found.
        self.patch(UbuntuDistroInfo, 'all').value = []
        self.assertEqual(
            'hwe-m',
            make_hwe_kernel_ui_text('hwe-m'))


class TestValidateOsystemAndDistroSeries(MAASServerTestCase):

    def test__raises_error_of_osystem_and_distro_series_dont_match(self):
        os = factory.make_name("os")
        release = "%s/%s" % (
            factory.make_name("os"), factory.make_name("release"))
        error = self.assertRaises(
            ValidationError, validate_osystem_and_distro_series, os, release)
        self.assertEqual(
            "%s in distro_series does not match with "
            "operating system %s." % (release, os), error.message)

    def test__raises_error_if_not_supported_osystem(self):
        os = factory.make_name("os")
        release = factory.make_name("release")
        error = self.assertRaises(
            ValidationError, validate_osystem_and_distro_series, os, release)
        self.assertEqual(
            "%s is not a support operating system." % os,
            error.message)

    def test__raises_error_if_not_supported_release(self):
        osystem = make_usable_osystem(self)
        release = factory.make_name("release")
        error = self.assertRaises(
            ValidationError, validate_osystem_and_distro_series,
            osystem['name'], release)
        self.assertEqual(
            "%s/%s is not a support operating system and release "
            "combination." % (osystem['name'], release),
            error.message)

    def test__returns_osystem_and_release_with_license_key_stripped(self):
        osystem = make_usable_osystem(self)
        release = osystem['default_release']
        self.assertEqual(
            (osystem['name'], release),
            validate_osystem_and_distro_series(osystem['name'], release + '*'))


class TestReleaseANewerThanB(MAASServerTestCase):

    def test_release_a_newer_than_b(self):
        # Since we wrap around 'p' we want to use 'p' as our starting point
        alphabet = ([chr(i) for i in range(ord('p'), ord('z') + 1)] +
                    [chr(i) for i in range(ord('a'), ord('p'))])
        previous_true = 0
        for i in alphabet:
            true_count = 0
            for j in alphabet:
                if release_a_newer_than_b('hwe-' + i, j):
                    true_count += 1
            previous_true += 1
            self.assertEqual(previous_true, true_count)


class TestValidateHweKernel(MAASServerTestCase):

    def test_validate_hwe_kernel_returns_default_kernel(self):
        self.patch(
            BootResource.objects,
            'get_usable_hwe_kernels').return_value = ('hwe-t', 'hwe-u')
        hwe_kernel = validate_hwe_kernel(
            None, None, 'amd64/generic', 'ubuntu', 'trusty')
        self.assertEqual(hwe_kernel, 'hwe-t')

    def test_validate_hwe_kernel_set_kernel(self):
        self.patch(
            BootResource.objects,
            'get_usable_hwe_kernels').return_value = ('hwe-t', 'hwe-v')
        hwe_kernel = validate_hwe_kernel(
            'hwe-v', None, 'amd64/generic', 'ubuntu', 'trusty')
        self.assertEqual(hwe_kernel, 'hwe-v')

    def test_validate_hwe_kernel_fails_with_nongeneric_arch_and_kernel(self):
        exception_raised = False
        try:
            validate_hwe_kernel(
                'hwe-v', None, 'armfh/hardbank', 'ubuntu', 'trusty')
        except ValidationError as e:
            self.assertEqual(
                'Subarchitecture(hardbank) must be generic when setting ' +
                'hwe_kernel.', e.message)
            exception_raised = True
        self.assertEqual(True, exception_raised)

    def test_validate_hwe_kernel_fails_with_missing_hwe_kernel(self):
        exception_raised = False
        self.patch(
            BootResource.objects,
            'get_usable_hwe_kernels').return_value = ('hwe-t', 'hwe-u')
        try:
            validate_hwe_kernel(
                'hwe-v', None, 'amd64/generic', 'ubuntu', 'trusty')
        except ValidationError as e:
            self.assertEqual(
                'hwe-v is not available for ubuntu/trusty on amd64/generic.',
                e.message)
            exception_raised = True
        self.assertEqual(True, exception_raised)

    def test_validate_hwe_kernel_fails_with_old_kernel_and_newer_release(self):
        exception_raised = False
        self.patch(
            BootResource.objects,
            'get_usable_hwe_kernels').return_value = ('hwe-t', 'hwe-v')
        try:
            validate_hwe_kernel(
                'hwe-t', None, 'amd64/generic', 'ubuntu', 'vivid')
        except ValidationError as e:
            self.assertEqual(
                'hwe-t is too old to use on ubuntu/vivid.',
                e.message)
            exception_raised = True
        self.assertEqual(True, exception_raised)

    def test_validate_hwe_kern_fails_with_old_kern_and_new_min_hwe_kern(self):
        exception_raised = False
        self.patch(
            BootResource.objects,
            'get_usable_hwe_kernels').return_value = ('hwe-t', 'hwe-v')
        try:
            validate_hwe_kernel(
                'hwe-t', 'hwe-v', 'amd64/generic', 'ubuntu', 'precise')
        except ValidationError as e:
            self.assertEqual(
                'hwe_kernel(hwe-t) is older than min_hwe_kernel(hwe-v).',
                e.message)
            exception_raised = True
        self.assertEqual(True, exception_raised)

    def test_validate_hwe_kernel_fails_with_no_avalible_kernels(self):
        exception_raised = False
        self.patch(
            BootResource.objects,
            'get_usable_hwe_kernels').return_value = ('hwe-t', 'hwe-v')
        try:
            validate_hwe_kernel(
                'hwe-t', 'hwe-v', 'amd64/generic', 'ubuntu', 'precise')
        except ValidationError as e:
            self.assertEqual(
                'hwe_kernel(hwe-t) is older than min_hwe_kernel(hwe-v).',
                e.message)
            exception_raised = True
        self.assertEqual(True, exception_raised)

    def test_validate_hwe_kern_fails_with_old_release_and_newer_hwe_kern(self):
        exception_raised = False
        try:
            validate_hwe_kernel(
                None, 'hwe-v', 'amd64/generic', 'ubuntu', 'trusty')
        except ValidationError as e:
            self.assertEqual(
                'trusty has no kernels availible which meet' +
                ' min_hwe_kernel(hwe-v).', e.message)
            exception_raised = True
        self.assertEqual(True, exception_raised)

    def test_validate_hwe_kern_always_sets_kern_with_commissionable_os(self):
        self.patch(
            BootResource.objects,
            'get_usable_hwe_kernels').return_value = ('hwe-t', 'hwe-v')
        mock_get_config = self.patch(Config.objects, "get_config")
        mock_get_config.return_value = 'trusty'
        kernel = validate_hwe_kernel(
            None,
            'hwe-v',
            '%s/generic' % factory.make_name('arch'),
            factory.make_name("osystem"),
            factory.make_name("distro"))
        self.assertThat(
            mock_get_config, MockAnyCall('commissioning_osystem'))
        self.assertThat(
            mock_get_config, MockAnyCall('commissioning_distro_series'))
        self.assertEqual('hwe-v', kernel)
