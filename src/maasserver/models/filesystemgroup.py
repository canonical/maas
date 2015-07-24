# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a filesystem group. Contains a set of filesystems that create
a virtual block device. E.g. LVM Volume Group."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'FilesystemGroup',
    ]

from collections import Counter
from uuid import uuid4

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.db.models import (
    CharField,
    Manager,
    Q,
)
from django.http import Http404
from django.shortcuts import get_object_or_404
from maasserver import DefaultMeta
from maasserver.enum import (
    CACHE_MODE_TYPE,
    CACHE_MODE_TYPE_CHOICES,
    FILESYSTEM_GROUP_RAID_TYPES,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_GROUP_TYPE_CHOICES,
    FILESYSTEM_TYPE,
)
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import get_one


class BaseFilesystemGroupManager(Manager):
    """A utility to manage the collection of FilesystemGroup."""

    extra_filters = {}

    def get_queryset(self):
        return super(
            BaseFilesystemGroupManager,
            self).get_queryset().filter(**self.extra_filters)

    def get_object_or_404(
            self, system_id, filesystem_group_id, user, perm):
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
        partition_query = Q(
            filesystems__partition__partition_table__block_device=block_device)
        return self.filter(
            Q(filesystems__block_device=block_device) |
            partition_query).distinct()

    def filter_by_node(self, node):
        """Return all `FilesystemGroup` that are related to node."""
        partition_query = Q(**{
            "filesystems__partition__partition_table__"
            "block_device__node": node,
            })
        return self.filter(
            Q(filesystems__block_device__node=node) |
            partition_query).distinct()

    def get_available_name_for(self, filesystem_group):
        """Return an available name that can be used for a `VirtualBlockDevice`
        based on the `filesystem_group`'s group_type and other block devices
        on the node.
        """
        prefix = filesystem_group.get_name_prefix()
        node = filesystem_group.get_node()
        idx = -1
        for filesystem_group in self.filter_by_node(
                node).filter(name__startswith=prefix):
            name = filesystem_group.name.replace(prefix, "")
            try:
                name_idx = int(name)
            except ValueError:
                pass
            else:
                idx = max(idx, name_idx)
        return "%s%s" % (prefix, idx + 1)


class FilesystemGroupManager(BaseFilesystemGroupManager):
    """All the FilesystemGroup objects together."""


class VolumeGroupManager(BaseFilesystemGroupManager):
    """Volume groups."""

    extra_filters = {'group_type': FILESYSTEM_GROUP_TYPE.LVM_VG}

    def create_volume_group(self, name, block_devices, partitions, uuid=None):
        """Create a `VolumeGroup` with the list of block devices and
        partitions."""
        # Circual imports.
        from maasserver.models.filesystem import Filesystem
        volume_group = VolumeGroup.objects.create(name=name, uuid=uuid)
        for block_device in block_devices:
            Filesystem.objects.create(
                fstype=FILESYSTEM_TYPE.LVM_PV, block_device=block_device,
                filesystem_group=volume_group)
        for partition in partitions:
            Filesystem.objects.create(
                fstype=FILESYSTEM_TYPE.LVM_PV, partition=partition,
                filesystem_group=volume_group)
        volume_group.save()
        return volume_group


class RAIDManager(BaseFilesystemGroupManager):
    """RAID groups"""

    extra_filters = {'group_type__in': FILESYSTEM_GROUP_RAID_TYPES}

    def create_raid(self, level, name=None, uuid=None, block_devices=[],
                    partitions=[], spare_devices=[], spare_partitions=[]):

        # Avoid circular import issues
        from maasserver.models.filesystem import Filesystem

        # Create a FilesystemGroup for this RAID
        raid = RAID(name=name, group_type=level, uuid=uuid)
        raid.save()

        for block_device in block_devices:
            Filesystem.objects.create(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=block_device,
                filesystem_group=raid)
        for partition in partitions:
            Filesystem.objects.create(
                fstype=FILESYSTEM_TYPE.RAID,
                partition=partition,
                filesystem_group=raid)
        for block_device in spare_devices:
            Filesystem.objects.create(
                fstype=FILESYSTEM_TYPE.RAID_SPARE,
                block_device=block_device,
                filesystem_group=raid)
        for partition in spare_partitions:
            Filesystem.objects.create(
                fstype=FILESYSTEM_TYPE.RAID_SPARE,
                partition=partition,
                filesystem_group=raid)
        raid.save()
        return raid


