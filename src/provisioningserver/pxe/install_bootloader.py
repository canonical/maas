# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Install a PXE pre-boot loader for TFTP download."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "add_arguments",
    "run",
    ]

import filecmp
import os.path
from shutil import copyfile

from celeryconfig import TFTPROOT
from provisioningserver.pxe.tftppath import (
    compose_bootloader_path,
    locate_tftp_path,
    )


def make_destination(tftproot, arch, subarch):
    """Locate a loader's destination.  Create containing directory if needed.

    :param tftproot: The root directory served up by the TFTP server,
        e.g. /var/lib/tftpboot/.
    :param arch: Main architecture to locate the destination for.
    :param subarch: Sub-architecture of the main architecture.
    :return: Full path describing the filename that the installed loader
        should end up having.  For example, the loader for i386 (with
        sub-architecture "generic") should install at
        /maas/i386/generic/pxelinux.0.
    """
    path = locate_tftp_path(
        compose_bootloader_path(arch, subarch),
        tftproot=tftproot)
    directory = os.path.dirname(path)
    if not os.path.isdir(directory):
        os.makedirs(directory)
    return path


def are_identical_files(old, new):
    """Are `old` and `new` identical?

    If `old` does not exist, the two are considered different (`new` is
    assumed to exist).
    """
    if os.path.isfile(old):
        return filecmp.cmp(old, new, shallow=False)
    else:
        return False


def install_bootloader(loader, destination):
    """Install bootloader file at path `loader` as `destination`.

    Installation will be atomic.  If an identical loader is already
    installed, it will be left untouched.

    However it is still conceivable, depending on the TFTP implementation,
    that a download that is already in progress may suddenly start receiving
    data from the new file instead of the one it originally started
    downloading.

    :param loader: Name of loader to install.
    :param destination: Loader's intended filename, including full path,
        where it will become available over TFTP.
    """
    if are_identical_files(destination, loader):
        return

    # Copy new loader next to the old one, to ensure that it is on the
    # same filesystem.  Once it is, we can replace the old one with an
    # atomic rename operation.
    temp_file = '%s.new' % destination
    if os.path.exists(temp_file):
        os.remove(temp_file)
    copyfile(loader, temp_file)
    os.rename(temp_file, destination)


def add_arguments(parser):
    parser.add_argument(
        '--arch', dest='arch', default=None,
        help="Main system architecture that the bootloader is for.")
    parser.add_argument(
        '--subarch', dest='subarch', default='generic',
        help="Sub-architecture of the main architecture [%(default)s].")
    parser.add_argument(
        '--loader', dest='loader', default=None,
        help="PXE pre-boot loader to install.")
    parser.add_argument(
        '--tftproot', dest='tftproot', default=TFTPROOT, help=(
            "Store to this TFTP directory tree instead of the "
            "default [%(default)s]."))


def run(args):
    """Install a PXE pre-boot loader into the TFTP directory structure.

    This won't overwrite an existing loader if its contents are unchanged.
    However the new loader you give it will be deleted regardless.
    """
    destination = make_destination(args.tftproot, args.arch, args.subarch)
    install_bootloader(args.loader, destination)
    if os.path.exists(args.loader):
        os.remove(args.loader)
