# Copyright 2015-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with the storage model."""

from maasserver.enum import FILESYSTEM_TYPE


def get_effective_filesystem(model):
    """Return the effective `Filesystem` for the `model`.

    A `BlockDevice` or `Partition` can have up to two `Filesystem` one with
    `acquired` set to False and another set to `True`. When the `Node` for
    `model` is in an allocated state the acquired `Filesystem` will be used
    over the non-acquired `Filesystem`.

    :param model: Model to get active `Filesystem` from.
    :type model: Either `BlockDevice` or `Partition`.
    :returns: Active `Filesystem` for `model`.
    :rtype: `Filesystem`
    """
    from maasserver.models import BlockDevice, Partition

    assert isinstance(model, (BlockDevice, Partition))

    node = model.get_node()
    filesystems = list(model.filesystem_set.all())
    if node.is_in_allocated_state():
        # Return the acquired filesystem.
        for filesystem in filesystems:
            if filesystem.acquired:
                return filesystem
        # No acquired filesystem, could be a filesystem that is not
        # mountable so we return that filesystem.
        for filesystem in filesystems:
            if not filesystem.is_mountable:
                return filesystem
        return None
    else:
        # Not in allocated state so return the filesystem that is not an
        # acquired filesystem.
        for filesystem in filesystems:
            if not filesystem.acquired:
                return filesystem
        return None


def used_for(model):
    """Return what the block device or partition is being used for."

    :param model: Model to get active `Filesystem` or `PartitionTable` from.
    :type model: Either `BlockDevice` or `Partition`.
    :returns: What the block device or partition is being used for.
    :rtype: `str`
    """
    # Avoid circular imports
    from maasserver.models import BlockDevice

    filesystem = get_effective_filesystem(model)
    if filesystem is not None:
        if filesystem.is_mounted:
            return "{} formatted filesystem mounted at {}".format(
                filesystem.fstype,
                filesystem.mount_point,
            )
        elif filesystem.fstype == FILESYSTEM_TYPE.LVM_PV:
            return "LVM volume for %s" % filesystem.filesystem_group.name
        elif filesystem.fstype == FILESYSTEM_TYPE.RAID:
            return "Active {} device for {}".format(
                filesystem.filesystem_group.group_type,
                filesystem.filesystem_group.name,
            )
        elif filesystem.fstype == FILESYSTEM_TYPE.RAID_SPARE:
            return "Spare {} device for {}".format(
                filesystem.filesystem_group.group_type,
                filesystem.filesystem_group.name,
            )
        elif filesystem.fstype == FILESYSTEM_TYPE.BCACHE_CACHE:
            return "Cache device for %s" % filesystem.cache_set.get_name()
        elif filesystem.fstype == FILESYSTEM_TYPE.BCACHE_BACKING:
            return "Backing device for %s" % filesystem.filesystem_group.name
        elif filesystem.fstype == FILESYSTEM_TYPE.VMFS6:
            return "VMFS extent for %s" % filesystem.filesystem_group.name
        else:
            return "Unmounted %s formatted filesystem" % filesystem.fstype
    elif isinstance(model, BlockDevice):
        partition_table = model.get_partitiontable()
        if partition_table is not None:
            partitions = len(partition_table.partitions.all())
            if partitions > 1:
                message = "%s partitioned with %d partitions"
            else:
                message = "%s partitioned with %d partition"
            return message % (partition_table.table_type, partitions)
    return "Unused"
