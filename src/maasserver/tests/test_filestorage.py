# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the FileStorage model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import codecs
from io import BytesIO
import os
import shutil

from django.conf import settings
from maasserver.models import FileStorage
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from maastesting.utils import age_file
from testtools.matchers import (
    GreaterThan,
    LessThan,
    )


class FileStorageTest(TestCase):
    """Testing of the :class:`FileStorage` model."""

    def make_upload_dir(self):
        """Create the upload directory, and arrange for eventual deletion.

        The directory must not already exist.  If it does, this method will
        fail rather than arrange for deletion of a directory that may
        contain meaningful data.

        :return: Absolute path to the `FileStorage` upload directory.  This
            is the directory where the actual files are stored.
        """
        media_root = settings.MEDIA_ROOT
        self.assertFalse(os.path.exists(media_root), "See media/README")
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        os.mkdir(media_root)
        upload_dir = os.path.join(media_root, FileStorage.upload_dir)
        os.mkdir(upload_dir)
        return upload_dir

    def get_media_path(self, filename):
        """Get the path to a given stored file, relative to MEDIA_ROOT."""
        return os.path.join(FileStorage.upload_dir, filename)

    def make_data(self, including_text='data'):
        """Return arbitrary data.

        :param including_text: Text to include in the data.  Leave something
            here to make failure messages more recognizable.
        :type including_text: basestring
        :return: A string of bytes, including `including_text`.
        :rtype: bytes
        """
        # Note that this won't automatically insert any non-ASCII bytes.
        # Proper handling of real binary data is tested separately.
        text = "%s %s" % (including_text, factory.getRandomString())
        return text.encode('ascii')

    def test_get_existing_storage_returns_None_if_none_found(self):
        nonexistent_file = factory.getRandomString()
        self.assertIsNone(
            FileStorage.objects.get_existing_storage(nonexistent_file))

    def test_get_existing_storage_finds_FileStorage(self):
        self.make_upload_dir()
        storage = factory.make_file_storage()
        self.assertEqual(
            storage,
            FileStorage.objects.get_existing_storage(storage.filename))

    def test_save_file_creates_storage(self):
        self.make_upload_dir()
        filename = factory.getRandomString()
        data = self.make_data()
        storage = FileStorage.objects.save_file(filename, BytesIO(data))
        self.assertEqual(
            (filename, data),
            (storage.filename, storage.data.read()))

    def test_storage_can_be_retrieved(self):
        self.make_upload_dir()
        filename = factory.getRandomString()
        data = self.make_data()
        factory.make_file_storage(filename=filename, data=data)
        storage = FileStorage.objects.get(filename=filename)
        self.assertEqual(
            (filename, data),
            (storage.filename, storage.data.read()))

    def test_stores_binary_data(self):
        self.make_upload_dir()

        # This horrible binary data could never, ever, under any
        # encoding known to man be interpreted as text(1).  Switch the
        # bytes of the byte-order mark around and by design you get an
        # invalid codepoint; put a byte with the high bit set between bytes
        # that have it cleared, and you have a guaranteed non-UTF-8
        # sequence.
        #
        # (1) Provided, of course, that man know only about ASCII and
        # UTF.
        binary_data = codecs.BOM64_LE + codecs.BOM64_BE + b'\x00\xff\x00'

        # And yet, because FileStorage supports binary data, it comes
        # out intact.
        storage = factory.make_file_storage(filename="x", data=binary_data)
        self.assertEqual(binary_data, storage.data.read())

    def test_overwrites_file(self):
        # If a file of the same name has already been stored, the
        # reference to the old data gets overwritten with one to the new
        # data.  They are actually different files on the filesystem.
        self.make_upload_dir()
        filename = 'filename-%s' % factory.getRandomString()
        old_storage = factory.make_file_storage(
            filename=filename, data=self.make_data('old data'))
        new_data = self.make_data('new-data')
        new_storage = factory.make_file_storage(
            filename=filename, data=new_data)
        self.assertNotEqual(old_storage.data.name, new_storage.data.name)
        self.assertEqual(
            new_data, FileStorage.objects.get(filename=filename).data.read())

    def test_list_stored_files_lists_files(self):
        filename = factory.getRandomString()
        factory.make_file(
            location=self.make_upload_dir(), name=filename,
            contents=self.make_data())
        self.assertIn(
            self.get_media_path(filename),
            FileStorage.objects.list_stored_files())

    def test_list_stored_files_includes_referenced_files(self):
        self.make_upload_dir()
        storage = factory.make_file_storage()
        self.assertIn(
            storage.data.name, FileStorage.objects.list_stored_files())

    def test_list_referenced_files_lists_FileStorage_files(self):
        self.make_upload_dir()
        storage = factory.make_file_storage()
        self.assertIn(
            storage.data.name, FileStorage.objects.list_referenced_files())

    def test_list_referenced_files_excludes_unreferenced_files(self):
        filename = factory.getRandomString()
        factory.make_file(
            location=self.make_upload_dir(), name=filename,
            contents=self.make_data())
        self.assertNotIn(
            self.get_media_path(filename),
            FileStorage.objects.list_referenced_files())

    def test_list_referenced_files_uses_file_name_not_FileStorage_name(self):
        self.make_upload_dir()
        filename = factory.getRandomString()
        # The filename we're going to use is already taken.  The file
        # we'll be looking at will have to have a different name.
        factory.make_file_storage(filename=filename)
        storage = factory.make_file_storage(filename=filename)
        # It's the name of the file, not the FileStorage.filename, that
        # is in list_referenced_files.
        self.assertIn(
            storage.data.name, FileStorage.objects.list_referenced_files())

    def test_is_old_returns_False_for_recent_file(self):
        filename = factory.getRandomString()
        path = factory.make_file(
            location=self.make_upload_dir(), name=filename,
            contents=self.make_data())
        age_file(path, FileStorage.objects.grace_time - 60)
        self.assertFalse(
            FileStorage.objects.is_old(self.get_media_path(filename)))

    def test_is_old_returns_True_for_old_file(self):
        filename = factory.getRandomString()
        path = factory.make_file(
            location=self.make_upload_dir(), name=filename,
            contents=self.make_data())
        age_file(path, FileStorage.objects.grace_time + 1)
        self.assertTrue(
            FileStorage.objects.is_old(self.get_media_path(filename)))

    def test_collect_garbage_deletes_garbage(self):
        filename = factory.getRandomString()
        path = factory.make_file(
            location=self.make_upload_dir(), name=filename,
            contents=self.make_data())
        age_file(path, FileStorage.objects.grace_time + 1)
        FileStorage.objects.collect_garbage()
        self.assertFalse(
            FileStorage.storage.exists(self.get_media_path(filename)))

    def test_grace_time_is_generous_but_not_unlimited(self):
        # Grace time for garbage collection is long enough that it won't
        # expire while the request that wrote it is still being handled.
        # But it won't keep a file around for ages.  For instance, it'll
        # be more than 20 seconds, but less than a day.
        self.assertThat(FileStorage.objects.grace_time, GreaterThan(20))
        self.assertThat(FileStorage.objects.grace_time, LessThan(24 * 60 * 60))

    def test_collect_garbage_leaves_recent_files_alone(self):
        filename = factory.getRandomString()
        factory.make_file(
            location=self.make_upload_dir(), name=filename,
            contents=self.make_data())
        FileStorage.objects.collect_garbage()
        self.assertTrue(
            FileStorage.storage.exists(self.get_media_path(filename)))

    def test_collect_garbage_leaves_referenced_files_alone(self):
        self.make_upload_dir()
        storage = factory.make_file_storage()
        age_file(storage.data.path, FileStorage.objects.grace_time + 1)
        FileStorage.objects.collect_garbage()
        self.assertTrue(FileStorage.storage.exists(storage.data.name))

    def test_collect_garbage_tolerates_missing_upload_dir(self):
        # When MAAS is freshly installed, the upload directory is still
        # missing.  But...
        FileStorage.objects.collect_garbage()
        # ...we get through garbage collection without breakage.
        pass
