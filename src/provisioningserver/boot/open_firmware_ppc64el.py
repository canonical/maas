# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""OpenFirmware PPC64EL Boot Method"""


from provisioningserver.boot import BootMethod


class OpenFirmwarePPC64ELBootMethod(BootMethod):

    name = "open-firmware_ppc64el"
    bios_boot_method = "open-firmware"
    template_subdir = None
    bootloader_arches = ["ppc64el", "ppc64"]
    bootloader_path = "bootppc64.bin"
    bootloader_files = ["bootppc64.bin"]
    arch_octet = "00:0C"
    user_class = None
