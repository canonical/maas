# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Partition`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type

from django.http import Http404
from django.shortcuts import get_object_or_404
from maasserver.api.support import (
    operation,
    OperationsHandler,
)
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPIValidationError,
)
from maasserver.forms import (
    AddPartitionForm,
    FormatPartitionForm,
    MountPartitionForm,
)
from maasserver.models import (
    BlockDevice,
    Partition,
    PartitionTable,
)
from piston.utils import rc


DISPLAYED_PARTITION_FIELDS = (
    'id',
    'uuid',
    'path',
    'type',
    'size',
    'bootable',
    ('filesystem', (
        'fstype',
        'label',
        'uuid',
        'mount_point',
    )),
)


def get_partition_by_id_or_name__or_404(partition_id, partition_table):
    """Get the partition by its partition_id or its name.

    :raise Http404: If the partition does not exist.
    """
    try:
        partition = Partition.objects.get_partition_by_id_or_name(
            partition_id, partition_table)
    except Partition.DoesNotExist:
        raise Http404()
    return partition


class PartitionsHandler(OperationsHandler):
    """Manage partitions on a block device."""
    api_doc_section_name = "Partitions"
    update = delete = None
    fields = DISPLAYED_PARTITION_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return (
            'partitions_handler', ["system_id", "device_id"])

    def read(self, request, system_id, device_id):
        """List all partitions on the block device.

        Returns 404 if the node or the block device are not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NODE_PERMISSION.VIEW)
        partition_table = device.partitiontable_set.get()
        if partition_table is None:
            return []
        else:
            return partition_table.partitions.all()

    def create(self, request, system_id, device_id):
        """Create a partition on the block device.

        :param size: The size of the partition.
        :param uuid: UUID for the partition. Only used if the partition table
            type for the block device is GPT.
        :param bootable: If the partition should be marked bootable.

        Returns 404 if the node or the block device are not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NODE_PERMISSION.EDIT)
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
    def resource_uri(cls, partition=None):
        # See the comment in NodeHandler.resource_uri.
        if partition is None:
            system_id = "system_id"
            device_id = "device_id"
            partition_id = "partition_id"
        else:
            partition_id = partition.id
            block_device = partition.partition_table.block_device
            device_id = block_device.id
            system_id = block_device.node.system_id
        return (
            'partition_handler', (system_id, device_id, partition_id))

    def read(self, request, system_id, device_id, partition_id):
        """Read partition.

        Returns 404 if the node, block device, or partition are not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NODE_PERMISSION.VIEW)
        partition_table = get_object_or_404(
            PartitionTable, block_device=device)
        return get_partition_by_id_or_name__or_404(
            partition_id, partition_table)

    def delete(self, request, system_id, device_id, partition_id):
        """Delete partition.

        Returns 404 if the node, block device, or partition are not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NODE_PERMISSION.EDIT)
        partition_table = get_object_or_404(
            PartitionTable, block_device=device)
        partition = get_partition_by_id_or_name__or_404(
            partition_id, partition_table)
        partition.delete()
        return rc.DELETED

    @operation(idempotent=False)
    def format(self, request, system_id, device_id, partition_id):
        """Format a partition.

        :param fstype: Type of filesystem.
        :param uuid: The UUID for the filesystem.
        :param label: The label for the filesystem.

        Returns 403 when the user doesn't have the ability to format the \
            partition.
        Returns 404 if the node, block device, or partition is not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NODE_PERMISSION.EDIT)
        partition_table = get_object_or_404(
            PartitionTable, block_device=device)
        partition = get_partition_by_id_or_name__or_404(
            partition_id, partition_table)
        form = FormatPartitionForm(partition, data=request.data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        else:
            return form.save()

    @operation(idempotent=False)
    def unformat(self, request, system_id, device_id, partition_id):
        """Unformat a partition."""
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NODE_PERMISSION.EDIT)
        partition_table = get_object_or_404(
            PartitionTable, block_device=device)
        partition = get_partition_by_id_or_name__or_404(
            partition_id, partition_table)
        filesystem = partition.filesystem
        if filesystem is None:
            raise MAASAPIBadRequest("Partition is not formatted.")
        if filesystem.mount_point:
            raise MAASAPIBadRequest(
                "Filesystem is mounted and cannot be unformatted. Unmount the "
                "filesystem before unformatting the partition.")
        if filesystem.filesystem_group is not None:
            raise MAASAPIBadRequest(
                "Filesystem is part of a filesystem group, and cannot be "
                "unformatted. Remove partition from filesystem group "
                "before unformatting the partition.")
        partition.remove_filesystem()
        return partition

    @operation(idempotent=False)
    def mount(self, request, system_id, device_id, partition_id):
        """Mount the filesystem on partition.

        :param mount_point: Path on the filesystem to mount.

        Returns 403 when the user doesn't have the ability to mount the \
            partition.
        Returns 404 if the node, block device, or partition is not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NODE_PERMISSION.EDIT)
        partition_table = get_object_or_404(
            PartitionTable, block_device=device)
        partition = get_partition_by_id_or_name__or_404(
            partition_id, partition_table)
        form = MountPartitionForm(partition, data=request.data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        else:
            return form.save()

    @operation(idempotent=False)
    def unmount(self, request, system_id, device_id, partition_id):
        """Unmount the filesystem on partition.

        Returns 400 if the partition is not formatted or not currently \
            mounted.
        Returns 403 when the user doesn't have the ability to unmount the \
            partition.
        Returns 404 if the node, block device, or partition is not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NODE_PERMISSION.EDIT)
        partition_table = get_object_or_404(
            PartitionTable, block_device=device)
        partition = get_partition_by_id_or_name__or_404(
            partition_id, partition_table)
        filesystem = partition.filesystem
        if filesystem is None:
            raise MAASAPIBadRequest("Partition is not formatted.")
        if not filesystem.mount_point:
            raise MAASAPIBadRequest("Filesystem is already unmounted.")
        filesystem.mount_point = None
        filesystem.save()
        return partition
