# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Construct TFTP paths for UEFI files."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'compose_uefi_bootloader_path',
    ]


def compose_uefi_bootloader_path():
    """Compose the TFTP path for a UEFI pre-boot loader.
    """
    return "bootx64.efi"
