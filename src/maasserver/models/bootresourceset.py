# Copyright 2014-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Resource Set."""


from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    ManyToManyField,
    Sum,
)

from maasserver.enum import BOOT_RESOURCE_FILE_TYPE
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel

# `BootResourceSet` must contain at least one of the file types to be consider
# as supporting the ability to xinstall. 'xinstall' being the
# fastpath-installer.
XINSTALL_TYPES = (
    BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE,
    BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE,
    BOOT_RESOURCE_FILE_TYPE.ROOT_TGZ,
    BOOT_RESOURCE_FILE_TYPE.ROOT_TBZ,
    BOOT_RESOURCE_FILE_TYPE.ROOT_TXZ,
    BOOT_RESOURCE_FILE_TYPE.ROOT_DD,
)


class BootResourceSet(CleanSave, TimestampedModel):
    """Set of files that make up a `BootResource`. Each `BootResource` can
    have a different set of files. As new versions of the `BootResource` is
    synced, generated, or uploaded then new sets are created.

    A booting node will always select the newest `BootResourceSet` for the
    selected `BootResource`. Older booted nodes might be using past versions.
    Older `BootResourceSet` are removed once zero nodes are referencing them.

    Each `BootResourceSet` contains a set of files. For user uploaded boot
    resources this is only one file. For synced and generated resources this
    can be multiple files.

    :ivar resource: `BootResource` set belongs to. When `BootResource` is
        deleted, this `BootResourceSet` will be deleted. Along with all
        associated files.
    :ivar version: Version name for the set. This normally is in the format
        of YYYYmmdd.r.
    :ivar label: Label for this version. For GENERATED and UPLOADED its always
        generated or uploaded respectively. For SYNCED its depends on the
        source, either daily or release.
    """

    class Meta:
        unique_together = (("resource", "version"),)

    resource = ForeignKey(
        "BootResource", related_name="sets", editable=False, on_delete=CASCADE
    )

    version = CharField(max_length=255, editable=False)

    label = CharField(max_length=255, editable=False)

    sync = ManyToManyField("RegionController", editable=True, blank=True)

    def __str__(self):
        return f"<BootResourceSet {self.version}/{self.label}>"

    @property
    def commissionable(self):
        """True if `BootResourceSet` supports the ability to commission a
        node."""
        types = {resource_file.filetype for resource_file in self.files.all()}
        return (
            BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL in types
            and BOOT_RESOURCE_FILE_TYPE.BOOT_INITRD in types
            and (
                BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE in types
                or BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE in types
            )
        )

    @property
    def xinstallable(self):
        """True if `BootResourceSet` supports the ability to xinstall to a
        node."""
        return any(
            resource_file.filetype in XINSTALL_TYPES
            for resource_file in self.files.all()
        )

    @property
    def total_size(self):
        """Total amount of space this set will consume."""
        total_size = self.files.all().aggregate(
            total_size=Sum("largefile__total_size")
        )["total_size"]
        if total_size is None:
            total_size = 0
        return total_size

    @property
    def size(self):
        """Amount of space this set currently consumes."""
        size = self.files.all().aggregate(size=Sum("largefile__size"))["size"]
        if size is None:
            size = 0
        return size

    @property
    def progress(self):
        """Percentage complete for all files in the set."""
        size_info = self.files.all().aggregate(
            total_size=Sum("largefile__total_size"),
            size=Sum("largefile__size"),
        )
        if size_info["size"] is None:
            size_info["size"] = 0
        if size_info["total_size"] is None:
            size_info["total_size"] = 0
        if size_info["size"] <= 0:
            # Handle division by zero
            return 0
        return 100.0 * size_info["size"] / float(size_info["total_size"])

    @property
    def complete(self):
        """True if all files in the set are complete."""
        if not self.files.exists():
            return False
        size_info = self.files.all().aggregate(
            total_size=Sum("largefile__total_size"),
            size=Sum("largefile__size"),
        )
        return size_info["total_size"] == size_info["size"]
