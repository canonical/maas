# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Windows Operating System."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "WindowsOS",
    ]

import re

from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystem,
    )


WINDOWS_CHOICES = {
    'win2012': 'Windows "Server 2012"',
    'win2012r2': 'Windows "Server 2012 R2"',
    'win2012hv': 'Windows "Hyper-V Server 2012"',
    'win2012hvr2': 'Windows "Hyper-V Server 2012 R2"',
}

WINDOWS_DEFAULT = 'win2012hvr2'

REQUIRE_LICENSE_KEY = ['win2012', 'win2012r2']


class WindowsOS(OperatingSystem):
    """Windows operating system."""

    name = "windows"
    title = "Windows"

    def get_boot_image_purposes(self, arch, subarch, release, label):
        """Gets the purpose of each boot image. Windows only allows install."""
        return [BOOT_IMAGE_PURPOSE.INSTALL]

    def get_supported_releases(self):
        """Gets list of supported releases for Windows."""
        return WINDOWS_CHOICES.keys()

    def get_default_release(self):
        """Gets the default release to use when a release is not
        explicit."""
        return WINDOWS_DEFAULT

    def format_release_choices(self, releases):
        """Formats the release choices that are presented to the user."""
        choices = []
        releases = sorted(releases, reverse=True)
        for release in releases:
            title = WINDOWS_CHOICES.get(release)
            if title is not None:
                choices.append((release, title))
        return choices

    def requires_license_key(self, release):
        return release in REQUIRE_LICENSE_KEY

    def validate_license_key(self, release, key):
        r = re.compile('^([A-Za-z0-9]{5}-){4}[A-Za-z0-9]{5}$')
        return r.match(key)

    def compose_preseed(self, node, token, metadata_url):
        """Since this method exists in the WindowsOS class, it will be called
        to provide preseed to all booting Windows nodes.
        """

        # Sets the hostname in the preseed. Using just the hostname
        # not the FQDN.
        hostname = node.hostname.split(".", 1)[0]
        # Windows max hostname length is 15 characters.
        if len(hostname) > 15:
            hostname = hostname[:15]

        credentials = {
            'maas_metadata_url': metadata_url,
            'maas_oauth_consumer_secret': '',
            'maas_oauth_consumer_key': token.consumer.key,
            'maas_oauth_token_key': token.key,
            'maas_oauth_token_secret': token.secret,
            'hostname': hostname,
            }
        return credentials
