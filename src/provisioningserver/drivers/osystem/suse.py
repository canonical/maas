# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""SUSE Operating System."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "SUSEOS",
    ]

from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystem,
    )


DISTRO_SERIES_CHOICES = {
    'opensuse13': 'openSUSE 13.1',
}

DISTRO_SERIES_DEFAULT = 'opensuse13'
assert DISTRO_SERIES_DEFAULT in DISTRO_SERIES_CHOICES


class SUSEOS(OperatingSystem):
    """SUSE operating system."""

    name = "suse"
    title = "SUSE"

    def get_boot_image_purposes(self, arch, subarch, release, label):
        """Gets the purpose of each boot image."""
        return [
            BOOT_IMAGE_PURPOSE.XINSTALL
            ]

    def get_supported_releases(self):
        """Gets list of supported releases for SUSE."""
        return list(DISTRO_SERIES_CHOICES.keys())

    def get_default_release(self):
        """Gets the default release to use when a release is not
        explicit."""
        return DISTRO_SERIES_DEFAULT

    def format_release_choices(self, releases):
        """Formats the release choices that are presented to the user."""
        choices = []
        releases = sorted(releases, reverse=True)
        for release in releases:
            title = DISTRO_SERIES_CHOICES.get(release)
            if title is not None:
                choices.append((release, title))
        return choices
