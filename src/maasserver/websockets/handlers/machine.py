# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The machine handler for the WebSocket connection."""

__all__ = [
    "MachineHandler",
]

from operator import itemgetter

from django.core.exceptions import ValidationError
from maasserver.enum import (
    INTERFACE_LINK_TYPE,
    IPADDRESS_TYPE,
    NODE_PERMISSION,
    NODE_STATUS,
)
from maasserver.exceptions import NodeActionError
from maasserver.forms import (
    AddPartitionForm,
    AdminNodeWithMACAddressesForm,
    CreateBcacheForm,
    CreateCacheSetForm,
    CreateLogicalVolumeForm,
    CreateRaidForm,
    CreateVolumeGroupForm,
    FormatBlockDeviceForm,
    FormatPartitionForm,
    MountFilesystemForm,
    UpdatePhysicalBlockDeviceForm,
    UpdateVirtualBlockDeviceForm,
)
from maasserver.forms_interface import (
    BondInterfaceForm,
    InterfaceForm,
    PhysicalInterfaceForm,
    VLANInterfaceForm,
)
from maasserver.forms_interface_link import InterfaceLinkForm
from maasserver.models.blockdevice import BlockDevice
from maasserver.models.cacheset import CacheSet
from maasserver.models.filesystemgroup import VolumeGroup
from maasserver.models.interface import Interface
from maasserver.models.node import (
    Machine,
    Node,
)
from maasserver.models.partition import Partition
from maasserver.models.subnet import Subnet
from maasserver.models.tag import Tag
from maasserver.node_action import compile_node_actions
from maasserver.rpc import getClientFromIdentifiers
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maasserver.websockets.base import (
    HandlerError,
    HandlerPermissionError,
)
from maasserver.websockets.handlers.node import (
    node_prefetch,
    NodeHandler,
)
from provisioningserver.drivers.power import POWER_QUERY_TIMEOUT
from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.cluster import PowerQuery
from provisioningserver.rpc.exceptions import (
    NoConnectionsAvailable,
    PowerActionFail,
    UnknownPowerType,
)
from provisioningserver.utils.twisted import (
    asynchronous,
    deferWithTimeout,
)
from twisted.internet.defer import (
    CancelledError,
    inlineCallbacks,
    returnValue,
)


maaslog = get_maas_logger("websockets.machine")


