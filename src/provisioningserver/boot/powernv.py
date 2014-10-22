# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""PowerNV Boot Method"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'PowerNVBootMethod',
    ]

import re

from provisioningserver.boot import (
    BootMethod,
    BytesReader,
    get_parameters,
    )
from provisioningserver.boot.pxe import (
    ARP_HTYPE,
    re_mac_address,
    )
from provisioningserver.kernel_opts import compose_kernel_command_line
from provisioningserver.utils import find_mac_via_arp
from tftp.backend import FilesystemReader
from twisted.python.context import get

# The pxelinux.cfg path is prefixed with the architecture for the
# PowerNV nodes. This prefix is set by the path-prefix dhcpd option.
# We assume that the ARP HTYPE (hardware type) that PXELINUX sends is
# always Ethernet.
re_config_file = r'''
    # Optional leading slash(es).
    ^/*
    ppc64el           # PowerNV pxe prefix, set by dhcpd
    /
    pxelinux[.]cfg    # PXELINUX expects this.
    /
    (?: # either a MAC
        {htype:02x}    # ARP HTYPE.
        -
        (?P<mac>{re_mac_address.pattern})    # Capture MAC.
    | # or "default"
        default
    )
    $
'''

re_config_file = re_config_file.format(
    htype=ARP_HTYPE.ETHERNET, re_mac_address=re_mac_address)
re_config_file = re.compile(re_config_file, re.VERBOSE)


def format_bootif(mac):
    """Formats a mac address into the BOOTIF format, expected by
    the linux kernel."""
    mac = mac.replace(':', '-')
    mac = mac.lower()
    return '%02x-%s' % (ARP_HTYPE.ETHERNET, mac)


class PowerNVBootMethod(BootMethod):

    name = "powernv"
    template_subdir = "pxe"
    bootloader_path = "pxelinux.0"
    arch_octet = "00:0E"
    path_prefix = "ppc64el/"

    def get_remote_mac(self):
        """Gets the requestors MAC address from arp cache.

        This is used, when the pxelinux.cfg is requested without the mac
        address appended. This is needed to inject the BOOTIF into the
        pxelinux.cfg that is returned to the node.
        """
        remote_host, remote_port = get("remote", (None, None))
        return find_mac_via_arp(remote_host)

    def get_params(self, backend, path):
        """Gets the matching parameters from the requested path."""
        match = re_config_file.match(path)
        if match is not None:
            return get_parameters(match)
        if path.lstrip('/').startswith(self.path_prefix):
            return {'path': path}
        return None

    def match_path(self, backend, path):
        """Checks path for the configuration file that needs to be
        generated.

        :param backend: requesting backend
        :param path: requested path
        :returns: dict of match params from path, None if no match
        """
        params = self.get_params(backend, path)
        if params is None:
            return None
        params['arch'] = "ppc64el"
        if 'mac' not in params:
            mac = self.get_remote_mac()
            if mac is not None:
                params['mac'] = mac
        return params

    def get_reader(self, backend, kernel_params, **extra):
        """Render a configuration file as a unicode string.

        :param backend: requesting backend
        :param kernel_params: An instance of `KernelParameters`.
        :param extra: Allow for other arguments. This is a safety valve;
            parameters generated in another component (for example, see
            `TFTPBackend.get_config_reader`) won't cause this to break.
        """
        # Due to the path prefix, all requested files from the client will
        # contain that prefix. Removing the prefix from the path will return
        # the correct path in the tftp root.
        if 'path' in extra:
            path = extra['path']
            path = path.replace(self.path_prefix, '', 1)
            target_path = backend.base.descendant(path.split('/'))
            return FilesystemReader(target_path)

        # Return empty config for PowerNV local. PowerNV fails to
        # support the LOCALBOOT flag. Empty config will allow it
        # to select the first device.
        if kernel_params.purpose == 'local':
            return BytesReader("".encode("utf-8"))

        template = self.get_template(
            kernel_params.purpose, kernel_params.arch,
            kernel_params.subarch)
        namespace = self.compose_template_namespace(kernel_params)

        # Modify the kernel_command to inject the BOOTIF. PowerNV fails to
        # support the IPAPPEND pxelinux flag.
        def kernel_command(params):
            cmd_line = compose_kernel_command_line(params)
            if 'mac' in extra:
                mac = extra['mac']
                mac = format_bootif(mac)
                return '%s BOOTIF=%s' % (cmd_line, mac)
            return cmd_line

        namespace['kernel_command'] = kernel_command
        return BytesReader(template.substitute(namespace).encode("utf-8"))

    def install_bootloader(self, destination):
        """Does nothing. No extra boot files are required. All of the boot
        files from PXEBootMethod will suffice."""
