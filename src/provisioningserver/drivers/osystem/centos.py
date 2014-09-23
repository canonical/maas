# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""CentOS Operating System."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "CentOS",
    ]

from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystem,
    )


DISTRO_SERIES_CHOICES = {
    'centos65': 'CentOS 6.5',
}

DISTRO_SERIES_DEFAULT = 'centos65'
assert DISTRO_SERIES_DEFAULT in DISTRO_SERIES_CHOICES


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
        return release in DISTRO_SERIES_CHOICES

    def get_default_release(self):
        """Gets the default release to use when a release is not
        explicit."""
        return DISTRO_SERIES_DEFAULT

    def get_release_title(self, release):
        """Return the title for the given release."""
        return DISTRO_SERIES_CHOICES.get(release)
