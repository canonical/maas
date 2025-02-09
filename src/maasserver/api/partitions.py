# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Partition`."""

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404
from piston3.utils import rc

from maasserver.api.support import operation, OperationsHandler
from maasserver.api.utils import get_mandatory_param
from maasserver.enum import NODE_STATUS
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPIValidationError,
    NodeStateViolation,
)
from maasserver.forms import AddPartitionForm, FormatPartitionForm
from maasserver.forms.filesystem import MountFilesystemForm
from maasserver.models import BlockDevice, Partition, PartitionTable
from maasserver.permissions import NodePermission

DISPLAYED_PARTITION_FIELDS = (
    "system_id",
    "device_id",
    "id",
    "uuid",
    "path",
    "type",
    "size",
    "bootable",
    "filesystem",
    "used_for",
    "tags",
)


def get_partition_by_id_or_name__or_404(node_config, partition_id):
    """Get the partition by its ID or its name.

    :raise Http404: If the partition does not exist.
    """
    try:
        partition = Partition.objects.get_partition_by_id_or_name(
            node_config, partition_id
        )
    except Partition.DoesNotExist:
        raise Http404()  # noqa: B904
    return partition


def raise_error_for_invalid_state_on_allocated_operations(
    node, user, operation
):
    if node.status not in [NODE_STATUS.READY, NODE_STATUS.ALLOCATED]:
        raise NodeStateViolation(
            "Cannot %s partition because the node is not Ready "
            "or Allocated." % operation
        )
    if node.status == NODE_STATUS.READY and not user.is_superuser:
        raise PermissionDenied(
            "Cannot %s partition because you don't have the "
            "permissions on a Ready node." % operation
        )


