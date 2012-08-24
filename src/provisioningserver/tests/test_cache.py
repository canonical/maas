# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests cache."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from multiprocessing.managers import DictProxy

from maastesting.factory import factory
from provisioningserver import cache
from provisioningserver.testing.testcase import PservTestCase


class TestCache(PservTestCase):

    def test_initialize_initializes_backend(self):
        self.patch(cache, 'initialized', False)
        cache.initialize()
        self.addCleanup(cache._manager.shutdown)
        self.assertIsInstance(cache.cache.cache_backend, DictProxy)

    def test_cache_stores_value(self):
        key = factory.getRandomString()
        value = factory.getRandomString()
        cache.cache.set(key, value)
        self.assertEqual(value, cache.cache.get(key))

    def test_cache_clears_cache(self):
        cache.cache.set(factory.getRandomString(), factory.getRandomString())
        cache.cache.clear()
        self.assertEqual(0, len(cache.cache.cache_backend))
