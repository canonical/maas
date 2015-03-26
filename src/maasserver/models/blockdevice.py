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

from collections import Iterable

from django.db.models import (
    BigIntegerField,
    CharField,
    FilePathField,
    ForeignKey,
    IntegerField,
    Manager,
)
from djorm_pgarray.fields import ArrayField
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.converters import human_readable_bytes
from maasserver.utils.orm import psql_array


class BlockDeviceManager(Manager):
    """Manager for `BlockDevice` class."""

    def filter_by_tags(self, tags):
        if not isinstance(tags, list):
            if isinstance(tags, unicode) or not isinstance(tags, Iterable):
                raise ValueError("Requires iterable object to filter.")
            tags = list(tags)
        tags_where, tags_params = psql_array(tags, sql_type="text")
        where_contains = (
            '"maasserver_blockdevice"."tags"::text[] @> %s' % tags_where)
        return self.extra(
            where=[where_contains], params=tags_params)


class BlockDevice(CleanSave, TimestampedModel):
    """A block device attached to a node."""

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""
        unique_together = ("node", "path")
        ordering = ["id"]

    objects = BlockDeviceManager()

    node = ForeignKey('Node', null=False, editable=False)

    name = CharField(
        max_length=255, blank=False,
        help_text="Name of block device. (e.g. sda)")

    path = FilePathField(
        blank=False,
        help_text="Path of block device. (e.g. /dev/sda)")

    id_path = FilePathField(
        blank=True, null=True,
        help_text="Path of by-id alias. (e.g. /dev/disk/by-id/wwn-0x50004...)")

    size = BigIntegerField(
        blank=False, null=False,
        help_text="Size of block device in bytes.")

    block_size = IntegerField(
        blank=False, null=False,
        help_text="Size of a block on the device in bytes.")

    tags = ArrayField(
        dbtype="text", blank=True, null=False, default=[])

    def display_size(self, include_suffix=True):
        return human_readable_bytes(self.size, include_suffix=include_suffix)

    def add_tag(self, tag):
        """Add tag to block device."""
        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag):
        """Remove tag from block device."""
        if tag in self.tags:
            self.tags.remove(tag)

    def __unicode__(self):
        return '{size} attached to {node}'.format(
            size=human_readable_bytes(self.size),
            node=self.node)
