# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
"""Utilities for working with operating systems."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'get_distro_series_initial',
    'get_release_requires_key',
    'list_all_releases_requiring_keys',
    'list_all_usable_osystems',
    'list_all_usable_releases',
    'list_osystem_choices',
    'list_release_choices',
    'list_commissioning_choices',
    ]


from operator import itemgetter

from maasserver.clusterrpc.osystems import gen_all_known_operating_systems


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