class BcacheManager(BaseFilesystemGroupManager):
    """Bcache groups"""

    extra_filters = {'group_type': FILESYSTEM_GROUP_TYPE.BCACHE}

    def validate_bcache_creation_parameters(
            self, cache_mode, cache_device, cache_partition,
            backing_device, backing_partition, validate_mode=True):
        """Validate bcache creation parameters. Raises ValidationErrors as
        needed. We don't always need to validate the mode, so, there is an
        option for that."""

        if validate_mode and cache_mode not in (
                CACHE_MODE_TYPE.WRITEBACK, CACHE_MODE_TYPE.WRITETHROUGH,
                CACHE_MODE_TYPE.WRITEAROUND):
            raise ValidationError('Invalid cache mode: %s' % cache_mode)

        if cache_device and cache_partition:
            raise ValidationError(
                'A Bcache can have either a caching device or partition.')

        if backing_device and backing_partition:
            raise ValidationError(
                'A Bcache can have either a backing device or partition.')

        if not cache_device and not cache_partition:
            raise ValidationError(
                'Either cache_device or cache_partition must be '
                'specified.')

        if not backing_device and not backing_partition:
            raise ValidationError(
                'Either backing_device or backing_partition must be '
                'specified.')

    def create_bcache(
            self, name=None, uuid=None, cache_device=None,
            cache_partition=None, backing_device=None,
            backing_partition=None, cache_mode=None):
        """Creates a bcache of type `cache_type` using the desired cache and
        backing elements."""

        self.validate_bcache_creation_parameters(
            cache_mode, cache_device, cache_partition, backing_device,
            backing_partition)

        # Avoid circular import issues
        from maasserver.models.filesystem import Filesystem

        # Create filesystems on the target devices and partitions
        if cache_device is not None:
            cache_filesystem = Filesystem.objects.create(
                block_device=cache_device,
                fstype=FILESYSTEM_TYPE.BCACHE_CACHE)
        elif cache_partition is not None:
            cache_filesystem = Filesystem.objects.create(
                partition=cache_partition,
                fstype=FILESYSTEM_TYPE.BCACHE_CACHE)

        if backing_device is not None:
            backing_filesystem = Filesystem(
                block_device=backing_device,
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING)
        elif backing_partition is not None:
            backing_filesystem = Filesystem(
                partition=backing_partition,
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING)

        # Setup the cache FilesystemGroup and attach the filesystems to it.
        bcache_filesystem_group = FilesystemGroup.objects.create(
            name=name,
            uuid=uuid,
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_mode=cache_mode)

        cache_filesystem.filesystem_group = bcache_filesystem_group
        cache_filesystem.save()

        backing_filesystem.filesystem_group = bcache_filesystem_group
        backing_filesystem.save()

        bcache_filesystem_group.save()

        return bcache_filesystem_group


