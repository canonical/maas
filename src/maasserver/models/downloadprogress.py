# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model to record progress of boot-image downloads."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'DownloadProgress',
    ]


from django.core.exceptions import ValidationError
from django.db.models import (
    CharField,
    ForeignKey,
    IntegerField,
    Manager,
    )
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class DownloadProgressManager(Manager):
    """Manager for `DownloadProgress`.

    Don't import or instantiate this directly; access as `<Class>.objects` on
    the model class it manages.
    """

    def get_latest_download(self, nodegroup, filename):
        """Return the latest `DownloadProgress` for a download, or None."""
        reports = self.filter(nodegroup=nodegroup, filename=filename)
        latest = reports.order_by('-id')[:1]
        if len(latest) > 0:
            return latest[0]
        else:
            return None


class DownloadProgress(CleanSave, TimestampedModel):
    """Progress report from a cluster for one of its boot-image downloads.

    Each download on each cluster controller gets its own record.  The
    `bytes_downloaded` and last-change timestamp are updated with each progress
    report for that download.  The creation timestamp reflects the time of the
    download's first progress report.

    A cluster may download a file of the same name as a file it has downloaded
    once already.  The new download will have a new record.

    The download is complete when `bytes_downloaded` equals `size`.

    :ivar nodegroup: The cluster whose controller is doing this download.
    :ivar filename: Name of the file being downloaded.
    :ivar size: Size of the file, in bytes.
    :ivar bytes_downloaded: Number of bytes that have been downloaded.  This
        may not be known in advance, but must be set at some point for any
        successful download.
    :ivar error: Failure message.  If this is set, the download is considered
        a failure.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = DownloadProgressManager()

    nodegroup = ForeignKey('maasserver.NodeGroup', editable=False)

    filename = CharField(max_length=255, editable=False)

    size = IntegerField(blank=True, null=True, editable=True)

    bytes_downloaded = IntegerField()

    error = CharField(max_length=1000, blank=True)

    def clean(self):
        if self.bytes_downloaded < 0:
            raise ValidationError("Bytes downloaded is less than zero.")
        if self.size is not None:
            if self.size < 0:
                raise ValidationError("File size is less than zero.")
            if self.bytes_downloaded > self.size:
                raise ValidationError(
                    "Downloaded more bytes than the file is supposed to have.")
