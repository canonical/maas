# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DHCP management module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'configure_dhcp',
    ]

from collections import defaultdict

from django.conf import settings
from maasserver.enum import NODEGROUP_STATUS
from maasserver.exceptions import UnresolvableHost
from maasserver.models import Config
from maasserver.rpc import getClientFor
from netaddr import IPAddress
from provisioningserver.rpc.cluster import ConfigureDHCPv6
from provisioningserver.tasks import (
    restart_dhcp_server,
    stop_dhcp_server,
    write_dhcp_config,
    )
from provisioningserver.utils.twisted import synchronous


def split_ipv4_ipv6_interfaces(interfaces):
    """Divide `interfaces` into IPv4 ones and IPv6 ones.

    :param interfaces: An iterable of cluster interfaces.
    :return: A tuple of two separate iterables: IPv4 cluster interfaces for
        `nodegroup`, and its IPv6 cluster interfaces.
    """
    split = defaultdict(list)
    for interface in interfaces:
        split[interface.network.version].append(interface)
    assert len(split.keys()) <= 2, (
        "Unexpected IP version(s): %s" % ', '.join(split.keys()))
    return split[4], split[6]


def make_subnet_config(interface, dns_servers, ntp_server):
    """Return DHCP subnet configuration dict for a cluster interface."""
    return {
        'subnet': unicode(
            IPAddress(interface.ip_range_low) &
            IPAddress(interface.subnet_mask)),
        'subnet_mask': interface.subnet_mask,
        'subnet_cidr': unicode(interface.network.cidr),
        'broadcast_ip': interface.broadcast_ip,
        'interface': interface.interface,
        'router_ip': unicode(interface.router_ip),
        'dns_servers': dns_servers,
        'ntp_server': ntp_server,
        'domain_name': interface.nodegroup.name,
        'ip_range_low': interface.ip_range_low,
        'ip_range_high': interface.ip_range_high,
        }


def configure_dhcpv4(nodegroup, interfaces, ntp_server):
    """Write DHCPv4 configuration and restart the DHCPv4 server."""
    # Circular imports.
    from maasserver.dns.zonegenerator import get_dns_server_address

    if len(interfaces) == 0:
        # No IPv4 interfaces are configured as being managed by this cluster.
        # Stop the DHCP server.
        #
        # A config generated for this setup would not be valid.  It results in
        # the DHCP server failing with the error: "Not configured to listen on
        # any interfaces!"
        stop_dhcp_server.apply_async(queue=nodegroup.work_queue)
        return

    try:
        dns_servers = get_dns_server_address(nodegroup, ipv4=True, ipv6=False)
    except UnresolvableHost:
        # No IPv4 DNS server addresses found.  As a space-separated string,
        # that becomes the empty string.
        dns_servers = ''

    dhcp_subnet_configs = [
        make_subnet_config(interface, dns_servers, ntp_server)
        for interface in interfaces
        ]

    reload_dhcp_server_subtask = restart_dhcp_server.subtask(
        options={'queue': nodegroup.work_queue})
    task_kwargs = dict(
        dhcp_subnets=dhcp_subnet_configs,
        omapi_key=nodegroup.dhcp_key,
        dhcp_interfaces=' '.join(
            [interface.interface for interface in interfaces]),
        callback=reload_dhcp_server_subtask,
    )
    write_dhcp_config.apply_async(
        queue=nodegroup.work_queue, kwargs=task_kwargs)


@synchronous
def configure_dhcpv6(nodegroup, interfaces, ntp_server):
    """Write DHCPv6 configuration and restart the DHCPv6 server.

    Delegates the work to the cluster controller, and waits for it
    to complete.

    :raise NoConnectionsAvailable: if the region controller could not get
        an RPC connection to the cluster controller.
    :raise CannotConfigureDHCP: if configuration could not be written, or
        restart of the DHCP server fails.
    """
    # XXX jtv 2014-08-26 bug=1361590: UI/API requests to update cluster
    # interfaces will block on this.  We may need an asynchronous error
    # backchannel.

    # Circular imports.
    from maasserver.dns.zonegenerator import get_dns_server_address

    try:
        dns_servers = get_dns_server_address(nodegroup, ipv4=False, ipv6=True)
    except UnresolvableHost:
        # No IPv6 DNS server addresses found.  As a space-separated string,
        # that becomes the empty string.
        dns_servers = ''

    subnets = [
        make_subnet_config(interface, dns_servers, ntp_server)
        for interface in interfaces
        ]
    client = getClientFor(nodegroup.uuid)
    # XXX jtv 2014-08-26 bug=1361673: If this fails remotely, the error
    # needs to be reported gracefully to the caller.
    call = client(
        ConfigureDHCPv6, omapi_key=nodegroup.dhcp_key, subnet_configs=subnets)
    # Keep the timeout short: the UI may be waiting for completion.
    call.wait(5)


def configure_dhcp(nodegroup):
    """Write the DHCP configuration files and restart the DHCP servers."""
    # Let's get this out of the way first up shall we?
    if not settings.DHCP_CONNECT:
        # For the uninitiated, DHCP_CONNECT is set, by default, to False
        # in all tests and True in non-tests.  This avoids unnecessary
        # calls to async tasks.
        return

    if nodegroup.status == NODEGROUP_STATUS.ACCEPTED:
        # Cluster is an accepted one.  Control DHCP for its managed interfaces.
        interfaces = nodegroup.get_managed_interfaces()
    else:
        # Cluster isn't accepted.  Effectively, it manages no interfaces.
        interfaces = []

    # Make sure this nodegroup has a key to communicate with the dhcp
    # server.
    nodegroup.ensure_dhcp_key()

    ntp_server = Config.objects.get_config("ntp_server")

    ipv4_interfaces, ipv6_interfaces = split_ipv4_ipv6_interfaces(interfaces)

    configure_dhcpv4(nodegroup, ipv4_interfaces, ntp_server)
    configure_dhcpv6(nodegroup, ipv6_interfaces, ntp_server)
