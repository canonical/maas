# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Write config output for ISC DHCPD."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "DHCPConfigError",
    "get_config",
]


from textwrap import dedent

from provisioningserver.pxe.tftppath import compose_bootloader_path
import tempita


class DHCPConfigError(Exception):
    """Exception raised for errors processing the DHCP config."""


# Architectures that we support netbooting for.
# Actually we don't really do amd64; those systems get to use the i386
# bootloader instead.
bootloader_architectures = [
    ('amd64', 'generic'),
    ('arm', 'highbank'),
    ('i386', 'generic'),
    ]

template_content = dedent("""\
    class "pxe" {
      match if substring (option vendor-class-identifier, 0, 9) = "PXEClient";
    }
    class "uboot-highbank" {
      match if substring (option vendor-class-identifier, 0, 21) = \
        "U-boot.armv7.highbank";
    }

    subnet {{subnet}} netmask {{subnet_mask}} {
           next-server {{next_server}};
           option subnet-mask {{subnet_mask}};
           option broadcast-address {{broadcast_address}};
           option domain-name-servers {{dns_servers}};
           option routers {{gateway}};
           range dynamic-bootp {{low_range}} {{high_range}};

           pool {
                   allow members of "uboot-highbank";
                   filename "{{bootloaders['arm', 'highbank']}}";
           }
           pool {
                   allow members of "pxe";
                   filename "{{bootloaders['i386', 'generic']}}";
           }
    }
""")

template = tempita.Template(
    template_content, name="%s.template" % __name__)


def compose_bootloaders():
    """Compose "bootloaders" dict for substitution in the DHCP template.

    The bootloaders dict maps tuples of (architecture, subarchitecture) to
    their respective TFTP bootloader paths.

    Thus, bootloaders['i386', 'generic'] yields the TFTP path for the i386
    bootloader.
    """
    return {
        (arch, subarch): compose_bootloader_path(arch, subarch)
        for arch, subarch in bootloader_architectures}


def get_config(**params):
    """Return a DHCP config file based on the supplied parameters.

    :param subnet: The base subnet declaration. e.g. 192.168.1.0
    :param subnet_mask: The mask for the above subnet, e.g. 255.255.255.0
    :param next_server: The address of the TFTP server for PXE booting.
    :param broadcast_address: The broadcast IP address for the subnet,
        e.g. 192.168.1.255
    :param dns_servers: One or more IP addresses of the DNS server for the
        subnet
    :param gateway: The router/gateway IP address for the subnet.
    :param low_range: The first IP address in the range of IP addresses to
        allocate
    :param high_range: The last IP address in the range of IP addresses to
        allocate
    """
    params['bootloaders'] = compose_bootloaders()

    # This is a really simple substitution for now but it's encapsulated
    # here so that its implementation can be changed later if required.
    try:
        return template.substitute(params)
    except NameError, error:
        raise DHCPConfigError(*error.args)