class MachineHandler(NodeHandler):

    class Meta(NodeHandler.Meta):
        abstract = False
        queryset = node_prefetch(Machine.objects.all())
        allowed_methods = [
            'list',
            'get',
            'create',
            'update',
            'action',
            'set_active',
            'check_power',
            'create_physical',
            'create_vlan',
            'create_bond',
            'update_interface',
            'delete_interface',
            'link_subnet',
            'unlink_subnet',
            'update_filesystem',
            'update_disk_tags',
            'update_disk',
            'delete_disk',
            'delete_partition',
            'delete_volume_group',
            'delete_cache_set',
            'create_partition',
            'create_cache_set',
            'create_bcache',
            'create_raid',
            'create_volume_group',
            'create_logical_volume',
            'set_boot_disk',
        ]
        form = AdminNodeWithMACAddressesForm
        exclude = [
            "status_expires",
            "parent",
            "boot_interface",
            "boot_cluster_ip",
            "token",
            "netboot",
            "agent_name",
            "power_state_queried",
            "power_state_updated",
            "gateway_link_ipv4",
            "gateway_link_ipv6",
            "enable_ssh",
            "skip_networking",
            "skip_storage",
            "instance_power_parameters",
            "address_ttl",
            "url",
            "dns_process",
            "managing_process",
            "last_image_sync",
        ]
        list_fields = [
            "system_id",
            "hostname",
            "owner",
            "cpu_count",
            "memory",
            "power_state",
            "domain",
            "zone",
        ]
        listen_channels = [
            "machine",
        ]

    def get_queryset(self):
        """Return `QuerySet` for devices only viewable by `user`."""
        nodes = super(MachineHandler, self).get_queryset()
        return Machine.objects.get_nodes(
            self.user, NODE_PERMISSION.VIEW, from_nodes=nodes)

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        data = super(MachineHandler, self).dehydrate(
            obj, data, for_list=for_list)

        if not for_list:
            # Add info specific to a machine.
            data["show_os_info"] = self.dehydrate_show_os_info(obj)
            devices = [
                self.dehydrate_device(device)
                for device in obj.children.all()
            ]
            data["devices"] = sorted(
                devices, key=itemgetter("fqdn"))

        return data

    def dehydrate_show_os_info(self, obj):
        """Return True if OS information should show in the UI."""
        return (
            obj.status == NODE_STATUS.DEPLOYING or
            obj.status == NODE_STATUS.FAILED_DEPLOYMENT or
            obj.status == NODE_STATUS.DEPLOYED or
            obj.status == NODE_STATUS.RELEASING or
            obj.status == NODE_STATUS.FAILED_RELEASING or
            obj.status == NODE_STATUS.DISK_ERASING or
            obj.status == NODE_STATUS.FAILED_DISK_ERASING)

    def dehydrate_device(self, device):
        """Return the `Device` formatted for JSON encoding."""
        return {
            "fqdn": device.fqdn,
            "interfaces": [
                self.dehydrate_interface(interface, device)
                for interface in device.interface_set.all().order_by('id')
            ],
        }

    def get_form_class(self, action):
        """Return the form class used for `action`."""
        if action in ("create", "update"):
            return AdminNodeWithMACAddressesForm
        else:
            raise HandlerError("Unknown action: %s" % action)

    def preprocess_form(self, action, params):
        """Process the `params` to before passing the data to the form."""
        new_params = {}

        # Only copy the allowed fields into `new_params` to be passed into
        # the form.
        new_params["mac_addresses"] = self.get_mac_addresses(params)
        new_params["hostname"] = params.get("hostname")
        new_params["architecture"] = params.get("architecture")
        new_params["power_type"] = params.get("power_type")
        if "zone" in params:
            new_params["zone"] = params["zone"]["name"]
        if "domain" in params:
            new_params["domain"] = params["domain"]["name"]
        if "min_hwe_kernel" in params:
            new_params["min_hwe_kernel"] = params["min_hwe_kernel"]

        # Cleanup any fields that have a None value.
        new_params = {
            key: value
            for key, value in new_params.items()
            if value is not None
        }

        return super(NodeHandler, self).preprocess_form(action, new_params)

    def create(self, params):
        """Create the object from params."""
        # Only admin users can perform create.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        # Create the object, then save the power parameters because the
        # form will not save this information.
        data = super(NodeHandler, self).create(params)
        node_obj = Node.objects.get(system_id=data['system_id'])
        node_obj.power_type = params.get("power_type", '')
        node_obj.power_parameters = params.get("power_parameters", {})
        node_obj.save()

        # Start the commissioning process right away, which has the
        # desired side effect of initializing the node's power state.
        node_obj.start_commissioning(self.user)

        return self.full_dehydrate(node_obj)

    def update(self, params):
        """Update the object from params."""
        # Only admin users can perform update.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        # Update the node with the form. The form will not update the
        # power_type or power_parameters, so we perform that here.
        data = super(NodeHandler, self).update(params)
        node_obj = Node.objects.get(system_id=data['system_id'])
        node_obj.power_type = params.get("power_type", '')
        node_obj.power_parameters = params.get("power_parameters", {})

        # Update the tags for the node and disks.
        self.update_tags(node_obj, params['tags'])
        node_obj.save()
        return self.full_dehydrate(node_obj)

    def update_filesystem(self, params):
        node = self.get_object(params)
        block_id = params.get('block_id')
        partition_id = params.get('partition_id')
        fstype = params.get('fstype')
        mount_point = params.get('mount_point')

        if node.status not in [NODE_STATUS.ALLOCATED, NODE_STATUS.READY]:
            raise HandlerError(
                "Node must be allocated or ready to edit storage")
        if not self.user.is_superuser and node.owner_id != self.user.id:
            raise HandlerPermissionError()

        if partition_id:
            self.update_partition_filesystem(
                node, block_id, partition_id, fstype, mount_point)
        else:
            self.update_blockdevice_filesystem(
                node, block_id, fstype, mount_point)

    def update_partition_filesystem(
            self, node, block_id, partition_id, fstype, mount_point):
        partition = Partition.objects.get(
            id=partition_id,
            partition_table__block_device__node=node)
        fs = partition.get_effective_filesystem()
        if not fstype:
            if fs:
                fs.delete()
                return
        if fs is None or fstype != fs.fstype:
            form = FormatPartitionForm(partition, {'fstype': fstype})
            if not form.is_valid():
                raise HandlerError(form.errors)
            form.save()
            fs = partition.get_effective_filesystem()
        if mount_point != fs.mount_point:
            # XXX: Elsewhere, a mount_point of "" would somtimes mean that the
            # filesystem is mounted, sometimes that it is *not* mounted. Which
            # is correct was not clear from the code history, so the existing
            # behaviour is maintained here.
            if mount_point is None or mount_point == "":
                fs.mount_point = None
                fs.save()
            else:
                form = MountFilesystemForm(
                    partition.get_effective_filesystem(),
                    {'mount_point': mount_point})
                if not form.is_valid():
                    raise HandlerError(form.errors)
                else:
                    form.save()

    def update_blockdevice_filesystem(
            self, node, block_id, fstype, mount_point):
        blockdevice = BlockDevice.objects.get(id=block_id, node=node)
        fs = blockdevice.get_effective_filesystem()
        if not fstype:
            if fs:
                fs.delete()
                return
        if fs is None or fstype != fs.fstype:
            form = FormatBlockDeviceForm(blockdevice, {'fstype': fstype})
            if not form.is_valid():
                raise HandlerError(form.errors)
            form.save()
            fs = blockdevice.get_effective_filesystem()
        if mount_point != fs.mount_point:
            # XXX: Elsewhere, a mount_point of "" would somtimes mean that the
            # filesystem is mounted, sometimes that it is *not* mounted. Which
            # is correct was not clear from the code history, so the existing
            # behaviour is maintained here.
            if mount_point is None or mount_point == "":
                fs.mount_point = None
                fs.save()
            else:
                form = MountFilesystemForm(
                    blockdevice.get_effective_filesystem(),
                    {'mount_point': mount_point})
                if not form.is_valid():
                    raise HandlerError(form.errors)
                else:
                    form.save()

    def update_tags(self, node_obj, tags):
        # Loop through the nodes current tags. If the tag exists in `tags` then
        # nothing needs to be done so its removed from `tags`. If it does not
        # exists then the tag was removed from the node and should be removed
        # from the nodes set of tags.
        for tag in node_obj.tags.all():
            if tag.name not in tags:
                node_obj.tags.remove(tag)
            else:
                tags.remove(tag.name)

        # All the tags remaining in `tags` are tags that are not linked to
        # node. Get or create that tag and add the node to the tags set.
        for tag_name in tags:
            tag_obj, _ = Tag.objects.get_or_create(name=tag_name)
            if tag_obj.is_defined:
                raise HandlerError(
                    "Cannot add tag %s to node because it has a "
                    "definition." % tag_name)
            tag_obj.node_set.add(node_obj)
            tag_obj.save()

    def update_disk_tags(self, params):
        """Update all the tags on all disks."""
        node = self.get_object(params)
        disk_obj = BlockDevice.objects.get(id=params['block_id'], node=node)
        disk_obj.tags = params['tags']
        disk_obj.save(update_fields=['tags'])

    def update_disk(self, params):
        """Update disk information."""
        # Only admin users can perform delete.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        node = self.get_object(params)
        device = BlockDevice.objects.get(
            id=params['block_id'], node=node).actual_instance
        if device.type == 'physical':
            form = UpdatePhysicalBlockDeviceForm(
                instance=device, data=params)
        elif device.type == 'virtual':
            form = UpdateVirtualBlockDeviceForm(
                instance=device, data=params)
        else:
            raise HandlerError(
                'Cannot update block device of type %s' % device.type)
        if not form.is_valid():
            raise HandlerError(form.errors)
        else:
            form.save()

    def delete_disk(self, params):
        # Only admin users can perform delete.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        node = self.get_object(params)
        block_id = params.get('block_id')
        if block_id is not None:
            block_device = BlockDevice.objects.get(id=block_id, node=node)
            block_device.delete()

    def delete_partition(self, params):
        # Only admin users can perform delete.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        node = self.get_object(params)
        partition_id = params.get('partition_id')
        if partition_id is not None:
            partition = Partition.objects.get(
                id=partition_id, partition_table__block_device__node=node)
            partition.delete()

    def delete_volume_group(self, params):
        # Only admin users can perform delete.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        node = self.get_object(params)
        volume_group_id = params.get('volume_group_id')
        if volume_group_id is not None:
            volume_group = VolumeGroup.objects.get(id=volume_group_id)
            if volume_group.get_node() != node:
                raise VolumeGroup.DoesNotExist()
            volume_group.delete()

    def delete_cache_set(self, params):
        # Only admin users can perform delete.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        node = self.get_object(params)
        cache_set_id = params.get('cache_set_id')
        if cache_set_id is not None:
            cache_set = CacheSet.objects.get(id=cache_set_id)
            if cache_set.get_node() != node:
                raise CacheSet.DoesNotExist()
            cache_set.delete()

    def create_partition(self, params):
        """Create a partition."""
        # Only admin users can perform delete.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        node = self.get_object(params)
        disk_obj = BlockDevice.objects.get(id=params['block_id'], node=node)
        form = AddPartitionForm(
            disk_obj, {
                'size': params['partition_size'],
            })
        if not form.is_valid():
            raise HandlerError(form.errors)
        else:
            partition = form.save()

        if 'fstype' in params:
            self.update_partition_filesystem(
                node, disk_obj.id, partition.id,
                params.get("fstype"), params.get("mount_point"))

    def create_cache_set(self, params):
        """Create a cache set."""
        # Only admin users can perform delete.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        node = self.get_object(params)
        block_id = params.get('block_id')
        partition_id = params.get('partition_id')

        data = {}
        if partition_id is not None:
            data["cache_partition"] = partition_id
        elif block_id is not None:
            data["cache_device"] = block_id
        else:
            raise HandlerError(
                "Either block_id or partition_id is required.")

        form = CreateCacheSetForm(node=node, data=data)
        if not form.is_valid():
            raise HandlerError(form.errors)
        else:
            form.save()

    def create_bcache(self, params):
        """Create a bcache."""
        # Only admin users can perform delete.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        node = self.get_object(params)
        block_id = params.get('block_id')
        partition_id = params.get('partition_id')

        data = {
            "name": params["name"],
            "cache_set": params["cache_set"],
            "cache_mode": params["cache_mode"],
        }

        if partition_id is not None:
            data["backing_partition"] = partition_id
        elif block_id is not None:
            data["backing_device"] = block_id
        else:
            raise HandlerError(
                "Either block_id or partition_id is required.")

        form = CreateBcacheForm(node=node, data=data)
        if not form.is_valid():
            raise HandlerError(form.errors)
        else:
            bcache = form.save()

        if 'fstype' in params:
            self.update_blockdevice_filesystem(
                node, bcache.virtual_device.id,
                params.get("fstype"), params.get("mount_point"))

    def create_raid(self, params):
        """Create a RAID."""
        # Only admin users can perform delete.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        node = self.get_object(params)
        form = CreateRaidForm(node=node, data=params)
        if not form.is_valid():
            raise HandlerError(form.errors)
        else:
            raid = form.save()

        if 'fstype' in params:
            self.update_blockdevice_filesystem(
                node, raid.virtual_device.id,
                params.get("fstype"), params.get("mount_point"))

    def create_volume_group(self, params):
        """Create a volume group."""
        # Only admin users can perform delete.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        node = self.get_object(params)
        form = CreateVolumeGroupForm(node=node, data=params)
        if not form.is_valid():
            raise HandlerError(form.errors)
        else:
            form.save()

    def create_logical_volume(self, params):
        """Create a logical volume."""
        # Only admin users can perform delete.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        node = self.get_object(params)
        volume_group = VolumeGroup.objects.get(id=params['volume_group_id'])
        if volume_group.get_node() != node:
            raise VolumeGroup.DoesNotExist()
        form = CreateLogicalVolumeForm(
            volume_group, {
                'name': params['name'],
                'size': params['size'],
            })
        if not form.is_valid():
            raise HandlerError(form.errors)
        else:
            logical_volume = form.save()

        if 'fstype' in params:
            self.update_blockdevice_filesystem(
                node, logical_volume.id,
                params.get("fstype"), params.get("mount_point"))

    def set_boot_disk(self, params):
        """Set the disk as the boot disk."""
        # Only admin users can perform delete.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        node = self.get_object(params)
        device = BlockDevice.objects.get(
            id=params['block_id'], node=node).actual_instance
        if device.type != 'physical':
            raise HandlerError(
                "Only a physical disk can be set as the boot disk.")
        node.boot_disk = device
        node.save()

    def action(self, params):
        """Perform the action on the object."""
        obj = self.get_object(params)
        action_name = params.get("action")
        actions = compile_node_actions(obj, self.user)
        action = actions.get(action_name)
        if action is None:
            raise NodeActionError(
                "%s action is not available for this node." % action_name)
        extra_params = params.get("extra", {})
        return action.execute(**extra_params)

    def _create_link_on_interface(self, interface, params):
        """Create a link on a new interface."""
        mode = params.get("mode", None)
        subnet_id = params.get("subnet", None)
        if mode is not None:
            if mode != INTERFACE_LINK_TYPE.LINK_UP:
                link_form = InterfaceLinkForm(instance=interface, data=params)
                if link_form.is_valid():
                    link_form.save()
                else:
                    raise ValidationError(link_form.errors)
            elif subnet_id is not None:
                link_ip = interface.ip_addresses.get(
                    alloc_type=IPADDRESS_TYPE.STICKY, ip__isnull=True)
                link_ip.subnet = Subnet.objects.get(id=subnet_id)
                link_ip.save()

    def create_physical(self, params):
        """Create physical interface."""
        # Only admin users can perform create.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        node = self.get_object(params)
        form = PhysicalInterfaceForm(node=node, data=params)
        if form.is_valid():
            interface = form.save()
            self._create_link_on_interface(interface, params)
        else:
            raise ValidationError(form.errors)

    def create_vlan(self, params):
        """Create VLAN interface."""
        # Only admin users can perform create.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        node = self.get_object(params)
        params['parents'] = [params.pop('parent')]
        form = VLANInterfaceForm(node=node, data=params)
        if form.is_valid():
            interface = form.save()
            self._create_link_on_interface(interface, params)
        else:
            raise ValidationError(form.errors)

    def create_bond(self, params):
        """Create bond interface."""
        # Only admin users can perform create.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        node = self.get_object(params)
        form = BondInterfaceForm(node=node, data=params)
        if form.is_valid():
            interface = form.save()
            self._create_link_on_interface(interface, params)
        else:
            raise ValidationError(form.errors)

    def update_interface(self, params):
        """Update the interface."""
        # Only admin users can perform update.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        node = self.get_object(params)
        interface = Interface.objects.get(node=node, id=params["interface_id"])
        interface_form = InterfaceForm.get_interface_form(interface.type)
        form = interface_form(instance=interface, data=params)
        if form.is_valid():
            form.save()
        else:
            raise ValidationError(form.errors)

    def delete_interface(self, params):
        """Delete the interface."""
        # Only admin users can perform delete.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        node = self.get_object(params)
        interface = Interface.objects.get(node=node, id=params["interface_id"])
        interface.delete()

    def link_subnet(self, params):
        """Create or update the link."""
        # Only admin users can perform update.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        node = self.get_object(params)
        interface = Interface.objects.get(node=node, id=params["interface_id"])
        subnet = None
        if "subnet" in params:
            subnet = Subnet.objects.get(id=params["subnet"])
        if "link_id" in params:
            # We are updating an already existing link.
            interface.update_link_by_id(
                params["link_id"], params["mode"], subnet,
                ip_address=params.get("ip_address", None))
        else:
            # We are creating a new link.
            interface.link_subnet(
                params["mode"], subnet,
                ip_address=params.get("ip_address", None))

    def unlink_subnet(self, params):
        """Delete the link."""
        # Only admin users can perform unlink.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        node = self.get_object(params)
        interface = Interface.objects.get(node=node, id=params["interface_id"])
        interface.unlink_subnet_by_id(params["link_id"])

    @asynchronous
    @inlineCallbacks
    def check_power(self, params):
        """Check the power state of the node."""

        # XXX: This is largely the same function as
        # update_power_state_of_node.

        @transactional
        def get_node_rack_and_power_info():
            obj = self.get_object(params)
            if obj.power_type is not None:
                node_info = obj.system_id, obj.hostname
                conn_info = obj._get_bmc_client_connection_info()
                try:
                    power_info = obj.get_effective_power_info()
                except UnknownPowerType:
                    return node_info, conn_info, None
                else:
                    return node_info, conn_info, power_info
            else:
                raise HandlerError(
                    "%s: Unable to query power state; no power state defined"
                    % obj.hostname)

        @transactional
        def update_power_state(state):
            obj = self.get_object(params)
            obj.update_power_state(state)

        # Grab info about the node, its connections to its BMC, and its power
        # parameters from the database. If it can't be queried we can return
        # early, but first update the node's power state with what we know we
        # don't know.
        node_info, conn_info, power_info = (
            yield deferToDatabase(get_node_rack_and_power_info))
        if power_info is None or not power_info.can_be_queried:
            yield deferToDatabase(update_power_state, "unknown")
            returnValue("unknown")

        # Get a client to any of the rack controllers that has access to
        # that BMC.
        node_id, node_hostname = node_info
        client_idents, fallback_idents = conn_info
        try:
            client = yield getClientFromIdentifiers(client_idents)
        except NoConnectionsAvailable:
            try:
                client = yield getClientFromIdentifiers(fallback_idents)
            except NoConnectionsAvailable:
                maaslog.error(
                    "Unable to get any RPC connection to the BMC for '%s'.",
                    node_hostname)
                raise HandlerError(
                    "Unable to connect to any rack controller that has access "
                    "to this node's BMC.") from None

        # Query the power state via the node's cluster.
        try:
            response = yield deferWithTimeout(
                POWER_QUERY_TIMEOUT, client, PowerQuery, system_id=node_id,
                hostname=node_hostname, power_type=power_info.power_type,
                context=power_info.power_parameters)
        except CancelledError:
            # We got fed up waiting. The query may later discover the node's
            # power state but by then we won't be paying attention.
            maaslog.error("%s: Timed-out querying power.", node_hostname)
            state = "error"
        except PowerActionFail:
            # We discard the reason. That will have bee`n logged elsewhere.
            # Here we're signalling something very simple back to the user.
            state = "error"
        except NotImplementedError:
            # The power driver has declared that it doesn't after all know how
            # to query the power for this node, so "unknown" seems appropriate.
            state = "unknown"
        else:
            state = response["state"]

        yield deferToDatabase(update_power_state, state)
        returnValue(state)
