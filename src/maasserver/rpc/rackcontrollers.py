# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to rack controllers."""

__all__ = [
    "handle_upgrade",
    "register",
    "update_interfaces",
    "update_last_image_sync",
]

from typing import Optional

from django.db.models import Q
from maasserver import (
    locks,
    worker_user,
)
from maasserver.enum import NODE_TYPE
from maasserver.models import (
    Node,
    NodeGroupToRackController,
    RackController,
    StaticIPAddress,
)
from maasserver.models.node import typecast_node
from maasserver.models.timestampedmodel import now
from maasserver.utils import synchronised
from maasserver.utils.orm import (
    transactional,
    with_connection,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils import typed
from provisioningserver.utils.twisted import synchronous


maaslog = get_maas_logger('rpc.rackcontrollers')


@synchronous
@transactional
def handle_upgrade(rack_controller, nodegroup_uuid):
    """Handle upgrading from MAAS 1.9. Set the VLAN the rack controller
    should manage."""
    if (nodegroup_uuid is not None and
            len(nodegroup_uuid) > 0 and
            not nodegroup_uuid.isspace()):
        ng_to_racks = NodeGroupToRackController.objects.filter(
            uuid=nodegroup_uuid)
        vlans = [
            ng_to_rack.subnet.vlan
            for ng_to_rack in ng_to_racks
        ]
        # The VLAN object can only be related to a RackController
        for nic in rack_controller.interface_set.all():
            if nic.vlan in vlans:
                nic.vlan.primary_rack = rack_controller
                nic.vlan.dhcp_on = True
                nic.vlan.save()
                maaslog.info(
                    "DHCP setting from NodeGroup(%s) have been migrated "
                    "to %s." % (nodegroup_uuid, nic.vlan))
        for ng_to_rack in ng_to_racks:
            ng_to_rack.delete()


@synchronous
@with_connection
@synchronised(locks.rack_registration)
@transactional
def register(system_id=None, hostname='', interfaces=None, url=None):
    """Register a new rack controller if not already registered.

    Attempt to see if the rack controller was already registered as a node.
    This can be looked up either by system_id, hostname, or mac address. If
    found convert the existing node into a rack controller. If not found
    create a new rack controller. After the rack controller has been
    registered and successfully connected we will refresh all commissioning
    data.

    :return: A ``rack-controller``.
    """
    if interfaces is None:
        interfaces = {}

    node = find(system_id, hostname, interfaces)
    if node is None:
        node = RackController.objects.create(hostname=hostname)
        maaslog.info("Created new rack controller %s.", node.hostname)
    elif node.is_rack_controller:
        maaslog.info("Registering existing rack controller %s.", node.hostname)
    elif node.is_region_controller:
        maaslog.info(
            "Converting %s into a region and rack controller.", node.hostname)
        node.node_type = NODE_TYPE.REGION_AND_RACK_CONTROLLER
        node.save()
    else:
        maaslog.info("Converting %s into a rack controller.", node.hostname)
        node.node_type = NODE_TYPE.RACK_CONTROLLER
        node.save()

    rackcontroller = typecast_node(node, RackController)

    # Update `rackcontroller.url` from the given URL, but only when the
    # hostname is not 'localhost' (i.e. the default value used when the master
    # cluster connects).
    update_fields = []
    if url is not None and url.hostname != "localhost":
        if rackcontroller.url != url.geturl():
            rackcontroller.url = url.geturl()
            update_fields.append("url")
    if rackcontroller.owner is None:
        rackcontroller.owner = worker_user.get_worker_user()
        update_fields.append("owner")
    rackcontroller.save(update_fields=update_fields)
    # Update networking information every time we see a rack.
    rackcontroller.update_interfaces(interfaces)
    return rackcontroller


@typed
def find(system_id: Optional[str], hostname: str, interfaces: dict):
    """Find an existing node by `system_id`, `hostname`, and `interfaces`.

    :type system_id: str or None
    :type hostname: str
    :type interfaces: dict
    :return: An instance of :class:`Node` or `None`
    """
    mac_addresses = {
        interface["mac_address"] for interface in interfaces.values()
        if "mac_address" in interface
    }
    query = (
        Q(system_id=system_id) | Q(hostname=hostname) |
        Q(interface__mac_address__in=mac_addresses)
    )
    return Node.objects.filter(query).first()


@transactional
def update_foreign_dhcp(system_id, interface_name, dhcp_ip=None):
    """Update the external_dhcp field of the VLAN for the interface.

    :param system_id: Rack controller system_id.
    :param interface_name: The name of the interface.
    :param dhcp_ip: The IP address of the responding DHCP server.
    """
    rack_controller = RackController.objects.get(system_id=system_id)
    interface = rack_controller.interface_set.filter(
        name=interface_name).select_related("vlan").first()
    if interface is not None:
        if dhcp_ip is not None:
            sip = StaticIPAddress.objects.filter(ip=dhcp_ip).first()
            if sip is not None:
                # Check that its not an IP address of a rack controller
                # providing that DHCP service.
                rack_interfaces_serving_dhcp = sip.interface_set.filter(
                    node__node_type__in=[
                        NODE_TYPE.RACK_CONTROLLER,
                        NODE_TYPE.REGION_AND_RACK_CONTROLLER],
                    vlan__dhcp_on=True)
                if rack_interfaces_serving_dhcp.exists():
                    # Not external. It's a MAAS DHCP server.
                    dhcp_ip = None
        if interface.vlan.external_dhcp != dhcp_ip:
            interface.vlan.external_dhcp = dhcp_ip
            interface.vlan.save()


@synchronous
@transactional
def update_interfaces(system_id, interfaces):
    """Update the interface definition on the rack controller."""
    rack_controller = RackController.objects.get(system_id=system_id)
    rack_controller.update_interfaces(interfaces)


@synchronous
@transactional
def update_last_image_sync(system_id):
    """Update rack controller's last_image_sync.

    for :py:class:`~provisioningserver.rpc.region.UpdateLastImageSync.
    """
    RackController.objects.filter(
        system_id=system_id).update(last_image_sync=now())
