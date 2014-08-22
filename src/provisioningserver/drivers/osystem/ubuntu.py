# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Ubuntu Operating System."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "UbuntuOS",
    ]

from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystem,
    )


DISTRO_SERIES_CHOICES = {
    'precise': 'Ubuntu 12.04 LTS "Precise Pangolin"',
    'quantal': 'Ubuntu 12.10 "Quantal Quetzal"',
    'raring': 'Ubuntu 13.04 "Raring Ringtail"',
    'saucy': 'Ubuntu 13.10 "Saucy Salamander"',
    'trusty': 'Ubuntu 14.04 LTS "Trusty Tahr"',
}

COMMISIONING_DISTRO_SERIES = [
    'trusty',
]

DISTRO_SERIES_DEFAULT = 'trusty'
COMMISIONING_DISTRO_SERIES_DEFAULT = 'trusty'


class UbuntuOS(OperatingSystem):
    """Ubuntu operating system."""

    name = "ubuntu"
    title = "Ubuntu"

    def get_boot_image_purposes(self, arch, subarch, release, label):
        """Gets the purpose of each boot image."""
        return [
            BOOT_IMAGE_PURPOSE.COMMISSIONING,
            BOOT_IMAGE_PURPOSE.INSTALL,
            BOOT_IMAGE_PURPOSE.XINSTALL,
            BOOT_IMAGE_PURPOSE.DISKLESS,
            ]

    def get_supported_releases(self):
        """Gets list of supported releases for Ubuntu."""
        # To make this data better, could pull this information from
        # simplestreams. So only need to update simplestreams for a
        # new release.
        return DISTRO_SERIES_CHOICES.keys()

    def get_default_release(self):
        """Gets the default release to use when a release is not
        explicit."""
        return DISTRO_SERIES_DEFAULT

    def get_supported_commissioning_releases(self):
        """Gets the supported commissioning releases for Ubuntu. This
        only exists on Ubuntu, because that is the only operating
        system that supports commissioning.
        """
        return COMMISIONING_DISTRO_SERIES

    def get_default_commissioning_release(self):
        """Gets the default commissioning release for Ubuntu. This only exists
        on Ubuntu, because that is the only operating system that supports
        commissioning.
        """
        return COMMISIONING_DISTRO_SERIES_DEFAULT

    def get_release_title(self, release):
        """Return the title for the given release."""
        return DISTRO_SERIES_CHOICES.get(release)
