# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :class:`LargeFile`."""


from io import BytesIO
from random import randint
from unittest.mock import ANY, call

from django.db import transaction
import psycopg2
from testtools.matchers import (
    Equals,
    HasLength,
    Is,
    MatchesListwise,
    MatchesStructure,
)
from twisted.internet.task import Clock

from maasserver.fields import LargeObjectFile
from maasserver.models import largefile as largefile_module
from maasserver.models import signals
from maasserver.models.largefile import LargeFile
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import post_commit_hooks
from maastesting.crochet import wait_for
from maastesting.matchers import MockCalledOnceWith, MockCallsMatch


class TestLargeFileManager(MAASServerTestCase):
    def test_has_file(self):
        largefile = factory.make_LargeFile()
        self.assertTrue(LargeFile.objects.has_file(largefile.sha256))

    def test_get_file(self):
        largefile = factory.make_LargeFile()
        obj = LargeFile.objects.get_file(largefile.sha256)
        self.assertEqual(largefile, obj)

    def test_get_or_create_file_from_content_returns_same_largefile(self):
        largefile = factory.make_LargeFile()
        stream = largefile.content.open("rb")
        self.addCleanup(stream.close)
        self.assertEqual(
            largefile,
            LargeFile.objects.get_or_create_file_from_content(stream),
        )

    def test_get_or_create_file_from_content_returns_new_largefile(self):
        content = factory.make_bytes(1024)
        largefile = LargeFile.objects.get_or_create_file_from_content(
            BytesIO(content)
        )
        with largefile.content.open("rb") as stream:
            written_content = stream.read()
        self.assertEqual(content, written_content)
        self.assertEqual(len(content), largefile.size)


class TestLargeFile(MAASServerTestCase):
    mock_delete_large_object_content_later = False

    def test_content(self):
        size = randint(512, 1024)
        content = factory.make_bytes(size=size)
        largefile = factory.make_LargeFile(content, size=size)
        with largefile.content.open("rb") as stream:
            data = stream.read()
        self.assertEqual(content, data)

    def test_empty_content(self):
        size = 0
        content = b""
        largefile = factory.make_LargeFile(content, size=size)
        with largefile.content.open("rb") as stream:
            data = stream.read()
        self.assertEqual(content, data)

    def test_progress(self):
        size = randint(512, 1024)
        total_size = randint(1025, 2048)
        content = factory.make_bytes(size=size)
        largefile = factory.make_LargeFile(content, size=total_size)
        self.assertEqual(total_size / float(size), largefile.progress)

    def test_progress_of_empty_file(self):
        size = 0
        content = b""
        largefile = factory.make_LargeFile(content, size=size)
        self.assertEqual(0, largefile.progress)

    def test_complete_returns_False_when_content_incomplete(self):
        size = randint(512, 1024)
        total_size = randint(1025, 2048)
        content = factory.make_bytes(size=size)
        largefile = factory.make_LargeFile(content, size=total_size)
        self.assertFalse(largefile.complete)

    def test_complete_returns_True_when_content_is_complete(self):
        largefile = factory.make_LargeFile()
        self.assertTrue(largefile.complete)

    def test_valid_returns_False_when_complete_is_False(self):
        size = randint(512, 1024)
        total_size = randint(1025, 2048)
        content = factory.make_bytes(size=size)
        largefile = factory.make_LargeFile(content, size=total_size)
        self.assertFalse(largefile.valid)

    def test_valid_returns_False_when_content_doesnt_have_equal_sha256(self):
        largefile = factory.make_LargeFile()
        with largefile.content.open("wb") as stream:
            stream.write(factory.make_bytes(size=largefile.total_size))
        self.assertFalse(largefile.valid)

    def test_valid_returns_True_when_content_has_equal_sha256(self):
        largefile = factory.make_LargeFile()
        self.assertTrue(largefile.valid)

    def test_delete_does_nothing_if_linked(self):
        largefile = factory.make_LargeFile()
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        factory.make_BootResourceFile(resource_set, largefile)
        largefile.delete()
        self.assertTrue(LargeFile.objects.filter(id=largefile.id).exists())

    def test_deletes_content_asynchronously(self):
        self.patch(signals.largefiles, "delete_large_object_content_later")
        largefile = factory.make_LargeFile()
        self.addCleanup(largefile.content.unlink)
        with post_commit_hooks:
            largefile.delete()
        self.assertThat(
            signals.largefiles.delete_large_object_content_later,
            MockCalledOnceWith(largefile.content),
        )

    def test_deletes_content_asynchronously_for_queries_too(self):
        self.patch(signals.largefiles, "delete_large_object_content_later")
        for _ in 1, 2:
            largefile = factory.make_LargeFile()
            self.addCleanup(largefile.content.unlink)
        with post_commit_hooks:
            LargeFile.objects.all().delete()
        self.assertThat(
            signals.largefiles.delete_large_object_content_later,
            MockCallsMatch(call(ANY), call(ANY)),
        )


class TestDeleteLargeObjectContentLater(MAASTransactionServerTestCase):
    mock_delete_large_object_content_later = False

    def test_schedules_unlink(self):
        # We're going to capture the delayed call that
        # delete_large_object_content_later() creates.
        clock = self.patch(largefile_module, "reactor", Clock())

        with transaction.atomic():
            largefile = factory.make_LargeFile()
            oid = largefile.content.oid

        with post_commit_hooks:
            largefile.delete()

        # Deleting `largefile` resulted in a call being scheduled.
        delayed_calls = clock.getDelayedCalls()
        self.assertThat(delayed_calls, HasLength(1))
        [delayed_call] = delayed_calls

        # It is scheduled to be run on the next iteration of the reactor.
        self.assertFalse(delayed_call.called)
        self.assertThat(
            delayed_call,
            MatchesStructure(
                func=MatchesStructure.byEquality(__name__="unlink"),
                args=MatchesListwise([Is(largefile.content)]),
                kw=Equals({}),
                time=Equals(0),
            ),
        )

        # Call the delayed function ourselves instead of advancing `clock` so
        # that we can wait for it to complete (it returns a Deferred).
        func = wait_for()(delayed_call.func)
        func(*delayed_call.args, **delayed_call.kw)

        # The content has been removed from the database.
        with transaction.atomic():
            error = self.assertRaises(
                psycopg2.OperationalError, LargeObjectFile(oid).open, "rb"
            )
            self.assertDocTestMatches(
                "ERROR: large object ... does not exist", str(error)
            )
