# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
"""Utilities for working with operating systems."""

__all__ = [
    'get_distro_series_initial',
    'get_release_requires_key',
    'list_all_releases_requiring_keys',
    'list_all_usable_osystems',
    'list_all_usable_releases',
    'list_all_usable_hwe_kernels',
    'list_hwe_kernel_choices',
    'list_osystem_choices',
    'list_release_choices',
    'list_commissioning_choices',
    'make_hwe_kernel_ui_text',
    'validate_hwe_kernel',
    ]

from operator import itemgetter

from distro_info import UbuntuDistroInfo
from django.core.exceptions import ValidationError
from maasserver.clusterrpc.osystems import gen_all_known_operating_systems
from maasserver.models import (
    BootResource,
    BootSourceCache,
    Config,
)


def list_all_usable_osystems():
    """Return all operating systems that can be used for nodes."""
    osystems = [
        osystem
        for osystem in gen_all_known_operating_systems()
        if len(osystem['releases']) > 0
        ]
    return sorted(osystems, key=itemgetter('title'))


def list_osystem_choices(osystems, include_default=True):
    """Return Django "choices" list for `osystem`.

    :param include_default: When true includes the 'Default OS' in choice
        selection.
    """
    if include_default:
        choices = [('', 'Default OS')]
    else:
        choices = []
    choices += [
        (osystem['name'], osystem['title'])
        for osystem in osystems
        ]
    return choices


def list_all_usable_releases(osystems):
    """Return dictionary of usable `releases` for each operating system."""
    distro_series = {}
    for osystem in osystems:
        distro_series[osystem['name']] = sorted(
            [release for release in osystem['releases']],
            key=itemgetter('title'))
    return distro_series


def list_all_usable_hwe_kernels(releases):
    """Return dictionary of usable `kernels` for each os/release."""
    kernels = {}
    for osystem, osystems in releases.items():
        if osystem not in kernels:
            kernels[osystem] = {}
        for release in osystems:
            os_release = osystem + '/' + release['name']
            kernels[osystem][release['name']] = list_hwe_kernel_choices(
                sorted([
                    i for i in BootResource.objects.get_usable_hwe_kernels(
                        os_release)
                    if release_a_newer_than_b(i, release['name'])]))
    return kernels


def make_hwe_kernel_ui_text(hwe_kernel):
    if not hwe_kernel:
        return hwe_kernel
    release_letter = hwe_kernel.replace('hwe-', '')
    boot_sources = BootSourceCache.objects.filter(
        release__startswith=release_letter,
        subarch=hwe_kernel)
    if len(boot_sources) > 0:
        return "%s (%s)" % (boot_sources[0].release, hwe_kernel)
    else:
        ubuntu = UbuntuDistroInfo()
        for release in ubuntu.all:
            if release.startswith(release_letter):
                return "%s (%s)" % (release, hwe_kernel)
    return hwe_kernel


def list_hwe_kernel_choices(hwe_kernels):
    return [(hwe_kernel, make_hwe_kernel_ui_text(hwe_kernel))
            for hwe_kernel in hwe_kernels
            ]


def list_all_releases_requiring_keys(osystems):
    """Return dictionary of OS name mapping to `releases` that require
    license keys."""
    distro_series = {}
    for osystem in osystems:
        releases = [
            release
            for release in osystem['releases']
            if release['requires_license_key']
            ]
        if len(releases) > 0:
            distro_series[osystem['name']] = sorted(
                releases, key=itemgetter('title'))
    return distro_series


def get_release_requires_key(release):
    """Return asterisk for any release that requires
    a license key.

    This is used by the JS, to display the licese_key field.
    """
    if release['requires_license_key']:
        return '*'
    return ''


def list_release_choices(releases, include_default=True,
                         with_key_required=True):
    """Return Django "choices" list for `releases`.

    :param include_default: When true includes the 'Default OS Release' in
        choice selection.
    :param with_key_required: When true includes the release_requires_key in
        the choice.
    """
    if include_default:
        choices = [('', 'Default OS Release')]
    else:
        choices = []
    for os_name, os_releases in releases.items():
        for release in os_releases:
            if with_key_required:
                requires_key = get_release_requires_key(release)
            else:
                requires_key = ''
            choices.append((
                '%s/%s%s' % (os_name, release['name'], requires_key),
                release['title']
                ))
    return choices


def get_osystem_from_osystems(osystems, name):
    """Return osystem from osystems with the given name."""
    for osystem in osystems:
        if osystem['name'] == name:
            return osystem
    return None


def get_release_from_osystem(osystem, name):
    """Return release from osystem with the given release name."""
    for release in osystem['releases']:
        if release['name'] == name:
            return release
    return None


def get_distro_series_initial(osystems, instance, with_key_required=True):
    """Returns the distro_series initial value for the instance.

    :param with_key_required: When true includes the release_requires_key in
        the choice.
    """
    osystem_name = instance.osystem
    series = instance.distro_series
    osystem = get_osystem_from_osystems(osystems, osystem_name)
    if not with_key_required:
        key_required = ''
    elif osystem is not None:
        release = get_release_from_osystem(osystem, series)
        if release is not None:
            key_required = get_release_requires_key(release)
        else:
            key_required = ''
    else:
        # OS of the instance isn't part of the given OSes list so we can't
        # figure out if the key is required or not, default to not requiring
        # it.
        key_required = ''
    if osystem_name is not None and osystem_name != '':
        if series is None:
            series = ''
        return '%s/%s%s' % (osystem_name, series, key_required)
    return None


