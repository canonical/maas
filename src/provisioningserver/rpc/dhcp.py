# Copyright 2014-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to DHCP."""

__all__ = [
    "configure",
    "DHCPv4Server",
    "DHCPv6Server",
]

from collections import namedtuple
from operator import itemgetter
import os
import re

from netaddr import AddrConversionError, IPAddress
from twisted.internet.defer import inlineCallbacks, maybeDeferred
from twisted.internet.threads import deferToThread

from provisioningserver.dhcp import DHCPv4Server, DHCPv6Server
from provisioningserver.dhcp.config import get_config
from provisioningserver.dhcp.omapi import OmapiClient, OmapiError
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.rpc.exceptions import (
    CannotConfigureDHCP,
    CannotCreateHostMap,
    CannotModifyHostMap,
    CannotRemoveHostMap,
)
from provisioningserver.service_monitor import service_monitor
from provisioningserver.utils.fs import sudo_delete_file, sudo_write_file
from provisioningserver.utils.service_monitor import (
    SERVICE_STATE,
    ServiceActionError,
)
from provisioningserver.utils.shell import ExternalProcessError
from provisioningserver.utils.twisted import asynchronous, synchronous

maaslog = get_maas_logger("dhcp")
log = LegacyLogger()


# Holds the current state of DHCPv4 and DHCPv6.
_current_server_state = {}


DHCPStateBase = namedtuple(
    "DHCPStateBase",
    [
        "omapi_key",
        "failover_peers",
        "shared_networks",
        "hosts",
        "interfaces",
        "global_dhcp_snippets",
    ],
)


class DHCPState(DHCPStateBase):
    """Holds the current known state of the DHCP server."""

    def __new__(
        cls,
        omapi_key,
        failover_peers,
        shared_networks,
        hosts,
        interfaces,
        global_dhcp_snippets,
    ):
        failover_peers = sorted(failover_peers, key=itemgetter("name"))
        shared_networks = sorted(shared_networks, key=itemgetter("name"))
        hosts = {host["mac"]: host for host in hosts}
        interfaces = sorted(interface["name"] for interface in interfaces)
        global_dhcp_snippets = sorted(
            global_dhcp_snippets, key=itemgetter("name")
        )
        return DHCPStateBase.__new__(
            cls,
            omapi_key=omapi_key,
            failover_peers=failover_peers,
            shared_networks=shared_networks,
            hosts=hosts,
            interfaces=interfaces,
            global_dhcp_snippets=global_dhcp_snippets,
        )

    def requires_restart(self, other_state, is_dhcpv6_server=False):
        """Return True when this state differs from `other_state` enough to
        require a restart."""

        def gather_hosts_dhcp_snippets(hosts):
            hosts_dhcp_snippets = list()
            for _, host in hosts.items():
                for dhcp_snippet in host["dhcp_snippets"]:
                    hosts_dhcp_snippets.append(dhcp_snippet)
            return sorted(hosts_dhcp_snippets, key=itemgetter("name"))

        def ipv6_hosts_require_restart(hosts):
            if is_dhcpv6_server:  # dhcpv4 can still manage ipv6 subnets
                return False

            for host in hosts.values():
                ip = host.get("ip")
                if ip is not None:
                    try:
                        IPAddress(ip).ipv4()
                    except AddrConversionError:
                        return True
            return False

        # Currently the OMAPI doesn't allow you to add or remove arbitrary
        # config options. So gather a list of DHCP snippets from
        hosts_dhcp_snippets = gather_hosts_dhcp_snippets(self.hosts)
        other_hosts_dhcp_snippets = gather_hosts_dhcp_snippets(
            other_state.hosts
        )

        return (
            self.omapi_key != other_state.omapi_key
            or self.failover_peers != other_state.failover_peers
            or self.shared_networks != other_state.shared_networks
            or self.interfaces != other_state.interfaces
            or self.global_dhcp_snippets != other_state.global_dhcp_snippets
            or hosts_dhcp_snippets != other_hosts_dhcp_snippets
            or ipv6_hosts_require_restart(self.hosts)
            or ipv6_hosts_require_restart(other_state.hosts)
        )

    def host_diff(self, other_state):
        """Return tuple with the hosts that need to be removed, need to be
        added, and need be updated."""
        remove, add, modify = [], [], []
        for mac, host in self.hosts.items():
            if mac not in other_state.hosts:
                add.append(host)
            elif host["ip"] != other_state.hosts[mac]["ip"]:
                modify.append(host)
        for mac, host in other_state.hosts.items():
            if mac not in self.hosts:
                remove.append(host)
        return remove, add, modify

    def get_config(self, server):
        """Return the configuration for `server`."""
        dhcpd_config = get_config(
            server.template_basename,
            omapi_key=self.omapi_key,
            failover_peers=self.failover_peers,
            ipv6=server.ipv6,
            shared_networks=self.shared_networks,
            hosts=sorted(self.hosts.values(), key=itemgetter("host")),
            global_dhcp_snippets=sorted(
                self.global_dhcp_snippets, key=itemgetter("name")
            ),
        )
        return dhcpd_config, " ".join(self.interfaces)


