# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The device handler for the WebSocket connection."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DeviceHandler",
    ]

from maasserver.clusterrpc import dhcp
from maasserver.enum import (
    IPADDRESS_TYPE,
    NODE_PERMISSION,
)
from maasserver.exceptions import NodeActionError
from maasserver.forms import (
    DeviceForm,
    DeviceWithMACsForm,
)
from maasserver.models.node import Device
from maasserver.models.nodegroup import NodeGroup
from maasserver.models.nodegroupinterface import NodeGroupInterface
from maasserver.node_action import compile_node_actions
from maasserver.utils.orm import commit_within_atomic_block
from maasserver.websockets.base import (
    HandlerDoesNotExistError,
    HandlerError,
)
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from provisioningserver.logger import get_maas_logger


maaslog = get_maas_logger("websockets.device")


class DEVICE_IP_ASSIGNMENT:
    """The vocabulary of a `Device`'s possible IP assignment type. This value
    is calculated by looking at the overall model for a `Device`. This is not
    set directly on the model."""
    #: Device is outside of MAAS control.
    EXTERNAL = "external"

    #: Device receives ip address from `NodeGroupInterface` dynamic range.
    DYNAMIC = "dynamic"

    #: Device has ip address assigned from `NodeGroupInterface` static range.
    STATIC = "static"


def update_host_maps(static_mappings, nodegroups):
    """Helper to call update_host_maps will static mappings for all
    `nodegroups`."""
    static_mappings = {
        nodegroup: dict(static_mappings)
        for nodegroup in nodegroups
        }
    return list(dhcp.update_host_maps(static_mappings))


def get_MACAddress_from_list(mac_addresses, mac):
    """Return the `MACAddress` object based on the mac value."""
    for mac_obj in mac_addresses:
        if mac_obj.mac_address == mac:
            return mac_obj
    return None


def delete_device_and_static_ip_addresses(
        device, external_static_ips, assigned_sticky_ips):
    """Delete the created external and sticky ips and the created device.

    This function calls `commit_within_atomic_block` to force the transaction
    to be saved.
    """
    for static_ip, _ in external_static_ips:
        static_ip.deallocate()
    for static_ip, _ in assigned_sticky_ips:
        static_ip.deallocate()
    device.delete()
    commit_within_atomic_block()


def log_static_allocations(device, external_static_ips, assigned_sticky_ips):
    """Log the allocation of the static ip address."""
    all_ips = [
        static_ip.ip
        for static_ip, _ in external_static_ips
        ]
    all_ips.extend([
        static_ip.ip
        for static_ip, _ in assigned_sticky_ips
        ])
    if len(all_ips) > 0:
        maaslog.info(
            "%s: Sticky IP address(es) allocated: %s",
            device.hostname, ', '.join(all_ips))


