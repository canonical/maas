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
    ]


from maasserver.models import (
    BootImage,
    NodeGroup,
    )
from provisioningserver.drivers.osystem import OperatingSystemRegistry


def list_all_usable_osystems(have_images=True):
    """Return all operating systems that can be used for nodes.

    :param have_images: If set to true then its only the operating systems for
    which any nodegroup has the boot images available for that operating
    system.
    """
    if not have_images:
        osystems = set([osystem for _, osystem in OperatingSystemRegistry])
    else:
        # The Node edit form offers all usable operating systems as options for
        # the osystem field.  Not all of these may be available in the node's
        # nodegroup, but to represent that accurately in the UI would depend on
        # the currently selected nodegroup.  Narrowing the options down further
        # would have to happen browser-side.
        osystems = set()
        for nodegroup in NodeGroup.objects.all():
            osystems = osystems.union(
                BootImage.objects.get_usable_osystems(nodegroup))
        osystems = [
            OperatingSystemRegistry[osystem] for osystem in osystems
            if osystem in OperatingSystemRegistry
            ]
    return sorted(osystems, key=lambda osystem: osystem.title)


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
        (osystem.name, osystem.title)
        for osystem in osystems
        ]
    return choices


def list_all_usable_releases(osystems, have_images=True):
    """Return dictionary of usable `releases` for each operating system.

    :param have_images: If set to true then its only the releases for
    which any nodegroup has the boot images available for that release.
    """
    distro_series = {}
    nodegroups = list(NodeGroup.objects.all())
    for osystem in osystems:
        releases = set()
        if not have_images:
            releases = releases.union(osystem.get_supported_releases())
        else:
            for nodegroup in nodegroups:
                releases = releases.union(
                    BootImage.objects.get_usable_releases(
                        nodegroup, osystem.name))
        distro_series[osystem.name] = sorted(releases)
    return distro_series


def list_all_releases_requiring_keys(osystems):
    """Return dictionary of OS name mapping to `releases` that require
    license keys."""
    distro_series = {}
    for osystem in osystems:
        releases = [
            release
            for release in osystem.get_supported_releases()
            if osystem.requires_license_key(release)
            ]
        if len(releases) > 0:
            distro_series[osystem.name] = sorted(releases)
    return distro_series


def get_release_requires_key(osystem, release):
    """Return astrisk for any release that requires
    a license key.

    This is used by the JS, to display the licese_key field.
    """
    if osystem.requires_license_key(release):
        return '*'
    return ''


def list_release_choices(releases, include_default=True, include_latest=True,
                         with_key_required=True):
    """Return Django "choices" list for `releases`.

    :param include_default: When true includes the 'Default OS Release' in
        choice selection.
    :param include_latest: When true includes the 'Latest OS Release' in
        choice selection.
    :param with_key_required: When true includes the release_requires_key in
        the choice.
    """
    if include_default:
        choices = [('', 'Default OS Release')]
    else:
        choices = []
    for key, value in releases.items():
        osystem = OperatingSystemRegistry[key]
        options = osystem.format_release_choices(value)
        if with_key_required:
            requires_key = get_release_requires_key(osystem, '')
        else:
            requires_key = ''
        if include_latest:
            choices.append((
                '%s/%s' % (osystem.name, requires_key),
                'Latest %s Release' % osystem.title
                ))
        for name, title in options:
            if with_key_required:
                requires_key = get_release_requires_key(osystem, name)
            else:
                requires_key = ''
            choices.append((
                '%s/%s%s' % (osystem.name, name, requires_key),
                title
                ))
    return choices


def get_distro_series_initial(instance, with_key_required=True):
    """Returns the distro_series initial value for the instance.

    :param with_key_required: When true includes the release_requires_key in
        the choice.
    """
    osystem_name = instance.osystem
    series = instance.distro_series
    osystem = OperatingSystemRegistry.get_item(osystem_name)
    if not with_key_required:
        key_required = ''
    elif osystem is not None:
        key_required = get_release_requires_key(osystem, series)
    if osystem_name is not None and osystem_name != '':
        if series is None:
            series = ''
        return '%s/%s%s' % (osystem_name, series, key_required)
    return None
