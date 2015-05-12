# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Ubuntu Operating System."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "UbuntuOS",
    ]

from distro_info import UbuntuDistroInfo
from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystem,
)
from provisioningserver.drivers.osystem.debian_networking import (
    compose_network_interfaces,
)
from provisioningserver.udev import compose_network_interfaces_udev_rules
from provisioningserver.utils.curtin import (
    compose_recursive_copy,
    compose_write_text_file,
)


class UbuntuOS(OperatingSystem):
    """Ubuntu operating system."""

    name = "ubuntu"
    title = "Ubuntu"

    def get_boot_image_purposes(self, arch, subarch, release, label):
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
        return UbuntuDistroInfo().lts()

    def get_default_release(self):
        """Gets the default release to use when a release is not
        explicit."""
        return self.get_lts_release()

    def get_supported_commissioning_releases(self):
        """Gets the supported commissioning releases for Ubuntu. This
        only exists on Ubuntu, because that is the only operating
        system that supports commissioning.
        """
        return [self.get_lts_release()]

    def get_default_commissioning_release(self):
        """Gets the default commissioning release for Ubuntu. This only exists
        on Ubuntu, because that is the only operating system that supports
        commissioning.
        """
        return self.get_lts_release()

    def get_distro_series_info_row(self, release):
        """Returns the distro series row information from python-distro-info.
        """
        info = UbuntuDistroInfo()
        for row in info._avail(info._date):
            if row['series'] == release:
                return row
        return None

    def get_release_title(self, release):
        """Return the title for the given release."""
        row = self.get_distro_series_info_row(release)
        if row is None:
            return None
        return UbuntuDistroInfo()._format("fullname", row)

    def compose_curtin_network_preseed(self, interfaces, auto_interfaces,
                                       ips_mapping, gateways_mapping,
                                       disable_ipv4=False, nameservers=None,
                                       netmasks=None):
        """As defined in `OperatingSystem`: generate networking Curtin preseed.

        Supports:
        * Static IPv6 address and gateway configuration.
        * DHCP-based IPv4 configuration.
        * Assigning network interface names through udev rules.
        * Disabling IPv4.
        """
        interfaces_file = compose_network_interfaces(
            interfaces, auto_interfaces, ips_mapping=ips_mapping,
            gateways_mapping=gateways_mapping, disable_ipv4=disable_ipv4,
            nameservers=nameservers, netmasks=netmasks)
        udev_rules = compose_network_interfaces_udev_rules(interfaces)
        write_files = {
            'write_files': {
                'etc_network_interfaces': compose_write_text_file(
                    '/tmp/maas/etc/network/interfaces', interfaces_file,
                    permissions=0644),
                'udev_persistent_net': compose_write_text_file(
                    '/tmp/maas/etc/udev/rules.d/70-persistent-net.rules',
                    udev_rules, permissions=0644),
            },
        }
        late_commands = {
            'late_commands': {
                'copy_etc': compose_recursive_copy('/tmp/maas/etc', '/'),
            },
        }
        return [write_files, late_commands]
