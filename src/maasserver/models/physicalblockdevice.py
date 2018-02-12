# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a nodes physical block device."""

__all__ = [
    'PhysicalBlockDevice',
    ]


from django.core.exceptions import ValidationError
from django.db.models import CharField
from maasserver import DefaultMeta
from maasserver.models.blockdevice import (
    BlockDevice,
    BlockDeviceManager,
)
from maasserver.utils.converters import human_readable_bytes


class PhysicalBlockDeviceManager(BlockDeviceManager):
    """Manager for `PhysicalBlockDevice` class."""

    def number_of_physical_devices_for(self, node):
        """Return count of `PhysicalBlockDevice` that belong to `node`."""
        return self.filter(node=node).count()

    def total_size_of_physical_devices_for(self, node):
        """Return total size of all `PhysicalBlockDevice` for the `node`."""
        return sum(device.size for device in self.filter(node=node))


class PhysicalBlockDevice(BlockDevice):
    """A physical block device attached to a node."""

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = PhysicalBlockDeviceManager()

    model = CharField(
        max_length=255, blank=True, null=False,
        help_text="Model name of block device.")

    serial = CharField(
        max_length=255, blank=True, null=False,
        help_text="Serial number of block device.")

    firmware_version = CharField(
        max_length=255, blank=True, null=True,
        help_text="Firmware version of block device.")

    def clean(self):
        if not self.id_path and not (self.model and self.serial):
            raise ValidationError(
                "serial/model are required if id_path is not provided.")
        super(PhysicalBlockDevice, self).clean()

    def __str__(self):
        return '{model} S/N {serial} {size} attached to {node}'.format(
            model=self.model, serial=self.serial,
            size=human_readable_bytes(self.size), node=self.node)