@synchronous
def _write_config(server, state):
    """Write the configuration file."""
    dhcpd_config, interfaces_config = state.get_config(server)
    try:
        sudo_write_file(
            server.config_filename, dhcpd_config.encode("utf-8"), mode=0o640
        )
        sudo_write_file(
            server.interfaces_filename,
            interfaces_config.encode("utf-8"),
            mode=0o640,
        )
    except ExternalProcessError as e:
        # ExternalProcessError.__str__ contains a generic failure message
        # as well as the command and its error output. On the other hand,
        # ExternalProcessError.output_as_unicode contains just the error
        # output which is probably the best information on what went wrong.
        # Log the full error information, but keep the exception message
        # short and to the point.
        maaslog.error(
            "Could not rewrite %s server configuration (for network "
            "interfaces %s): %s",
            server.descriptive_name,
            interfaces_config,
            str(e),
        )
        raise CannotConfigureDHCP(  # noqa: B904
            "Could not rewrite %s server configuration: %s"
            % (server.descriptive_name, e.output_as_unicode)
        )


@synchronous
def _delete_config(server):
    """Delete the server config."""
    if os.path.exists(server.config_filename):
        sudo_delete_file(server.config_filename)


@synchronous
def _update_hosts(server, remove, add, modify):
    """Update the hosts using the OMAPI."""
    omapi_client = OmapiClient(server.omapi_key, server.ipv6)
    try:
        for host in remove:
            omapi_client.del_host(host["mac"])
    except OmapiError as e:
        raise CannotRemoveHostMap(str(e))  # noqa: B904
    try:
        for host in add:
            omapi_client.add_host(host["mac"], host["ip"])
    except OmapiError as e:
        raise CannotCreateHostMap(str(e))  # noqa: B904
    try:
        for host in modify:
            omapi_client.update_host(host["mac"], host["ip"])
    except OmapiError as e:
        raise CannotModifyHostMap(str(e))  # noqa: B904


@asynchronous
def _catch_service_error(server, action, call, *args, **kwargs):
    """Helper to catch `ServiceActionError` and `Exception` when performing
    `call`."""

    def eb(failure):
        message = "{} server failed to {}: {}".format(
            server.descriptive_name,
            action,
            failure.value,
        )
        # A ServiceActionError will have already been logged by the
        # service monitor, so don't log a second time.
        if not failure.check(ServiceActionError):
            maaslog.error(message)
        # Squash everything into CannotConfigureDHCP.
        raise CannotConfigureDHCP(message) from failure.value

    return maybeDeferred(call, *args, **kwargs).addErrback(eb)


def _debug_hostmap_msg_remove(hosts):
    """Helper to create the debug log message for OMAPI remove."""

    def _inner():
        if hosts:
            return ", ".join(host["mac"] for host in hosts)
        else:
            return "none"

    # Uses and inner function so its only called if the rack controller is
    # configured in debug mode. In normal mode this will not be called and
    # no work will be performed.
    return _inner


def _debug_hostmap_msg(hosts):
    """Helper to create the debug log message for OMAPI add/modify."""

    def _inner():
        if hosts:
            return ", ".join(
                "{} -> {}".format(host["mac"], host["ip"]) for host in hosts
            )
        else:
            return "none"

    # Uses and inner function so its only called if the rack controller is
    # configured in debug mode. In normal mode this will not be called and
    # no work will be performed.
    return _inner


