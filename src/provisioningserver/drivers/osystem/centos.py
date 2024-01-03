# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""CentOS Operating System."""


import re

from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystem,
)

# Regex matcher that is used to check if the release is supported. The release
# name just has to start with 'centos' to be supported but the major, minor,
# and title are found if available to help format the title.
DISTRO_MATCHER = re.compile(
    r"^centos((?P<major>[0-9])(?P<minor>[0-9])?)?([\-\.]?(?P<title>.+))?$",
    re.I,
)
DISTRO_SERIES_DEFAULT = "centos70"


class CentOS(OperatingSystem):
    """CentOS operating system."""

    name = "centos"
    title = "CentOS"

    def get_boot_image_purposes(self):
        """Gets the purpose of each boot image."""
        return [BOOT_IMAGE_PURPOSE.XINSTALL]

    def get_default_release(self):
        """Gets the default release to use when a release is not
        explicit."""
        return DISTRO_SERIES_DEFAULT

    def get_release_title(self, release):
        """Return the title for the given release."""
        matched = DISTRO_MATCHER.match(release)
        if matched is None:
            # This should never happen as is_release_supported will return
            # false but just in case it does...
            return f"{self.title} {release}"

        ret = self.title
        major = matched.group("major")
        minor = matched.group("minor")
        title = matched.group("title")
        # MAAS provided images via streams are not bound to a minor
        # release version, which means we always provide the latest
        # available release from CentOS 6 and CentOS 7.  To address
        # LP: #1654063, we need to ensure we don't surface a version
        # unless we have specifically done so in the streams.
        #
        # Since we cannot change the streams without breaking backwards
        # compat on older MAAS', we need to ensure that we don't show
        # the minor version on CentOS 7.0, and CentOS 6.6, as they come
        # from the stream and the minor version doesn't match to what
        # we publish. As such, we ensure that we only return minor
        # if we have any other version other that X.0, 7.0 and 6.6.
        if major is not None and minor is None or minor == "0":
            ret = f"{ret} {major}"
        elif major == "6" and minor == "6":
            ret = f"{ret} {major}"
        elif None not in (major, minor):
            ret = f"{ret} {major}.{minor}"

        if title is not None:
            ret = f"{ret} {title}"

        return ret
