# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a nodes block device."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'BlockDevice',
    ]


from django.db.models import (
    BigIntegerField,
    CharField,
    FilePathField,
    ForeignKey,
    IntegerField,
    )
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.converters import human_readable_bytes


class BlockDevice(CleanSave, TimestampedModel):
    """A block device attached to a node."""

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""
        unique_together = ("node", "path")

    node = ForeignKey('Node', null=False, editable=False)

    name = CharField(
        max_length=255, blank=False,
        help_text="Name of block device. (e.g. sda)")

    path = FilePathField(
        blank=False,
        help_text="Path of block device. (e.g. /dev/sda)")

    size = BigIntegerField(
        blank=False, null=False,
        help_text="Size of block device in bytes.")

    block_size = IntegerField(
        blank=False, null=False,
        help_text="Size of a block on the device in bytes.")

    def display_size(self, include_suffix=True):
        return human_readable_bytes(self.size, include_suffix=include_suffix)