@asynchronous
@inlineCallbacks
def configure(
    server,
    failover_peers,
    shared_networks,
    hosts,
    interfaces,
    global_dhcp_snippets=None,
):
    """Configure the DHCPv6/DHCPv4 server, and restart it as appropriate.

    This method is not safe to call concurrently. The clusterserver ensures
    that this method is not called concurrently.

    :param server: A `DHCPServer` instance.
    :param failover_peers: List of dicts with failover parameters for each
        subnet where HA is enabled.
    :param shared_networks: List of dicts with shared network parameters that
        contain a list of subnets when the DHCP should server shared.
        If no shared network are defined, the DHCP server will be stopped.
    :param hosts: List of dicts with host parameters that
        contain a list of hosts the DHCP should statically.
    :param interfaces: List of interfaces that DHCP should use.
    :param global_dhcp_snippets: List of all global DHCP snippets
    """
    stopping = len(shared_networks) == 0

    if global_dhcp_snippets is None:
        global_dhcp_snippets = []

    if stopping:
        log.debug(
            "Deleting configuration and stopping the {name} service.",
            name=server.descriptive_name,
        )

        # Remove the config so that the even an administrator cannot turn it on
        # accidently when it should be off.
        yield deferToThread(_delete_config, server)

        # Ensure that the service is off and is staying off.
        service = service_monitor.getServiceByName(server.dhcp_service)
        service.off()
        yield _catch_service_error(
            server, "stop", service_monitor.ensureService, server.dhcp_service
        )
        _current_server_state[server.dhcp_service] = None
    else:
        # Get the new state for the DHCP server.
        new_state = DHCPState(
            server.omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )

        # Always write the config, that way its always up-to-date. Even if
        # we are not going to restart the services. This makes sure that even
        # the comments in the file are updated.
        log.debug(
            "Writing updated DHCP configuration for {name} service.",
            name=server.descriptive_name,
        )
        yield deferToThread(_write_config, server, new_state)

        # Service should always be on if shared_networks exists.
        service = service_monitor.getServiceByName(server.dhcp_service)
        service.on()

        # Perform the required action based on the state change.
        current_state = _current_server_state.get(server.dhcp_service, None)
        if current_state is None:
            log.debug(
                "Unknown previous state; restarting {name} service.",
                name=server.descriptive_name,
            )
            yield _catch_service_error(
                server,
                "restart",
                service_monitor.restartService,
                server.dhcp_service,
            )
        elif new_state.requires_restart(
            current_state, is_dhcpv6_server=server.ipv6
        ):
            log.debug(
                "Restarting {name} service; configuration change requires "
                "full restart.",
                name=server.descriptive_name,
            )
            yield _catch_service_error(
                server,
                "restart",
                service_monitor.restartService,
                server.dhcp_service,
            )
        else:
            # No restart required update the host mappings if needed.
            remove, add, modify = new_state.host_diff(current_state)
            if len(remove) + len(add) + len(modify) == 0:
                # Nothing has changed, do nothing but make sure its running.
                log.debug(
                    "Doing nothing; {name} service configuration has not "
                    "changed.",
                    name=server.descriptive_name,
                )
                yield _catch_service_error(
                    server,
                    "start",
                    service_monitor.ensureService,
                    server.dhcp_service,
                )
            else:
                log.debug(
                    "Ensuring {name} service is running before updating "
                    "using the OMAPI.",
                    name=server.descriptive_name,
                )
                # Check the state of the service. Only if the services was on
                # should the host maps be updated over the OMAPI.
                before_state = yield service_monitor.getServiceState(
                    server.dhcp_service, now=True
                )
                yield _catch_service_error(
                    server,
                    "start",
                    service_monitor.ensureService,
                    server.dhcp_service,
                )
                if before_state.active_state == SERVICE_STATE.ON:
                    # Was already running, so update host maps over OMAPI
                    # instead of performing a full restart.
                    log.debug(
                        "Writing to OMAPI for {name} service:\n"
                        "\tremove: {remove()}\n"
                        "\tadd: {add()}\n"
                        "\tmodify: {modify()}\n",
                        name=server.descriptive_name,
                        remove=_debug_hostmap_msg_remove(remove),
                        add=_debug_hostmap_msg(add),
                        modify=_debug_hostmap_msg(modify),
                    )
                    try:
                        yield deferToThread(
                            _update_hosts, server, remove, add, modify
                        )
                    except Exception:
                        # Error updating the host maps over the OMAPI.
                        # Restart the DHCP service so that the host maps
                        # are in-sync with what MAAS expects.
                        maaslog.warning(
                            "Failed to update all host maps. Restarting %s "
                            "service to ensure host maps are in-sync."
                            % (server.descriptive_name)
                        )
                        yield _catch_service_error(
                            server,
                            "restart",
                            service_monitor.restartService,
                            server.dhcp_service,
                        )
                else:
                    log.debug(
                        "Usage of OMAPI skipped; {name} service was started "
                        "with new configuration.",
                        name=server.descriptive_name,
                    )

        # Update the current state to the new state.
        _current_server_state[server.dhcp_service] = new_state


def _parse_dhcpd_errors(error_str):
    """Parse the output of dhcpd -t -cf <file> into a list of dictionaries

    dhcpd-4.3.3-5ubuntu11 -t -cf outputs each syntax error on three lines.
    First contains the filename, line number, and what the error is. Second
    outputs the line which has the syntax error and third is a pointer to the
    where on the previous line the error was detected."""
    processing_config = False
    errors = []
    error = {}
    error_regex = re.compile("line (?P<line_num>[0-9]+): (?P<error>.+)")
    for line in error_str.splitlines():
        m = error_regex.search(line)
        # Don't start processing till we get past header and end processing
        # once we get to the footer.
        if not processing_config and m is None:
            continue
        elif not processing_config and m is not None:
            processing_config = True
        elif line.startswith("Configuration file errors encountered"):
            break
        if m is not None:
            # New error, append previous error to the list of errors
            if error.get("error") is not None:
                errors.append(error)
                error = {}
            error["error"] = m.group("error")
            error["line_num"] = int(m.group("line_num"))
        elif m is None and line.strip() == "^":
            error["position"] = line
        else:
            error["line"] = line

    if error != {}:
        errors.append(error)

    return errors
