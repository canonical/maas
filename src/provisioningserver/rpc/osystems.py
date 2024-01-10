# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to operating systems."""


from provisioningserver.drivers.osystem import OperatingSystemRegistry
from provisioningserver.rpc import exceptions


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
