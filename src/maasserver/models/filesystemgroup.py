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

from django.core.exceptions import ValidationError
from django.db.models import (
    CharField,
    Manager,
    Q,
)
from maasserver import DefaultMeta
from maasserver.enum import (
    FILESYSTEM_GROUP_RAID_TYPES,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_GROUP_TYPE_CHOICES,
    FILESYSTEM_TYPE,
)
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class FilesystemGroupManager(Manager):
    """Manager for `FilesystemGroup` class."""

    def get_filesystem_groups_for(self, block_device):
        """Return all the `FilesystemGroup`s that are related to
        block_device."""
        partition_query = Q(
            filesystems__partition__partition_table__block_device=block_device)
        return self.filter(
            Q(filesystems__block_device=block_device) |
            partition_query).distinct()


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
            return self.virtual_devices.all()[0]

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
            return min_size
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
        raise ValueError("Unknown raid type: %s" % self.group_type)

    def get_bcache_backing_filesystem(self):
        """Return the filesystem that is the backing device for the Bcache."""
        for filesystem in self.filesystems.all():
            if filesystem.fstype == FILESYSTEM_TYPE.BCACHE_BACKING:
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

    def get_lvm_allocated_size(self):
        """Returns the space already allocated to virtual block devices.

        Calculated from the total size of all virtual block devices in this
        group.
        """
        return sum(
            logical_volume.size
            for logical_volume in self.virtual_devices.all()
        )

    def get_lvm_free_space(self):
        """Returns the total unallocated space on this FilesystemGroup"""
        return self.get_lvm_size() - self.get_lvm_allocated_size()

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
            # RAID 0 can only contain 2 RAID filesystems and no spares are
            # allowed.
            if num_raid != 2 or num_raid_spare != 0:
                raise ValidationError(
                    "RAID level 0 must have exactly 2 raid devices and "
                    "no spares.")
        elif self.group_type == FILESYSTEM_GROUP_TYPE.RAID_1:
            # RAID 1 must have at least 2 RAID filesystems and should not
            # have any spares.
            if num_raid < 2 or num_raid_spare != 0:
                raise ValidationError(
                    "RAID level 1 must have atleast 2 raid devices and "
                    "no spares.")
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

    def save(self, *args, **kwargs):
        # Prevent the group_type from changing. This is not supported and will
        # break the linked filesystems and the created virtual block device(s).
        if self.pk is not None:
            orig = FilesystemGroup.objects.get(pk=self.pk)
            if orig.group_type != self.group_type:
                raise ValidationError(
                    "Cannot change the group_type of a FilesystemGroup.")

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

    def get_virtual_block_device_prefix(self):
        """Return the prefix that should be used when creating a linked virtual
        block device."""
        if self.is_lvm():
            return "lv"
        elif self.is_raid():
            return "md"
        elif self.is_bcache():
            return "bcache"
        else:
            raise ValueError("Unknown group_type.")

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
            raise ValueError("Unknown group_type.")
