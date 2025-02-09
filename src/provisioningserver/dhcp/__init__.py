# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Monitored service driver."""

from abc import ABCMeta, abstractproperty

from provisioningserver.path import get_maas_data_path

# Name of the DHCPv4 configuration file.
DHCPv4_CONFIG_FILE = "dhcpd.conf"

# Name of the DHCPv4 interfaces file.
DHCPv4_INTERFACES_FILE = "dhcpd-interfaces"

# NAme of the DHCPv6 configuration file.
DHCPv6_CONFIG_FILE = "dhcpd6.conf"

# Name of the DHCPv6 interfaces file.
DHCPv6_INTERFACES_FILE = "dhcpd6-interfaces"

# Message to put in the DHCP config file when the DHCP server gets stopped.
DISABLED_DHCP_SERVER = "# DHCP server stopped and disabled."


class DHCPServer(metaclass=ABCMeta):  # noqa: B024
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

    descriptive_name = abstractproperty()
    template_basename = abstractproperty()
    interfaces_filename = abstractproperty()
    config_filename = abstractproperty()
    dhcp_service = abstractproperty()
    ipv6 = abstractproperty()

    def __init__(self, omapi_key):
        super().__init__()
        self.omapi_key = omapi_key


class DHCPv4Server(DHCPServer):
    """Represents the settings for a DHCPv4 server.

    See `DHCPServer`.
    """

    descriptive_name = "DHCPv4"
    template_basename = "dhcpd.conf.template"
    interfaces_filename = get_maas_data_path(DHCPv4_INTERFACES_FILE)
    config_filename = get_maas_data_path(DHCPv4_CONFIG_FILE)
    dhcp_service = "dhcpd"
    ipv6 = False


class DHCPv6Server(DHCPServer):
    """Represents the settings for a DHCPv6 server.

    See `DHCPServer`.
    """

    descriptive_name = "DHCPv6"
    template_basename = "dhcpd6.conf.template"
    interfaces_filename = get_maas_data_path(DHCPv6_INTERFACES_FILE)
    config_filename = get_maas_data_path(DHCPv6_CONFIG_FILE)
    dhcp_service = "dhcpd6"
    ipv6 = True
