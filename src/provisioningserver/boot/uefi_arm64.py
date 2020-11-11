# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""UEFI ARM64 Boot Method"""


from provisioningserver.boot import BootMethod


class UEFIARM64BootMethod(BootMethod):

    name = "uefi_arm64"
    bios_boot_method = "uefi"
    template_subdir = "uefi"
    bootloader_arches = ["arm64"]
    bootloader_path = "grubaa64.efi"
    bootloader_files = ["grubaa64.efi"]
    arch_octet = "00:0B"
    user_class = None
