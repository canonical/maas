# Copyright 2014-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.core.exceptions import ValidationError
from django.db.models import CASCADE, CharField, ForeignKey

from maasserver import DefaultMeta
from maasserver.models.blockdevice import BlockDevice
from maasserver.utils.converters import human_readable_bytes


class PhysicalBlockDevice(BlockDevice):
    """A physical block device attached to a node."""

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

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

    def serialize(self):
        """Serialize the model so it can be detected outside of MAAS."""
        return {
            "id": self.id,
            "name": self.name,
            "id_path": self.id_path,
            "model": self.model,
            "serial": self.serial,
        }
