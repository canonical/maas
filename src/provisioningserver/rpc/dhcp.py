# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to DHCP."""

__all__ = [
    "configure",
    "DHCPv4Server",
    "DHCPv6Server",
]

import os

from provisioningserver.dhcp import (
    DHCPv4Server,
    DHCPv6Server,
)
from provisioningserver.dhcp.config import get_config
from provisioningserver.drivers.service import ServiceRegistry
from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.exceptions import CannotConfigureDHCP
from provisioningserver.service_monitor import (
    service_monitor,
    ServiceActionError,
)
from provisioningserver.utils.fs import (
    sudo_delete_file,
    sudo_write_file,
)
from provisioningserver.utils.shell import ExternalProcessError
from provisioningserver.utils.twisted import synchronous


maaslog = get_maas_logger("dhcp")


@synchronous
def configure(server, failover_peers, subnet_configs):
    """Configure the DHCPv6/DHCPv4 server, and restart it as appropriate.

    :param server: A `DHCPServer` instance.
    :param failover_peers: List of dicts with failover parameters for each
        subnet where HA is enabled.
    :param subnet_configs: List of dicts with subnet parameters for each
        subnet for which the DHCP server should serve DHCP. If no subnets
        are defined, the DHCP server will be stopped.
    """
    stopping = len(subnet_configs) == 0

    if stopping:
        if os.path.exists(server.config_filename):
            sudo_delete_file(server.config_filename)

        service = ServiceRegistry.get_item(server.dhcp_service)
        service.off()
        try:
            service_monitor.ensure_service(server.dhcp_service)
        except ServiceActionError as e:
            # Error is already logged by the service monitor, nothing to
            # log for this exception.
            raise CannotConfigureDHCP(
                "%s server failed to stop: %s" % (
                    server.descriptive_name, e))
        except Exception as e:
            maaslog.error(
                "%s server failed to stop: %s",
                server.descriptive_name, e)
            raise CannotConfigureDHCP(
                "%s server failed to stop: %s" % (
                    server.descriptive_name, e))
    else:
        dhcpd_config = get_config(
            server.template_basename, omapi_key=server.omapi_key,
            failover_peers=failover_peers, dhcp_subnets=subnet_configs)
        interfaces = {subnet['interface'] for subnet in subnet_configs}
        interfaces_config = ' '.join(sorted(interfaces))
        try:
            sudo_write_file(
                server.config_filename, dhcpd_config.encode("utf-8"))
            sudo_write_file(
                server.interfaces_filename, interfaces_config.encode("utf-8"))
        except ExternalProcessError as e:
            # ExternalProcessError.__str__ contains a generic failure message
            # as well as the command and its error output. On the other hand,
            # ExternalProcessError.output_as_unicode contains just the error
            # output which is probably the best information on what went
            # wrong. Log the full error information, but keep the exception
            # message short and to the point.
            maaslog.error(
                "Could not rewrite %s server configuration (for network "
                "interfaces %s): %s", server.descriptive_name,
                interfaces_config, str(e))
            raise CannotConfigureDHCP(
                "Could not rewrite %s server configuration: %s" % (
                    server.descriptive_name, e.output_as_unicode))

        service = ServiceRegistry.get_item(server.dhcp_service)
        service.on()
        try:
            service_monitor.restart_service(server.dhcp_service)
        except ServiceActionError as e:
            # Error is already logged by the service monitor, nothing to
            # log for this exception.
            raise CannotConfigureDHCP(
                "%s server failed to restart: %s" % (
                    server.descriptive_name, e))
        except Exception as e:
            maaslog.error(
                "%s server failed to restart (for network interfaces "
                "%s): %s", server.descriptive_name, interfaces_config, e)
            raise CannotConfigureDHCP(
                "%s server failed to restart: %s" % (
                    server.descriptive_name, e))
