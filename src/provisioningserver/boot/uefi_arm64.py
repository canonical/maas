# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""UEFI ARM64 Boot Method"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'UEFIARM64BootMethod',
    ]


import glob
import os.path
from textwrap import dedent
from urlparse import urlparse

from provisioningserver.boot import (
    BootMethodInstallError,
    get_ports_archive_url,
    utils,
)
from provisioningserver.boot.install_bootloader import install_bootloader
from provisioningserver.boot.uefi import UEFIBootMethod
from provisioningserver.utils.fs import tempdir
from provisioningserver.utils.shell import call_and_check


CONFIG_FILE_ARM64 = dedent("""
    # MAAS GRUB2 pre-loader configuration file

    # Load based on MAC address first.
    configfile (pxe)/grub/grub.cfg-${net_default_mac}

    # Failed to load based on MAC address.
    # Load arm64 by default, UEFI only supported by 64-bit
    configfile (pxe)/grub/grub.cfg-default-arm64
    """)


class UEFIARM64BootMethod(UEFIBootMethod):

    name = "uefi_arm64"
    bios_boot_method = "uefi"
    template_subdir = "uefi"
    bootloader_arches = ['arm64']
    bootloader_path = "grubaa64.efi"
    arch_octet = "00:0B"  # ARM64 EFI

    def match_path(self, backend, path):
        """Doesn't need to do anything, as the UEFIBootMethod provides
        the grub implementation needed.
        """
        return None

    def get_reader(self, backend, kernel_params, **extra):
        """Doesn't need to do anything, as the UEFIBootMethod provides
        the grub implementation needed.
        """
        return None

    def install_bootloader(self, destination):
        """Installs the required files for UEFI ARM64 booting into the
        tftproot.
        """
        ports_archive_url = get_ports_archive_url()
        archive_url = ports_archive_url.strip(urlparse(ports_archive_url).path)
        with tempdir() as tmp:
            # Download the grub-efi-arm64-bin package
            data, filename = utils.get_updates_package(
                'grub-efi-arm64-bin', archive_url,
                'main', 'arm64')
            if data is None:
                raise BootMethodInstallError(
                    'Failed to download grub-efi-arm64-bin package from '
                    'the archive.')
            grub_output = os.path.join(tmp, filename)
            with open(grub_output, 'wb') as stream:
                stream.write(data)

            # Extract the package with dpkg
            call_and_check(["dpkg", "-x", grub_output, tmp])

            # Output the embedded config, so grub-mkimage can use it
            config_output = os.path.join(tmp, 'grub.cfg')
            with open(config_output, 'wb') as stream:
                stream.write(CONFIG_FILE_ARM64.encode('utf-8'))

            # Get list of grub modules
            module_dir = os.path.join(
                tmp, 'usr', 'lib', 'grub', 'arm64-efi')
            modules = []
            for module_path in glob.glob(os.path.join(module_dir, '*.mod')):
                module_filename = os.path.basename(module_path)
                module_name, _ = os.path.splitext(module_filename)
                # XXX newell 2015-04-28 bug=1459871,1459872: The module
                # skipping logic below can be removed once the listed bugs have
                # been fixed and released. See listed bugs for details.
                if module_name in ('setjmp', 'setjmp_test', 'progress'):
                    continue
                modules.append(module_name)

            # Generate the grub bootloader
            mkimage_output = os.path.join(tmp, self.bootloader_path)
            args = [
                'grub-mkimage',
                '-o', mkimage_output,
                '-O', 'arm64-efi',
                '-d', module_dir,
                '-c', config_output,
                ]
            call_and_check(args + modules)

            install_bootloader(
                mkimage_output,
                os.path.join(destination, self.bootloader_path))
