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
    "configure_dhcpv6",
    "create_host_maps",
    "remove_host_maps",
    "stop_and_disable_dhcpv4",
    "stop_and_disable_dhcpv6",
]

from provisioningserver.dhcp import control
from provisioningserver.dhcp.config import get_config
from provisioningserver.dhcp.omshell import Omshell
from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.exceptions import (
    CannotConfigureDHCP,
    CannotCreateHostMap,
    CannotRemoveHostMap,
    CannotStopDHCP,
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


def configure_dhcpv6(omapi_key, subnet_configs):
    """Configure the DHCPv6 server, and restart it as appropriate.

    :param omapi_key: OMAPI secret key.
    :param subnet_configs: List of dicts with subnet parameters for each
        subnet for which the DHCP server should serve DHCPv6.  If no subnets
        are defined, the DHCP server will be stopped.
    """

    interfaces = ' '.join(
        sorted({subnet['interface'] for subnet in subnet_configs}))
    dhcpd_config = get_config(
        'dhcpd6.conf.template',
        omapi_key=omapi_key, dhcp_subnets=subnet_configs)
    try:
        sudo_write_file(DHCPv6_CONFIG_FILE, dhcpd_config)
        sudo_write_file(DHCPv6_INTERFACES_FILE, interfaces)
    except ExternalProcessError as e:
        # ExternalProcessError.__unicode__ contains a generic failure message
        # as well as the command and its error output.  On the other hand,
        # ExternalProcessError.output_as_unicode contains just the error
        # output which is probably the best information on what went wrong.
        # Log the full error information, but keep the exception message short
        # and to the point.
        maaslog.error(
            "Could not rewrite DHCPv6 server configuration "
            "(for network interfaces %s): %s",
            ', '.join(interfaces), unicode(e))
        raise CannotConfigureDHCP(
            "Could not rewrite DHCPv6 server configuration: %s"
            % e.output_as_unicode)

    if len(subnet_configs) == 0:
        try:
            control.stop_dhcpv6()
        except ExternalProcessError as e:
            maaslog.error("DHCPv6 server failed to stop: %s", unicode(e))
            raise CannotConfigureDHCP(
                "DHCPv6 server failed to stop: %s" % e.output_as_unicode)
    else:
        try:
            control.restart_dhcpv6()
        except ExternalProcessError as e:
            maaslog.error(
                "DHCPv6 server failed to restart "
                "(for network interfaces %s): %s",
                ', '.join(interfaces), unicode(e))
            raise CannotConfigureDHCP(
                "DHCPv6 server failed to restart: %s" % e.output_as_unicode)


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


# Message to put in the DHCP config file when the DHCP server gets stopped.
DISABLED_DHCP_SERVER = "# DHCP server stopped and disabled."


def stop_and_disable_dhcp_server(config_file, stop_server):
    """Write a blank config file and stop the DHCP server.

    :param config_file: The configuration file to clear in order to disable
        the server.
    :param stop_server: The function to call to stop the server. It's expected
        that this will, at worst, raise `ExternalProcessError`.
    :raises: `CannotConfigureDHCP` if writing the configuration file fails.
    :raises: `CannotStopDHCP` if stopping the DHCP server fails.
    """
    # Empty out the configuration file, leaving a message behind as to why.
    # The empty config file avoids having outdated config lying around.
    try:
        sudo_write_file(config_file, DISABLED_DHCP_SERVER)
    except ExternalProcessError as error:
        raise CannotConfigureDHCP(unicode(error))
    # Stop the server using the given function.
    try:
        stop_server()
    except ExternalProcessError as error:
        raise CannotStopDHCP(unicode(error))


def stop_and_disable_dhcpv4():
    """Stop the DHCPv4 server, and disable it to prevent accidental restarts.

    See `stop_and_disable_dhcp_server`.
    """
    return stop_and_disable_dhcp_server(
        DHCPv4_CONFIG_FILE, control.stop_dhcpv4)


def stop_and_disable_dhcpv6():
    """Stop the DHCPv6 server, and disable it to prevent accidental starts.

    See `stop_and_disable_dhcp_server`.
    """
    return stop_and_disable_dhcp_server(
        DHCPv6_CONFIG_FILE, control.stop_dhcpv6)
