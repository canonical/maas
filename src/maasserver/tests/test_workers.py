# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.workers`"""


import os
import random
import sys
from unittest.mock import call

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from maasserver.workers import (
    set_max_workers_count,
    WorkerProcess,
    WorkersService,
)
from maastesting.crochet import wait_for
from maastesting.matchers import MockCalledOnceWith, MockCallsMatch
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.twisted import DeferredValue

wait_for_reactor = wait_for()


class TestWorkersCount(MAASTestCase):
    def test_MAX_WORKERS_COUNT_default_cpucount(self):
        from maasserver.workers import MAX_WORKERS_COUNT

        self.assertEqual(os.cpu_count(), MAX_WORKERS_COUNT)

    def test_set_max_workers_count(self):
        worker_count = random.randint(1, 8)
        set_max_workers_count(worker_count)
        from maasserver.workers import MAX_WORKERS_COUNT

        self.assertEqual(worker_count, MAX_WORKERS_COUNT)


class TestWorkersService(MAASTestCase):
    def test_defaults_to_max_workers_and_argv_zero(self):
        worker_count = random.randint(1, 8)
        set_max_workers_count(worker_count)
        service = WorkersService(reactor)

        from maasserver.workers import MAX_WORKERS_COUNT

        self.assertEqual(MAX_WORKERS_COUNT, service.worker_count)
        self.assertEqual(sys.argv[0], service.worker_cmd)

    def test_calls_spawnWorkers_on_start(self):
        service = WorkersService(reactor)
        self.patch(service, "spawnWorkers")
        service.startService()
        self.assertThat(service.spawnWorkers, MockCalledOnceWith())

    def test_spawnWorkers_calls__spawnWorker_for_missing_workers(self):
        worker_count = random.randint(2, 16)
        service = WorkersService(reactor, worker_count=worker_count)
        self.patch(service, "_spawnWorker")
        pid = random.randint(1, 500)
        service.workers[pid] = WorkerProcess(service)
        service.spawnWorkers()
        calls = [call(runningImport=True)] + [
            call() for _ in range(worker_count - 2)
        ]
        self.assertThat(service._spawnWorker, MockCallsMatch(*calls))

    @wait_for_reactor
    @inlineCallbacks
    def test_killWorker_spawns_another(self):
        service = WorkersService(reactor, worker_count=1, worker_cmd="cat")

        dv = DeferredValue()
        original_unregisterWorker = service.unregisterWorker

        def mock_unregisterWorker(*args, **kwargs):
            original_unregisterWorker(*args, **kwargs)
            dv.set(None)

        self.patch(
            service, "unregisterWorker"
        ).side_effect = mock_unregisterWorker

        try:
            service.startService()

            self.assertEqual(1, len(service.workers))
            pid = list(service.workers.keys())[0]
            service.killWorker(pid)
            yield dv.get(timeout=2)
            self.assertNotIn(pid, service.workers)
            self.assertEqual(1, len(service.workers))
        finally:
            service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_termWorker_spawns_another(self):
        service = WorkersService(reactor, worker_count=1, worker_cmd="cat")

        dv = DeferredValue()
        original_unregisterWorker = service.unregisterWorker

        def mock_unregisterWorker(*args, **kwargs):
            original_unregisterWorker(*args, **kwargs)
            dv.set(None)

        self.patch(
            service, "unregisterWorker"
        ).side_effect = mock_unregisterWorker

        try:
            service.startService()

            self.assertEqual(1, len(service.workers))
            pid = list(service.workers.keys())[0]
            service.termWorker(pid)
            yield dv.get(timeout=2)
            self.assertNotIn(pid, service.workers)
            self.assertEqual(1, len(service.workers))
        finally:
            service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_stopService_doesnt(self):
        service = WorkersService(reactor, worker_count=1, worker_cmd="cat")

        dv = DeferredValue()
        original_unregisterWorker = service.unregisterWorker

        def mock_unregisterWorker(*args, **kwargs):
            original_unregisterWorker(*args, **kwargs)
            dv.set(None)

        self.patch(
            service, "unregisterWorker"
        ).side_effect = mock_unregisterWorker

        try:
            service.startService()
            self.assertEqual(1, len(service.workers))
        finally:
            service.stopService()

        yield dv.get(timeout=2)
        self.assertEqual({}, service.workers)
