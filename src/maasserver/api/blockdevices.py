# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `BlockDevice`."""

from django.core.exceptions import PermissionDenied
from piston3.utils import rc

from maasserver.api.support import admin_method, operation, OperationsHandler
from maasserver.api.utils import get_mandatory_param
from maasserver.enum import NODE_STATUS
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPIValidationError,
    NodeStateViolation,
)
from maasserver.forms import (
    CreatePhysicalBlockDeviceForm,
    FormatBlockDeviceForm,
    UpdateDeployedPhysicalBlockDeviceForm,
    UpdatePhysicalBlockDeviceForm,
    UpdateVirtualBlockDeviceForm,
)
from maasserver.forms.filesystem import MountFilesystemForm
from maasserver.models import (
    BlockDevice,
    Machine,
    PhysicalBlockDevice,
    VirtualBlockDevice,
)
from maasserver.permissions import NodePermission

DISPLAYED_BLOCKDEVICE_FIELDS = (
    "system_id",
    "id",
    "name",
    "uuid",
    "type",
    "path",
    "model",
    "serial",
    "id_path",
    "size",
    "block_size",
    "available_size",
    "used_size",
    "used_for",
    "tags",
    "filesystem",
    "partition_table_type",
    "partitions",
    "firmware_version",
    "storage_pool",
    "numa_node",
)


def raise_error_for_invalid_state_on_allocated_operations(
    node, user, operation
):
    if node.status not in [NODE_STATUS.READY, NODE_STATUS.ALLOCATED]:
        raise NodeStateViolation(
            "Cannot %s block device because the machine is not Ready "
            "or Allocated." % operation
        )
    if node.status == NODE_STATUS.READY and not user.is_superuser:
        raise PermissionDenied(
            "Cannot %s block device because you don't have the "
            "permissions on a Ready machine." % operation
        )


class BlockDevicesHandler(OperationsHandler):
    """Manage block devices on a machine."""

    api_doc_section_name = "Block devices"
    replace = update = delete = None
    fields = DISPLAYED_BLOCKDEVICE_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("blockdevices_handler", ["system_id"])

    def read(self, request, system_id):
        """@description-title List block devices
        @description List all block devices belonging to a machine.

        @param (string) "{system_id}" [required=true] The machine system_id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of block
        devices.
        @success-example "success-json" [exkey=block-devs-read] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            Not Found
        """
        machine = Machine.objects.get_node_or_404(
            system_id, request.user, NodePermission.view
        )
        return machine.current_config.blockdevice_set.all()

    @admin_method
    def create(self, request, system_id):
        """@description-title Create a block device
        @description Create a physical block device.

        @param (string) "{system_id}" [required=true] The machine system_id.

        @param (string) "name" [required=true] Name of the block device.

        @param (string) "model" [required=false] Model of the block device.

        @param (string) "serial" [required=false] Serial number of the block
        device.

        @param (string) "id_path" [required=false] Only used if model and
        serial cannot be provided. This should be a path that is fixed and
        doesn't change depending on the boot order or kernel version.

        @param (string) "size" [required=true] Size of the block device.

        @param (string) "block_size" [required=true] Block size of the block
        device.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new block
        device.
        @success-example "success-json" [exkey=block-devs-create] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            Not Found
        """
        machine = Machine.objects.get_node_or_404(
            system_id, request.user, NodePermission.admin
        )
        form = CreatePhysicalBlockDeviceForm(machine, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)


