# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""S390X Boot Method"""


import re

from tftp.backend import FilesystemReader

from provisioningserver.boot import (
    BootMethod,
    BytesReader,
    get_parameters,
    get_remote_mac,
)
from provisioningserver.boot.pxe import ARP_HTYPE, re_mac_address
from provisioningserver.kernel_opts import compose_kernel_command_line

# The pxelinux.cfg path is prefixed with the architecture for the
# S390x nodes. This prefix is set by the path-prefix dhcpd option.
# We assume that the ARP HTYPE (hardware type) that PXELINUX sends is
# always Ethernet.
re_config_file = r"""
    # Optional leading slash(es).
    ^/*
    s390x           # S390x pxe prefix, set by dhcpd
    /
    (pxelinux[.]cfg/)?    # Not sent on s390x KVM
    (?: # either a MAC
        {htype:02x}    # ARP HTYPE.
        -
        (?P<mac>{re_mac_address.pattern})    # Capture MAC.
    | # or "default"
        default
    )
    $
"""

re_config_file = re_config_file.format(
    htype=ARP_HTYPE.ETHERNET, re_mac_address=re_mac_address
)
re_config_file = re_config_file.encode("ascii")
re_config_file = re.compile(re_config_file, re.VERBOSE)

# Due to the "s390x" prefix all files requested from the client using
# relative paths will have that prefix. Capturing the path after that prefix
# will give us the correct path in the local tftp root on disk.
re_other_file = r"""
    # Optional leading slash(es).
    ^/*
    s390x           # S390x PXE prefix, set by dhcpd.
    /
    (?P<path>.+)      # Capture path.
    $
"""
re_other_file = re_other_file.encode("ascii")
re_other_file = re.compile(re_other_file, re.VERBOSE)


def format_bootif(mac):
    """Formats a mac address into the BOOTIF format, expected by
    the linux kernel."""
    mac = mac.replace(":", "-")
    mac = mac.lower()
    return f"{ARP_HTYPE.ETHERNET:02x}-{mac}"


class S390XBootMethod(BootMethod):
    name = "s390x"
    bios_boot_method = "s390x"
    template_subdir = "pxe"
    bootloader_arches = ["s390x"]
    # boots390x.bin is a place holder to allow the path_prefix to be set.
    # s390x KVM uses a bootloader shipped with KVM.
    bootloader_path = "boots390x.bin"
    arch_octet = "00:1F"
    path_prefix = "s390x/"
    user_class = None

    def get_params(self, backend, path):
        """Gets the matching parameters from the requested path."""
        match = re_config_file.match(path)
        if match is not None:
            return get_parameters(match)
        match = re_other_file.match(path)
        if match is not None:
            return get_parameters(match)
        return None

    def match_path(self, backend, path):
        """Checks path for the configuration file that needs to be
        generated.

        :param backend: requesting backend
        :param path: requested path
        :return: dict of match params from path, None if no match
        """
        params = self.get_params(backend, path)
        if params is None:
            return None
        params["arch"] = "s390x"
        if "mac" not in params:
            mac = get_remote_mac()
            if mac is not None:
                params["mac"] = mac
        return params

    def get_reader(self, backend, kernel_params, mac=None, path=None, **extra):
        """Render a configuration file as a unicode string.

        :param backend: requesting backend
        :param kernel_params: An instance of `KernelParameters`.
        :param path: Optional MAC address discovered by `match_path`.
        :param path: Optional path discovered by `match_path`.
        :param extra: Allow for other arguments. This is a safety valve;
            parameters generated in another component (for example, see
            `TFTPBackend.get_config_reader`) won't cause this to break.
        """
        if path is not None:
            # This is a request for a static file, not a configuration file.
            # The prefix was already trimmed by `match_path` so we need only
            # return a FilesystemReader for `path` beneath the backend's base.
            target_path = backend.base.descendant(path.split("/"))
            return FilesystemReader(target_path)

        # Return empty config for S390x local. S390x fails to
        # support the LOCALBOOT flag. Empty config will allow it
        # to select the first device.
        if kernel_params.purpose == "local":
            return BytesReader(b"")

        template = self.get_template(
            kernel_params.purpose, kernel_params.arch, kernel_params.subarch
        )
        namespace = self.compose_template_namespace(kernel_params)

        # Modify the kernel_command to inject the BOOTIF. S390x fails to
        # support the IPAPPEND pxelinux flag.
        def kernel_command(params):
            cmd_line = compose_kernel_command_line(params)
            if mac is not None:
                return f"{cmd_line} BOOTIF={format_bootif(mac)}"
            return cmd_line

        namespace["kernel_command"] = kernel_command
        return BytesReader(template.substitute(namespace).encode("utf-8"))

    def link_bootloader(self, destination: str):
        """Does nothing. No extra boot files are required. All of the boot
        files from PXEBootMethod will suffice."""
