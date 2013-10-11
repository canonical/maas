# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the nonces cleanup module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


import time

from maasserver.nonces_cleanup import (
    cleanup_old_nonces,
    create_checkpoint_nonce,
    delete_old_nonces,
    find_checkpoint_nonce,
    get_time_string,
    key_prefix,
    time as module_time,
    timestamp_threshold,
    )
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import ContainsAll
from piston.models import Nonce
from testtools.matchers import StartsWith


class TestCleanupOldNonces(MAASServerTestCase):

    def test_cleanup_old_nonces_returns_0_if_no_checkpoint(self):
        self.assertEquals(0, cleanup_old_nonces())

    def test_cleanup_old_nonces_cleans_up_old_nonces(self):
        now = time.time()
        # Patch the module's time module so that the nonces appear as if
        # they were created now - timestamp_threshold seconds ago.
        timemod = self.patch(module_time, "time")
        timemod.return_value = now - timestamp_threshold
        old_nonces = [Nonce.objects.create() for i in range(3)]
        self.assertEquals(0, cleanup_old_nonces())
        # Patch the module's time module back.
        timemod.return_value = now
        new_nonces = [Nonce.objects.create() for i in range(3)]

        cleanup_count = cleanup_old_nonces()

        # The old nonces plus the checkpoint nonce are deleted.
        self.assertEquals(len(old_nonces) + 1, cleanup_count)
        self.assertThat(Nonce.objects.all(), ContainsAll(new_nonces))
        self.assertEqual(len(new_nonces) + 1, Nonce.objects.all().count())


class TestUtilities(MAASServerTestCase):

    def test_create_checkpoint_nonce_creates_checkpoint_nonce(self):
        before = time.time()
        create_checkpoint_nonce()
        checkpoint = Nonce.objects.get(token_key='', consumer_key='')
        after = time.time()
        checkpoint_time = checkpoint.key[len(key_prefix):]
        self.assertLessEqual(before, float(checkpoint_time))
        self.assertGreaterEqual(after, float(checkpoint_time))

    def test_create_checkpoint_nonce_gets_checkpoint_if_exists(self):
        now = time.time()
        self.patch(module_time, "time").return_value = now
        create_checkpoint_nonce()
        nonce1 = Nonce.objects.filter(
            token_key='', consumer_key='').latest('id')
        create_checkpoint_nonce()
        nonce2 = Nonce.objects.filter(
            token_key='', consumer_key='').latest('id')
        self.assertEqual(nonce1.id, nonce2.id)

    def test_delete_old_nonces_delete_nonces(self):
        # Create old nonces.
        [Nonce.objects.create() for i in range(3)]
        checkpoint = Nonce.objects.create()
        new_nonces = [Nonce.objects.create() for i in range(3)]
        delete_old_nonces(checkpoint)
        self.assertItemsEqual(new_nonces, Nonce.objects.all())

    def test_find_checkpoint_nonce_returns_None_if_no_checkpoint(self):
        self.assertIsNone(find_checkpoint_nonce())

    def test_find_checkpoint_nonce_returns_most_recent_checkpoint(self):
        now = time.time()
        self.patch(module_time, "time").return_value = now
        # Create a "checkpoint" nonce created timestamp_threshold + 5
        # seconds ago.
        Nonce.objects.create(
            token_key='', consumer_key='',
            key=get_time_string(now - 5 - timestamp_threshold))
        # Create a "checkpoint" nonce created timestamp_threshold
        # seconds ago.
        checkpoint = Nonce.objects.create(
            token_key='', consumer_key='',
            key=get_time_string(now - timestamp_threshold))
        # Create a "checkpoint" nonce created 1 second ago.
        Nonce.objects.create(
            token_key='', consumer_key='', key=get_time_string(now - 1))

        self.assertEqual(checkpoint, find_checkpoint_nonce())

    def test_get_time_string_returns_comparable_string(self):
        now = time.time()
        self.assertGreater(get_time_string(now + 1), get_time_string(now))

    def test_get_time_string_ends_with_suffix(self):
        now = time.time()
        self.assertThat(get_time_string(now), StartsWith(key_prefix))
