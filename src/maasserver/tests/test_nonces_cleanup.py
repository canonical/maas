# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the nonces cleanup module."""


import time

from piston3.models import Nonce
from twisted.internet.defer import maybeDeferred
from twisted.internet.task import Clock

from maasserver import nonces_cleanup
from maasserver.nonces_cleanup import (
    cleanup_old_nonces,
    create_checkpoint_nonce,
    delete_old_nonces,
    find_checkpoint_nonce,
    get_time_string,
    key_prefix,
    NonceCleanupService,
)
from maasserver.nonces_cleanup import time as module_time
from maasserver.nonces_cleanup import timestamp_threshold
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestCleanupOldNonces(MAASServerTestCase):
    def test_cleanup_old_nonces_returns_0_if_no_checkpoint(self):
        self.assertEqual(0, cleanup_old_nonces())

    def test_cleanup_old_nonces_cleans_up_old_nonces(self):
        now = time.time()
        # Patch the module's time module so that the nonces appear as if
        # they were created now - timestamp_threshold seconds ago.
        timemod = self.patch(module_time, "time")
        timemod.return_value = now - timestamp_threshold
        old_nonces = [
            Nonce.objects.create(token_key=factory.make_string())
            for _ in range(3)
        ]
        self.assertEqual(0, cleanup_old_nonces())
        # Patch the module's time module back.
        timemod.return_value = now
        new_nonces = [
            Nonce.objects.create(token_key=factory.make_string())
            for _ in range(3)
        ]

        cleanup_count = cleanup_old_nonces()

        # The old nonces plus the checkpoint nonce are deleted.
        self.assertEqual(len(old_nonces) + 1, cleanup_count)
        self.assertGreaterEqual(set(Nonce.objects.all()), set(new_nonces))
        self.assertEqual(len(new_nonces) + 1, Nonce.objects.all().count())


class TestUtilities(MAASServerTestCase):
    def test_create_checkpoint_nonce_creates_checkpoint_nonce(self):
        before = time.time()
        create_checkpoint_nonce()
        checkpoint = Nonce.objects.get(token_key="", consumer_key="")
        after = time.time()
        checkpoint_time = checkpoint.key[len(key_prefix) :]
        self.assertLessEqual(before, float(checkpoint_time))
        self.assertGreaterEqual(after, float(checkpoint_time))

    def test_create_checkpoint_nonce_gets_checkpoint_if_exists(self):
        now = time.time()
        self.patch(module_time, "time").return_value = now
        create_checkpoint_nonce()
        nonce1 = Nonce.objects.filter(token_key="", consumer_key="").latest(
            "id"
        )
        create_checkpoint_nonce()
        nonce2 = Nonce.objects.filter(token_key="", consumer_key="").latest(
            "id"
        )
        self.assertEqual(nonce1.id, nonce2.id)

    def test_delete_old_nonces_delete_nonces(self):
        # Create old nonces.
        [
            Nonce.objects.create(token_key=factory.make_string())
            for _ in range(3)
        ]
        checkpoint = Nonce.objects.create(token_key=factory.make_string())
        new_nonces = [
            Nonce.objects.create(token_key=factory.make_string())
            for _ in range(3)
        ]
        delete_old_nonces(checkpoint)
        self.assertCountEqual(new_nonces, Nonce.objects.all())

    def test_find_checkpoint_nonce_returns_None_if_no_checkpoint(self):
        self.assertIsNone(find_checkpoint_nonce())

    def test_find_checkpoint_nonce_returns_most_recent_checkpoint(self):
        now = time.time()
        self.patch(module_time, "time").return_value = now
        # Create a "checkpoint" nonce created timestamp_threshold + 5
        # seconds ago.
        Nonce.objects.create(
            token_key="",
            consumer_key="",
            key=get_time_string(now - 5 - timestamp_threshold),
        )
        # Create a "checkpoint" nonce created timestamp_threshold
        # seconds ago.
        checkpoint = Nonce.objects.create(
            token_key="",
            consumer_key="",
            key=get_time_string(now - timestamp_threshold),
        )
        # Create a "checkpoint" nonce created 1 second ago.
        Nonce.objects.create(
            token_key="", consumer_key="", key=get_time_string(now - 1)
        )

        self.assertEqual(checkpoint, find_checkpoint_nonce())

    def test_get_time_string_returns_comparable_string(self):
        now = time.time()
        self.assertGreater(get_time_string(now + 1), get_time_string(now))

    def test_get_time_string_ends_with_suffix(self):
        now = time.time()
        self.assertTrue(get_time_string(now).startswith(key_prefix))


class TestNonceCleanupService(MAASServerTestCase):
    def test_init_with_default_interval(self):
        # The service itself calls `cleanup_old_nonces` in a thread, via
        # a couple of decorators. This indirection makes it clearer to
        # mock `cleanup_old_nonces` here and track calls to it.
        cleanup_old_nonces = self.patch(nonces_cleanup, "cleanup_old_nonces")
        # Making `deferToDatabase` use the current thread helps testing.
        self.patch(nonces_cleanup, "deferToDatabase", maybeDeferred)

        service = NonceCleanupService()
        # Use a deterministic clock instead of the reactor for testing.
        service.clock = Clock()

        # The interval is stored as `step` by TimerService,
        # NonceCleanupService's parent class.
        interval = 24 * 60 * 60  # seconds.
        self.assertEqual(service.step, interval)

        # `cleanup_old_nonces` is not called before the service is
        # started.
        cleanup_old_nonces.assert_not_called()
        # `cleanup_old_nonces` is called the moment the service is
        # started.
        service.startService()
        cleanup_old_nonces.assert_called_once_with()
        # Advancing the clock by `interval - 1` means that
        # `cleanup_old_nonces` has still only been called once.
        service.clock.advance(interval - 1)
        cleanup_old_nonces.assert_called_once_with()
        cleanup_old_nonces.reset_mock()
        # Advancing the clock one more second causes another call to
        # `cleanup_old_nonces`.
        service.clock.advance(1)
        cleanup_old_nonces.assert_called_once_with()

    def test_interval_can_be_set(self):
        interval = self.getUniqueInteger()
        service = NonceCleanupService(interval)
        self.assertEqual(interval, service.step)
