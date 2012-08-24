# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Storage for uploaded files."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'FileStorage',
    ]


from errno import ENOENT
import os
import time

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db.models import (
    CharField,
    FileField,
    Manager,
    Model,
    )
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.utils.orm import get_one


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
    # The time, in seconds, that an unreferenced file is allowed to
    # persist in order to satisfy ongoing requests.
    grace_time = 12 * 60 * 60

    def get_existing_storage(self, filename):
        """Return an existing `FileStorage` of this name, or None."""
        return get_one(self.filter(filename=filename))

    def save_file(self, filename, file_object):
        """Save the file to the filesystem and persist to the database.

        The file will end up in MEDIA_ROOT/storage/

        If a file of that name already existed, it will be replaced by the
        new contents.
        """
        # This probably ought to read in chunks but large files are
        # not expected.  Also note that uploading a file with the same
        # name as an existing one will cause that file to be written
        # with a new generated name, and the old one remains where it
        # is.  See https://code.djangoproject.com/ticket/6157 - the
        # Django devs consider deleting things dangerous ... ha.
        # HOWEVER - this operation would need to be atomic anyway so
        # it's safest left how it is for now (reads can overlap with
        # writes from Juju).
        content = ContentFile(file_object.read())

        storage = self.get_existing_storage(filename)
        if storage is None:
            storage = FileStorage(filename=filename)
        storage.data.save(filename, content)
        return storage

    def list_stored_files(self):
        """Find the files stored in the filesystem."""
        dirs, files = FileStorage.storage.listdir(FileStorage.upload_dir)
        return [
            os.path.join(FileStorage.upload_dir, filename)
            for filename in files]

    def list_referenced_files(self):
        """Find the names of files that are referenced from `FileStorage`.

        :return: All file paths within MEDIA ROOT (relative to MEDIA_ROOT)
            that have `FileStorage` entries referencing them.
        :rtype: frozenset
        """
        return frozenset(
            file_storage.data.name
            for file_storage in self.all())

    def is_old(self, storage_filename):
        """Is the named file in the filesystem storage old enough to be dead?

        :param storage_filename: The name under which the file is stored in
            the filesystem, relative to MEDIA_ROOT.  This need not be the
            same name as its filename as stored in the `FileStorage` object.
            It includes the name of the upload directory.
        """
        file_path = os.path.join(settings.MEDIA_ROOT, storage_filename)
        mtime = os.stat(file_path).st_mtime
        expiry = mtime + self.grace_time
        return expiry <= time.time()

    def collect_garbage(self):
        """Clean up stored files that are no longer accessible."""
        # Avoid circular imports.
        from maasserver.models import logger

        try:
            stored_files = self.list_stored_files()
        except OSError as e:
            if e.errno != ENOENT:
                raise
            logger.info(
                "Upload directory does not exist yet.  "
                "Skipping garbage collection.")
            return
        referenced_files = self.list_referenced_files()
        for path in stored_files:
            if path not in referenced_files and self.is_old(path):
                FileStorage.storage.delete(path)


class FileStorage(CleanSave, Model):
    """A simple file storage keyed on file name.

    :ivar filename: A unique file name to use for the data being stored.
    :ivar data: The file's actual data.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    storage = FileSystemStorage()

    upload_dir = "storage"

    # Unix filenames can be longer than this (e.g. 255 bytes), but leave
    # some extra room for the full path, as well as a versioning suffix.
    filename = CharField(max_length=200, unique=True, editable=False)
    data = FileField(upload_to=upload_dir, storage=storage, max_length=255)

    objects = FileStorageManager()

    def __unicode__(self):
        return self.filename
