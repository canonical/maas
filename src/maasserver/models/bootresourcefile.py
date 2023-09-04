# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Resource File."""


from django.db.models import (
    BigIntegerField,
    CASCADE,
    CharField,
    ForeignKey,
    JSONField,
)

from maasserver.enum import (
    BOOT_RESOURCE_FILE_TYPE,
    BOOT_RESOURCE_FILE_TYPE_CHOICES,
)
from maasserver.models.bootresourceset import BootResourceSet
from maasserver.models.cleansave import CleanSave
from maasserver.models.largefile import LargeFile
from maasserver.models.timestampedmodel import TimestampedModel


class BootResourceFile(CleanSave, TimestampedModel):
    """File associated with a `BootResourceSet`.

    Each `BootResourceSet` contains a set of files. For user uploaded boot
    resources this is only one file. For synced and generated resources this
    can be multiple files.

    :ivar resource_set: `BootResourceSet` file belongs to. When
        `BootResourceSet` is deleted, this `BootResourceFile` will be deleted.
    :ivar largefile: Actual file information and data. See
        :class:`LargeFile` (obsolete).
    :ivar filename: Name of the file.
    :ivar filetype: Type of the file. See the vocabulary
        :class:`BOOT_RESOURCE_FILE_TYPE`.
    :ivar extra: Extra information about the file. This is only used
        for synced Ubuntu images.
    """

    class Meta:
        unique_together = (("resource_set", "filename"),)

    resource_set = ForeignKey(
        BootResourceSet,
        related_name="files",
        editable=False,
        on_delete=CASCADE,
    )

    largefile = ForeignKey(LargeFile, on_delete=CASCADE, null=True)

    filename = CharField(max_length=255, editable=False)

    filetype = CharField(
        max_length=20,
        choices=BOOT_RESOURCE_FILE_TYPE_CHOICES,
        default=BOOT_RESOURCE_FILE_TYPE.ROOT_TGZ,
        editable=False,
    )

    extra = JSONField(blank=True, default=dict)

    sha256 = CharField(max_length=64, blank=True)

    size = BigIntegerField(default=0)

    def __str__(self):
        return f"<BootResourceFile {self.filename}/{self.filetype}>"
