# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""ESXi Operating System."""

import re

from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystem,
)


class ESXi(OperatingSystem):
    """ESXi operating system."""

    name = "esxi"
    title = "VMware ESXi"

    def get_boot_image_purposes(self):
        """Gets the purpose of each boot image."""
        return [BOOT_IMAGE_PURPOSE.XINSTALL]

    def get_default_release(self):
        """Gets the default release to use when a release is not
        explicit."""
        return "6.7"

    def get_release_title(self, release):
        """Return the title for the given release."""
        ret = self.title
        m = re.search(
            r"^((?P<major>[0-9])(\.(?P<minor>[0-9]))?(\.(?P<micro>[0-9]))?)?"
            r"([\-\.]?(?P<title>.+)?)$",
            release,
        )
        if m is None:
            return ret
        if m.group("major"):
            ret = "{} {}".format(ret, m.group("major"))
        if m.group("minor"):
            ret = "{}.{}".format(ret, m.group("minor"))
        if m.group("micro"):
            ret = "{}.{}".format(ret, m.group("micro"))
        if m.group("title"):
            ret = "{} {}".format(ret, m.group("title"))
        return ret

    def get_image_filetypes(self) -> dict[str, str]:
        return self._get_image_filetypes(dd=True)
