# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Operating System class used for custom images."""


from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystem,
)


class CaringoOS(OperatingSystem):
    """Custom operating system."""

    name = "caringo"
    title = "Caringo"

    def get_boot_image_purposes(self, arch, subarch, release, label):
        """Gets the purpose of each boot image."""
        return [BOOT_IMAGE_PURPOSE.EPHEMERAL]

    def is_release_supported(self, release):
        """Return True when the release is supported, False otherwise."""
        # All release are supported, since the user uploaded it.
        return True

    def get_default_release(self):
        """Gets the default release to use when a release is not
        explicit."""
        # No default for this OS.
        return ""

    def get_release_title(self, release):
        """Return the title for the given release."""
        # Return the same name, since the cluster does not know about the
        # title of the image. The region will fix the title for the UI.
        return release
