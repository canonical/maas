# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""PowerKVM and PowerVM Boot Method"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'PowerKVMBootMethod',
    ]

import glob
import os.path
from textwrap import dedent

from provisioningserver.boot import (
    BootMethod,
    BootMethodInstallError,
    utils,
)
from provisioningserver.boot.install_bootloader import install_bootloader
from provisioningserver.utils.fs import tempdir
from provisioningserver.utils.shell import call_and_check


GRUB_CONFIG = dedent("""\
    configfile (pxe)/grub/grub.cfg-${net_default_mac}
    configfile (pxe)/grub/grub.cfg-default-ppc64el
    """)


class PowerKVMBootMethod(BootMethod):

    name = "powerkvm"
    bios_boot_method = "pxe"
    template_subdir = None
    bootloader_path = "bootppc64.bin"
    bootloader_arches = ['ppc64el']
    arch_octet = "00:0C"

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
        """Installs the required files for PowerKVM/PowerVM booting into the
        tftproot.
        """
        with tempdir() as tmp:
            # Download the grub-ieee1275-bin package
            data, filename = utils.get_updates_package(
                'grub-ieee1275-bin', 'http://ports.ubuntu.com',
                'main', 'ppc64el')
            if data is None:
                raise BootMethodInstallError(
                    'Failed to download grub-ieee1275-bin package from '
                    'the archive.')
            grub_output = os.path.join(tmp, filename)
            with open(grub_output, 'wb') as stream:
                stream.write(data)

            # Extract the package with dpkg, and install the shim
            call_and_check(["dpkg", "-x", grub_output, tmp])

            # Output the embedded config, so grub-mkimage can use it
            config_output = os.path.join(tmp, 'grub.cfg')
            with open(config_output, 'wb') as stream:
                stream.write(GRUB_CONFIG.encode('utf-8'))

            # Get list of grub modules
            module_dir = os.path.join(
                tmp, 'usr', 'lib', 'grub', 'powerpc-ieee1275')
            modules = []
            for module_path in glob.glob(os.path.join(module_dir, '*.mod')):
                module_filename = os.path.basename(module_path)
                module_name, _ = os.path.splitext(module_filename)
                modules.append(module_name)

            # Generate the grub bootloader
            mkimage_output = os.path.join(tmp, self.bootloader_path)
            args = [
                'grub-mkimage',
                '-o', mkimage_output,
                '-O', 'powerpc-ieee1275',
                '-d', module_dir,
                '-c', config_output,
                ]
            call_and_check(args + modules)

            install_bootloader(
                mkimage_output,
                os.path.join(destination, self.bootloader_path))
