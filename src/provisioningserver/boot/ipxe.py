# Copyright 2017-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""IPXE Boot Method"""


from itertools import repeat
import os
import re
from textwrap import dedent

import tempita

from provisioningserver.boot import BootMethod, BytesReader, get_parameters

CONFIG_FILE = dedent(
    """\
    #!ipxe
    # MAAS iPXE pre-loader configuration file

    # Load based on MAC address first.
    chain http://${next-server}:5248/ipxe.cfg-${mac} ||

    # Failed to load based on MAC address.
    chain http://${next-server}:5248/ipxe.cfg-default-amd64
    """
)

# iPXE represents a MAC address in IEEE 802 colon-seperated format.
re_mac_address_octet = r"[0-9a-f]{2}"
re_mac_address = re.compile(":".join(repeat(re_mac_address_octet, 6)))

# Match the grub/grub.cfg-* request for UEFI (aka. GRUB2)
re_config_file = r"""
    # Optional leading slash(es).
    ^/*
    ipxe[.]cfg   # UEFI (aka. GRUB2) expects this.
    -
    (?: # either a MAC
        (?P<mac>{re_mac_address.pattern}) # Capture UEFI MAC.
    | # or "default"
        default
          (?: # perhaps with specified arch, with a separator of '-'
            [-](?P<arch>\w+) # arch
            (?:-(?P<subarch>\w+))? # optional subarch
          )?
    )
    $
"""

re_config_file = re_config_file.format(re_mac_address=re_mac_address)
re_config_file = re_config_file.encode("ascii")
re_config_file = re.compile(re_config_file, re.VERBOSE)


class IPXEBootMethod(BootMethod):
    """Boot method for iPXE boot loader."""

    name = "ipxe"
    bios_boot_method = "ipxe"
    template_subdir = "ipxe"
    bootloader_arches = []
    bootloader_path = "ipxe.cfg"
    arch_octet = None
    user_class = "iPXE"
    path_prefix_http = True
    absolute_url_as_filename = True

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
        params = get_parameters(match)

        # MAC address is in the wrong format, fix it
        mac = params.get("mac")
        if mac is not None:
            params["mac"] = mac.replace(":", "-")

        return params

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
        # fs_host and the kernel parameter comes through as part of
        # the simplestream.
        step1 = template.substitute(namespace)
        return BytesReader(
            tempita.Template(step1).substitute(namespace).encode("utf-8")
        )

    def link_bootloader(self, destination: str):
        """Install the ipxe.cfg to chainload with append MAC address."""
        super().link_bootloader(destination)
        config_dst = os.path.join(destination, "ipxe.cfg")
        with open(config_dst, "wb") as stream:
            stream.write(CONFIG_FILE.encode("utf-8"))
