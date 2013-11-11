# Copyright 2012 Canonical Ltd.  This software is licensed under the
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
    'is_dhcp_managed',
    ]

from django.conf import settings
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.models import Config
from netaddr import IPAddress
from provisioningserver.tasks import (
    restart_dhcp_server,
    write_dhcp_config,
    )


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

    # Make sure this nodegroup has a key to communicate with the dhcp
    # server.
    nodegroup.ensure_dhcp_key()

    interface = nodegroup.get_managed_interface()
    subnet = unicode(
        IPAddress(interface.ip_range_low) &
        IPAddress(interface.subnet_mask))
    reload_dhcp_server_subtask = restart_dhcp_server.subtask(
        options={'queue': nodegroup.work_queue})
    task_kwargs = dict(
        subnet=subnet,
        omapi_key=nodegroup.dhcp_key,
        subnet_mask=interface.subnet_mask,
        dhcp_interfaces=interface.interface,
        broadcast_ip=interface.broadcast_ip,
        router_ip=interface.router_ip,
        dns_servers=get_dns_server_address(nodegroup),
        ntp_server=Config.objects.get_config("ntp_server"),
        domain_name=nodegroup.name,
        ip_range_low=interface.ip_range_low,
        ip_range_high=interface.ip_range_high,
        callback=reload_dhcp_server_subtask,
    )
    write_dhcp_config.apply_async(
        queue=nodegroup.work_queue, kwargs=task_kwargs)
