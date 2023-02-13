# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""PXE Boot Method"""


from itertools import repeat
import os
import re
import shutil

import tempita

from provisioningserver.boot import BootMethod, BytesReader, get_parameters
from provisioningserver.events import EVENT_TYPES, try_send_rack_event
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.fs import atomic_copy, atomic_symlink

maaslog = get_maas_logger("pxe")


class ARP_HTYPE:
    """ARP Hardware Type codes."""

    ETHERNET = 0x01


# PXELINUX represents a MAC address in IEEE 802 hyphen-separated
# format.  See http://www.syslinux.org/wiki/index.php/PXELINUX.
re_mac_address_octet = r"[0-9a-f]{2}"
re_mac_address = re.compile("-".join(repeat(re_mac_address_octet, 6)))

re_hardware_uuid = re.compile(
    "[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-"
    "[a-fA-F0-9]{12}"
)

# We assume that the ARP HTYPE (hardware type) that PXELINUX sends is
# always Ethernet.
re_config_file = r"""
    # Optional leading slash(es).
    ^/*
    pxelinux[.]cfg    # PXELINUX expects this.
    /
    (?: # either a MAC
        {htype:02x}    # ARP HTYPE.
        -
        (?P<mac>{re_mac_address.pattern})    # Capture MAC.
    | # or hardware uuid
        (?P<hardware_uuid>{re_hardware_uuid.pattern})
    | # or "default"
        default
          (?: # perhaps with specified arch, with a separator of either '-'
            # or '.', since the spec was changed and both are unambiguous
            [.-](?P<arch>\w+) # arch
            (?:-(?P<subarch>\w+))? # optional subarch
          )?
    )
    $
"""

re_config_file = re_config_file.format(
    htype=ARP_HTYPE.ETHERNET,
    re_mac_address=re_mac_address,
    re_hardware_uuid=re_hardware_uuid,
)
re_config_file = re_config_file.encode("ascii")
re_config_file = re.compile(re_config_file, re.VERBOSE)


