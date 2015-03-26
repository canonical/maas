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
    'configure_dhcp_now',
    ]

from collections import defaultdict
import threading

from django.conf import settings
from maasserver.enum import NODEGROUP_STATUS
from maasserver.exceptions import UnresolvableHost
from maasserver.models import Config
from maasserver.rpc import getClientFor
from maasserver.utils.orm import (
    post_commit,
    transactional,
)
from netaddr import IPAddress
from provisioningserver.rpc.cluster import (
    ConfigureDHCPv4,
    ConfigureDHCPv6,
)
from provisioningserver.utils.twisted import (
    callOut,
    callOutToThread,
    synchronous,
)


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
        'router_ip': (
            None if not interface.router_ip
            else unicode(interface.router_ip)),
        'dns_servers': dns_servers,
        'ntp_server': ntp_server,
        'domain_name': interface.nodegroup.name,
        'ip_range_low': interface.ip_range_low,
        'ip_range_high': interface.ip_range_high,
        }


@synchronous
def do_configure_dhcp(ip_version, nodegroup, interfaces, ntp_server):
    """Write DHCP configuration and restart the DHCP server.

    Delegates the work to the cluster controller, and waits for it
    to complete.

    :param ip_version: The IP version to configure for, either 4 or 6.

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

    if ip_version == 4:
        command = ConfigureDHCPv4
    elif ip_version == 6:
        command = ConfigureDHCPv6
    else:
        raise AssertionError(
            "Only IPv4 and IPv6 are supported, not IPv%s."
            % (ip_version,))

    try:
        dns_servers = get_dns_server_address(
            nodegroup, ipv4=(ip_version == 4), ipv6=(ip_version == 6))
    except UnresolvableHost:
        # No IPv6 DNS server addresses found.  As a space-separated string,
        # that becomes the empty string.
        dns_servers = ''

    omapi_key = nodegroup.dhcp_key
    subnets = [
        make_subnet_config(interface, dns_servers, ntp_server)
        for interface in interfaces
        ]
    client = getClientFor(nodegroup.uuid)
    # XXX jtv 2014-08-26 bug=1361673: If this fails remotely, the error
    # needs to be reported gracefully to the caller.
    client(command, omapi_key=omapi_key, subnet_configs=subnets).wait(60)


def configure_dhcpv4(nodegroup, interfaces, ntp_server):
    """Call `do_configure_dhcp` for IPv4.

    This serves mainly as a convenience for testing.
    """
    return do_configure_dhcp(4, nodegroup, interfaces, ntp_server)


def configure_dhcpv6(nodegroup, interfaces, ntp_server):
    """Call `do_configure_dhcp` for IPv6.

    This serves mainly as a convenience for testing.
    """
    return do_configure_dhcp(6, nodegroup, interfaces, ntp_server)


def configure_dhcp_now(nodegroup):
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


class Changes:
    """A record of pending DHCP changes, and the means to apply them."""

    # FIXME: This has elements in common with the Changes class in
    # maasserver.dns.config. Consider extracting the common parts into a
    # shared superclass.

    def __init__(self):
        super(Changes, self).__init__()
        self.reset()

    def reset(self):
        self.hook = None
        self.clusters = []

    def activate(self):
        """Arrange for a post-commit hook to be called.

        The hook will apply any pending changes and reset this object to a
        pristine state.

        Can be called multiple times; only one hook will be added.
        """
        if self.hook is None:
            self.hook = post_commit()
            self.hook.addCallback(callOutToThread, self.apply)
            self.hook.addBoth(callOut, self.reset)
        return self.hook

    @transactional
    def apply(self):
        """Apply all requested changes."""
        clusters = {cluster.id: cluster for cluster in self.clusters}
        for cluster in clusters.viewvalues():
            configure_dhcp_now(cluster)


class ChangeConsolidator(threading.local):
    """A singleton used to consolidate DHCP changes.

    Maintains a thread-local `Changes` instance into which changes are
    written. Requesting any change within a transaction automatically arranges
    a post-commit call to apply those changes, after consolidation.
    """

    # FIXME: This has elements in common with the ChangeConsolidator class in
    # maasserver.dns.config. Consider extracting the common parts into a
    # shared superclass.

    def __init__(self):
        super(ChangeConsolidator, self).__init__()
        self.changes = Changes()

    def configure(self, cluster):
        """Request that DHCP be configured for `cluster`.

        This does nothing if `settings.DHCP_CONNECT` is `False`.
        """
        if settings.DHCP_CONNECT:
            self.changes.clusters.append(cluster)
            return self.changes.activate()


# Singleton, for internal use only.
consolidator = ChangeConsolidator()

# The public API.
configure_dhcp = consolidator.configure
