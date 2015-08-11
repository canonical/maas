# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Monitored service driver."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DHCPv4Server",
    "DHCPv6Server",
    ]

from abc import (
    ABCMeta,
    abstractproperty,
)

from provisioningserver.path import get_path

# Location of the DHCPv4 configuration file.
DHCPv4_CONFIG_FILE = '/var/lib/maas/dhcpd.conf'

# Location of the DHCPv4 interfaces file.
DHCPv4_INTERFACES_FILE = '/var/lib/maas/dhcpd-interfaces'

# Location of the DHCPv6 configuration file.
DHCPv6_CONFIG_FILE = '/var/lib/maas/dhcpd6.conf'

# Location of the DHCPv6 interfaces file.
DHCPv6_INTERFACES_FILE = '/var/lib/maas/dhcpd6-interfaces'

# Message to put in the DHCP config file when the DHCP server gets stopped.
DISABLED_DHCP_SERVER = "# DHCP server stopped and disabled."


class DHCPServer:
    """Represents the settings for a DHCP server.

    :cvar descriptive_name: A name to use for this server in human-readable
        texts.
    :cvar template_basename: The base filename for the template to use when
        generating configuration for this server.
    :cvar interfaces_filename: The full path and filename for the server's
        interfaces file.
    :cvar config_filename: The full path and filename for the server's
        configuration file.
    :ivar omapi_key: The OMAPI secret key for the server.
    """

    __metaclass__ = ABCMeta

    descriptive_name = abstractproperty()
    template_basename = abstractproperty()
    interfaces_filename = abstractproperty()
    config_filename = abstractproperty()
    dhcp_service = abstractproperty()

    def __init__(self, omapi_key):
        super(DHCPServer, self).__init__()
        self.omapi_key = omapi_key


class DHCPv4Server(DHCPServer):
    """Represents the settings for a DHCPv4 server.

    See `DHCPServer`.
    """

    descriptive_name = "DHCPv4"
    template_basename = 'dhcpd.conf.template'
    interfaces_filename = get_path(DHCPv4_INTERFACES_FILE)
    config_filename = get_path(DHCPv4_CONFIG_FILE)
    dhcp_service = "dhcp4"


class DHCPv6Server(DHCPServer):
    """Represents the settings for a DHCPv6 server.

    See `DHCPServer`.
    """

    descriptive_name = "DHCPv6"
    template_basename = 'dhcpd6.conf.template'
    interfaces_filename = get_path(DHCPv6_INTERFACES_FILE)
    config_filename = get_path(DHCPv6_CONFIG_FILE)
    dhcp_service = "dhcp6"
