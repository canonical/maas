# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""PXE Boot Method"""


from itertools import repeat
import re

import tempita

from provisioningserver.boot import BootMethod, BytesReader, get_parameters
from provisioningserver.logger import get_maas_logger

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
