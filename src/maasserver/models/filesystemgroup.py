# Copyright 2015-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a filesystem group. Contains a set of filesystems that create
a virtual block device. E.g. LVM Volume Group."""


from itertools import chain
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    Manager,
    Q,
    TextField,
)
from django.http import Http404
from django.shortcuts import get_object_or_404

from maasserver.enum import (
    CACHE_MODE_TYPE,
    CACHE_MODE_TYPE_CHOICES,
    FILESYSTEM_GROUP_RAID_TYPES,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_GROUP_TYPE_CHOICES,
    FILESYSTEM_TYPE,
)
from maasserver.models.cacheset import CacheSet
from maasserver.models.cleansave import CleanSave
from maasserver.models.numa import NUMANode
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import get_one

# Size of LVM physical extent. 4MiB
LVM_PE_SIZE = 4 * 1024 * 1024

# Size of the RAID overhead. 128k is maximum used.
RAID_SUPERBLOCK_OVERHEAD = 128 * 1024


class BaseFilesystemGroupManager(Manager):
    """A utility to manage the collection of FilesystemGroup."""

    extra_filters = {}

    def get_queryset(self):
        return super().get_queryset().filter(**self.extra_filters)

    def get_object_or_404(self, system_id, filesystem_group_id, user, perm):
        """Fetch a `FilesystemGroup` by its `Node`'s system_id and its id.
        Raise exceptions if no `FilesystemGroup` with this id exist, if the
        `Node` with system_id doesn't exist, if the `FilesystemGroup` doesn't
        exist on the `Node`, or if the provided user has not the required
        permission on this `Node` and `FilesystemGroup`.

        :param name: The system_id.
        :type name: string
        :param name: The filesystem_group_id.
        :type name: int
        :param user: The user that should be used in the permission check.
        :type user: django.contrib.auth.models.User
        :param perm: The permission to assert that the user has on the node.
        :type perm: unicode
        :raises: django.http.Http404_,
            :class:`maasserver.exceptions.PermissionDenied`.

        .. _django.http.Http404: https://
           docs.djangoproject.com/en/dev/topics/http/views/
           #the-http404-exception
        """
        params = self.extra_filters.copy()
        try:
            filesystem_group_id = int(filesystem_group_id)
        except ValueError:
            # Not an integer, we will use the name of the group instead.
            params["name"] = filesystem_group_id
        else:
            # It is an integer use it for the block device id.
            params["id"] = filesystem_group_id
        filesystem_group = get_object_or_404(self.model, **params)
        node = filesystem_group.get_node()
        if node.system_id != system_id:
            raise Http404()
        if not user.has_perm(perm, filesystem_group):
            raise PermissionDenied()
        return filesystem_group

    def filter_by_block_device(self, block_device):
        """Return all the `FilesystemGroup`s that are related to
        block_device."""
        cache_set_partition_query = Q(
            cache_set__filesystems__partition__partition_table__block_device=(
                block_device
            )
        )
        partition_query = Q(
            filesystems__partition__partition_table__block_device=block_device
        )
        return self.filter(
            Q(cache_set__filesystems__block_device=block_device)
            | cache_set_partition_query
            | Q(filesystems__block_device=block_device)
            | partition_query
        ).distinct()

    def filter_by_node(self, node):
        """Return all `FilesystemGroup` that are related to node."""
        if node is None:
            # return an empty queryset
            return self.none()

        node_config = node.current_config
        cache_set_partition_query = Q(
            **{
                "cache_set__filesystems__partition__partition_table__"
                "block_device__node_config": node_config
            }
        )
        partition_query = Q(
            **{
                "filesystems__partition__partition_table__"
                "block_device__node_config": node_config
            }
        )
        return self.filter(
            Q(cache_set__filesystems__block_device__node_config=node_config)
            | cache_set_partition_query
            | Q(filesystems__block_device__node_config=node_config)
            | partition_query
        ).distinct()

    def get_available_name_for(self, filesystem_group):
        """Return an available name that can be used for a `VirtualBlockDevice`
        based on the `filesystem_group`'s group_type and other block devices
        on the node.
        """
        prefix = filesystem_group.get_name_prefix()
        node = filesystem_group.get_node()
        idx = -1
        for filesystem_group in self.filter_by_node(node).filter(
            name__startswith=prefix
        ):
            name = filesystem_group.name.replace(prefix, "")
            try:
                name_idx = int(name)
            except ValueError:
                pass
            else:
                idx = max(idx, name_idx)
        return f"{prefix}{idx + 1}"


class FilesystemGroupManager(BaseFilesystemGroupManager):
    """All the FilesystemGroup objects together."""


class VolumeGroupManager(BaseFilesystemGroupManager):
    """Volume groups."""

    extra_filters = {"group_type": FILESYSTEM_GROUP_TYPE.LVM_VG}

    def create_volume_group(self, name, block_devices, partitions, uuid=None):
        """Create a `VolumeGroup` with the list of block devices and
        partitions."""
        from maasserver.models.filesystem import Filesystem

        if block_devices:
            bdev = block_devices[0]
        else:
            bdev = partitions[0].partition_table.block_device
        node_config = bdev.node_config
        volume_group = VolumeGroup.objects.create(name=name, uuid=uuid)

        for block_device in block_devices:
            Filesystem.objects.create(
                node_config=node_config,
                fstype=FILESYSTEM_TYPE.LVM_PV,
                block_device=block_device,
                filesystem_group=volume_group,
            )
        for partition in partitions:
            Filesystem.objects.create(
                node_config=node_config,
                fstype=FILESYSTEM_TYPE.LVM_PV,
                partition=partition,
                filesystem_group=volume_group,
            )
        volume_group.save(force_update=True)
        return volume_group


class RAIDManager(BaseFilesystemGroupManager):
    """RAID groups"""

    extra_filters = {"group_type__in": FILESYSTEM_GROUP_RAID_TYPES}

    def create_raid(
        self,
        level,
        name=None,
        uuid=None,
        block_devices=[],
        partitions=[],
        spare_devices=[],
        spare_partitions=[],
    ):
        from maasserver.models.filesystem import Filesystem

        # Create a FilesystemGroup for this RAID
        raid = RAID(group_type=level, name=name, uuid=uuid)
        raid.save()

        if block_devices:
            bdev = block_devices[0]
        elif spare_devices:
            bdev = spare_devices[0]
        elif partitions:
            bdev = partitions[0].partition_table.block_device
        elif spare_partitions:
            bdev = partitions[0].partition_table.block_device
        else:
            bdev = None  # this only happens if there are no devices at all, in
            # which case no filesystem is created
        node_config = bdev.node_config if bdev else None
        for block_device in block_devices:
            Filesystem.objects.create(
                node_config=node_config,
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=block_device,
                filesystem_group=raid,
            )
        for partition in partitions:
            Filesystem.objects.create(
                node_config=node_config,
                fstype=FILESYSTEM_TYPE.RAID,
                partition=partition,
                filesystem_group=raid,
            )
        for block_device in spare_devices:
            Filesystem.objects.create(
                node_config=node_config,
                fstype=FILESYSTEM_TYPE.RAID_SPARE,
                block_device=block_device,
                filesystem_group=raid,
            )
        for partition in spare_partitions:
            Filesystem.objects.create(
                node_config=node_config,
                fstype=FILESYSTEM_TYPE.RAID_SPARE,
                partition=partition,
                filesystem_group=raid,
            )
        raid.save(force_update=True)
        return raid


class BcacheManager(BaseFilesystemGroupManager):
    """Bcache groups"""

    extra_filters = {"group_type": FILESYSTEM_GROUP_TYPE.BCACHE}

    def validate_bcache_creation_parameters(
        self,
        cache_set,
        cache_mode,
        backing_device,
        backing_partition,
        validate_mode=True,
    ):
        """Validate bcache creation parameters. Raises ValidationErrors as
        needed. We don't always need to validate the mode, so, there is an
        option for that."""

        if validate_mode and cache_mode not in (
            CACHE_MODE_TYPE.WRITEBACK,
            CACHE_MODE_TYPE.WRITETHROUGH,
            CACHE_MODE_TYPE.WRITEAROUND,
        ):
            raise ValidationError("Invalid cache mode: %s" % cache_mode)

        if cache_set is None:
            raise ValidationError("Bcache requires a cache_set.")

        if backing_device and backing_partition:
            raise ValidationError(
                "A Bcache can have either a backing device or partition."
            )

        if not backing_device and not backing_partition:
            raise ValidationError(
                "Either backing_device or backing_partition must be "
                "specified."
            )

    def create_bcache(
        self,
        cache_set,
        name=None,
        uuid=None,
        backing_device=None,
        backing_partition=None,
        cache_mode=None,
    ):
        """Creates a bcache of type `cache_type` using the desired cache and
        backing elements."""

        self.validate_bcache_creation_parameters(
            cache_set, cache_mode, backing_device, backing_partition
        )

        # Avoid circular import issues
        from maasserver.models.filesystem import Filesystem

        if backing_device is not None:
            backing_filesystem = Filesystem(
                node_config=backing_device.node_config,
                block_device=backing_device,
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
            )
        elif backing_partition is not None:
            node_config = (
                backing_partition.partition_table.block_device.node_config
            )
            backing_filesystem = Filesystem(
                node_config=node_config,
                partition=backing_partition,
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
            )

        # Setup the cache FilesystemGroup and attach the filesystems to it.
        bcache_filesystem_group = FilesystemGroup.objects.create(
            name=name,
            uuid=uuid,
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_mode=cache_mode,
            cache_set=cache_set,
        )
        backing_filesystem.filesystem_group = bcache_filesystem_group
        backing_filesystem.save()
        bcache_filesystem_group.save(force_update=True)
        return bcache_filesystem_group


class VMFSManager(BaseFilesystemGroupManager):
    """VMFS filesystem group"""

    extra_filters = {"group_type": FILESYSTEM_GROUP_TYPE.VMFS6}

    def create_vmfs(self, name, partitions, uuid=None):
        """Create a `VMFS` with the list of block devices and partitions."""
        from maasserver.models.filesystem import Filesystem

        node_config = partitions[0].partition_table.block_device.node_config
        vmfs = self.create(name=name, uuid=uuid)
        for partition in partitions:
            Filesystem.objects.create(
                node_config=node_config,
                fstype=FILESYSTEM_TYPE.VMFS6,
                partition=partition,
                filesystem_group=vmfs,
            )
        vmfs.save(force_update=True)
        vmfs.virtual_device.filesystem_set.create(
            node_config=node_config,
            fstype=FILESYSTEM_TYPE.VMFS6,
            mount_point=f"/vmfs/volumes/{name}",
        )
        return vmfs


class FilesystemGroup(CleanSave, TimestampedModel):
    """A filesystem group. Contains a set of filesystems that create
    a virtual block device. E.g. LVM Volume Group.

    :ivar uuid: UUID of the filesystem group.
    :ivar group_type: Type of filesystem group.
    :ivar name: Name of the filesytem group.
    :ivar create_params: Parameters that can be passed during the create
        command when the filesystem group is created.
    """

    objects = FilesystemGroupManager()

    uuid = TextField(default=uuid4)

    group_type = CharField(
        max_length=20,
        null=False,
        blank=False,
        choices=FILESYSTEM_GROUP_TYPE_CHOICES,
    )

    name = CharField(max_length=255, null=False, blank=False)

    create_params = CharField(max_length=255, null=True, blank=True)

    cache_mode = CharField(
        max_length=20, null=True, blank=True, choices=CACHE_MODE_TYPE_CHOICES
    )

    cache_set = ForeignKey(CacheSet, null=True, blank=True, on_delete=CASCADE)

    def __str__(self):
        return "%s device %s %d" % (self.group_type, self.name, self.id)

    @property
    def virtual_device(self):
        """Return the linked `VirtualBlockDevice`.

        This should never be called when the group_type is LVM_VG.
        `virtual_devices` should be used in that case, since LVM_VG
        supports multiple `VirtualBlockDevice`s.
        """
        if self.is_lvm():
            raise AttributeError(
                "virtual_device should not be called when "
                "group_type = LVM_VG."
            )
        else:
            # Return the first `VirtualBlockDevice` since it is the only one.
            # Using 'all()' instead of 'first()' so that if it was precached
            # that cache will be used.
            return get_one(self.virtual_devices.all())

    def get_numa_node_indexes(self):
        """Return NUMA node indexes for physical devices making the volume group."""
        block_devices = chain(
            *(
                filesystem.get_physical_block_devices()
                for filesystem in self.filesystems.all()
            )
        )
        numa_ids = {device.numa_node_id for device in block_devices}
        return list(
            NUMANode.objects.filter(id__in=numa_ids)
            .values_list("index", flat=True)
            .order_by("index")
        )

    def get_node(self):
        """`Node` this filesystem group belongs to."""
        from maasserver.models import Filesystem

        # don't use filesystem_set as the object might not be saved yet
        fs = Filesystem.objects.filter(filesystem_group=self).first()
        if fs is None:
            return None
        return fs.get_node()

    def get_size(self):
        """Size of this filesystem group.

        Calculated from the total size of all filesystems in this group.
        Its not calculated from its virtual_block_device size. The linked
        `VirtualBlockDevice` should calculate its size from this filesystem
        group.
        """
        if self.is_lvm():
            return self.get_lvm_size()
        elif self.is_raid():
            return self.get_raid_size()
        elif self.is_bcache():
            return self.get_bcache_size()
        elif self.is_vmfs():
            return self.get_total_size()
        else:
            return 0

    def get_lvm_size(self):
        """Size of this LVM volume group.

        Calculated from the total size of all filesystems in this group.
        Its not calculated from its virtual_block_device size.

        Note: Should only be called when the `group_type` is LVM_VG.
        """
        filesystems = list(self.filesystems.all())
        if len(filesystems) == 0:
            return 0
        else:
            pv_total_size = sum(
                filesystem.get_size() for filesystem in filesystems
            )
            number_of_extents, _ = divmod(pv_total_size, LVM_PE_SIZE)
            # Reserve one extent per filesystem for LVM headers - lp:1517129.
            return (number_of_extents - len(filesystems)) * LVM_PE_SIZE

    def get_smallest_filesystem_size(self):
        """Return the smallest filesystem size."""
        filesystems = list(self.filesystems.all())
        if len(filesystems) == 0:
            return 0
        else:
            return min(filesystem.get_size() for filesystem in filesystems)

    def get_total_size(self):
        """Return the size of all filesystems combined."""
        return sum(fs.get_size() for fs in self.filesystems.all())

    def get_raid_size(self):
        """Size of this RAID.

        Calculated based on the RAID type and how output size based on that
        type. The size will be calculated using the smallest size filesystem
        attached to this RAID. The linked `VirtualBlockDevice` should
        calculate its size from this filesystem group.

        Note: Should only be called when the `group_type` is in
            `FILESYSTEM_GROUP_RAID_TYPES`.
        """
        min_size = self.get_smallest_filesystem_size()
        if min_size <= 0:
            # Possible when no filesytems are attached to this group.
            return 0
        elif self.group_type == FILESYSTEM_GROUP_TYPE.RAID_0:
            return self.get_total_size() - (
                RAID_SUPERBLOCK_OVERHEAD * self.filesystems.count()
            )
        elif self.group_type == FILESYSTEM_GROUP_TYPE.RAID_1:
            return min_size - RAID_SUPERBLOCK_OVERHEAD
        else:
            num_raid = len(
                [
                    fstype
                    for fstype in self._get_all_fstypes()
                    if fstype == FILESYSTEM_TYPE.RAID
                ]
            )
            if self.group_type == FILESYSTEM_GROUP_TYPE.RAID_5:
                return (min_size * (num_raid - 1)) - RAID_SUPERBLOCK_OVERHEAD
            elif self.group_type == FILESYSTEM_GROUP_TYPE.RAID_6:
                return (min_size * (num_raid - 2)) - RAID_SUPERBLOCK_OVERHEAD
            elif self.group_type == FILESYSTEM_GROUP_TYPE.RAID_10:
                return (min_size * num_raid / 2) - RAID_SUPERBLOCK_OVERHEAD
        raise ValidationError("Unknown raid type: %s" % self.group_type)

    def get_bcache_backing_filesystem(self):
        """Return the filesystem that is the backing device for the Bcache."""
        for filesystem in self.filesystems.all():
            if filesystem.fstype == FILESYSTEM_TYPE.BCACHE_BACKING:
                return filesystem
        return None

    def get_bcache_backing_block_device(self):
        """Return the block_device that is the backing device for the Bcache.

        This will return the block device even if the backing is a partition.
        """
        filesystem = self.get_bcache_backing_filesystem()
        if filesystem is not None:
            if filesystem.block_device is not None:
                return filesystem.block_device
            else:
                return filesystem.partition.partition_table.block_device
        return None

    def get_bcache_size(self):
        """Size of this Bcache.

        Calculated based on the size of the backing device. The linked
        `VirtualBlockDevice` should calculate its size from this
        filesystem group.

        Note: Should only be called when the `group_type` is BCACHE.
        """
        backing_filesystem = self.get_bcache_backing_filesystem()
        if backing_filesystem is None:
            return 0
        else:
            return backing_filesystem.get_size()

    def get_lvm_allocated_size(self, skip_volumes=[]):
        """Returns the space already allocated to virtual block devices.

        Calculated from the total size of all virtual block devices in this
        group.
        """
        return sum(
            logical_volume.size
            for logical_volume in self.virtual_devices.all()
            if logical_volume not in skip_volumes
        )

    def get_lvm_free_space(self, skip_volumes=[]):
        """Returns the total unallocated space on this FilesystemGroup"""
        return self.get_lvm_size() - self.get_lvm_allocated_size(
            skip_volumes=skip_volumes
        )

    def clean(self, *args, **kwargs):
        super().clean(*args, **kwargs)

        # We allow the initial save to skip model validation, any
        # additional saves required filesystems linked. This is because the
        # object needs to exist in the database before the filesystems can
        # be linked.
        if not self.id:
            return

        # Grab all filesystems so that if the filesystems have been precached
        # it will be used. This prevents extra database queries.
        filesystems = list(self.filesystems.all())

        # Must at least have a filesystem added to the group.
        if len(filesystems) == 0:
            raise ValidationError(
                "At least one filesystem must have been added."
            )

        # All filesystems must belong all to the same node.
        nodes = {filesystem.get_node() for filesystem in filesystems}
        if len(nodes) > 1:
            raise ValidationError(
                "All added filesystems must belong to the same node."
            )

        # Validate all the different group types.
        if self.is_lvm():
            self._validate_lvm(filesystems=filesystems)
        elif self.is_raid():
            self._validate_raid(filesystems=filesystems)
        elif self.is_bcache():
            self._validate_bcache(filesystems=filesystems)

    def is_lvm(self):
        """Return True if `group_type` is LVM_VG type."""
        return self.group_type == FILESYSTEM_GROUP_TYPE.LVM_VG

    def is_raid(self):
        """Return True if `group_type` is a RAID type."""
        return self.group_type in FILESYSTEM_GROUP_RAID_TYPES

    def is_bcache(self):
        """Return True if `group_type` is BCACHE type."""
        return self.group_type == FILESYSTEM_GROUP_TYPE.BCACHE

    def is_vmfs(self):
        """Return True if `group_type` is VMFS."""
        return self.group_type == FILESYSTEM_GROUP_TYPE.VMFS6

    def _get_all_fstypes(self, filesystems=None):
        """Return list of all filesystem types attached."""
        # Grab all filesystems so that if the filesystems have been
        # precached it will be used. This prevents extra database queries.
        if filesystems is None:
            filesystems = list(self.filesystems.all())
        return [filesystem.fstype for filesystem in filesystems]

    def _validate_lvm(self, filesystems=None):
        """Validate attached filesystems are correct type for LVM_VG."""
        if not self.is_lvm():
            return
        unique_fstypes = set(self._get_all_fstypes(filesystems=filesystems))
        if unique_fstypes != {FILESYSTEM_TYPE.LVM_PV}:
            raise ValidationError(
                "Volume group can only contain lvm physical volumes."
            )

    def _validate_raid(self, filesystems=None):
        """Validate attached filesystems are correct count and type for RAID."""
        if not self.is_raid():
            return
        fstypes = self._get_all_fstypes(filesystems=filesystems)
        num_raid = len(
            [fstype for fstype in fstypes if fstype == FILESYSTEM_TYPE.RAID]
        )
        num_raid_spare = len(
            [
                fstype
                for fstype in fstypes
                if fstype == FILESYSTEM_TYPE.RAID_SPARE
            ]
        )
        if self.group_type == FILESYSTEM_GROUP_TYPE.RAID_0:
            # RAID 0 can contain 2 or more RAID filesystems and no spares are
            # allowed.
            if num_raid < 2 or num_raid_spare != 0:
                raise ValidationError(
                    "RAID level 0 must have at least 2 raid devices and "
                    "no spares."
                )
        elif self.group_type == FILESYSTEM_GROUP_TYPE.RAID_1:
            # RAID 1 must have at least 2 RAID filesystems.
            if num_raid < 2:
                raise ValidationError(
                    "RAID level 1 must have at least 2 raid devices and "
                    "any number of spares."
                )
        elif self.group_type == FILESYSTEM_GROUP_TYPE.RAID_5:
            # RAID 5 must have at least 3 RAID filesystems, but can have
            # spares.
            if num_raid < 3:
                raise ValidationError(
                    "RAID level 5 must have at least 3 raid devices and "
                    "any number of spares."
                )
        elif self.group_type == FILESYSTEM_GROUP_TYPE.RAID_6:
            # RAID 6 must have at least 4 RAID filesystems, but can have
            # spares.
            if num_raid < 4:
                raise ValidationError(
                    "RAID level 6 must have at least 4 raid devices and "
                    "any number of spares."
                )
        elif self.group_type == FILESYSTEM_GROUP_TYPE.RAID_10:
            # RAID 10 must have at least 4 RAID filesystems, but can have
            # spares.
            if num_raid < 3:
                raise ValidationError(
                    "RAID level 10 must have at least 3 raid devices and "
                    "any number of spares."
                )
        num_raid_invalid = len(
            [
                fstype
                for fstype in fstypes
                if (
                    fstype != FILESYSTEM_TYPE.RAID
                    and fstype != FILESYSTEM_TYPE.RAID_SPARE
                )
            ]
        )
        if num_raid_invalid > 0:
            raise ValidationError(
                "RAID can only contain raid device and raid spares."
            )

    def _validate_bcache(self, filesystems=None):
        """Validate attached filesystems are correct type for BCACHE."""
        if not self.is_bcache():
            return
        # Circular imports.
        from maasserver.models.virtualblockdevice import VirtualBlockDevice

        filesystems = [
            filesystem.fstype for filesystem in self.filesystems.all()
        ]
        if filesystems != [FILESYSTEM_TYPE.BCACHE_BACKING]:
            raise ValidationError(
                "Bcache can only contain one backing device."
            )
        backing_block_device = self.get_bcache_backing_block_device()
        backing_block_device = backing_block_device.actual_instance
        if isinstance(backing_block_device, VirtualBlockDevice):
            if backing_block_device.filesystem_group.is_lvm():
                raise ValidationError(
                    "Bcache cannot use a logical volume as a backing device."
                )
        if self.cache_mode is None:
            raise ValidationError("Bcache requires cache mode to be set.")
        if self.cache_set is None:
            raise ValidationError("Bcache requires an assigned cache set.")

    def save(self, *args, **kwargs):
        # Prevent saving if the size of the volume group is now smaller than
        # the total size of logical volumes.
        if (
            self.group_type == FILESYSTEM_GROUP_TYPE.LVM_VG
            and self.get_lvm_free_space() < 0
        ):
            raise ValidationError(
                "Volume group cannot be smaller than its logical volumes."
            )

        # Set the name correctly based on the type and generate a new UUID
        # if needed.
        if self.group_type is not None and self.name is None:
            self.name = FilesystemGroup.objects.get_available_name_for(self)
        # XXX this is needed because tests pass uuid=None by default
        if not self.uuid:
            self.uuid = uuid4()
        super().save(*args, **kwargs)

        # Update or create the virtual block device when the filesystem group
        # is saved. Does nothing if group_type is LVM_VG. Virtual block device
        # is not created until filesystems are linked because the filesystems
        # contain the node that this filesystem group belongs to.
        if self.filesystems.exists():
            from maasserver.models.virtualblockdevice import VirtualBlockDevice

            VirtualBlockDevice.objects.create_or_update_for(self)

    def delete(self, force=False):
        """Delete from the database.

        :param force: Delete any related object that prevents this object
            from being deleted.
        """
        if self.is_lvm() and not force and self.virtual_devices.exists():
            raise ValidationError(
                "This volume group has logical volumes; it cannot be deleted."
            )

        self.virtual_devices.all().delete()

        # Possible that the virtual block device has already deleted the
        # filesystem group. Skip the call if no id is set.
        if self.id is not None:
            super().delete()

    def get_nice_name(self):
        """Return the nice name for the filesystem group.

        This is used when showing error or log messages.
        """
        if self.is_lvm():
            return "volume group"
        elif self.is_raid():
            return "RAID"
        elif self.is_bcache():
            return "Bcache"
        elif self.is_vmfs():
            return "VMFS"
        else:
            raise ValueError("Unknown group_type.")

    def get_name_prefix(self):
        """Return the prefix that should be used when setting the name of
        this FilesystemGroup."""
        if self.is_lvm():
            return "vg"
        elif self.is_raid():
            return "md"
        elif self.is_bcache():
            return "bcache"
        elif self.is_vmfs():
            return "vmfs"
        else:
            raise ValidationError("Unknown group_type.")

    def get_virtual_block_device_block_size(self):
        """Return the block size that should be used on a created
        `VirtualBlockDevice` for this filesystem group."""
        if self.is_lvm():
            # Default for logical volume in LVM is 4096.
            return 4096
        elif self.is_raid():
            # mdadm by default creates raid devices with 512 block size.
            return 512
        elif self.is_bcache():
            # Bcache uses the block_size of the backing device.
            return self.get_bcache_backing_filesystem().get_block_size()
        elif self.is_vmfs():
            # By default VMFS uses a 1MB block size.
            return 1024
        else:
            raise ValidationError("Unknown group_type.")


# Piston serializes objects based on the object class.
# Here we define a proxy classes so that we can specialize how all the
# different group types are serialized on the API.


class VolumeGroup(FilesystemGroup):
    """A volume group."""

    objects = VolumeGroupManager()

    class Meta:
        proxy = True

    def __init__(self, *args, **kwargs):
        if not args:
            kwargs["group_type"] = FILESYSTEM_GROUP_TYPE.LVM_VG
        super().__init__(*args, **kwargs)

    def update_block_devices_and_partitions(self, block_devices, partitions):
        """Update the block devices and partitions that are in this
        volume group.
        """
        self._update_block_devices(block_devices)
        self._update_partitions(partitions)
        self.save(force_update=True)

    def _update_block_devices(self, block_devices):
        """Update the block devices that are in this volume group."""
        # Circual imports.
        from maasserver.models.filesystem import Filesystem

        block_devices = list(block_devices)
        current_filesystems = self.filesystems.filter(partition__isnull=True)
        for filesystem in current_filesystems:
            block_device = filesystem.block_device
            if block_device in block_devices:
                block_devices.remove(block_device)
            else:
                filesystem.delete()
        for new_block_device in block_devices:
            Filesystem.objects.create(
                node_config=new_block_device.node_config,
                fstype=FILESYSTEM_TYPE.LVM_PV,
                block_device=new_block_device,
                filesystem_group=self,
            )

    def _update_partitions(self, partitions):
        """Update the partitions that are in this volume group."""
        # Circual imports.
        from maasserver.models.filesystem import Filesystem

        partitions = list(partitions)
        current_filesystems = self.filesystems.filter(
            block_device__isnull=True
        )
        for filesystem in current_filesystems:
            partition = filesystem.partition
            if partition in partitions:
                partitions.remove(partition)
            else:
                filesystem.delete()
        for new_partition in partitions:
            node_config = (
                new_partition.partition_table.block_device.node_config
            )
            Filesystem.objects.create(
                node_config=node_config,
                fstype=FILESYSTEM_TYPE.LVM_PV,
                partition=new_partition,
                filesystem_group=self,
            )

    def create_logical_volume(self, name, size, uuid=None):
        """Create a logical volume in this volume group."""
        from maasserver.models.virtualblockdevice import VirtualBlockDevice

        return VirtualBlockDevice.objects.create(
            node_config=self.get_node().current_config,
            name=name,
            uuid=uuid,
            size=self.get_lvm_free_space() if size is None else size,
            block_size=self.get_virtual_block_device_block_size(),
            filesystem_group=self,
        )


class RAID(FilesystemGroup):
    """A RAID."""

    objects = RAIDManager()

    class Meta:
        proxy = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.group_type not in FILESYSTEM_GROUP_RAID_TYPES:
            raise ValueError("group_type must be a valid RAID type.")

    def add_device(self, device, fstype):
        """Adds a device to the array, creates the correct filesystem."""
        from maasserver.models.filesystem import Filesystem

        if device.node_config != self.get_node().current_config:
            raise ValidationError(
                "Device needs to be attached to the same node config "
                "as the rest of the array."
            )
        elif device.get_effective_filesystem() is not None:
            raise ValidationError(
                "There is another filesystem on this device."
            )
        else:
            Filesystem.objects.create(
                node_config=device.node_config,
                block_device=device,
                fstype=fstype,
                filesystem_group=self,
            )
        return self

    def add_partition(self, partition, fstype):
        """Adds a partition to the array, creates the correct filesystem."""
        # Avoid circular import.
        from maasserver.models.filesystem import Filesystem

        node = self.get_node()
        if partition.get_node() != node:
            raise ValidationError(
                "Partition must be on a device from the same node as the rest "
                "of the array."
            )
        elif partition.get_effective_filesystem() is not None:
            raise ValidationError(
                "There is another filesystem on this partition."
            )
        else:
            Filesystem.objects.create(
                node_config=node.current_config,
                partition=partition,
                fstype=fstype,
                filesystem_group=self,
            )
        return self

    def remove_device(self, device):
        """Removes the device from the RAID, removes the RAID filesystem.

        Raises a ValidationError if the device is not part of the array or if
        the array becomes invalid with the deletion.
        """
        filesystem = device.get_effective_filesystem()
        if filesystem is None or filesystem.filesystem_group_id != self.id:
            raise ValidationError("Device does not belong to this array.")
        else:
            # If validation passes, delete the filesystem.
            self.filesystems.remove(filesystem)

        try:
            self.save(force_update=True)  # Force validation.
        except ValidationError:
            # If we had a ValidationError, we need to reattach the Filesystem
            # to the FilesystemGroup.
            self.filesystems.add(filesystem)
            raise
        else:
            # If validation passes, delete the filesystem.
            filesystem.delete()

        return self

    def remove_partition(self, partition):
        """Removes the partition from the RAID, removes the RAID filesystem.

        Raises a ValidationError if the device is not part of the array or if
        the array becomes invalid with the deletion.
        """
        filesystem = partition.get_effective_filesystem()
        if filesystem is None or filesystem.filesystem_group_id != self.id:
            raise ValidationError("Partition does not belong to this array.")
        elif filesystem is not None:
            self.filesystems.remove(filesystem)

        try:
            self.save(force_update=True)  # Force validation.
        except ValidationError:
            # If we had a ValidationError, we need to reattach the Filesystem
            # to the FilesystemGroup.
            self.filesystems.add(filesystem)
            raise
        else:
            # If validation passes, delete the filesystem.
            filesystem.delete()

        return self


class Bcache(FilesystemGroup):
    """A Bcache."""

    objects = BcacheManager()

    class Meta:
        proxy = True

    def __init__(self, *args, **kwargs):
        if not args:
            kwargs["group_type"] = FILESYSTEM_GROUP_TYPE.BCACHE
        super().__init__(*args, **kwargs)


class VMFS(FilesystemGroup):
    """A VMFS."""

    objects = VMFSManager()

    class Meta:
        proxy = True

    def __init__(self, *args, **kwargs):
        if not args:
            kwargs["group_type"] = FILESYSTEM_GROUP_TYPE.VMFS6
        super().__init__(*args, **kwargs)
