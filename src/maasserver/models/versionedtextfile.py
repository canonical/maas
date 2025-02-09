# Copyright 2016-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""VersionedTextFile objects."""

from django.core.exceptions import ValidationError
from django.db.models import CASCADE, CharField, ForeignKey, TextField

from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class VersionedTextFile(CleanSave, TimestampedModel):
    """An immutable `TextFile` which keeps track of its previous versions.

    :ivar data: The data belonging to this TextFile.
    :ivar previous_version: Optional previous version of this file.
    """

    class Meta:
        verbose_name = "VersionedTextFile"
        verbose_name_plural = "VersionedTextFiles"

    previous_version = ForeignKey(
        "self",
        on_delete=CASCADE,
        default=None,
        blank=True,
        null=True,
        editable=True,
        related_name="next_versions",
    )

    data = TextField(
        editable=False, blank=True, null=True, help_text="File contents"
    )

    comment = CharField(
        editable=True,
        max_length=255,
        blank=True,
        null=True,
        unique=False,
        help_text="Description of this version",
    )

    def _dostounix(self, data):
        """Convert DOS/(CRLF) formatted text to Unix/LF formatted text.

        Make sure all data is is Unix formatted. All data used in this
        model will be written to an Ubuntu installation where most
        applications expect LF only.
        """
        # Django converts bytes to string on save, keep type for now.
        if isinstance(data, str):
            return data.replace("\r\n", "\n")
        elif isinstance(data, bytes):
            return data.replace(b"\r\n", b"\n")
        return data

    def update(self, new_data, comment=None):
        """Updates this `VersionedTextFile` with the specified `new_data` and
        returns a newly-created `VersionedTextFile`. If the file has changed,
        it will be updated with the specified `comment`, if supplied.
        """
        new_data = self._dostounix(new_data)
        if new_data == self.data:
            return self
        else:
            updated = VersionedTextFile(
                previous_version_id=self.id, data=new_data, comment=comment
            )
            updated.save()
            return updated

    def clean(self):
        if self.id is not None:
            raise ValidationError("VersionedTextFile contents are immutable.")

    def get_oldest_version(self):
        oldest_known = self
        while oldest_known.previous_version is not None:
            oldest_known = oldest_known.previous_version
        return oldest_known

    def revert(self, to, gc=True, gc_hook=None):
        """Return a VersionTextFile object in this objects history.

        The returned object is specified by the VersionTextFile id or a
        negative number with how far back to go. By default newer objects
        then the one returned will be removed. You can optionally provide a
        garbage collection hook which accepts a single parameter being the
        value being reverted to. This allows you to revert a value and do
        garbage collection when the foreign key is set to cascade.
        """
        if to == 0:
            return self
        elif to < 0:
            history = [textfile for textfile in self.previous_versions()]
            to = -to
            if to >= len(history):
                raise ValueError("Goes too far back.")
            if gc:
                if gc_hook is not None:
                    gc_hook(history[to])
                history[to - 1].delete()
            return history[to]
        else:
            next_textfile = None
            for textfile in self.previous_versions():
                if textfile.id == to:
                    if next_textfile is not None and gc:
                        if gc_hook is not None:
                            gc_hook(textfile)
                        next_textfile.delete()
                    return textfile
                next_textfile = textfile
            raise ValueError("%s not found in history" % to)

    def previous_versions(self):
        """Return an iterator of this object and all previous versions."""

        class VersionedTextFileIterator:
            def __init__(self, textfile):
                self.textfile = textfile

            def __iter__(self):
                return self

            def __next__(self):
                textfile = self.textfile
                if textfile is None:
                    raise StopIteration
                else:
                    self.textfile = self.textfile.previous_version
                    return textfile

        return VersionedTextFileIterator(self)

    def save(self, *args, **kwargs):
        if self.id is None:
            self.data = self._dostounix(self.data)
        return super().save(*args, **kwargs)
