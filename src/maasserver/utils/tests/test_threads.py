# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.utils.threads`."""

import random
from unittest.mock import sentinel

from django.db import connection
from twisted.internet import reactor
from twisted.internet.defer import DeferredSemaphore, inlineCallbacks

from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import orm, threads
from maastesting.crochet import wait_for
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.twisted import ThreadPool, ThreadUnpool

wait_for_reactor = wait_for()


class TestMakeFunctions(MAASTestCase):
    """Tests for the `make_*` functions."""

    def test_make_default_pool_creates_disconnected_pool(self):
        pool = threads.make_default_pool()
        self.assertIsInstance(pool, ThreadPool)
        self.assertIs(pool.context.contextFactory, orm.TotallyDisconnected)
        self.assertEqual(threads.max_threads_for_default_pool, pool.max)
        self.assertEqual(0, pool.min)

    def test_make_default_pool_accepts_max_threads_setting(self):
        maxthreads = random.randint(1, 1000)
        pool = threads.make_default_pool(maxthreads)
        self.assertEqual(maxthreads, pool.max)
        self.assertEqual(0, pool.min)

    def test_make_database_pool_creates_connected_pool(self):
        pool = threads.make_database_pool()
        self.assertIsInstance(pool, ThreadPool)
        self.assertIs(pool.context.contextFactory, orm.FullyConnected)
        self.assertEqual(threads.max_threads_for_database_pool, pool.max)
        self.assertEqual(0, pool.min)

    def test_make_database_pool_accepts_max_threads_setting(self):
        maxthreads = random.randint(1, 1000)
        pool = threads.make_database_pool(maxthreads)
        self.assertEqual(maxthreads, pool.max)
        self.assertEqual(0, pool.min)

    def test_make_database_unpool_creates_unpool(self):
        pool = threads.make_database_unpool()
        self.assertIsInstance(pool, ThreadUnpool)
        self.assertIs(pool.contextFactory, orm.ExclusivelyConnected)
        self.assertIsInstance(pool.lock, DeferredSemaphore)
        self.assertEqual(
            threads.max_threads_for_database_pool, pool.lock.limit
        )

    def test_make_database_unpool_accepts_max_threads_setting(self):
        maxthreads = random.randint(1, 1000)
        pool = threads.make_database_unpool(maxthreads)
        self.assertEqual(maxthreads, pool.lock.limit)


class TestInstallFunctions(MAASTestCase):
    """Tests for the `install_*` functions."""

    def test_install_default_pool_will_not_work_now(self):
        error = self.assertRaises(AssertionError, threads.install_default_pool)
        self.assertIn("Too late; ", str(error))

    def test_default_pool_is_disconnected_pool(self):
        pool = reactor.threadpool
        self.assertIsInstance(pool, ThreadPool)
        self.assertIs(pool.context.contextFactory, orm.TotallyDisconnected)
        self.assertEqual(0, pool.min)

    def test_install_database_pool_will_not_work_now(self):
        error = self.assertRaises(
            AssertionError, threads.install_database_pool
        )
        self.assertIn("Too late; ", str(error))

    def test_database_pool_is_connected_unpool(self):
        pool = reactor.threadpoolForDatabase
        self.assertIsInstance(pool, ThreadUnpool)
        self.assertIs(pool.contextFactory, orm.ExclusivelyConnected)


class TestDeferToDatabase(MAASServerTestCase):
    @wait_for_reactor
    @inlineCallbacks
    def test_defers_to_database_threadpool(self):
        @orm.transactional
        def call_in_database_thread(a, b):
            orm.validate_in_transaction(connection)
            return sentinel.called, a, b

        result = yield threads.deferToDatabase(
            call_in_database_thread, sentinel.a, b=sentinel.b
        )
        self.assertEqual((sentinel.called, sentinel.a, sentinel.b), result)


class TestCallOutToDatabase(MAASServerTestCase):
    @wait_for_reactor
    @inlineCallbacks
    def test_calls_out_to_database_threadpool(self):
        @orm.transactional
        def call_in_database_thread(a, b):
            orm.validate_in_transaction(connection)
            return sentinel.bar, a, b

        result = yield threads.callOutToDatabase(
            sentinel.foo, call_in_database_thread, sentinel.a, b=sentinel.b
        )
        self.assertIs(result, sentinel.foo)
