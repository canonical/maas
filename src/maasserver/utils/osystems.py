# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
"""Utilities for working with operating systems."""

__all__ = [
    'get_distro_series_initial',
    'get_release_requires_key',
    'get_release_version_from_string',
    'list_all_releases_requiring_keys',
    'list_all_usable_hwe_kernels',
    'list_all_usable_osystems',
    'list_all_usable_releases',
    'list_commissioning_choices',
    'list_hwe_kernel_choices',
    'list_osystem_choices',
    'list_release_choices',
    'make_hwe_kernel_ui_text',
    'release_a_newer_than_b',
    'validate_hwe_kernel',
    ]

from operator import itemgetter

from distro_info import UbuntuDistroInfo
from django.core.exceptions import ValidationError
from django.db.models import Q
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
        if len(osystem['releases']) > 0 and osystem['name'] != 'bootloader'
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
    # Fall back on getting it from DistroInfo.
    kernel_list = hwe_kernel.split('-')
    if len(kernel_list) >= 2:
        kernel = kernel_list[1]
    else:
        kernel = hwe_kernel
    # Try to get the release name from the SimpleStream
    ubuntu_release = get_release_from_db(kernel)
    if ubuntu_release is None:
        ubuntu_release = get_release_from_distro_info(kernel)
    if ubuntu_release is None:
        return hwe_kernel
    else:
        return "%s (%s)" % (ubuntu_release['series'], hwe_kernel)


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
            title = release['title']
            if not title:
                # Uploaded boot resources are not required to have a title.
                # Fallback to the name of the release when the title is
                # missing.
                title = release['name']
            choices.append((
                '%s/%s%s' % (os_name, release['name'], requires_key),
                title
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


def get_release_from_distro_info(string):
    """Convert an Ubuntu release or version into a release dict.

    This data is pulled from the UbuntuDistroInfo library which contains
    additional information such as the release, EOL, and code name."""
    ubuntu = UbuntuDistroInfo()
    release_found = False
    # We can only look at release names for 12.04+ as previous versions
    # have overlapping first letters(e.g Warty and Wily) which break looking
    # up old style kernels(e.g hwe-w).
    for row in ubuntu._rows:
        if (
                int(row['version'].split('.')[0]) >= 12 and
                row['series'].startswith(string) or
                row['version'].startswith(string)):
            release_found = True
            break
    if release_found:
        return row
    else:
        return None


def get_release_from_db(string):
    """Convert an Ubuntu release, version, or subarch into a release dict.

    This does not contain the release, eol, or created dates like
    get_release_from_distro_info does."""
    bsc = BootSourceCache.objects.filter(
        (
            (Q(subarch="hwe-%s" % string) | Q(subarch="ga-%s" % string)) &
            (
                Q(release_title__startswith=string) |
                Q(release__startswith=string)
            )
        ) |
        Q(release__startswith=string) |
        Q(release_title__startswith=string)).first()
    if bsc is None:
        return None
    elif None in (bsc.release_title, bsc.release, bsc.release_codename):
        return None
    else:
        return {
            'version': bsc.release_title,
            'eol-server': bsc.support_eol,
            'series': bsc.release,
            'codename': bsc.release_codename,
        }


def get_release_version_from_string(string):
    """Convert an Ubuntu release, version, or kernel into a version tuple.

    Takes a string input represneting an Ubuntu release, version, or hwe_kernel
    and returns a version tuple. The return value is a three integer tuple
    representing an Ubuntu major, minor values(e.g 16, 4 for Xenial) and a
    weight. The weight is used to give hwe and edge kernels a higher value when
    compared to a ga kernels. Rolling kernels and releases are given a
    very high value (999, 999) to always be the higher value during comparison.

    Input: ga-16.04, ga-16.04-lowlatency
    Output: (16, 4, 0)

    Input: xenial, 16.04, hwe-16.04, hwe-16.04-lowlatency
    Output: (16, 4, 1)

    Input: hwe-16.04-edge
    Output: (16, 4, 2)

    Input: rolling, hwe-rolling, hwe-rolling-lowlatency
    Output: (999, 999, 0)

    Input: hwe-rolling-edge, hwe-rolling-lowlatency-edge
    Output: (999, 999, 1)
    """
    parts = string.split('-')
    parts_len = len(parts)
    if parts_len == 1:
        # Just the release name, e.g xenial or 16.04
        release = string
        weight = 0
    elif parts_len == 2:
        # hwe kernel, e.g hwe-x or hwe-16.04
        release = parts[1]
        weight = 0
    elif parts_len == 3:
        # hwe edge or lowlatency kernel,
        # e.g hwe-16.04-edge or hwe-16.04-lowlatency
        release = parts[1]
        if parts[2] == 'edge':
            weight = 1
        else:
            weight = 0
    elif parts_len == 4:
        # hwe edge lowlatency kernel, e.g hwe-16.04-lowlatency-edge
        release = parts[1]
        if parts[3] == 'edge':
            weight = 1
        else:
            weight = 0
    else:
        raise ValueError("Unknown release or kernel %s!" % string)

    if parts[0] == 'hwe':
        weight += 1

    if release == 'rolling':
        # Rolling kernels are always the latest
        version = [999, 999]
    else:
        # First try to get release info from the SimpleStream
        ubuntu_release = get_release_from_db(release)
        if ubuntu_release is None:
            # Fall back on using the UbuntuDistroInfo library
            ubuntu_release = get_release_from_distro_info(release)
        if ubuntu_release is None:
            raise ValueError(
                "%s not found amoungst the known Ubuntu releases!" % string)
        # Remove 'LTS' from version if it exists
        version = ubuntu_release['version'].split(' ')[0]
        # Convert the version into a list of ints
        version = [int(seg) for seg in version.split('.')]

    return tuple(version + [weight])


def release_a_newer_than_b(a, b):
    """Compare two Ubuntu releases and return true if a >= b.

    The release names can be the full release name(e.g Precise, Trusty),
    release versions(e.g 12.04, 16.04), or an hwe kernel(e.g hwe-p, hwe-16.04,
    hwe-rolling-lowlatency-edge).
    """
    ver_a = get_release_version_from_string(a)
    ver_b = get_release_version_from_string(b)
    return ver_a >= ver_b


def validate_hwe_kernel(
        hwe_kernel, min_hwe_kernel, architecture, osystem, distro_series):
    """Validates that hwe_kernel works on the selected os/release/arch.

    Checks that the current hwe_kernel is avalible for the selected
    os/release/architecture combination, and that the selected hwe_kernel is >=
    min_hwe_kernel. If no hwe_kernel is selected one will be chosen.
    """
    def validate_kernel_str(kstr):
        return (kstr.startswith('hwe-') or kstr.startswith('ga-'))

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

    if (
            subarch != 'generic' and
            (
                (hwe_kernel and validate_kernel_str(hwe_kernel)) or
                (min_hwe_kernel and validate_kernel_str(min_hwe_kernel)))):
        raise ValidationError(
            'Subarchitecture(%s) must be generic when setting hwe_kernel.' %
            subarch)

    os_release = osystem + '/' + distro_series

    if hwe_kernel and validate_kernel_str(hwe_kernel):
        usable_kernels = BootResource.objects.get_usable_hwe_kernels(
            os_release, arch)
        if hwe_kernel not in usable_kernels:
            raise ValidationError(
                '%s is not available for %s on %s.' %
                (hwe_kernel, os_release, architecture))
        if not release_a_newer_than_b(hwe_kernel, distro_series):
            raise ValidationError(
                '%s is too old to use on %s.' % (hwe_kernel, os_release))
        if((min_hwe_kernel and validate_kernel_str(min_hwe_kernel)) and
           (not release_a_newer_than_b(hwe_kernel, min_hwe_kernel))):
            raise ValidationError(
                'hwe_kernel(%s) is older than min_hwe_kernel(%s).' %
                (hwe_kernel, min_hwe_kernel))
        return hwe_kernel
    elif(min_hwe_kernel and validate_kernel_str(min_hwe_kernel)):
        kernel_parts = min_hwe_kernel.split('-')
        if len(kernel_parts) == 2:
            kflavor = 'generic'
        else:
            kflavor = kernel_parts[2]
        usable_kernels = BootResource.objects.get_usable_hwe_kernels(
            os_release, arch, kflavor)
        for i in usable_kernels:
            if(release_a_newer_than_b(i, min_hwe_kernel) and
               release_a_newer_than_b(i, distro_series)):
                return i
        raise ValidationError(
            '%s has no kernels availible which meet min_hwe_kernel(%s).' %
            (distro_series, min_hwe_kernel))
    for kernel in BootResource.objects.get_usable_hwe_kernels(
            os_release, arch, 'generic'):
        if release_a_newer_than_b(kernel, distro_series):
            return kernel
    raise ValidationError('%s has no kernels available.' % distro_series)


def validate_min_hwe_kernel(min_hwe_kernel):
    """Check that the min_hwe_kernel is avalible."""
    if not min_hwe_kernel or min_hwe_kernel == "":
        return ""
    usable_kernels = BootResource.objects.get_usable_hwe_kernels()
    if min_hwe_kernel not in usable_kernels:
        raise ValidationError('%s is not a usable kernel.' % min_hwe_kernel)
    else:
        return min_hwe_kernel