class PXEBootMethod(BootMethod):
    name = "pxe"
    bios_boot_method = "pxe"
    template_subdir = "pxe"
    bootloader_arches = ["i386", "amd64"]
    bootloader_path = "lpxelinux.0"
    bootloader_files = [
        "lpxelinux.0",
        "chain.c32",
        "ifcpu64.c32",
        "ldlinux.c32",
        "libcom32.c32",
        "libutil.c32",
    ]
    arch_octet = "00:00"
    user_class = None
    path_prefix_http = True
    path_prefix_force = True

    def match_path(self, backend, path):
        """Checks path for the configuration file that needs to be
        generated.

        :param backend: requesting backend
        :param path: requested path
        :return: dict of match params from path, None if no match
        """
        match = re_config_file.match(path)
        if match is None:
            return None
        return get_parameters(match)

    def get_reader(self, backend, kernel_params, **extra):
        """Render a configuration file as a unicode string.

        :param backend: requesting backend
        :param kernel_params: An instance of `KernelParameters`.
        :param extra: Allow for other arguments. This is a safety valve;
            parameters generated in another component (for example, see
            `TFTPBackend.get_boot_method_reader`) won't cause this to break.
        """
        template = self.get_template(
            kernel_params.purpose, kernel_params.arch, kernel_params.subarch
        )
        kernel_params.mac = extra.get("mac", "")
        namespace = self.compose_template_namespace(kernel_params)

        # We are going to do 2 passes of tempita substitution because there
        # may be things like kernel params which include variables that can
        # only be populated at run time and thus contain variables themselves.
        # For example, an OS may need a kernel parameter that points back to
        # fs_host and the kernel parameter comes through as part of the simple
        # stream.
        step1 = template.substitute(namespace)
        return BytesReader(
            tempita.Template(step1).substitute(namespace).encode("utf-8")
        )

    def link_bootloader(self, destination: str):
        """Installs the required files for this boot method into the
        destination.

        :param destination: path to install bootloader
        """
        super().link_bootloader(destination)
        # When lpxelinux.0 doesn't exist we run find and copy to add that file
        # in the correct place.
        lpxelinux = os.path.join(destination, "lpxelinux.0")
        if not os.path.exists(lpxelinux):
            self._find_and_copy_bootloaders(
                destination, bootloader_files=["lpxelinux.0"]
            )

        # Symlink pxelinux.0 to lpxelinux.0 for backwards compatibility of
        # external DHCP servers that point next-server to pxelinux.0.
        pxelinux = os.path.join(destination, "pxelinux.0")
        atomic_symlink(lpxelinux, pxelinux)

    def _link_simplestream_bootloaders(self, stream_path, destination):
        super()._link_simplestream_bootloaders(stream_path, destination)

        # MAAS only requires the bootloader_files listed above to boot.
        # However some users may want to use extra PXE files in custom
        # configs or for debug. PXELinux checks / and then /syslinux so
        # create a symlink to the stream_path which contains all extra PXE
        # files. This also ensures if upstream ever starts requiring more
        # modules PXE will continue to work.
        syslinux_dst = os.path.join(destination, "syslinux")
        atomic_symlink(stream_path, syslinux_dst)

    def _find_and_copy_bootloaders(
        self, destination, log_missing=True, bootloader_files=None
    ):
        if bootloader_files is None:
            bootloader_files = self.bootloader_files
        boot_sources_base = os.path.realpath(os.path.join(destination, ".."))
        default_search_path = os.path.join(boot_sources_base, "current")
        syslinux_search_path = os.path.join(default_search_path, "syslinux")
        # In addition to the default search path search the previous
        # syslinux subdir as well. Previously MAAS didn't copy all of the
        # files required for PXE into the root tftp path. Also search the
        # paths the syslinux-common and pxelinux Ubuntu packages installs files
        # to on Xenial.
        search_paths = [
            default_search_path,
            syslinux_search_path,
            "/usr/lib/PXELINUX",
            "/usr/lib/syslinux/modules/bios",
        ]
        files_found = []
        for search_path in search_paths:
            for bootloader_file in bootloader_files:
                bootloader_src = os.path.join(search_path, bootloader_file)
                bootloader_src = os.path.realpath(bootloader_src)
                bootloader_dst = os.path.join(destination, bootloader_file)
                if os.path.exists(bootloader_src) and not os.path.exists(
                    bootloader_dst
                ):
                    # If the file was found in a previous snapshot copy it as
                    # once we're done the previous snapshot will be deleted. If
                    # the file was found elsewhere on the filesystem create a
                    # symlink so we stay current with that source.
                    if boot_sources_base in bootloader_src:
                        atomic_copy(bootloader_src, bootloader_dst)
                    else:
                        atomic_symlink(bootloader_src, bootloader_dst)
                    files_found.append(bootloader_file)

        missing_files = [
            bootloader_file
            for bootloader_file in bootloader_files
            if bootloader_file not in files_found
        ]
        if missing_files != []:
            files_are_missing = True
            if log_missing:
                err_msg = (
                    "Unable to find a copy of %s in the SimpleStream or in "
                    "the system search paths %s. The %s bootloader type may "
                    "not work."
                    % (
                        ", ".join(missing_files),
                        ", ".join(search_paths),
                        self.name,
                    )
                )
                try_send_rack_event(EVENT_TYPES.RACK_IMPORT_ERROR, err_msg)
                maaslog.error(err_msg)
        else:
            files_are_missing = False

        syslinux_search_paths = [
            syslinux_search_path,
            "/usr/lib/syslinux/modules/bios",
        ]
        for search_path in syslinux_search_paths:
            if os.path.exists(search_path):
                syslinux_src = os.path.realpath(search_path)
                syslinux_dst = os.path.join(destination, "syslinux")
                if destination in os.path.realpath(syslinux_src):
                    shutil.copy(bootloader_src, bootloader_dst)
                else:
                    atomic_symlink(syslinux_src, syslinux_dst)
                break

        return files_are_missing
