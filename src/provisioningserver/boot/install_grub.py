# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Install a GRUB2 pre-boot loader config for TFTP download."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "add_arguments",
    "run",
    ]

import os.path

from provisioningserver.boot.install_bootloader import make_destination
from provisioningserver.config import ClusterConfiguration
from provisioningserver.utils.fs import write_text_file


CONFIG_FILE = """
# MAAS GRUB2 pre-loader configuration file

# Load based on MAC address first.
configfile (pxe)/grub/grub.cfg-${net_default_mac}

# Failed to load based on MAC address.
# Load amd64 by default, UEFI only supported by 64-bit
configfile (pxe)/grub/grub.cfg-default-amd64
"""


def add_arguments(parser):
    pass


def run(args):
    """Install a GRUB2 pre-boot loader config into the TFTP
    directory structure.
    """
    with ClusterConfiguration.open() as config:
        destination_path = make_destination(config.grub_root)
        destination_file = os.path.join(destination_path, 'grub.cfg')
    write_text_file(destination_file, CONFIG_FILE)
