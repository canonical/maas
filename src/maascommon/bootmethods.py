#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Metadata definitions for boot methods."""

from abc import ABC, abstractmethod
from typing import Optional, Union


class BootMethodMetadata(ABC):
    # Path prefix that is used for the pxelinux.cfg. Used for
    # the dhcpd.conf that is generated.  Format is "path/to/dir/".
    # relative to tftpboot directory.
    path_prefix = None

    # Set to `True` to have the path_prefix to be an absolute prefix
    # for the HTTP boot endpoint. It is not required that `path_prefix`
    # also be set.
    path_prefix_http = False

    # Force that the path_prefix is sent over DHCP even if the client didn't
    # request that information.
    path_prefix_force = False

    # Use the full absolute URL for filename access. Instead of providing a
    # relative path to the `bootloader_path` ensure that the DHCP renders
    # with an absolute path.
    absolute_url_as_filename = False

    # When providing a URL in the bootloader make it HTTP instead of TFTP.
    # Includes "HTTPClient" as the vendor-class-identifier.
    http_url = False

    # Bootloader files to symlink into the root tftp directory.
    bootloader_files = []

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the boot method."""

    @property
    @abstractmethod
    def bios_boot_method(self) -> str:
        """Method used by the bios to boot. E.g. `pxe`."""

    @property
    @abstractmethod
    def template_subdir(self) -> Optional[str]:
        """Name of template sub-directory."""

    @property
    @abstractmethod
    def bootloader_arches(self) -> list[str]:
        """Arches for which this boot method is for."""

    @property
    @abstractmethod
    def bootloader_path(self) -> str:
        """Relative path from `path_prefix` to boot loader."""

    @property
    @abstractmethod
    def arch_octet(self) -> Optional[Union[list[str], str]]:
        """Architecture type that supports this method. Used for the
        dhcpd.conf file that is generated. Must be in the format XX:XX.
        See http://www.iana.org/assignments/dhcpv6-parameters/
        dhcpv6-parameters.xhtml#processor-architecture
        """

    @property
    @abstractmethod
    def user_class(self) -> Optional[str]:
        """User class that supports this method. Used for the
        dhcpd.conf file that is generated."""


class IPXEBootMetadata(BootMethodMetadata):
    path_prefix_http = True
    absolute_url_as_filename = True

    @property
    def name(self) -> str:
        return "ipxe"

    @property
    def bios_boot_method(self) -> str:
        return "ipxe"

    @property
    def template_subdir(self) -> str:
        return "ipxe"

    @property
    def bootloader_arches(self) -> list:
        return []

    @property
    def bootloader_path(self) -> str:
        return "ipxe.cfg"

    @property
    def arch_octet(self) -> None:
        return None

    @property
    def user_class(self) -> str:
        return "iPXE"


class PXEBootMetadata(BootMethodMetadata):
    path_prefix_http = True
    path_prefix_force = True
    bootloader_files = [
        "lpxelinux.0",
        "chain.c32",
        "ifcpu64.c32",
        "ldlinux.c32",
        "libcom32.c32",
        "libutil.c32",
    ]

    @property
    def name(self) -> str:
        return "pxe"

    @property
    def bios_boot_method(self) -> str:
        return "pxe"

    @property
    def template_subdir(self) -> str:
        return "pxe"

    @property
    def bootloader_arches(self) -> list[str]:
        return ["1386", "amd64"]

    @property
    def bootloader_path(self) -> str:
        return "lpxelinux.0"

    @property
    def arch_octet(self) -> str:
        return "00:00"

    @property
    def user_class(self) -> None:
        return None


class UefiAmd64BootMetadata(BootMethodMetadata):
    bootloader_files = ["bootx64.efi", "grubx64.efi"]

    @property
    def name(self) -> str:
        return "uefi_amd64_tftp"

    @property
    def bios_boot_method(self) -> str:
        return "uefi"

    @property
    def template_subdir(self) -> str:
        return "uefi"

    @property
    def bootloader_arches(self) -> list[str]:
        return ["amd64"]

    @property
    def bootloader_path(self) -> str:
        return "bootx64.efi"

    @property
    def arch_octet(self) -> str:
        return "00:07"

    @property
    def user_class(self) -> None:
        return None


class UefiAmd64HttpBootMetadata(UefiAmd64BootMetadata):
    absolute_url_as_filename = True
    http_url = True

    @property
    def name(self) -> str:
        return "uefi_amd64_http"

    @property
    def arch_octet(self) -> str:
        return "00:10"


# UEFI supports a byte code format called EBC which has its own boot octet.
# This allows developers to write UEFI binaries which are platform independent.
# To fix LP:1768034 MAAS was modified to respond to 00:09 with AMD64 GRUB. This
# is incorrect but did fix the bug.
class UefiEbcBootMetadata(UefiAmd64BootMetadata):
    @property
    def bootloader_arches(self) -> list[str]:
        return ["ebc"]

    @property
    def name(self) -> str:
        return "uefi_ebc_tftp"

    @property
    def arch_octet(self) -> str:
        return "00:09"


class UefiArm64BootMetadata(UefiAmd64BootMetadata):
    bootloader_files = ["bootaa64.efi", "grubaa64.efi"]

    @property
    def name(self) -> str:
        return "uefi_arm64_tftp"

    @property
    def bootloader_arches(self) -> list[str]:
        return ["arm64"]

    @property
    def bootloader_path(self) -> str:
        return "bootaa64.efi"

    @property
    def arch_octet(self) -> str:
        return "00:0B"


class UefiArm64HttpBootMetadata(UefiArm64BootMetadata):
    absolute_url_as_filename = True
    http_url = True

    @property
    def name(self) -> str:
        return "uefi_arm64_http"

    @property
    def arch_octet(self) -> str:
        return "00:13"


class OpenFirmwarePpc64elBootMetadata(UefiAmd64BootMetadata):
    bootloader_files = ["bootppc64.bin"]

    # Architecture is included in the name as open firmware can be used on
    # multiple architectures.
    @property
    def name(self) -> str:
        return "open-firmware_ppc64el"

    @property
    def bios_boot_method(self) -> str:
        return "open-firmware"

    @property
    def bootloader_arches(self) -> list[str]:
        return ["ppc64el", "ppc64"]

    @property
    def bootloader_path(self) -> str:
        return "bootppc64.bin"

    @property
    def arch_octet(self) -> str:
        return "00:0C"


class PowerNvBootMetadata(BootMethodMetadata):
    path_prefix = "ppc64el/"

    @property
    def name(self) -> str:
        return "powernv"

    @property
    def bios_boot_method(self) -> str:
        return "powernv"

    @property
    def template_subdir(self) -> str:
        return "pxe"

    @property
    def bootloader_arches(self) -> list[str]:
        return ["ppc64el"]

    @property
    def bootloader_path(self) -> str:
        return "pxelinux.0"

    @property
    def arch_octet(self) -> str:
        return "00:0E"

    @property
    def user_class(self) -> None:
        return None


class S390XBootMetadata(BootMethodMetadata):
    path_prefix = "s390x/"

    @property
    def name(self) -> str:
        return "s390x"

    @property
    def bios_boot_method(self) -> str:
        return "s390x"

    @property
    def template_subdir(self) -> str:
        return "pxe"

    @property
    def bootloader_arches(self) -> list[str]:
        return ["s390x"]

    # boots390x.bin is a place holder to allow the path_prefix to be set.
    # s390x KVM uses a bootloader shipped with KVM.
    @property
    def bootloader_path(self) -> str:
        return "boots390x.bin"

    @property
    def arch_octet(self) -> str:
        return "00:1F"

    @property
    def user_class(self) -> None:
        return None


class S390XPartitionBootMetadata(BootMethodMetadata):
    @property
    def name(self) -> str:
        return "s390x_partition"

    @property
    def bios_boot_method(self) -> str:
        return "s390x_partition"

    @property
    def template_subdir(self) -> str:
        return "s390x_partition"

    @property
    def bootloader_arches(self) -> list[str]:
        return ["s390x"]

    # S390X partitions has its bootloader built into the firmware. The
    # "bootloader" provided must be the bootloader configuration file. The
    # file format is similar to pxelinux.cfg but supports limited options
    # and requires an '=' to be used between keys and values.
    # https://www.ibm.com/support/pages/sites/default/files/inline-files/SB10-7176-01.pdf
    @property
    def bootloader_path(self) -> str:
        return "s390x_partition/maas"

    @property
    def arch_octet(self) -> str:
        return "00:20"

    @property
    def user_class(self) -> None:
        return None


class WindowsPXEBootMetadata(BootMethodMetadata):
    @property
    def name(self) -> str:
        return "windows"

    @property
    def bios_boot_method(self) -> str:
        return "windows"

    @property
    def template_subdir(self) -> str:
        return "windows"

    @property
    def bootloader_arches(self) -> list[str]:
        return []

    @property
    def bootloader_path(self) -> str:
        return "pxeboot.0"

    @property
    def arch_octet(self) -> None:
        return None

    @property
    def user_class(self) -> None:
        return None


BOOT_METHODS_METADATA: list[BootMethodMetadata] = [
    IPXEBootMetadata(),
    PXEBootMetadata(),
    UefiAmd64BootMetadata(),
    UefiAmd64HttpBootMetadata(),
    UefiEbcBootMetadata(),
    UefiArm64BootMetadata(),
    UefiArm64HttpBootMetadata(),
    OpenFirmwarePpc64elBootMetadata(),
    PowerNvBootMetadata(),
    S390XBootMetadata(),
    S390XPartitionBootMetadata(),
    WindowsPXEBootMetadata(),
]


def find_boot_method_by_arch_or_octet(
    arch: str, arch_octet: str
) -> BootMethodMetadata | None:
    """Finds the boot method corresponding to the *arch* or *arch_octet* passed.

    Args:
        - arch: architecture to look for
        - arch_octet: octet to match
    Returns:
        BootMethodMetadata if the arch or arch_octet matches, None otherwise.
    """
    for boot_method in BOOT_METHODS_METADATA:
        if boot_method.name == arch or boot_method.arch_octet == arch_octet:
            return boot_method
    return None
