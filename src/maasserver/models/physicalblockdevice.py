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
            node_config = kwargs["node_config"]
            node = node_config.node
            numa_node = kwargs.get("numa_node")
            if numa_node:
                if numa_node.node != node:
                    raise ValidationError(
                        "Node from NUMA node is different from the one from config."
                    )
            else:
                kwargs["numa_node"] = node.default_numanode
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
            node=self.get_node(),
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
