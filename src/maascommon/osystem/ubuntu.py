# Copyright 2014-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Ubuntu Operating System."""

from distro_info import UbuntuDistroInfo

from maascommon.osystem import BOOT_IMAGE_PURPOSE, OperatingSystem


class UbuntuOS(OperatingSystem):
    """Ubuntu operating system."""

    name = "ubuntu"
    title = "Ubuntu"

    def __init__(self):
        self.ubuntu_distro_info = UbuntuDistroInfo()

    def get_boot_image_purposes(self):
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
        return "noble"

    def get_default_release(self):
        """Gets the default release to use when a release is not
        explicit."""
        return self.get_lts_release()

    def get_supported_commissioning_releases(self):
        """Gets the supported commissioning releases for Ubuntu. This
        only exists on Ubuntu, because that is the only operating
        system that supports commissioning.
        """
        unsupported_releases = ["xenial"]
        return [
            name
            for name in self.ubuntu_distro_info.supported_esm()
            if name not in unsupported_releases
            if self.ubuntu_distro_info.is_lts(name)
        ]

    def get_default_commissioning_release(self):
        """Gets the default commissioning release for Ubuntu. This only exists
        on Ubuntu, because that is the only operating system that supports
        commissioning.
        """
        return self.get_lts_release()

    def get_distro_series_info_row(self, release):
        """Returns the distro series row information from python-distro-info."""
        info = self.ubuntu_distro_info
        for row in info._avail(info._date):
            if row.series == release:
                return row
        return None

    def get_release_title(self, release):
        """Return the title for the given release."""
        row = self.get_distro_series_info_row(release)
        if row is None:
            return None
        return self.ubuntu_distro_info._format("fullname", row)

    def get_image_filetypes(self) -> dict[str, str]:
        return self._get_image_filetypes(tgz=True, squashfs=True)

    def get_release_version(self, release) -> str | None:
        if release not in self.ubuntu_distro_info.all:
            return None
        version = self.ubuntu_distro_info.version(release)
        return version.replace(" LTS", "")