class DeviceHandler(TimestampedModelHandler):

    class Meta:
        queryset = (
            Device.devices.filter(installable=False)
            .select_related('nodegroup', 'owner')
            .prefetch_related('macaddress_set')
            .prefetch_related('macaddress_set__ip_addresses')
            .prefetch_related('macaddress_set__cluster_interface')
            .prefetch_related('nodegroup__nodegroupinterface_set')
            .prefetch_related('nodegroup__dhcplease_set')
            .prefetch_related('zone')
            .prefetch_related('tags'))
        pk = 'system_id'
        pk_type = unicode
        allowed_methods = ['list', 'get', 'set_active', 'create', 'action']
        exclude = [
            "id",
            "installable",
            "pxe_mac",
            "token",
            "netboot",
            "agent_name",
            "cpu_count",
            "memory",
            "power_state",
            "routers",
            "architecture",
            "boot_type",
            "status",
            "power_parameters",
            "power_state_updated",
            "disable_ipv4",
            "osystem",
            "power_type",
            "error_description",
            "error",
            "license_key",
            "distro_series",
            ]
        list_fields = [
            "system_id",
            "hostname",
            "owner",
            "zone",
            "parent",
            "pxe_mac",
            ]
        listen_channels = [
            "device",
            ]

    def get_queryset(self):
        """Return `QuerySet` for devices only vewable by `user`."""
        nodes = super(DeviceHandler, self).get_queryset()
        return Device.devices.get_nodes(
            self.user, NODE_PERMISSION.VIEW, from_nodes=nodes)

    def dehydrate_owner(self, user):
        """Return owners username."""
        if user is None:
            return ""
        else:
            return user.username

    def dehydrate_zone(self, zone):
        """Return zone name."""
        return {
            "id": zone.id,
            "name": zone.name,
            }

    def dehydrate_nodegroup(self, nodegroup):
        """Return the nodegroup name."""
        if nodegroup is None:
            return None
        else:
            return {
                "id": nodegroup.id,
                "uuid": nodegroup.uuid,
                "name": nodegroup.name,
                "cluster_name": nodegroup.cluster_name,
                }

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        data["fqdn"] = obj.fqdn
        data["actions"] = compile_node_actions(obj, self.user).keys()

        # Use the `get_pxe_mac` because for devices this will be the first
        # mac address assigned to this node, ordered by id, and using the
        # results cache. Not causing an extra query per device.
        primary_mac = obj.get_pxe_mac()
        data["primary_mac"] = (
            "%s" % primary_mac.mac_address
            if primary_mac is not None else "")
        data["extra_macs"] = [
            "%s" % mac_address.mac_address
            for mac_address in obj.macaddress_set.all()
            if mac_address != primary_mac
            ]

        data["ip_assignment"] = self.dehydrate_ip_assignment(obj, primary_mac)
        data["ip_address"] = self.dehydrate_ip_address(obj, primary_mac)

        data["tags"] = [
            tag.name
            for tag in obj.tags.all()
            ]
        return data

    def dehydrate_ip_assignment(self, obj, primary_mac):
        """Return the calculated `DEVICE_IP_ASSIGNMENT` based on the model."""
        if primary_mac is None:
            return ""
        # Calculate the length of the QuerySet instead of using `count` so
        # it doesn't perform another query to the database.
        num_ip_address = len(primary_mac.ip_addresses.all())
        if primary_mac.cluster_interface is None and num_ip_address > 0:
            return DEVICE_IP_ASSIGNMENT.EXTERNAL
        elif primary_mac.cluster_interface is not None and num_ip_address > 0:
            return DEVICE_IP_ASSIGNMENT.STATIC
        else:
            return DEVICE_IP_ASSIGNMENT.DYNAMIC

    def dehydrate_ip_address(self, obj, primary_mac):
        """Return the IP address for the device."""
        if primary_mac is None:
            return None

        # Get ip address from StaticIPAddress if available.
        static_ips = list(primary_mac.ip_addresses.all())
        if len(static_ips) > 0:
            return "%s" % static_ips[0].ip

        # Not in StaticIPAddress check in the leases for this devices
        # cluster.
        for lease in obj.nodegroup.dhcplease_set.all():
            if lease.mac == primary_mac.mac_address:
                return "%s" % lease.ip

        # Currently has no ip address.
        return None

    def get_object(self, params):
        """Get object by using the `pk` in `params`."""
        obj = super(DeviceHandler, self).get_object(params)
        if self.user.is_superuser or obj.owner == self.user:
            return obj
        raise HandlerDoesNotExistError(params[self._meta.pk])

    def get_form_class(self, action):
        """Return the form class used for `action`."""
        if action == "create":
            return DeviceWithMACsForm
        elif action == "update":
            return DeviceForm
        else:
            raise HandlerError("Unknown action: %s" % action)

    def get_mac_addresses(self, data):
        """Convert the given `data` into a list of mac addresses.

        This is used by the create method and the hydrate method.
        The `primary_mac` will always be the first entry in the list.
        """
        macs = data.get("extra_macs", [])
        if "primary_mac" in data:
            macs.insert(0, data["primary_mac"])
        return macs

    def preprocess_form(self, action, params):
        """Process the `params` to before passing the data to the form."""
        new_params = {
            "mac_addresses": self.get_mac_addresses(params),
            "hostname": params.get("hostname"),
            }

        # Cleanup any fields that have a None value.
        new_params = {
            key: value
            for key, value in new_params.viewitems()
            if value is not None
        }
        return super(DeviceHandler, self).preprocess_form(action, new_params)

    def create(self, params):
        """Create the object from params."""
        # XXX blake_r 03-04-15 bug=1440102: This is very ugly and a repeat
        # of code in other places. Needs to be refactored.

        # Create the object with the form and then create all of the interfaces
        # based on the users choices.
        data = super(DeviceHandler, self).create(params)
        device_obj = Device.objects.get(system_id=data['system_id'])
        mac_addresses = list(device_obj.macaddress_set.all())
        external_static_ips = []
        assigned_sticky_ips = []

        # Acquire all of the needed ip address based on the user selection.
        for nic in params["interfaces"]:
            mac_address = get_MACAddress_from_list(mac_addresses, nic["mac"])
            ip_assignment = nic["ip_assignment"]
            if ip_assignment == DEVICE_IP_ASSIGNMENT.EXTERNAL:
                sticky_ip = mac_address.set_static_ip(
                    nic["ip_address"], self.user, update_host_maps=False)
                external_static_ips.append(
                    (sticky_ip, mac_address))
            elif ip_assignment == DEVICE_IP_ASSIGNMENT.DYNAMIC:
                # Nothing needs to be done. It will get an ip address in the
                # dynamic range the first time it DHCP from a cluster
                # interface.
                pass
            elif ip_assignment == DEVICE_IP_ASSIGNMENT.STATIC:
                # Link the MAC address to the cluster interface.
                cluster_interface = NodeGroupInterface.objects.get(
                    id=nic["interface"])
                mac_address.cluster_interface = cluster_interface
                mac_address.save()

                # Convert an empty string to None.
                ip_address = nic.get("ip_address")
                if not ip_address:
                    ip_address = None

                # Claim the static ip.
                sticky_ips = mac_address.claim_static_ips(
                    alloc_type=IPADDRESS_TYPE.STICKY,
                    requested_address=ip_address, update_host_maps=False)
                assigned_sticky_ips.extend([
                    (static_ip, mac_address)
                    for static_ip in sticky_ips
                    ])

        # Commit all of the changes before telling the clusters to
        # update.
        commit_within_atomic_block()

        # Update the managed clusters with all the external static ip
        # addresses.
        if len(external_static_ips) > 0:
            dhcp_managed_clusters = [
                cluster
                for cluster in NodeGroup.objects.all()
                if cluster.manages_dhcp()
                ]
            claims = [
                (static_ip.ip, mac.mac_address.get_raw())
                for static_ip, mac in external_static_ips
                ]
            failures = update_host_maps(
                claims, dhcp_managed_clusters)
            if len(failures) > 0:
                # Delete the created device and ip addresses.
                delete_device_and_static_ip_addresses(
                    device_obj, external_static_ips, assigned_sticky_ips)

                # Now raise the first error to show a reason to the user.
                # It is possible to have multiple errors, but at the moment
                # we only raise the first error.
                raise HandlerError(failures[0].value)

        # Update the devices cluster with all the assigned sticky ip
        # addresses.
        if len(assigned_sticky_ips) > 0:
            claims = [
                (static_ip.ip, mac.mac_address.get_raw())
                for static_ip, mac in assigned_sticky_ips
                ]
            failures = update_host_maps(
                claims, [device_obj.nodegroup])
            if len(failures) > 0:
                # Delete the created device and ip addresses.
                delete_device_and_static_ip_addresses(
                    device_obj, external_static_ips, assigned_sticky_ips)

                # Now raise the first error to show a reason to the user.
                # It is possible to have multiple errors, but at the moment
                # we only raise the first error.
                raise HandlerError(failures[0].value)

        # Update the DNS zone for the master cluster as all device entries
        # go into that cluster.
        log_static_allocations(
            device_obj, external_static_ips, assigned_sticky_ips)
        if len(external_static_ips) > 0 or len(assigned_sticky_ips) > 0:
            from maasserver.dns import config as dns_config
            dns_config.dns_update_zones([NodeGroup.objects.ensure_master()])

        return self.full_dehydrate(device_obj)

    def action(self, params):
        """Perform the action on the object."""
        obj = self.get_object(params)
        action_name = params.get("action")
        actions = compile_node_actions(obj, self.user)
        action = actions.get(action_name)
        if action is None:
            raise NodeActionError(
                "%s action is not available for this device." % action_name)
        extra_params = params.get("extra", {})
        return action.execute(**extra_params)