class FilesystemGroup(CleanSave, TimestampedModel):
    """A filesystem group. Contains a set of filesystems that create
    a virtual block device. E.g. LVM Volume Group.

    :ivar uuid: UUID of the filesystem group.
    :ivar group_type: Type of filesystem group.
    :ivar name: Name of the filesytem group.
    :ivar create_params: Parameters that can be passed during the create
        command when the filesystem group is created.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = FilesystemGroupManager()

    uuid = CharField(
        max_length=36, unique=True, null=False, blank=False, editable=False)

    group_type = CharField(
        max_length=20, null=False, blank=False,
        choices=FILESYSTEM_GROUP_TYPE_CHOICES)

    name = CharField(
        max_length=255, null=False, blank=False)

    create_params = CharField(
        max_length=255, null=True, blank=True)

    cache_mode = CharField(
        max_length=20, null=True, blank=True,
        choices=CACHE_MODE_TYPE_CHOICES)

    def __unicode__(self):
        return '%s device %s %d' % (self.group_type, self.name, self.id)

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
                "group_type = LVM_VG.")
        else:
            # Return the first `VirtualBlockDevice` since it is the only one.
            # Using 'all()' instead of 'first()' so that if it was precached
            # that cache will be used.
            return get_one(self.virtual_devices.all())

    def get_node(self):
        """`Node` this filesystem group belongs to."""
        if self.filesystems.count() == 0:
            return None
        return self.filesystems.first().get_node()

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
        else:
            return 0

    def get_lvm_size(self):
        """Size of this LVM volume group.

        Calculated from the total size of all filesystems in this group.
        Its not calculated from its virtual_block_device size.

        Note: Should only be called when the `group_type` is LVM_VG.
        """
        return sum(
            filesystem.get_size()
            for filesystem in self.filesystems.all()
            )

    def get_smallest_filesystem_size(self):
        """Return the smallest filesystem size."""
        filesystems = list(self.filesystems.all())
        if len(filesystems) == 0:
            return 0
        else:
            return min(
                filesystem.get_size()
                for filesystem in filesystems
                )

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
            return min_size * self.filesystems.count()
        elif self.group_type == FILESYSTEM_GROUP_TYPE.RAID_1:
            return min_size
        else:
            num_raid = len([
                fstype
                for fstype in self._get_all_fstypes()
                if fstype == FILESYSTEM_TYPE.RAID
                ])
            if (self.group_type == FILESYSTEM_GROUP_TYPE.RAID_4 or
                    self.group_type == FILESYSTEM_GROUP_TYPE.RAID_5):
                return min_size * (num_raid - 1)
            elif self.group_type == FILESYSTEM_GROUP_TYPE.RAID_6:
                return min_size * (num_raid - 2)
        raise ValidationError("Unknown raid type: %s" % self.group_type)

    def get_bcache_backing_filesystem(self):
        """Return the filesystem that is the backing device for the Bcache."""
        for filesystem in self.filesystems.all():
            if filesystem.fstype == FILESYSTEM_TYPE.BCACHE_BACKING:
                return filesystem
        return None

    def get_bcache_cache_filesystem(self):
        """Return the filesystem that is the cache device for the Bcache."""
        for filesystem in self.filesystems.all():
            if filesystem.fstype == FILESYSTEM_TYPE.BCACHE_CACHE:
                return filesystem
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
            skip_volumes=skip_volumes)

    def clean(self, *args, **kwargs):
        super(FilesystemGroup, self).clean(*args, **kwargs)

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
                "At least one filesystem must have been added.")

        # All filesystems must belong all to the same node.
        nodes = {
            filesystem.get_node()
            for filesystem in filesystems
            }
        if len(nodes) > 1:
            raise ValidationError(
                "All added filesystems must belong to the same node.")

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

    def _get_all_fstypes(self, filesystems=None):
        """Return list of all filesystem types attached."""
        # Grab all filesystems so that if the filesystems have been
        # precached it will be used. This prevents extra database queries.
        if filesystems is None:
            filesystems = list(self.filesystems.all())
        return [
            filesystem.fstype
            for filesystem in filesystems
        ]

    def _validate_lvm(self, filesystems=None):
        """Validate attached filesystems are correct type for LVM_VG.
        """
        if not self.is_lvm():
            return
        unique_fstypes = set(self._get_all_fstypes(filesystems=filesystems))
        if unique_fstypes != set([FILESYSTEM_TYPE.LVM_PV]):
            raise ValidationError(
                "Volume group can only contain lvm physical volumes.")

    def _validate_raid(self, filesystems=None):
        """Validate attached filesystems are correct count and type for RAID.
        """
        if not self.is_raid():
            return
        fstypes = self._get_all_fstypes(filesystems=filesystems)
        num_raid = len([
            fstype
            for fstype in fstypes
            if fstype == FILESYSTEM_TYPE.RAID
            ])
        num_raid_spare = len([
            fstype
            for fstype in fstypes
            if fstype == FILESYSTEM_TYPE.RAID_SPARE
            ])
        if self.group_type == FILESYSTEM_GROUP_TYPE.RAID_0:
            # RAID 0 can contain 2 or more RAID filesystems and no spares are
            # allowed.
            if num_raid < 2 or num_raid_spare != 0:
                raise ValidationError(
                    "RAID level 0 must have at least 2 raid devices and "
                    "no spares.")
        elif self.group_type == FILESYSTEM_GROUP_TYPE.RAID_1:
            # RAID 1 must have at least 2 RAID filesystems.
            if num_raid < 2:
                raise ValidationError(
                    "RAID level 1 must have at least 2 raid devices and "
                    "any number of spares.")
        elif self.group_type == FILESYSTEM_GROUP_TYPE.RAID_4:
            # RAID 4 must have at least 3 RAID filesystems, but can have
            # spares.
            if num_raid < 3:
                raise ValidationError(
                    "RAID level 4 must have atleast 3 raid devices and "
                    "any number of spares.")
        elif self.group_type == FILESYSTEM_GROUP_TYPE.RAID_5:
            # RAID 5 must have at least 3 RAID filesystems, but can have
            # spares.
            if num_raid < 3:
                raise ValidationError(
                    "RAID level 5 must have atleast 3 raid devices and "
                    "any number of spares.")
        elif self.group_type == FILESYSTEM_GROUP_TYPE.RAID_6:
            # RAID 6 must have at least 4 RAID filesystems, but can have
            # spares.
            if num_raid < 4:
                raise ValidationError(
                    "RAID level 6 must have atleast 4 raid devices and "
                    "any number of spares.")
        num_raid_invalid = len([
            fstype
            for fstype in fstypes
            if (fstype != FILESYSTEM_TYPE.RAID and
                fstype != FILESYSTEM_TYPE.RAID_SPARE)
            ])
        if num_raid_invalid > 0:
            raise ValidationError(
                "RAID can only contain raid device and raid spares.")

    def _validate_bcache(self, filesystems=None):
        """Validate attached filesystems are correct type for BCACHE.
        """
        if not self.is_bcache():
            return
        fstypes_counter = Counter(
            self._get_all_fstypes(filesystems=filesystems))
        valid_counter = Counter(
            [FILESYSTEM_TYPE.BCACHE_CACHE, FILESYSTEM_TYPE.BCACHE_BACKING])
        if fstypes_counter != valid_counter:
            raise ValidationError(
                "Bcache must contain one cache and one backing device.")
        if self.cache_mode is None:
            raise ValidationError('Cache mode must be set for Bcache groups.')

    def save(self, *args, **kwargs):
        # Prevent the group_type from changing. This is not supported and will
        # break the linked filesystems and the created virtual block device(s).
        if self.pk is not None:
            orig = FilesystemGroup.objects.get(pk=self.pk)
            if orig.group_type != self.group_type:
                raise ValidationError(
                    "Cannot change the group_type of a FilesystemGroup.")

        # Prevent saving if the size of the volume group is now smaller than
        # the total size of logical volumes.
        if (self.group_type == FILESYSTEM_GROUP_TYPE.LVM_VG and
                self.get_lvm_free_space() < 0):
            raise ValidationError(
                "Volume group cannot be smaller than its logical volumes.")

        # Set the name correctly based on the type and generate a new UUID
        # if needed.
        if self.group_type is not None and self.name is None:
            self.name = FilesystemGroup.objects.get_available_name_for(self)
        if not self.uuid:
            self.uuid = uuid4()
        super(FilesystemGroup, self).save(*args, **kwargs)

        # Update or create the virtual block device when the filesystem group
        # is saved. Does nothing if group_type is LVM_VG. Virtual block device
        # is not created until filesystems are linked because the filesystems
        # contain the node that this filesystem group belongs to.
        if self.filesystems.count() > 0:
            from maasserver.models.virtualblockdevice import VirtualBlockDevice
            VirtualBlockDevice.objects.create_or_update_for(self)

    def delete(self, force=False):
        """Delete from the database.

        :param force: Delete any related object that prevents this object
            from being deleted.
        """
        if self.is_lvm():
            if self.virtual_devices.count() > 0:
                if force:
                    # Delete the linked virtual block devices, since the
                    # deletion of this object is forced.
                    self.virtual_devices.all().delete()
                else:
                    # Don't allow the filesystem group to be deleted if virtual
                    # block devices are linked. You cannot delete a volume
                    # group that has logical volumes.
                    raise ValidationError(
                        "This volume group has logical volumes; it cannot be "
                        "deleted.")
        else:
            # For the other types we delete the virtual block device.
            virtual_device = self.virtual_device
            if virtual_device is not None:
                self.virtual_device.delete()

        # Possible that the virtual block device has already deleted the
        # filesystem group. Skip the call if no id is set.
        if self.id is not None:
            super(FilesystemGroup, self).delete()

    def get_name_prefix(self):
        """Return the prefix that should be used when setting the name of
        this FilesystemGroup."""
        if self.is_lvm():
            return "vg"
        elif self.is_raid():
            return "md"
        elif self.is_bcache():
            return "bcache"
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
        super(VolumeGroup, self).__init__(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, *args, **kwargs)

    def update_block_devices_and_partitions(self, block_devices, partitions):
        """Update the block devices and partitions that are in this
        volume group.
        """
        self._update_block_devices(block_devices)
        self._update_partitions(partitions)
        self.save()

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
                fstype=FILESYSTEM_TYPE.LVM_PV, block_device=new_block_device,
                filesystem_group=self)

    def _update_partitions(self, partitions):
        """Update the partitions that are in this volume group."""
        # Circual imports.
        from maasserver.models.filesystem import Filesystem
        partitions = list(partitions)
        current_filesystems = self.filesystems.filter(
            block_device__isnull=True)
        for filesystem in current_filesystems:
            partition = filesystem.partition
            if partition in partitions:
                partitions.remove(partition)
            else:
                filesystem.delete()
        for new_partition in partitions:
            Filesystem.objects.create(
                fstype=FILESYSTEM_TYPE.LVM_PV, partition=new_partition,
                filesystem_group=self)

    def create_logical_volume(self, name, size, uuid=None):
        """Create a logical volume in this volume group."""
        # Circular imports.
        from maasserver.models.virtualblockdevice import VirtualBlockDevice
        return VirtualBlockDevice.objects.create(
            node=self.get_node(),
            name=name, uuid=uuid,
            size=size, block_size=self.get_virtual_block_device_block_size(),
            filesystem_group=self)


class RAID(FilesystemGroup):
    """A RAID."""

    objects = RAIDManager()

    class Meta:
        proxy = True

    def __init__(self, *args, **kwargs):
        super(RAID, self).__init__(*args, **kwargs)
        if self.group_type not in FILESYSTEM_GROUP_RAID_TYPES:
            raise ValueError("group_type must be a valid RAID type.")

    def add_device(self, device, fstype):
        """Adds a device to the array, creates the correct filesystem."""
        # Avoid circular import.
        from maasserver.models.filesystem import Filesystem
        if device.node != self.get_node():
            raise ValidationError(
                "Device needs to be from the same node as the rest of the "
                "array.")
        elif device.filesystem is not None:
            raise ValidationError(
                "There is another filesystem on this device.")
        else:
            Filesystem.objects.create(
                block_device=device, fstype=fstype, filesystem_group=self)
        return self

    def add_partition(self, partition, fstype):
        """Adds a partition to the array, creates the correct filesystem."""
        # Avoid circular import.
        from maasserver.models.filesystem import Filesystem
        if partition.get_node() != self.get_node():
            raise ValidationError(
                "Partition must be on a device from the same node as the rest "
                "of the array.")
        elif partition.filesystem is not None:
            raise ValidationError(
                "There is another filesystem on this partition.")
        else:
            Filesystem.objects.create(
                partition=partition, fstype=fstype, filesystem_group=self)
        return self

    def remove_device(self, device):
        """Removes the device from the RAID, removes the RAID filesystem.

        Raises a ValidationError if the device is not part of the array or if
        the array becomes invalid with the deletion.
        """
        if (device.filesystem is None
                or device.filesystem.filesystem_group_id != self.id):
            raise ValidationError("Device does not belong to this array.")
        else:
            # If validation passes, delete the filesystem.
            self.filesystems.remove(device.filesystem)

        try:
            self.save()  # Force validation.
        except ValidationError:
            # If we had a ValidationError, we need to reattach the Filesystem
            # to the FilesystemGroup.
            self.filesystems.add(device.filesystem)
            raise
        else:
            # If validation passes, delete the filesystem.
            device.filesystem.delete()

        return self

    def remove_partition(self, partition):
        """Removes the partition from the RAID, removes the RAID filesystem.

        Raises a ValidationError if the device is not part of the array or if
        the array becomes invalid with the deletion.
        """
        if (partition.filesystem is None
                or partition.filesystem.filesystem_group_id != self.id):
            raise ValidationError("Partition does not belong to this array.")
        elif partition.filesystem is not None:
            self.filesystems.remove(partition.filesystem)

        try:
            self.save()  # Force validation.
        except ValidationError:
            # If we had a ValidationError, we need to reattach the Filesystem
            # to the FilesystemGroup.
            self.filesystems.add(partition.filesystem)
            raise
        else:
            # If validation passes, delete the filesystem.
            partition.filesystem.delete()

        return self


class Bcache(FilesystemGroup):
    """A Bcache."""

    objects = BcacheManager()

    class Meta:
        proxy = True

    def __init__(self, *args, **kwargs):
        super(Bcache, self).__init__(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE, *args, **kwargs)
