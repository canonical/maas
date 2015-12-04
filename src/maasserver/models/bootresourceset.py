# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Resource Set."""

__all__ = [
    'BootResourceSet',
    ]

from django.db.models import (
    CharField,
    ForeignKey,
)
from maasserver import DefaultMeta
from maasserver.enum import BOOT_RESOURCE_FILE_TYPE
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel

# `BootResourceSet` must contain all file types to be consider as supporting
# the ability to commission.
COMMISSIONABLE_SET = {
    BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL,
    BOOT_RESOURCE_FILE_TYPE.BOOT_INITRD,
    BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE,
    }

# `BootResourceSet` must contain all file types to be consider as supporting
# the ability to install. 'install' being the 'Debian Installer'.
INSTALL_SET = {
    BOOT_RESOURCE_FILE_TYPE.DI_KERNEL,
    BOOT_RESOURCE_FILE_TYPE.DI_INITRD,
    }

# `BootResourceSet` must contain at least one of the file types to be consider
# as supporting the ability to xinstall. 'xinstall' being the
# fastpath-installer.
XINSTALL_TYPES = (
    BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE,
    BOOT_RESOURCE_FILE_TYPE.ROOT_TGZ,
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

    class Meta(DefaultMeta):
        unique_together = (
            ('resource', 'version'),
            )

    resource = ForeignKey('BootResource', related_name='sets', editable=False)

    version = CharField(max_length=255, editable=False)

    label = CharField(max_length=255, editable=False)

    def __str__(self):
        return "<BootResourceSet %s/%s>" % (self.version, self.label)

    @property
    def commissionable(self):
        """True if `BootResourceSet` supports the ability to commission a
        node."""
        types = {resource_file.filetype for resource_file in self.files.all()}
        return COMMISSIONABLE_SET.issubset(types)

    @property
    def installable(self):
        """True if `BootResourceSet` supports the ability to install to a
        node."""
        types = {resource_file.filetype for resource_file in self.files.all()}
        return INSTALL_SET.issubset(types)

    @property
    def xinstallable(self):
        """True if `BootResourceSet` supports the ability to xinstall to a
        node."""
        return any(
            resource_file.filetype in XINSTALL_TYPES
            for resource_file in self.files.all())

    @property
    def total_size(self):
        """Total amount of space this set will consume."""
        return sum(
            resource_file.largefile.total_size
            for resource_file in self.files.all())

    @property
    def size(self):
        """Amount of space this set currently consumes."""
        return sum(
            resource_file.largefile.size
            for resource_file in self.files.all())

    @property
    def progress(self):
        """Percentage complete for all files in the set."""
        size = self.size
        if size <= 0:
            # Handle division by zero
            return 0
        return 100.0 * size / float(self.total_size)

    @property
    def complete(self):
        """True if all files in the set are complete."""
        if not self.files.exists():
            return False
        for resource_file in self.files.all():
            if not resource_file.largefile.complete:
                return False
        return True
