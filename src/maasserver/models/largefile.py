# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Large file storage."""

from django.db.models import BigIntegerField, CharField, Manager

from maasserver.fields import LargeObjectField
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class FileStorageManager(Manager):
    pass


class LargeFile(CleanSave, TimestampedModel):
    """Files that are stored in the large object storage.

    Only unique files are stored in the database, as only one sha256 value
    can exist per file. This provides data deduplication on the file level.

    Currently only used by `BootResourceFile`. This speeds up the import
    process by only saving unique files.

    :ivar sha256: Calculated SHA256 value of `content`.
    :ivar size: Current size of `content`.
    :ivar total_size: Final size of `content`. The data might currently
        be saving, so total_size could be larger than `size`. `size` should
        never be larger than `total_size`.
    :ivar content: File data.
    """

    objects = FileStorageManager()

    sha256 = CharField(max_length=64, unique=True, editable=False)

    size = BigIntegerField(default=0, editable=False)

    total_size = BigIntegerField(editable=False)

    # content is stored directly in the database, in the large object storage.
    # Max file storage size is 4TB.
    content = LargeObjectField()