class BlockDeviceHandler(OperationsHandler):
    """Manage a block device on a machine."""

    api_doc_section_name = "Block device"
    create = replace = None
    model = BlockDevice
    fields = DISPLAYED_BLOCKDEVICE_FIELDS

    @classmethod
    def resource_uri(cls, block_device=None):
        # See the comment in NodeHandler.resource_uri.
        if block_device is None:
            system_id = "system_id"
            device_id = "id"
        else:
            device_id = block_device.id
            system_id = cls.system_id(block_device)
        return ("blockdevice_handler", (system_id, device_id))

    @classmethod
    def system_id(cls, block_device):
        return block_device.node_config.node.system_id

    @classmethod
    def name(cls, block_device):
        return block_device.actual_instance.get_name()

    @classmethod
    def uuid(cls, block_device):
        block_device = block_device.actual_instance
        if isinstance(block_device, VirtualBlockDevice):
            return block_device.uuid
        else:
            return None

    @classmethod
    def _model(cls, block_device):
        """Return the model for the block device.

        This is method is named `_model` because to Piston model is reserved
        because of the model attribute on the handler.
        See `maasserver.api.support.method_fields_reserved_fields_patch" for
        how this is handled.
        """
        block_device = block_device.actual_instance
        if isinstance(block_device, PhysicalBlockDevice):
            return block_device.model
        else:
            return None

    @classmethod
    def serial(cls, block_device):
        block_device = block_device.actual_instance
        if isinstance(block_device, PhysicalBlockDevice):
            return block_device.serial
        else:
            return None

    @classmethod
    def filesystem(cls, block_device):
        # XXX: This is almost the same as
        # m.api.partitions.PartitionHandler.filesystem.
        block_device = block_device.actual_instance
        filesystem = block_device.get_effective_filesystem()
        if filesystem is not None:
            return {
                "fstype": filesystem.fstype,
                "label": filesystem.label,
                "uuid": filesystem.uuid,
                "mount_point": filesystem.mount_point,
                "mount_options": filesystem.mount_options,
            }
        else:
            return None

    @classmethod
    def partition_table_type(cls, block_device):
        partition_table = block_device.get_partitiontable()
        if partition_table is not None:
            return partition_table.table_type

    @classmethod
    def partitions(cls, block_device):
        partition_table = block_device.get_partitiontable()
        return partition_table.partitions.all() if partition_table else []

    @classmethod
    def storage_pool(cls, block_device):
        block_device = block_device.actual_instance
        if not isinstance(block_device, PhysicalBlockDevice):
            return None

        vmdisk = getattr(block_device, "vmdisk", None)
        if vmdisk and vmdisk.backing_pool:
            return vmdisk.backing_pool.pool_id

        return None

    @classmethod
    def numa_node(cls, block_device):
        block_device = block_device.actual_instance
        if isinstance(block_device, PhysicalBlockDevice):
            return block_device.numa_node.index
        return None

    def read(self, request, system_id, id):
        """@description-title Read a block device
        @description Read a block device on a given machine.

        @param (string) "{system_id}" [required=true] The machine system_id.
        @param (string) "{id}" [required=true] The block device's id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        block device.
        @success-example "success-json" [exkey=block-devs-read-by-id]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or block device is
        not found.
        @error-example "not-found"
            Not Found
        """
        return BlockDevice.objects.get_block_device_or_404(
            system_id, id, request.user, NodePermission.view
        )

    def delete(self, request, system_id, id):
        """@description-title Delete a block device
        @description Delete block device on a given machine.

        @param (string) "{system_id}" [required=true] The machine system_id.
        @param (string) "{id}" [required=true] The block device's id.

        @success (http-status-code) "204" 204

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permissions to
        delete the block device.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or block device is
        not found.
        @error-example "not-found"
            Not Found

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, id, request.user, NodePermission.admin
        )
        node = device.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot delete block device because the machine is not Ready."
            )
        device.delete()
        return rc.DELETED

    def update(self, request, system_id, id):
        """@description-title Update a block device
        @description Update block device on a given machine.

        Machines must have a status of Ready to have access to all options.
        Machines with Deployed status can only have the name, model, serial,
        and/or id_path updated for a block device. This is intented to allow a
        bad block device to be replaced while the machine remains deployed.

        @param (string) "{system_id}" [required=true] The machine system_id.
        @param (string) "{id}" [required=true] The block device's id.

        @param (string) "name" [required=false] (Physical devices) Name of the
        block device.

        @param (string) "model" [required=false] (Physical devices) Model of
        the block device.

        @param (string) "serial" [required=false] (Physical devices) Serial
        number of the block device.

        @param (string) "id_path" [required=false] (Physical devices) Only used
        if model and serial cannot be provided. This should be a path that is
        fixed and doesn't change depending on the boot order or kernel version.

        @param (string) "size" [required=false] (Physical devices) Size of the
        block device.

        @param (string) "block_size" [required=false] (Physical devices) Block
        size of the block device.

        @param (string) "name" [required=false] (Virtual devices) Name of
        the block device.

        @param (string) "uuid" [required=false] (Virtual devices) UUID of
        the block device.

        @param (string) "size" [required=false] (Virtual devices) Size of
        the block device. (Only allowed for logical volumes.)

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        block device.
        @success-example "success-json" [exkey=block-devs-update] placeholder
        text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permissions to
        update the block device.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or block device is
        not found.
        @error-example "not-found"
            Not Found

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, id, request.user, NodePermission.admin
        )
        node = device.get_node()
        if node.status not in [NODE_STATUS.READY, NODE_STATUS.DEPLOYED]:
            raise NodeStateViolation(
                "Cannot update block device because the machine is not Ready."
            )
        if node.status == NODE_STATUS.DEPLOYED:
            if device.type == "physical":
                form = UpdateDeployedPhysicalBlockDeviceForm(
                    instance=device, data=request.data
                )
            else:
                raise NodeStateViolation(
                    "Cannot update virtual block device because the machine "
                    "is Deployed."
                )
        else:
            if device.type == "physical":
                form = UpdatePhysicalBlockDeviceForm(
                    instance=device, data=request.data
                )
            elif device.type == "virtual":
                form = UpdateVirtualBlockDeviceForm(
                    instance=device, data=request.data
                )
            else:
                raise ValueError(
                    "Cannot update block device of type %s" % device.type
                )
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def add_tag(self, request, system_id, id):
        """@description-title Add a tag
        @description Add a tag to block device on a given machine.

        @param (string) "{system_id}" [required=true] The machine system_id.
        @param (string) "{id}" [required=true] The block device's id.

        @param (string) "tag" [required=true] The tag being added.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        block device.
        @success-example "success-json" [exkey=block-devs-add-tag] placeholder
        text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permissions to
        add a tag.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or block device is
        not found.
        @error-example "not-found"
            Not Found

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, id, request.user, NodePermission.admin
        )
        node = device.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot update block device because the machine is not Ready."
            )
        device.add_tag(get_mandatory_param(request.POST, "tag"))
        device.save()
        return device

    @operation(idempotent=False)
    def remove_tag(self, request, system_id, id):
        """@description-title Remove a tag
        @description Remove a tag from block device on a given machine.

        @param (string) "{system_id}" [required=true] The machine system_id.
        @param (string) "{id}" [required=true] The block device's id.

        @param (string) "tag" [required=false] The tag being removed.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        block device.
        @success-example "success-json" [exkey=block-devs-remove-tag]
        placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permissions to
        remove a tag.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or block device is
        not found.
        @error-example "not-found"
            Not Found

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, id, request.user, NodePermission.admin
        )
        node = device.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot update block device because the machine is not Ready."
            )
        device.remove_tag(get_mandatory_param(request.POST, "tag"))
        device.save()
        return device

    @operation(idempotent=False)
    def format(self, request, system_id, id):
        """@description-title Format block device
        @description Format block device with filesystem.

        @param (string) "{system_id}" [required=true] The machine system_id.
        @param (string) "{id}" [required=true] The block device's id.

        @param (string) "fstype" [required=true] Type of filesystem.

        @param (string) "uuid" [required=false] UUID of the filesystem.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        block device.
        @success-example "success-json" [exkey=block-devs-format] placeholder
        text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permissions to
        format the block device.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or block device is
        not found.
        @error-example "not-found"
            Not Found

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, id, request.user, NodePermission.edit
        )
        node = device.get_node()
        raise_error_for_invalid_state_on_allocated_operations(
            node, request.user, "format"
        )
        form = FormatBlockDeviceForm(device, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def unformat(self, request, system_id, id):
        """@description-title Unformat a block device
        @description Unformat a previously formatted block device.

        @param (string) "{system_id}" [required=true] The machine system_id.
        @param (string) "{id}" [required=true] The block device's id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing
        the updated block device.
        @success-example "success-json" [exkey=block-devs-unformat] placeholder
        text

        @error (http-status-code) "400" 400
        @error (content) "problem" The block device is not formatted, currently
        mounted, or part of a filesystem group.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permissions to
        unformat the block device.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or block device is
        not found.
        @error-example "not-found"
            Not Found

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, id, request.user, NodePermission.edit
        )
        node = device.get_node()
        raise_error_for_invalid_state_on_allocated_operations(
            node, request.user, "unformat"
        )
        filesystem = device.get_effective_filesystem()
        if filesystem is None:
            raise MAASAPIBadRequest("Block device is not formatted.")
        if filesystem.is_mounted:
            raise MAASAPIBadRequest(
                "Filesystem is mounted and cannot be unformatted. Unmount the "
                "filesystem before unformatting the block device."
            )
        if filesystem.filesystem_group is not None:
            nice_name = filesystem.filesystem_group.get_nice_name()
            raise MAASAPIBadRequest(
                "Filesystem is part of a %s, and cannot be "
                "unformatted. Remove block device from %s "
                "before unformatting the block device."
                % (nice_name, nice_name)
            )
        filesystem.delete()
        return device

    @operation(idempotent=False)
    def mount(self, request, system_id, id):
        """@description-title Mount a filesystem
        @description Mount the filesystem on block device.

        @param (string) "{system_id}" [required=true] The machine system_id.
        @param (string) "{id}" [required=true] The block device's id.

        @param (string) "mount_point" [required=true] Path on the filesystem
        to mount.

        @param (string) "mount_options" [required=false] Options to pass to
        mount(8).

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        block device.
        @success-example "success-json" [exkey=block-devs-mount] placeholder
        text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permissions to
        mount the filesystem.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or block device is
        not found.
        @error-example "not-found"
            Not Found

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, id, request.user, NodePermission.edit
        )
        raise_error_for_invalid_state_on_allocated_operations(
            device.get_node(), request.user, "mount"
        )
        filesystem = device.get_effective_filesystem()
        form = MountFilesystemForm(filesystem, data=request.data)
        if form.is_valid():
            form.save()
            return device
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def unmount(self, request, system_id, id):
        """@description-title Unmount a filesystem
        @description Unmount the filesystem on block device.

        @param (string) "{system_id}" [required=true] The machine system_id.
        @param (string) "{id}" [required=true] The block device's id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        block device.
        @success-example "success-json" [exkey=block-devs-unmount] placeholder
        text

        @error (http-status-code) "400" 400
        @error (content) "problem" The block device is not formatted or
        currently mounted.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permissions to mount
        the filesystem.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or block device is
        not found.
        @error-example "not-found"
            Not Found

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, id, request.user, NodePermission.edit
        )
        node = device.get_node()
        raise_error_for_invalid_state_on_allocated_operations(
            node, request.user, "unmount"
        )
        filesystem = device.get_effective_filesystem()
        if filesystem is None:
            raise MAASAPIBadRequest("Block device is not formatted.")
        if not filesystem.is_mounted:
            raise MAASAPIBadRequest("Filesystem is already unmounted.")
        filesystem.mount_point = None
        filesystem.mount_options = None
        filesystem.save()
        return device

    @operation(idempotent=False)
    def set_boot_disk(self, request, system_id, id):
        """@description-title Set boot disk
        @description Set a block device as the boot disk for the machine.

        @param (string) "{system_id}" [required=true] The machine system_id.
        @param (string) "{id}" [required=true] The block device's id.

        @success (http-status-code) "server-success" 200
        @success (content) "success-content" Boot disk set.
        @success-example "success-content"
            OK

        @error (http-status-code) "400" 400
        @error (content) "problem" The block device is a virtual block device.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permissions to set
        the boot disk.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or block device is
        not found.
        @error-example "not-found"
            Not Found

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, id, request.user, NodePermission.admin
        )
        node = device.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot set as boot disk because the machine is not Ready."
            )
        if not isinstance(device, PhysicalBlockDevice):
            raise MAASAPIBadRequest(
                "Cannot set a %s block device as the boot disk." % device.type
            )
        node.boot_disk = device
        node.save()
        return rc.ALL_OK


class PhysicalBlockDeviceHandler(BlockDeviceHandler):
    """
    This handler only exists because piston requires a unique handler per
    class type. Without this class the resource_uri will not be added to any
    object that is of type `PhysicalBlockDevice` when it is emitted from the
    `BlockDeviceHandler`.

    Important: This should not be used in the urls_api.py. This is only here
        to support piston.
    """

    hidden = True
    model = PhysicalBlockDevice


class VirtualBlockDeviceHandler(BlockDeviceHandler):
    """
    This handler only exists because piston requires a unique handler per
    class type. Without this class the resource_uri will not be added to any
    object that is of type `VirtualBlockDevice` when it is emitted from the
    `BlockDeviceHandler`.

    Important: This should not be used in the urls_api.py. This is only here
        to support piston.
    """

    hidden = True
    model = VirtualBlockDevice
