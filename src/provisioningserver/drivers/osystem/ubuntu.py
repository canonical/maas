# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Ubuntu Operating System."""

__all__ = [
    "UbuntuOS",
    ]

from distro_info import UbuntuDistroInfo
from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystem,
)


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

    def is_release_supported(self, release):
        """Return True when the release is supported, False otherwise."""
        row = self.get_distro_series_info_row(release)
        return row is not None

    def get_lts_release(self):
        """Return the latest Ubuntu LTS release."""
        return UbuntuDistroInfo().lts()

    def get_default_release(self):
        """Gets the default release to use when a release is not
        explicit."""
        return self.get_lts_release()

    def get_supported_commissioning_releases(self):
        """Gets the supported commissioning releases for Ubuntu. This
        only exists on Ubuntu, because that is the only operating
        system that supports commissioning.
        """
        return [self.get_lts_release()]

    def get_default_commissioning_release(self):
        """Gets the default commissioning release for Ubuntu. This only exists
        on Ubuntu, because that is the only operating system that supports
        commissioning.
        """
        return self.get_lts_release()

    def get_distro_series_info_row(self, release):
        """Returns the distro series row information from python-distro-info.
        """
        info = UbuntuDistroInfo()
        for row in info._avail(info._date):
            if row['series'] == release:
                return row
        return None

    def get_release_title(self, release):
        """Return the title for the given release."""
        row = self.get_distro_series_info_row(release)
        if row is None:
            return None
        return UbuntuDistroInfo()._format("fullname", row)
