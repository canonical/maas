# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :class:`LargeFile`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from cStringIO import StringIO
from random import randint

from maasserver.models.largefile import LargeFile
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith


class TestLargeFileManager(MAASServerTestCase):

    def test_has_file(self):
        largefile = factory.make_large_file()
        self.assertTrue(LargeFile.objects.has_file(largefile.sha256))

    def test_get_file(self):
        largefile = factory.make_large_file()
        obj = LargeFile.objects.get_file(largefile.sha256)
        self.assertEqual(largefile, obj)

    def test_get_or_create_file_from_content_returns_same_largefile(self):
        largefile = factory.make_large_file()
        stream = largefile.content.open('rb')
        self.addCleanup(stream.close)
        self.assertEqual(
            largefile,
            LargeFile.objects.get_or_create_file_from_content(stream))

    def test_get_or_create_file_from_content_returns_new_largefile(self):
        content = factory.make_string(1024)
        largefile = LargeFile.objects.get_or_create_file_from_content(
            StringIO(content))
        with largefile.content.open('rb') as stream:
            written_content = stream.read()
        self.assertEqual(content, written_content)


class TestLargeFile(MAASServerTestCase):

    def test_content(self):
        size = randint(512, 1024)
        content = factory.make_string(size=size)
        largefile = factory.make_large_file(content, size=size)
        with largefile.content.open('rb') as stream:
            data = stream.read()
        self.assertEqual(content, data)

    def test_empty_content(self):
        size = 0
        content = ""
        largefile = factory.make_large_file(content, size=size)
        with largefile.content.open('rb') as stream:
            data = stream.read()
        self.assertEqual(content, data)

    def test_size(self):
        size = randint(512, 1024)
        total_size = randint(1025, 2048)
        content = factory.make_string(size=size)
        largefile = factory.make_large_file(content, size=total_size)
        self.assertEqual(size, largefile.size)

    def test_progress(self):
        size = randint(512, 1024)
        total_size = randint(1025, 2048)
        content = factory.make_string(size=size)
        largefile = factory.make_large_file(content, size=total_size)
        self.assertEqual(total_size / float(size), largefile.progress)

    def test_progress_of_empty_file(self):
        size = 0
        content = ""
        largefile = factory.make_large_file(content, size=size)
        self.assertEqual(0, largefile.progress)

    def test_complete_returns_False_when_content_incomplete(self):
        size = randint(512, 1024)
        total_size = randint(1025, 2048)
        content = factory.make_string(size=size)
        largefile = factory.make_large_file(content, size=total_size)
        self.assertFalse(largefile.complete)

    def test_complete_returns_True_when_content_is_complete(self):
        largefile = factory.make_large_file()
        self.assertTrue(largefile.complete)

    def test_valid_returns_False_when_complete_is_False(self):
        size = randint(512, 1024)
        total_size = randint(1025, 2048)
        content = factory.make_string(size=size)
        largefile = factory.make_large_file(content, size=total_size)
        self.assertFalse(largefile.valid)

    def test_valid_returns_False_when_content_doesnt_have_equal_sha256(self):
        largefile = factory.make_large_file()
        with largefile.content.open('wb') as stream:
            stream.write(factory.make_string(size=largefile.total_size))
        self.assertFalse(largefile.valid)

    def test_valid_returns_True_when_content_has_equal_sha256(self):
        largefile = factory.make_large_file()
        self.assertTrue(largefile.valid)

    def test_delete_calls_unlink_on_content(self):
        largefile = factory.make_large_file()
        content = largefile.content
        self.addCleanup(content.unlink)
        unlink_mock = self.patch(content, 'unlink')
        largefile.delete()
        self.assertThat(unlink_mock, MockCalledOnceWith())

    def test_delete_does_nothing_if_linked(self):
        largefile = factory.make_large_file()
        resource = factory.make_BootResource()
        resource_set = factory.make_boot_resource_set(resource)
        factory.make_boot_resource_file(resource_set, largefile)
        largefile.delete()
        self.assertTrue(LargeFile.objects.filter(id=largefile.id).exists())

    def test_delete_deletes_if_not_linked(self):
        largefile = factory.make_large_file()
        largefile.delete()
        self.assertFalse(LargeFile.objects.filter(id=largefile.id).exists())
