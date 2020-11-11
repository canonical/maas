# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a nodes physical block device."""


from django.core.exceptions import ValidationError
from django.db.models import CASCADE, CharField, ForeignKey, SET_NULL

from maasserver import DefaultMeta
from maasserver.models.blockdevice import BlockDevice, BlockDeviceManager
from maasserver.models.podstoragepool import PodStoragePool
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
        max_length=255,
        blank=True,
        null=False,
        help_text="Model name of block device.",
    )

    serial = CharField(
        max_length=255,
        blank=True,
        null=False,
        help_text="Serial number of block device.",
    )

    firmware_version = CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Firmware version of block device.",
    )

    # Only used when the machine is composed in a Pod that supports
    # storage pool.
    storage_pool = ForeignKey(
        PodStoragePool,
        blank=True,
        null=True,
        on_delete=SET_NULL,
        related_name="block_devices",
        help_text="Storage pool that this block device belongs to",
    )

    numa_node = ForeignKey(
        "NUMANode", related_name="blockdevices", on_delete=CASCADE
    )

    def __init__(self, *args, **kwargs):
        if kwargs:
            # only check when kwargs are passed, which is the normal case when
            # objects are created. If they're loaded from the DB, args get
            # passed instead.
            node = kwargs.get("node")
            numa_node = kwargs.get("numa_node")
            if node and numa_node:
                raise ValidationError("Can't set both node and numa_node")
            if not numa_node:
                kwargs["numa_node"] = node.default_numanode
            elif not node:
                kwargs["node"] = numa_node.node
        super().__init__(*args, **kwargs)

    def clean(self):
        if not self.id_path and not (self.model and self.serial):
            raise ValidationError(
                "serial/model are required if id_path is not provided."
            )
        super().clean()

    def __str__(self):
        return "{model} S/N {serial} {size} attached to {node}".format(
            model=self.model,
            serial=self.serial,
            size=human_readable_bytes(self.size),
            node=self.node,
        )
