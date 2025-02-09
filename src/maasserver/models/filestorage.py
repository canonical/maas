# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Storage for uploaded files."""

from uuid import uuid4

from django.contrib.auth.models import User
from django.db.models import CharField, ForeignKey, Manager, Model, PROTECT
from django.urls import reverse
from django.utils.http import urlencode

from maasserver.models.cleansave import CleanSave
from metadataserver.fields import Bin, BinaryField


class FileStorageManager(Manager):
    """Manager for `FileStorage` objects.

    Store files by calling `save_file`.  No two `FileStorage` objects can
    have the same filename at the same time.  Writing new data to a file
    whose name is already in use, replaces its `FileStorage` with one
    pointing to the new data.

    Underneath, however, the storage layer will keep the old version of the
    file around indefinitely.  Thus, if the overwriting transaction rolls
    back, it may leave the new file as garbage on the filesystem; but the
    original file will not be affected.  Also, any ongoing reads from the
    old file will continue without iterruption.
    """

    def save_file(self, filename, file_object, owner):
        """Save the file to the database.

        If a file of that name/owner already existed, it will be replaced by
        the new contents.
        """
        # This probably ought to read in chunks but large files are
        # not expected.
        content = Bin(file_object.read())
        storage, created = self.get_or_create(
            filename=filename, owner=owner, defaults={"content": content}
        )
        if not created:
            storage.content = content
            storage.save()
        return storage


def generate_filestorage_key():
    # Use true random UUID as this is used as an unguessable key.
    return "%s" % uuid4()


class FileStorage(CleanSave, Model):
    """A simple file storage keyed on file name.

    :ivar filename: A file name to use for the data being stored.
    :ivar owner: This file's owner..
    :ivar content: The file's actual data.
    """

    class Meta:
        unique_together = ("filename", "owner")

    filename = CharField(max_length=255, unique=False, editable=False)
    content = BinaryField(null=False, blank=True)
    # owner can be None: this is to support upgrading existing
    # installations where the files were not linked to users yet.
    owner = ForeignKey(
        User,
        default=None,
        blank=True,
        null=True,
        editable=False,
        on_delete=PROTECT,
    )
    key = CharField(
        max_length=36,
        unique=True,
        default=generate_filestorage_key,
        editable=False,
    )

    objects = FileStorageManager()

    def __str__(self):
        return self.filename

    @property
    def anon_resource_uri(self):
        """URI where the content of the file can be retrieved anonymously."""
        params = {"op": "get_by_key", "key": self.key}
        url = "{}?{}".format(reverse("files_handler"), urlencode(params))
        return url
