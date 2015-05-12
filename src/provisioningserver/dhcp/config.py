# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Write config output for ISC DHCPD."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DHCPConfigError",
    "get_config",
]


from itertools import (
    chain,
    repeat,
)
from platform import linux_distribution

from provisioningserver.boot import BootMethodRegistry
from provisioningserver.utils import locate_config
import tempita

# Location of DHCP templates, relative to the configuration directory.
TEMPLATES_DIR = "templates/dhcp"

# Used to generate the conditional bootloader behaviour
CONDITIONAL_BOOTLOADER = """
{{behaviour}} option arch = {{arch_octet}} {
          filename \"{{bootloader}}\";
          {{if path_prefix}}
          option path-prefix \"{{path_prefix}}\";
          {{endif}}
       }
"""

# Used to generate the PXEBootLoader special case
PXE_BOOTLOADER = """
else {
          filename \"{{bootloader}}\";
          {{if path_prefix}}
          option path-prefix \"{{path_prefix}}\";
          {{endif}}
       }
"""


class DHCPConfigError(Exception):
    """Exception raised for errors processing the DHCP config."""


def compose_conditional_bootloader():
    output = ""
    behaviour = chain(["if"], repeat("elsif"))
    for name, method in BootMethodRegistry:
        if name != "pxe" and method.arch_octet is not None:
            output += tempita.sub(
                CONDITIONAL_BOOTLOADER,
                behaviour=next(behaviour),
                arch_octet=method.arch_octet,
                bootloader=method.bootloader_path,
                path_prefix=method.path_prefix,
                ).strip() + ' '

    # The PXEBootMethod is used in an else statement for the generated
    # dhcpd config. This ensures that a booting node that does not
    # provide an architecture octet, or architectures that emulate
    # pxelinux can still boot.
    pxe_method = BootMethodRegistry.get_item('pxe')
    if pxe_method is not None:
        output += tempita.sub(
            PXE_BOOTLOADER,
            bootloader=pxe_method.bootloader_path,
            path_prefix=pxe_method.path_prefix,
            ).strip()
    return output.strip()


def get_config(template_name, **params):
    """Return a DHCP config file based on the supplied parameters.

    :param template_name: Template file name: `dhcpd.conf.template` for the
        IPv4 template, `dhcpd6.conf.template` for the IPv6 template.
    :param **params: Variables to be substituted into the template.
    :return: A full configuration, as unicode text.
    """
    template_file = locate_config(TEMPLATES_DIR, template_name)
    params['bootloader'] = compose_conditional_bootloader()
    params['platform_codename'] = linux_distribution()[2]
    params.setdefault("ntp_server")
    try:
        template = tempita.Template.from_filename(
            template_file, encoding="UTF-8")
        return template.substitute(**params)
    except (KeyError, NameError) as error:
        raise DHCPConfigError(*error.args)
