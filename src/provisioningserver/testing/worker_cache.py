# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Fixture to simulate the cache that worker processes normally share."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'WorkerCacheFixture',
    ]

from fixtures import Fixture
from provisioningserver import cache
from testtools.monkey import MonkeyPatcher


class WorkerCacheFixture(Fixture):
    """Fake the cache that worker processes share."""

    def setUp(self):
        super(WorkerCacheFixture, self).setUp()
        patcher = MonkeyPatcher(
            (cache, 'cache', cache.Cache({})),
            (cache, 'initialized', True))
        self.addCleanup(patcher.restore)
        patcher.patch()
