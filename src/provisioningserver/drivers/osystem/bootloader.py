# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Operating System class used for bootloaders."""


from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystem,
)


class BootLoaderOS(OperatingSystem):
    name = "bootloader"
    title = "Bootloader"

    def get_default_release(self):
        # No Default bootloader as it depends on the arch.
        return ""

    def get_release_title(self, release):
        # The title is the same as the release.
        return release

    def get_boot_image_purposes(self, arch, subarch, release, label):
        """Gets the purpose of each boot image."""
        return [BOOT_IMAGE_PURPOSE.BOOTLOADER]
