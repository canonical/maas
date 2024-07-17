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
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.twisted import DeferredValue

wait_for_reactor = wait_for()


class TestWorkersCount(MAASTestCase):
    def test_MAX_WORKERS_COUNT_default_cpucount(self):
        from maasserver.workers import MAX_WORKERS_COUNT

        assert os.cpu_count() == MAX_WORKERS_COUNT

    def test_set_max_workers_count(self):
        worker_count = random.randint(1, 8)
        set_max_workers_count(worker_count)
        from maasserver.workers import MAX_WORKERS_COUNT

        assert worker_count == MAX_WORKERS_COUNT


class TestWorkersService(MAASTestCase):
    def test_defaults_to_max_workers_and_argv_zero(self):
        worker_count = random.randint(1, 8)
        set_max_workers_count(worker_count)
        service = WorkersService(reactor)

        from maasserver.workers import MAX_WORKERS_COUNT

        assert MAX_WORKERS_COUNT == len(service.get_worker_ids())
        assert sys.argv[0] == service.worker_cmd

    def test_calls_spawnWorkers_on_start(self):
        service = WorkersService(reactor)
        self.patch(service, "spawnWorkers")
        service.startService()
        service.spawnWorkers.assert_called_once()

    def test_spawnWorkers_calls__spawnWorker_for_missing_workers(self):
        worker_count = random.randint(2, 16)
        set_max_workers_count(worker_count)
        service = WorkersService(reactor)
        self.patch(service, "_spawnWorker")
        pid = random.randint(1, 500)
        service.workers[pid] = WorkerProcess(service, worker_id="0")
        service.missing_worker_ids.remove("0")
        service.spawnWorkers()
        calls = [call("1", runningImport=True)] + [
            call(str(worker_id)) for worker_id in range(2, worker_count)
        ]
        service._spawnWorker.assert_has_calls(calls)

    def test_registerWorker(self):
        worker_count = 2
        set_max_workers_count(worker_count)
        service = WorkersService(reactor)
        self.patch(service, "_spawnWorker")

        worker = WorkerProcess(service, worker_id="0")
        worker.pid = 100
        service.registerWorker(worker)

        service.spawnWorkers()
        calls = [call("1", runningImport=True)]
        service._spawnWorker.assert_has_calls(calls)

    def test_unregisterWorker(self):
        worker_count = 2
        set_max_workers_count(worker_count)
        service = WorkersService(reactor)
        self.patch(service, "_spawnWorker")

        worker = WorkerProcess(service, worker_id="0")
        worker.pid = 100
        service.registerWorker(worker)
        service.unregisterWorker(worker, None)
        calls = [call("1", runningImport=True), call("0")]
        service._spawnWorker.assert_has_calls(calls)

    @wait_for_reactor
    @inlineCallbacks
    def test_killWorker_spawns_another(self):
        set_max_workers_count(1)
        service = WorkersService(reactor, worker_cmd="cat")

        dv = DeferredValue()
        original_unregisterWorker = service.unregisterWorker

        def mock_unregisterWorker(*args, **kwargs):
            original_unregisterWorker(*args, **kwargs)
            dv.set(None)

        self.patch(service, "unregisterWorker").side_effect = (
            mock_unregisterWorker
        )

        try:
            service.startService()

            self.assertEqual(1, len(service.workers))
            pid = list(service.workers.keys())[0]
            service.killWorker(pid)
            yield dv.get(timeout=2)
            assert pid not in service.workers
            assert len(service.workers) == 1
        finally:
            service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_termWorker_spawns_another(self):
        set_max_workers_count(1)
        service = WorkersService(reactor, worker_cmd="cat")

        dv = DeferredValue()
        original_unregisterWorker = service.unregisterWorker

        def mock_unregisterWorker(*args, **kwargs):
            original_unregisterWorker(*args, **kwargs)
            dv.set(None)

        self.patch(service, "unregisterWorker").side_effect = (
            mock_unregisterWorker
        )

        try:
            service.startService()

            self.assertEqual(1, len(service.workers))
            pid = list(service.workers.keys())[0]
            service.termWorker(pid)
            yield dv.get(timeout=2)
            assert pid not in service.workers
            assert len(service.workers) == 1
        finally:
            service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_stopService_doesnt(self):
        set_max_workers_count(1)
        service = WorkersService(reactor, worker_cmd="cat")

        dv = DeferredValue()
        original_unregisterWorker = service.unregisterWorker

        def mock_unregisterWorker(*args, **kwargs):
            original_unregisterWorker(*args, **kwargs)
            dv.set(None)

        self.patch(service, "unregisterWorker").side_effect = (
            mock_unregisterWorker
        )

        try:
            service.startService()
            assert len(service.workers) == 1
        finally:
            service.stopService()

        yield dv.get(timeout=2)
        assert len(service.workers) == 0
