# Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Operating System class used for custom images."""


from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystem,
)


class UbuntuCoreOS(OperatingSystem):
    """Ubuntu Core operating system."""

    name = "ubuntu-core"
    title = "Ubuntu Core"

    @property
    def default_fname(self) -> str:
        """Default image filename"""
        return "root-dd.xz"

    def get_boot_image_purposes(self):
        """Gets the purpose of each boot image."""
        return [BOOT_IMAGE_PURPOSE.XINSTALL]

    def get_default_release(self):
        """Gets the default release to use when a release is not
        explicit."""
        return "16"

    def get_release_title(self, release):
        """Return the title for the given release."""
        # Return the same name, since the cluster does not know about the
        # title of the image. The region will fix the title for the UI.
        return release

    def get_image_filetypes(self) -> dict[str, str]:
        return self._get_image_filetypes(dd=True)
