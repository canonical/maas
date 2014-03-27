# Copyright 2014 Canonical Ltd.  This software is licensed under the
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

from provisioningserver.config import Config
from provisioningserver.boot.install_bootloader import make_destination

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
    config = Config.load(args.config_file)
    grubroot = os.path.join(config["tftp"]["root"], 'grub')
    destination_path = make_destination(grubroot)
    destination = os.path.join(destination_path, 'grub.cfg')
    with open(destination, 'wb') as stream:
        stream.write(CONFIG_FILE.encode("utf-8"))
