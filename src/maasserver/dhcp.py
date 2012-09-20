# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DHCP management module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'configure_dhcp',
    'is_dhcp_managed',
    ]

from django.conf import settings
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.models import NodeGroup
from maasserver.server_address import get_maas_facing_server_address
from netaddr import IPAddress
from provisioningserver.tasks import write_dhcp_config


def is_dhcp_disabled_until_task_routing_in_place(nodegroup):
    """Until proper task routing is in place, disable DHCP for non-master
    nodegroups.

    # XXX: rvb 2012-09-19 bug=1039366: Tasks are not routed yet.
    Until proper task routing is in place, the only DHCP config which can be
    written is the one for the master nodegroup.
    """
    if nodegroup == NodeGroup.objects.ensure_master():
        return False
    else:
        return True


def is_dhcp_managed(nodegroup):
    """Does MAAS manage the DHCP server for this Nodegroup?"""
    interface = nodegroup.get_managed_interface()
    return (
        settings.DHCP_CONNECT and
        nodegroup.status == NODEGROUP_STATUS.ACCEPTED and
        interface is not None and
        interface.management in (
            NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS))


def configure_dhcp(nodegroup):
    """Write the DHCP configuration file and restart the DHCP server."""
    # Circular imports.
    from maasserver.dns import get_dns_server_address

    if not is_dhcp_managed(nodegroup):
        return

    # XXX: rvb 2012-09-19 bug=1039366: Tasks are not routed yet.
    if is_dhcp_disabled_until_task_routing_in_place(nodegroup):
        return

    # Use the server's address (which is where the central TFTP
    # server is) for the next_server setting.  We'll want to proxy
    # it on the local worker later, and then we can use
    # next_server=self.worker_ip.
    next_server = get_maas_facing_server_address()

    interface = nodegroup.get_managed_interface()
    subnet = str(
        IPAddress(interface.ip_range_low) &
        IPAddress(interface.subnet_mask))
    write_dhcp_config.delay(
        subnet=subnet, next_server=next_server, omapi_key=nodegroup.dhcp_key,
        subnet_mask=interface.subnet_mask,
        broadcast_ip=interface.broadcast_ip,
        router_ip=interface.router_ip,
        dns_servers=get_dns_server_address(),
        ip_range_low=interface.ip_range_low,
        ip_range_high=interface.ip_range_high)
