# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Resource Set."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'BootResourceSet',
    ]

from django.db.models import (
    CharField,
    ForeignKey,
    )
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


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

    def __repr__(self):
        return "<BootResourceSet %s/%s>" % (self.version, self.label)
