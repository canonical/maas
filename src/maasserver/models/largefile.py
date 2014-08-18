# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Large file storage."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'LargeFile',
    ]

import os

from django.db.models import (
    BigIntegerField,
    CharField,
    Manager,
    )
from django.db.models.signals import post_delete
from django.dispatch import receiver
from maasserver import DefaultMeta
from maasserver.fields import LargeObjectField
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import get_one


class FileStorageManager(Manager):
    """Manager for `LargeFile` objects."""

    def has_file(self, sha256):
        """True if file with sha256 value exists."""
        return self.filter(sha256=sha256).exists()

    def get_file(self, sha256):
        """Return file based on SHA256 value."""
        return get_one(self.filter(sha256=sha256))


class LargeFile(CleanSave, TimestampedModel):
    """Files that are stored in the large object storage.

    Only unique files are stored in the database, as only one sha256 value
    can exist per file. This provides data deduplication on the file level.

    Currently only used by `BootResourceFile`. This speeds up the import
    process by only saving unique files.

    :ivar sha256: Calculated SHA256 value of `content`.
    :ivar total_size: Final size of `content`. The data might currently
        be saving, so total_size could be larger than `size`. `size` should
        never be larger than `total_size`.
    :ivar content: File data.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = FileStorageManager()

    sha256 = CharField(max_length=64, unique=True, editable=False)

    total_size = BigIntegerField(editable=False)

    # content is stored directly in the database, in the large object storage.
    # Max file storage size is 4TB.
    content = LargeObjectField()

    @property
    def size(self):
        """Size of content."""
        with self.content.open('rb') as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
        return size

    @property
    def progress(self):
        """Precentage of `content` saved."""
        if self.size <= 0:
            # Handle division of zero
            return 0
        return self.total_size / float(self.size)

    @property
    def complete(self):
        """`content` has been completely saved."""
        return (self.total_size == self.size)

    def delete(self, *args, **kwargs):
        """Delete this object.

        Important: You must remove your reference to this object or
        it will not delete. Object will only be deleted if no other objects are
        referencing this object.
        """
        links = [
            rel.get_accessor_name()
            for rel in self._meta.get_all_related_objects()
            ]
        for link in links:
            if getattr(self, link).exists():
                return
        super(LargeFile, self).delete(*args, **kwargs)


@receiver(post_delete)
def delete_large_object(sender, instance, **kwargs):
    """Delete the large object when the `LargeFile` is deleted.

    This is done using the `post_delete` signal instead of overriding delete
    on `LargeFile`, so it works correctly for both the model and
    `QuerySet`.
    """
    if sender == LargeFile:
        if instance.content is not None:
            instance.content.unlink()
