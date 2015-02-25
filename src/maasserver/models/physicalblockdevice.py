# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a nodes physical block device."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'PhysicalBlockDevice',
    ]


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

    def __unicode__(self):
        return '{model} S/N {serial} {size} attached to {node}'.format(
            model=self.model, serial=self.serial,
            size=human_readable_bytes(self.size), node=self.node)
