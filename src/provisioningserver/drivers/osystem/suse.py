# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""SUSE Operating System."""

import re

from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystem,
)

DISTRO_MATCHER = re.compile(
    r"^(?P<product>sles|opensuse|tumbleweed)(?P<major>\d+)?(\.(?P<minor>\d+))?(-(?P<title>.+))?$",
    re.I,
)

SUSE_PRODUCTS = {
    "sles": "SUSE Linux Enterprise Server",
    "opensuse": "OpenSUSE",
    "tumbleweed": "OpenSUSE Tumbleweed",
}


DISTRO_SERIES_DEFAULT = "tumbleweed"


class SUSEOS(OperatingSystem):
    """SUSE operating system."""

    name = "suse"
    title = "SUSE"

    def get_boot_image_purposes(self):
        """Gets the purpose of each boot image."""
        return [BOOT_IMAGE_PURPOSE.XINSTALL]

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
            return f"{self.title} {release}"

        prod = matched.group("product")
        major = matched.group("major")
        minor = matched.group("minor")
        title = matched.group("title")

        ret = SUSE_PRODUCTS[prod]
        if major is not None:
            ret = f"{ret} {major}"
        if minor is not None:
            if prod == "sles":
                ret = f"{ret} SP{minor}"
            else:
                ret = f"{ret}.{minor}"
        if title is not None:
            ret = f"{ret} {title}"
        return ret
