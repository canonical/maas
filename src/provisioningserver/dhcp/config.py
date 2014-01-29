# Copyright 2012-2013 Canonical Ltd.  This software is licensed under the
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


from platform import linux_distribution

from provisioningserver.pxe.tftppath import compose_bootloader_path
from provisioningserver.utils import locate_config
import tempita

# Location of DHCP templates, relative to the configuration directory.
TEMPLATES_DIR = "templates/dhcp"


class DHCPConfigError(Exception):
    """Exception raised for errors processing the DHCP config."""


def get_config(**params):
    """Return a DHCP config file based on the supplied parameters."""
    template_file = locate_config(TEMPLATES_DIR, 'dhcpd.conf.template')
    params['bootloader'] = compose_bootloader_path()
    params['platform_codename'] = linux_distribution()[2]
    params.setdefault("ntp_server")
    try:
        template = tempita.Template.from_filename(
            template_file, encoding="UTF-8")
        return template.substitute(**params)
    except (KeyError, NameError) as error:
        raise DHCPConfigError(*error.args)
