# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to operating systems."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "gen_operating_systems",
    "validate_license_key",
]

from provisioningserver.drivers.osystem import OperatingSystemRegistry
from provisioningserver.rpc import exceptions


def gen_operating_system_releases(osystem):
    """Yield operating system release dicts.

    Each dict adheres to the response specification of an operating
    system release in the ``ListOperatingSystems`` RPC call.
    """
    releases_for_commissioning = set(
        osystem.get_supported_commissioning_releases())
    for release in osystem.get_supported_releases():
        requires_license_key = osystem.requires_license_key(release)
        can_commission = release in releases_for_commissioning
        yield {
            "name": release,
            "title": osystem.get_release_title(release),
            "requires_license_key": requires_license_key,
            "can_commission": can_commission,
        }


def gen_operating_systems():
    """Yield operating system dicts.

    Each dict adheres to the response specification of an operating
    system in the ``ListOperatingSystems`` RPC call.
    """

    for _, os in sorted(OperatingSystemRegistry):
        default_release = os.get_default_release()
        default_commissioning_release = os.get_default_commissioning_release()
        yield {
            "name": os.name,
            "title": os.title,
            "releases": gen_operating_system_releases(os),
            "default_release": default_release,
            "default_commissioning_release": default_commissioning_release,
        }


def validate_license_key(osystem, release, key):
    """Validate a license key.

    :raises NoSuchOperatingSystem: If ``osystem`` is not found.
    """
    try:
        osystem = OperatingSystemRegistry[osystem]
    except KeyError:
        raise exceptions.NoSuchOperatingSystem(osystem)
    else:
        return osystem.validate_license_key(release, key)
