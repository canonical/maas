# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Operating System class used for custom images."""

__all__ = [
    "CustomOS",
    ]

import os

from provisioningserver.config import ClusterConfiguration
from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystem,
)


class CustomOS(OperatingSystem):
    """Custom operating system."""

    name = "custom"
    title = "Custom"

    def get_boot_image_purposes(self, arch, subarch, release, label):
        """Gets the purpose of each boot image."""
        # Custom images can only be used with XINSTALL.
        return [BOOT_IMAGE_PURPOSE.XINSTALL]

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

    def get_xinstall_parameters(self, arch, subarch, release, label):
        """Returns the xinstall image name and type for given image."""
        filetypes = {
            "root-tgz": "tgz",
            "root-dd": "dd-tgz",
            "root-dd.xz": "dd-xz",
        }
        with ClusterConfiguration.open() as config:
            dd_path = os.path.join(
                config.tftp_root, "custom", arch,
                subarch, release, label)
        filename, filetype = "root-tgz", "tgz"
        try:
            for fname in os.listdir(dd_path):
                if fname in filetypes.keys():
                    filename, filetype = fname, filetypes[fname]
                    break
        except FileNotFoundError:
            # In case the path does not exist
            pass
        return filename, filetype
