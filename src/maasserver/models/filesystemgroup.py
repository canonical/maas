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

from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db.models import CharField
from maasserver import DefaultMeta
from maasserver.enum import FILESYSTEM_GROUP_TYPE_CHOICES
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class FilesystemGroup(CleanSave, TimestampedModel):
    """A filesystem group. Contains a set of filesystems that create
    a virtual block device. E.g. LVM Volume Group.

    :ivar uuid: UUID of the filesystem group.
    :ivar group_type: Type of filesystem group.
    :ivar create_params: Parameters that can be passed during the create
        command when the filesystem group is created.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    uuid = CharField(
        max_length=36, unique=True, null=False, blank=False, editable=False)

    group_type = CharField(
        max_length=20, choices=FILESYSTEM_GROUP_TYPE_CHOICES)

    name = CharField(
        max_length=255, null=False, blank=False)

    create_params = CharField(
        max_length=255, null=True, blank=True)

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
        return sum(
            filesystem.get_size()
            for filesystem in self.filesystems.all()
            )

    def clean(self, *args, **kwargs):
        super(FilesystemGroup, self).clean(*args, **kwargs)

        # We allow the initial save to not have filesystems linked, any
        # additional saves required filesystems linked. This is because the
        # object needs to exist in the database before the filesystems can
        # be linked.
        if not self.id:
            return

        # Must at least have a filesystem added to the group.
        if self.filesystems.count() == 0:
            raise ValidationError(
                "At least one filesystem must have been added.")

        # All filesystems must belong all to the same node.
        nodes = {
            filesystem.get_node()
            for filesystem in self.filesystems.all()
            }
        if len(nodes) > 1:
            raise ValidationError(
                "All added filesystems must belong to the same node.")

    def save(self, *args, **kwargs):
        if not self.uuid:
            self.uuid = uuid4()
        super(FilesystemGroup, self).save(*args, **kwargs)
