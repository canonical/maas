# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.rackdservices.http_image_service`"""

__all__ = []

import random
from unittest.mock import call

from crochet import wait_for
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
)
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from provisioningserver.rackdservices.http_image_service import (
    HTTPImageProcess,
    HTTPImageService,
)
from provisioningserver.utils.twisted import DeferredValue
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks


wait_for_reactor = wait_for(30)  # 30 seconds.


class TestHTTPImageService(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_calls_spawnWorkers_on_start(self):
        worker_count = random.randint(1, 8)
        service = HTTPImageService(reactor, worker_count)
        self.patch(service, 'spawnWorkers')
        service.startService()
        self.assertThat(service.spawnWorkers, MockCalledOnceWith())

    def test_spawnWorkers_calls__spawnWorker_for_missing_workers(self):
        worker_count = random.randint(2, 16)
        service = HTTPImageService(reactor, worker_count)
        self.patch(service, '_spawnWorker')
        pid = random.randint(1, 500)
        service.workers[pid] = HTTPImageProcess(service)
        service.spawnWorkers()
        calls = [
            call()
            for _ in range(worker_count - 1)
        ]
        self.assertThat(service._spawnWorker, MockCallsMatch(*calls))

    @inlineCallbacks
    def test_killWorker_spawns_another(self):
        service = HTTPImageService(reactor, 1, worker_cmd='cat')

        dv = DeferredValue()
        original_unregisterWorker = service.unregisterWorker

        def mock_unregisterWorker(*args, **kwargs):
            original_unregisterWorker(*args, **kwargs)
            dv.set(None)

        self.patch(service, 'unregisterWorker').side_effect = (
            mock_unregisterWorker)

        try:
            service.startService()

            self.assertEquals(1, len(service.workers))
            pid = list(service.workers.keys())[0]
            service.killWorker(pid)
            yield dv.get(timeout=2)
            self.assertNotIn(pid, service.workers)
            self.assertEquals(1, len(service.workers))
        finally:
            service.stopService()

    @inlineCallbacks
    def test_stopService_doesnt(self):
        service = HTTPImageService(reactor, 1, worker_cmd='cat')

        dv = DeferredValue()
        original_unregisterWorker = service.unregisterWorker

        def mock_unregisterWorker(*args, **kwargs):
            original_unregisterWorker(*args, **kwargs)
            dv.set(None)

        self.patch(service, 'unregisterWorker').side_effect = (
            mock_unregisterWorker)

        try:
            service.startService()
            self.assertEquals(1, len(service.workers))
        finally:
            service.stopService()

        yield dv.get(timeout=2)
        self.assertEqual({}, service.workers)
