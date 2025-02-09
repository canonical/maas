# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the FileStorage model."""

from io import BytesIO

from maasserver.models import FileStorage
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.utils import sample_binary_data


class TestFileStorage(MAASServerTestCase):
    def make_data(self, including_text="data"):
        """Return arbitrary data.

        :param including_text: Text to include in the data.  Leave something
            here to make failure messages more recognizable.
        :type including_text: unicode
        :return: A string of bytes, including `including_text`.
        :rtype: bytes
        """
        # Note that this won't automatically insert any non-ASCII bytes.
        # Proper handling of real binary data is tested separately.
        text = f"{including_text} {factory.make_string()}"
        return text.encode("ascii")

    def test_save_file_creates_storage(self):
        filename = factory.make_string()
        content = self.make_data()
        user = factory.make_User()
        storage = FileStorage.objects.save_file(
            filename, BytesIO(content), user
        )
        self.assertEqual(
            (filename, content, user),
            (storage.filename, storage.content, storage.owner),
        )

    def test_storage_can_be_retrieved(self):
        filename = factory.make_string()
        content = self.make_data()
        factory.make_FileStorage(filename=filename, content=content)
        storage = FileStorage.objects.get(filename=filename)
        self.assertEqual(
            (filename, content), (storage.filename, storage.content)
        )

    def test_stores_binary_data(self):
        storage = factory.make_FileStorage(content=sample_binary_data)
        self.assertEqual(sample_binary_data, storage.content)

    def test_overwrites_file(self):
        # If a file of the same name has already been stored, the
        # reference to the old data gets overwritten with one to the new
        # data.
        filename = factory.make_name("filename")
        old_storage = factory.make_FileStorage(
            filename=filename, content=self.make_data("old data")
        )
        new_data = self.make_data("new-data")
        new_storage = factory.make_FileStorage(
            filename=filename, content=new_data
        )
        self.assertEqual(old_storage.filename, new_storage.filename)
        self.assertEqual(
            new_data, FileStorage.objects.get(filename=filename).content
        )

    def test_key_gets_generated(self):
        # The generated system_id looks good.
        storage = factory.make_FileStorage()
        self.assertEqual(len(storage.key), 36)

    def test_key_includes_random_part(self):
        storage1 = factory.make_FileStorage()
        storage2 = factory.make_FileStorage()
        self.assertNotEqual(storage1.key, storage2.key)
