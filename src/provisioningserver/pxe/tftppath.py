# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Construct TFTP paths for PXE files."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'compose_bootloader_path',
    'compose_config_path',
    'compose_image_path',
    'locate_tftp_path',
    ]

import os.path

from provisioningserver.enum import ARP_HTYPE


def compose_bootloader_path():
    """Compose the TFTP path for a PXE pre-boot loader.

    All Intel-like architectures will use `pxelinux.0`. Other architectures
    simulate PXELINUX and don't actually load `pxelinux.0`, but use its path
    to figure out where configuration files are located.
    """
    return "maas/pxelinux.0"


# TODO: move this; it is now only used for testing.
def compose_config_path(mac):
    """Compose the TFTP path for a PXE configuration file.

    The path returned is relative to the TFTP root, as it would be
    identified by clients on the network.

    :param mac: A MAC address, in IEEE 802 hyphen-separated form,
        corresponding to the machine for which this configuration is
        relevant. This relates to PXELINUX's lookup protocol.
    :return: Path for the corresponding PXE config file as exposed over
        TFTP.
    """
    # Not using os.path.join: this is a TFTP path, not a native path. Yes, in
    # practice for us they're the same. We always assume that the ARP HTYPE
    # (hardware type) that PXELINUX sends is Ethernet.
    return "maas/pxelinux.cfg/{htype:02x}-{mac}".format(
        htype=ARP_HTYPE.ETHERNET, mac=mac)


def compose_image_path(arch, subarch, release, purpose):
    """Compose the TFTP path for a PXE kernel/initrd directory.

    The path returned is relative to the TFTP root, as it would be
    identified by clients on the network.

    :param arch: Main machine architecture.
    :param subarch: Sub-architecture, or "generic" if there is none.
    :param release: Operating system release, e.g. "precise".
    :param purpose: Purpose of the image, e.g. "install" or
        "commissioning".
    :return: Path for the corresponding image directory (containing a
        kernel and initrd) as exposed over TFTP.
    """
    return '/'.join(['maas', arch, subarch, release, purpose])


def locate_tftp_path(path, tftproot):
    """Return the local filesystem path corresponding to `path`.

    The return value gives the filesystem path where you'd have to put
    a file if you wanted it made available over TFTP as `path`.

    :param path: Path as used in the TFTP protocol for which you want the
        local filesystem equivalent. Pass `None` to get the root of the TFTP
        hierarchy.
    :param tftproot: The TFTP root directory.
    """
    if path is None:
        return tftproot
    return os.path.join(tftproot, path.lstrip('/'))
