# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""PXE Boot Method"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'PXEBootMethod',
    ]

from itertools import repeat
import os.path
import re

from provisioningserver.boot import (
    BootMethod,
    BytesReader,
    get_parameters,
    )
from provisioningserver.boot.install_bootloader import install_bootloader
from provisioningserver.utils import atomic_symlink

# Bootloader file names to install.
BOOTLOADERS = ['pxelinux.0', 'chain.c32', 'ifcpu64.c32', 'poweroff.com']

# Possible locations in which to find the bootloader files. Search these
# in this order for each file.  (This exists because locations differ
# across Ubuntu releases.)
BOOTLOADER_DIRS = ['/usr/lib/syslinux', '/usr/lib/syslinux/modules/bios']

# List of possible directories where to find additioning bootloader files.
# The first existing directory will be symlinked to /syslinux/ inside
# the TFTP root directory.
SYSLINUX_DIRS = [
    # Location for syslinux version 6 (the version in Utopic).
    '/usr/lib/syslinux/modules/bios',
    # Location for syslinux version 4 (the version in Trusty).
    '/usr/lib/syslinux'
]


class ARP_HTYPE:
    """ARP Hardware Type codes."""

    ETHERNET = 0x01


# PXELINUX represents a MAC address in IEEE 802 hyphen-separated
# format.  See http://www.syslinux.org/wiki/index.php/PXELINUX.
re_mac_address_octet = r'[0-9a-f]{2}'
re_mac_address = re.compile(
    "-".join(repeat(re_mac_address_octet, 6)))

# We assume that the ARP HTYPE (hardware type) that PXELINUX sends is
# always Ethernet.
re_config_file = r'''
    # Optional leading slash(es).
    ^/*
    pxelinux[.]cfg    # PXELINUX expects this.
    /
    (?: # either a MAC
        {htype:02x}    # ARP HTYPE.
        -
        (?P<mac>{re_mac_address.pattern})    # Capture MAC.
    | # or "default"
        default
          (?: # perhaps with specified arch, with a separator of either '-'
            # or '.', since the spec was changed and both are unambiguous
            [.-](?P<arch>\w+) # arch
            (?:-(?P<subarch>\w+))? # optional subarch
          )?
    )
    $
'''

re_config_file = re_config_file.format(
    htype=ARP_HTYPE.ETHERNET, re_mac_address=re_mac_address)
re_config_file = re.compile(re_config_file, re.VERBOSE)


class PXEBootMethod(BootMethod):

    name = "pxe"
    template_subdir = "pxe"
    bootloader_path = "pxelinux.0"
    arch_octet = "00:00"

    def match_path(self, backend, path):
        """Checks path for the configuration file that needs to be
        generated.

        :param backend: requesting backend
        :param path: requested path
        :returns: dict of match params from path, None if no match
        """
        match = re_config_file.match(path)
        if match is None:
            return None
        return get_parameters(match)

    def get_reader(self, backend, kernel_params, **extra):
        """Render a configuration file as a unicode string.

        :param backend: requesting backend
        :param kernel_params: An instance of `KernelParameters`.
        :param extra: Allow for other arguments. This is a safety valve;
            parameters generated in another component (for example, see
            `TFTPBackend.get_boot_method_reader`) won't cause this to break.
        """
        template = self.get_template(
            kernel_params.purpose, kernel_params.arch,
            kernel_params.subarch)
        namespace = self.compose_template_namespace(kernel_params)
        return BytesReader(template.substitute(namespace).encode("utf-8"))

    def locate_bootloader(self, bootloader):
        """Search BOOTLOADER_DIRS for bootloader.

        :return: The full file path where the bootloader was found, or None.
        """
        for dir in BOOTLOADER_DIRS:
            filename = os.path.join(dir, bootloader)
            if os.path.exists(filename):
                return filename
        return None

    def locate_syslinux_dir(self):
        """Search for an existing directory among SYSLINUX_DIRS."""
        for bootloader_dir in SYSLINUX_DIRS:
            if os.path.exists(bootloader_dir):
                return bootloader_dir
        return None

    def install_bootloader(self, destination):
        """Installs the required files and symlinks into the tftproot."""
        for bootloader in BOOTLOADERS:
            # locate_bootloader might return None but happy to let that
            # traceback here is it should never happen unless there's a
            # serious problem with packaging.
            bootloader_src = self.locate_bootloader(bootloader)
            bootloader_dst = os.path.join(destination, bootloader)
            install_bootloader(bootloader_src, bootloader_dst)

        # Create /syslinux/ symlink.  PXE linux tries this subdirectory
        # when trying to fetch files for PXE-booting.
        bootloader_dir = self.locate_syslinux_dir()
        if bootloader_dir is not None:
            atomic_symlink(
                bootloader_dir, os.path.join(destination, 'syslinux'))
