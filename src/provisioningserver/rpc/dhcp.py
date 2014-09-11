# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to DHCP."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "configure",
    "create_host_maps",
    "DHCPv4Server",
    "DHCPv6Server",
    "remove_host_maps",
]

from abc import (
    ABCMeta,
    abstractmethod,
    abstractproperty,
    )

from provisioningserver.dhcp import control
from provisioningserver.dhcp.config import get_config
from provisioningserver.dhcp.omshell import Omshell
from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.exceptions import (
    CannotConfigureDHCP,
    CannotCreateHostMap,
    CannotRemoveHostMap,
    )
from provisioningserver.utils.fs import sudo_write_file
from provisioningserver.utils.shell import ExternalProcessError


maaslog = get_maas_logger("dhcp")

# Location of the DHCPv4 configuration file.
DHCPv4_CONFIG_FILE = '/etc/maas/dhcpd.conf'

# Location of the DHCPv4 interfaces file.
DHCPv4_INTERFACES_FILE = '/var/lib/maas/dhcpd-interfaces'

# Location of the DHCPv6 configuration file.
DHCPv6_CONFIG_FILE = '/etc/maas/dhcpd6.conf'

# Location of the DHCPv6 interfaces file.
DHCPv6_INTERFACES_FILE = '/var/lib/maas/dhcpd6-interfaces'

# Message to put in the DHCP config file when the DHCP server gets stopped.
DISABLED_DHCP_SERVER = "# DHCP server stopped and disabled."


class DHCPServer:
    """Represents the settings and controls for a DHCP server.

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

    def __init__(self, omapi_key):
        super(DHCPServer, self).__init__()
        self.omapi_key = omapi_key

    @abstractmethod
    def stop(self):
        """Stop the DHCP server."""

    @abstractmethod
    def restart(self):
        """Restart the DHCP server."""


def configure(server, subnet_configs):
    """Configure the DHCPv6/DHCPv4 server, and restart it as appropriate.

    :param server: A `DHCPServer` instance.
    :param subnet_configs: List of dicts with subnet parameters for each
        subnet for which the DHCP server should serve DHCP. If no subnets
        are defined, the DHCP server will be stopped.
    """
    stopping = len(subnet_configs) == 0

    if stopping:
        dhcpd_config = DISABLED_DHCP_SERVER
    else:
        dhcpd_config = get_config(
            server.template_basename, omapi_key=server.omapi_key,
            dhcp_subnets=subnet_configs)

    interfaces = {subnet['interface'] for subnet in subnet_configs}
    interfaces_config = ' '.join(sorted(interfaces))

    try:
        sudo_write_file(server.config_filename, dhcpd_config)
        sudo_write_file(server.interfaces_filename, interfaces_config)
    except ExternalProcessError as e:
        # ExternalProcessError.__unicode__ contains a generic failure
        # message as well as the command and its error output. On the
        # other hand, ExternalProcessError.output_as_unicode contains just
        # the error output which is probably the best information on what
        # went wrong. Log the full error information, but keep the
        # exception message short and to the point.
        maaslog.error(
            "Could not rewrite %s server configuration (for network "
            "interfaces %s): %s", server.descriptive_name,
            interfaces_config, unicode(e))
        raise CannotConfigureDHCP(
            "Could not rewrite %s server configuration: %s" % (
                server.descriptive_name, e.output_as_unicode))

    if stopping:
        try:
            server.stop()
        except ExternalProcessError as e:
            maaslog.error(
                "%s server failed to stop: %s", server.descriptive_name,
                unicode(e))
            raise CannotConfigureDHCP(
                "%s server failed to stop: %s" % (
                    server.descriptive_name, e.output_as_unicode))
    else:
        try:
            server.restart()
        except ExternalProcessError as e:
            maaslog.error(
                "%s server failed to restart (for network interfaces "
                "%s): %s", server.descriptive_name, interfaces_config,
                unicode(e))
            raise CannotConfigureDHCP(
                "%s server failed to restart: %s" % (
                    server.descriptive_name, e.output_as_unicode))


class DHCPv4Server(DHCPServer):
    """Represents the settings and controls for a DHCPv4 server.

    See `DHCPServer`.
    """

    descriptive_name = "DHCPv4"
    template_basename = 'dhcpd.conf.template'
    interfaces_filename = DHCPv4_INTERFACES_FILE
    config_filename = DHCPv4_CONFIG_FILE

    def stop(self):
        """Stop the DHCPv4 server."""
        control.stop_dhcpv4()

    def restart(self):
        """Restart the DHCPv4 server."""
        control.restart_dhcpv4()


class DHCPv6Server(DHCPServer):
    """Represents the settings and controls for a DHCPv6 server.

    See `DHCPServer`.
    """

    descriptive_name = "DHCPv6"
    template_basename = 'dhcpd6.conf.template'
    interfaces_filename = DHCPv6_INTERFACES_FILE
    config_filename = DHCPv6_CONFIG_FILE

    def stop(self):
        """Stop the DHCPv6 server."""
        control.stop_dhcpv6()

    def restart(self):
        """Restart the DHCPv6 server."""
        control.restart_dhcpv6()


def create_host_maps(mappings, shared_key):
    """Create DHCP host maps for the given mappings.

    :param mappings: A list of dicts containing ``ip_address`` and
        ``mac_address`` keys.
    :param shared_key: The key used to access the DHCP server via OMAPI.
    """
    # See bug 1039362 regarding server_address.
    omshell = Omshell(server_address='127.0.0.1', shared_key=shared_key)
    for mapping in mappings:
        ip_address = mapping["ip_address"]
        mac_address = mapping["mac_address"]
        try:
            omshell.create(ip_address, mac_address)
        except ExternalProcessError as e:
            maaslog.error(
                "Could not create host map for %s with address %s: %s",
                mac_address, ip_address, unicode(e))
            raise CannotCreateHostMap("%s \u2192 %s: %s" % (
                mac_address, ip_address, e.output_as_unicode))


def remove_host_maps(ip_addresses, shared_key):
    """Remove DHCP host maps for the given IP addresses.

    :param ip_addresses: A list of IP addresses.
    :param shared_key: The key used to access the DHCP server via OMAPI.
    """
    # See bug 1039362 regarding server_address.
    omshell = Omshell(server_address='127.0.0.1', shared_key=shared_key)
    for ip_address in ip_addresses:
        try:
            omshell.remove(ip_address)
        except ExternalProcessError as e:
            maaslog.error(
                "Could not remove host map for %s: %s",
                ip_address, unicode(e))
            raise CannotRemoveHostMap("%s: %s" % (
                ip_address, e.output_as_unicode))