class PartitionsHandler(OperationsHandler):
    """Manage partitions on a block device."""

    api_doc_section_name = "Partitions"
    update = delete = None
    fields = DISPLAYED_PARTITION_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("partitions_handler", ["system_id", "device_id"])

    def read(self, request, system_id, device_id):
        """@description-title List partitions
        @description List partitions on a device with the given system_id and
        device_id.

        @param (string) "{system_id}" [required=true] The system_id.
        @param (int) "{device_id}" [required=true] The block device_id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of
        partition objects.
        @success-example "success-json" [exkey=partitions-read]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or device is not
        found.
        @error-example "not-found"
            No BlockDevice matches the given query.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.view
        )
        partition_table = device.partitiontable_set.get()
        if partition_table is None:
            return []
        else:
            return partition_table.partitions.all()

    def create(self, request, system_id, device_id):
        """@description-title Create a partition
        @description Create a partition on a block device.

        @param (string) "{system_id}" [required=true] The system_id.
        @param (int) "{device_id}" [required=true] The block device_id.

        @param (int) "size" [required=false] The size of the partition in bytes.
        If not specified, all available space will be used.

        @param (string) "uuid" [required=false] UUID for the partition. Only
        used if the partition table type for the block device is GPT.

        @param (boolean) "bootable" [required=false] If the partition should be
        marked bootable.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new
        partition object.
        @success-example "success-json" [exkey=partitions-create]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or device is not
        found.
        @error-example "not-found"
            No BlockDevice matches the given query.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.admin
        )
        node = device.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot create partition because the node is not Ready."
            )
        form = AddPartitionForm(device, data=request.data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        else:
            return form.save()


class PartitionHandler(OperationsHandler):
    """Manage partition on a block device."""

    api_doc_section_name = "Partitions"
    create = replace = update = None
    model = Partition
    fields = DISPLAYED_PARTITION_FIELDS

    @classmethod
    def filesystem(cls, partition):
        # XXX: This is almost the same as
        # m.api.blockdevices.BlockDeviceHandler.filesystem.
        filesystem = partition.get_effective_filesystem()
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
    def resource_uri(cls, partition=None):
        # See the comment in NodeHandler.resource_uri.
        if partition is None:
            system_id = "system_id"
            device_id = "device_id"
            partition_id = "id"
        else:
            partition_id = partition.id
            device_id = cls.device_id(partition)
            system_id = cls.system_id(partition)
        return ("partition_handler", (system_id, device_id, partition_id))

    @classmethod
    def system_id(cls, partition):
        block_device = partition.partition_table.block_device
        return block_device.node_config.node.system_id

    @classmethod
    def device_id(cls, partition):
        return partition.partition_table.block_device.id

    def read(self, request, system_id, device_id, id):
        """@description-title Read a partition
        @description Read the partition from machine system_id and device
        device_id with the given partition id.

        @param (string) "{system_id}" [required=true] The system_id.
        @param (int) "{device_id}" [required=true] The block device_id.
        @param (int) "{id}" [required=true] The partition id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        partition object.
        @success-example "success-json" [exkey=partitions-read]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine, device or partition
        is not found.
        @error-example "not-found"
            No BlockDevice matches the given query.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.view
        )
        return get_partition_by_id_or_name__or_404(device.node_config, id)

    def delete(self, request, system_id, device_id, id):
        """@description-title Delete a partition
        @description Delete the partition from machine system_id and device
        device_id with the given partition id.

        @param (string) "{system_id}" [required=true] The system_id.
        @param (int) "{device_id}" [required=true] The block device_id.
        @param (int) "{id}" [required=true] The partition id.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine, device or partition
        is not found.
        @error-example "not-found"
            No BlockDevice matches the given query.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.admin
        )
        partition_table = get_object_or_404(
            PartitionTable, block_device=device
        )
        node = device.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot delete block device because the node is not Ready."
            )
        partition = get_partition_by_id_or_name__or_404(device.node_config, id)
        partition_table.delete_partition(partition)
        return rc.DELETED

    @operation(idempotent=False)
    def format(self, request, system_id, device_id, id):
        """@description-title Format a partition
        @description Format the partition on machine system_id and device
        device_id with the given partition id.

        @param (string) "{system_id}" [required=true] The system_id.
        @param (int) "{device_id}" [required=true] The block device_id.
        @param (int) "{id}" [required=true] The partition id.

        @param (string) "fstype" [required=true] Type of filesystem.

        @param (string) "uuid" [required=false] The UUID for the filesystem.

        @param (string) "label" [required=false] The label for the filesystem.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        partition object.
        @success-example "success-json" [exkey=partitions-format]
        placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permissions to
        format the partition.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine, device or partition
        is not found.
        @error-example "not-found"
            No BlockDevice matches the given query.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.edit
        )
        node = device.get_node()
        partition = get_partition_by_id_or_name__or_404(device.node_config, id)
        raise_error_for_invalid_state_on_allocated_operations(
            node, request.user, "format"
        )
        form = FormatPartitionForm(partition, data=request.data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        else:
            return form.save()

    @operation(idempotent=False)
    def unformat(self, request, system_id, device_id, id):
        """@description-title Unformat a partition
        @description Unformat the partition on machine system_id and device
        device_id with the given partition id.

        @param (string) "{system_id}" [required=true] The system_id.
        @param (int) "{device_id}" [required=true] The block device_id.
        @param (int) "{id}" [required=true] The partition id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        partition object.
        @success-example "success-json" [exkey=partitions-unformat]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine, device or partition
        is not found.
        @error-example "not-found"
            No BlockDevice matches the given query.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.edit
        )
        node = device.get_node()
        partition = get_partition_by_id_or_name__or_404(device.node_config, id)
        raise_error_for_invalid_state_on_allocated_operations(
            node, request.user, "unformat"
        )
        filesystem = partition.get_effective_filesystem()
        if filesystem is None:
            raise MAASAPIBadRequest("Partition is not formatted.")
        if filesystem.is_mounted:
            raise MAASAPIBadRequest(
                "Filesystem is mounted and cannot be unformatted. Unmount the "
                "filesystem before unformatting the partition."
            )
        if filesystem.filesystem_group is not None:
            nice_name = filesystem.filesystem_group.get_nice_name()
            raise MAASAPIBadRequest(
                "Filesystem is part of a %s, and cannot be "
                "unformatted. Remove partition from %s "
                "before unformatting the partition." % (nice_name, nice_name)
            )
        filesystem.delete()
        return partition

    @operation(idempotent=False)
    def mount(self, request, system_id, device_id, id):
        """@description-title Mount a filesystem
        @description Mount a filesystem on machine system_id, device device_id
        and partition id.

        @param (string) "{system_id}" [required=true] The system_id.
        @param (int) "{device_id}" [required=true] The block device_id.
        @param (int) "{id}" [required=true] The partition id.

        @param (string) "mount_point" [required=true] Path on the filesystem to
        mount.

        @param (string) "mount_options" [required=false] Options to pass to
        mount(8).

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        partition object.
        @success-example "success-json" [exkey=partitions-mount] placeholder
        text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permissions to mount
        the filesystem.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine, device or partition
        is not found.
        @error-example "not-found"
            No BlockDevice matches the given query.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.edit
        )
        node = device.get_node()
        partition = get_partition_by_id_or_name__or_404(device.node_config, id)
        raise_error_for_invalid_state_on_allocated_operations(
            node, request.user, "mount"
        )
        filesystem = partition.get_effective_filesystem()
        form = MountFilesystemForm(filesystem, data=request.data)
        if form.is_valid():
            form.save()
            return partition
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def unmount(self, request, system_id, device_id, id):
        """@description-title Unmount a filesystem
        @description Unmount a filesystem on machine system_id, device
        device_id and partition id.

        @param (string) "{system_id}" [required=true] The system_id.
        @param (int) "{device_id}" [required=true] The block device_id.
        @param (int) "{id}" [required=true] The partition id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        partition object.
        @success-example "success-json" [exkey=partitions-unmount] placeholder
        text

        @error (http-status-code) "400" 400
        @error (content) "part-prob" The partition is not formatted or not
        currently mounted.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permissions to
        unmount the filesystem.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine, device or partition
        is not found.
        @error-example "not-found"
            No BlockDevice matches the given query.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.edit
        )
        node = device.get_node()
        partition = get_partition_by_id_or_name__or_404(device.node_config, id)
        raise_error_for_invalid_state_on_allocated_operations(
            node, request.user, "unmount"
        )
        filesystem = partition.get_effective_filesystem()
        if filesystem is None:
            raise MAASAPIBadRequest("Partition is not formatted.")
        if not filesystem.is_mounted:
            raise MAASAPIBadRequest("Filesystem is already unmounted.")
        filesystem.mount_point = None
        filesystem.mount_options = None
        filesystem.save()
        return partition

    @operation(idempotent=False)
    def add_tag(self, request, system_id, device_id, id):
        """@description-title Add a tag
        @description Add a tag to a partition on machine system_id, device
        device_id and partition id.

        @param (string) "{system_id}" [required=true] The system_id.
        @param (int) "{device_id}" [required=true] The block device_id.
        @param (int) "{id}" [required=true] The partition id.

        @param (string) "tag" [required=true] The tag being added.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        partition object.
        @success-example "success-json" [exkey=partitions-add-tag] placeholder
        text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permissions to
        add a tag.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine, device or partition
        is not found.
        @error-example "not-found"
            No BlockDevice matches the given query.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.admin
        )
        partition = get_partition_by_id_or_name__or_404(device.node_config, id)
        partition.add_tag(get_mandatory_param(request.POST, "tag"))
        partition.save()
        return partition

    @operation(idempotent=False)
    def remove_tag(self, request, system_id, device_id, id):
        """@description-title Remove a tag
        @description Remove a tag from a partition on machine system_id, device
        device_id and partition id.

        @param (string) "{system_id}" [required=true] The system_id.
        @param (int) "{device_id}" [required=true] The block device_id.
        @param (int) "{id}" [required=true] The partition id.

        @param (string) "tag" [required=true] The tag being removed.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        partition object.
        @success-example "success-json" [exkey=partitions-rem-tag] placeholder
        text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permissions to
        remove a tag.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine, device or partition
        is not found.
        @error-example "not-found"
            No BlockDevice matches the given query.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.admin
        )
        partition = get_partition_by_id_or_name__or_404(device.node_config, id)
        partition.remove_tag(get_mandatory_param(request.POST, "tag"))
        partition.save()
        return partition
