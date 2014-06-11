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
    'get_distro_series_inital',
    'get_release_requires_key',
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


def list_all_usable_osystems():
    """Return all operating systems that can be used for nodes.

    These are the operating systems for which any nodegroup has the boot images
    required to boot the node.
    """
    # The Node edit form offers all usable operating systems as options for the
    # osystem field.  Not all of these may be available in the node's
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


def list_osystem_choices(osystems):
    """Return Django "choices" list for `osystem`."""
    choices = [('', 'Default OS')]
    choices += [
        (osystem.name, osystem.title)
        for osystem in osystems
        ]
    return choices


def list_all_usable_releases(osystems):
    """Return dictionary of usable `releases` for each opertaing system."""
    distro_series = {}
    nodegroups = list(NodeGroup.objects.all())
    for osystem in osystems:
        releases = set()
        for nodegroup in nodegroups:
            releases = releases.union(
                BootImage.objects.get_usable_releases(nodegroup, osystem.name))
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


def list_release_choices(releases):
    """Return Django "choices" list for `releases`."""
    choices = [('', 'Default OS Release')]
    for key, value in releases.items():
        osystem = OperatingSystemRegistry[key]
        options = osystem.format_release_choices(value)
        requires_key = get_release_requires_key(osystem, '')
        choices += [(
            '%s/%s' % (osystem.name, requires_key),
            'Latest %s Release' % osystem.title
            )]
        choices += [(
            '%s/%s%s' % (
                osystem.name,
                name,
                get_release_requires_key(osystem, name)
                ),
            title
            )
            for name, title in options
            ]
    return choices


def get_distro_series_inital(instance):
    """Returns the distro_series initial value for the instance."""
    osystem = instance.osystem
    series = instance.distro_series
    os_obj = OperatingSystemRegistry.get_item(osystem)
    if os_obj is not None:
        key_required = get_release_requires_key(os_obj, series)
    else:
        key_required = ''
    if osystem is not None and osystem != '':
        if series is None:
            series = ''
        return '%s/%s%s' % (osystem, series, key_required)
    return None