def list_commissioning_choices(osystems):
    """Return Django "choices" list for releases that can be used for
    commissioning."""
    ubuntu = get_osystem_from_osystems(osystems, 'ubuntu')
    if ubuntu is None:
        return []
    else:
        releases = sorted(ubuntu['releases'], key=itemgetter('title'))
        return [
            (release['name'], release['title'])
            for release in releases
            if release['can_commission']
            ]


def validate_osystem_and_distro_series(osystem, distro_series):
    """Validate `osystem` and `distro_series` are valid choices."""
    if '/' in distro_series:
        series_os, release = distro_series.split('/', 1)
        if series_os != osystem:
            raise ValidationError(
                "%s in distro_series does not match with "
                "operating system %s." % (distro_series, osystem))
    else:
        release = distro_series
    release = release.replace('*', '')
    usable_osystems = list_all_usable_osystems()
    found_osystem = get_osystem_from_osystems(usable_osystems, osystem)
    if found_osystem is None:
        raise ValidationError(
            "%s is not a support operating system." % osystem)
    found_release = get_release_from_osystem(found_osystem, release)
    if found_release is None:
        raise ValidationError(
            "%s/%s is not a support operating system and release "
            "combination." % (osystem, release))
    return osystem, release


def release_a_newer_than_b(a, b):
    """Compare two Ubuntu releases and return true if a >= b.

    The release names can be the full release name(e.g Precise, Trusty), or
    a hardware enablement(e.g hwe-p, hwe-t). The function wraps around the
    letter 'p' as Precise was the first version of Ubuntu MAAS supported
    """
    def get_release_num(release):
        release = release.lower()
        if 'hwe-' in release:
            release = release.replace('hwe-', '')
        return ord(release[0])

    # Compare release versions based off of the first letter of their
    # release name or the letter in hwe-<letter>. Wrap around the letter
    # 'p' as that is the first version of Ubuntu MAAS supported.
    num_a = get_release_num(a)
    num_b = get_release_num(b)
    num_wrap = ord('p')

    if((num_a >= num_wrap and num_b >= num_wrap and num_a >= num_b) or
       (num_a < num_wrap and num_b >= num_wrap and num_a < num_b) or
       (num_a < num_wrap and num_b < num_wrap and num_a >= num_b)):
        return True
    else:
        return False


def validate_hwe_kernel(
        hwe_kernel, min_hwe_kernel, architecture, osystem, distro_series):
    """Validates that hwe_kernel works on the selected os/release/arch.

    Checks that the current hwe_kernel is avalible for the selected
    os/release/architecture combination, and that the selected hwe_kernel is >=
    min_hwe_kernel. If no hwe_kernel is selected one will be chosen.
    """
    if (not osystem or
       (not architecture or architecture == '') or
       (not distro_series or distro_series == '')):
        return hwe_kernel

    # If we're not deploying Ubuntu we are just setting the kernel to be used
    # during deployment
    if osystem != "ubuntu":
        osystem = Config.objects.get_config('commissioning_osystem')
        distro_series = Config.objects.get_config(
            'commissioning_distro_series')

    arch, subarch = architecture.split('/')

    if (subarch != 'generic' and
        ((hwe_kernel and hwe_kernel.startswith('hwe-')) or
         (min_hwe_kernel and min_hwe_kernel.startswith('hwe-')))):
        raise ValidationError(
            'Subarchitecture(%s) must be generic when setting hwe_kernel.' %
            subarch)

    os_release = osystem + '/' + distro_series
    usable_kernels = BootResource.objects.get_usable_hwe_kernels(
        os_release, arch)

    if hwe_kernel and hwe_kernel.startswith('hwe-'):
        if hwe_kernel not in usable_kernels:
            raise ValidationError(
                '%s is not available for %s on %s.' %
                (hwe_kernel, os_release, architecture))
        if not release_a_newer_than_b(hwe_kernel, distro_series):
            raise ValidationError(
                '%s is too old to use on %s.' % (hwe_kernel, os_release))
        if((min_hwe_kernel and min_hwe_kernel.startswith('hwe-')) and
           (not release_a_newer_than_b(hwe_kernel, min_hwe_kernel))):
            raise ValidationError(
                'hwe_kernel(%s) is older than min_hwe_kernel(%s).' %
                (hwe_kernel, min_hwe_kernel))
        return hwe_kernel
    elif(min_hwe_kernel and min_hwe_kernel.startswith('hwe-')):
        for i in usable_kernels:
            if(release_a_newer_than_b(i, min_hwe_kernel) and
               release_a_newer_than_b(i, distro_series)):
                return i
        raise ValidationError(
            '%s has no kernels availible which meet min_hwe_kernel(%s).' %
            (distro_series, min_hwe_kernel))
    return 'hwe-' + distro_series[0]


def validate_min_hwe_kernel(min_hwe_kernel):
    """Check that the min_hwe_kernel is avalible."""
    if not min_hwe_kernel or min_hwe_kernel == "":
        return ""
    usable_kernels = BootResource.objects.get_usable_hwe_kernels()
    if min_hwe_kernel not in usable_kernels:
        raise ValidationError('%s is not a usable kernel.' % min_hwe_kernel)
    return min_hwe_kernel
