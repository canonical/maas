# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""SUSE Operating System."""


from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystem,
)

DISTRO_SERIES_CHOICES = {"opensuse13": "openSUSE 13.1"}

DISTRO_SERIES_DEFAULT = "opensuse13"
assert DISTRO_SERIES_DEFAULT in DISTRO_SERIES_CHOICES


class SUSEOS(OperatingSystem):
    """SUSE operating system."""

    name = "suse"
    title = "SUSE"

    def get_boot_image_purposes(self, arch, subarch, release, label):
        """Gets the purpose of each boot image."""
        return [BOOT_IMAGE_PURPOSE.XINSTALL]

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
