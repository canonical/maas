# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""CentOS Operating System."""

__all__ = [
    "CentOS",
    ]

import re

from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystem,
)


DISTRO_SERIES_DEFAULT = 'centos65'

# Regex matcher that is used to check if the release is supported.
# It needs to match the name "centosXY". Where "X" is the major version
# and "Y" is the minor version.
DISTRO_MATCHER = re.compile("centos(?P<major>[0-9])(?P<minor>[0-9])?\Z")


class CentOS(OperatingSystem):
    """CentOS operating system."""

    name = "centos"
    title = "CentOS"

    def get_boot_image_purposes(self, arch, subarch, release, label):
        """Gets the purpose of each boot image."""
        return [
            BOOT_IMAGE_PURPOSE.XINSTALL
            ]

    def is_release_supported(self, release):
        """Return True when the release is supported, False otherwise."""
        matched = DISTRO_MATCHER.match(release)
        return matched is not None

    def get_default_release(self):
        """Gets the default release to use when a release is not
        explicit."""
        return DISTRO_SERIES_DEFAULT

    def get_release_title(self, release):
        """Return the title for the given release."""
        matched = DISTRO_MATCHER.match(release)
        if matched is None:
            return None
        matched_dict = matched.groupdict()
        major = matched_dict['major']
        minor = matched_dict['minor']
        if minor is None:
            minor = '0'
        return "CentOS %s.%s" % (major, minor)
