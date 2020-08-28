# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a nodes iscsi block device."""

__all__ = ["ISCSIBlockDevice"]

from curtin.block.iscsi import IscsiDisk
from django.core.exceptions import ValidationError
from django.db.models import CharField

from maasserver import DefaultMeta
from maasserver.models.blockdevice import BlockDevice, BlockDeviceManager


def get_iscsi_target(target):
    """Formats the iscsi target to always include a 'iscsi:' at the beginning."""
    if not target.startswith("iscsi:"):
        return "iscsi:%s" % target
    else:
        return target


def validate_iscsi_target(target):
    """Validates that the `target` conforms to curtins requirement of
    RFC4173."""
    try:
        # Curtin requires that it start with 'iscsi:'. The user can either
        # provide it or not, MAAS will do the correct thing.
        IscsiDisk(get_iscsi_target(target))
    except ValueError as exc:
        raise ValidationError(str(exc))


class ISCSIBlockDeviceManager(BlockDeviceManager):
    """Manager for `ISCSIBlockDevice` class."""

    def total_size_of_iscsi_devices_for(self, node):
        """Return total size of all `ISCSIBlockDevice` for the `node`."""
        return sum(device.size for device in self.filter(node=node))


class ISCSIBlockDevice(BlockDevice):
    """An iscsi block device attached to a node."""

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = ISCSIBlockDeviceManager()

    target = CharField(
        max_length=4096,
        unique=True,
        null=False,
        blank=False,
        editable=True,
        validators=[validate_iscsi_target],
    )

    def __str__(self):
        return "{target} attached to {node}".format(
            target=self.target, node=self.node
        )

    def save(self, *args, **kwargs):
        # Normilize the target to always include a 'iscsi:' at the start.
        self.target = get_iscsi_target(self.target)
        return super().save(*args, **kwargs)
