# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Workers executor."""

import os
import sys

from twisted.application import service
from twisted.internet import protocol
from twisted.internet.process import ProcessExitedAlready

from provisioningserver.logger import LegacyLogger

log = LegacyLogger()

MAX_WORKERS_COUNT = int(
    os.environ.get("MAAS_REGIOND_WORKER_COUNT", os.cpu_count())
)


def set_max_workers_count(worker_count):
    """Set the global `MAX_WORKERS_COUNT`."""
    global MAX_WORKERS_COUNT
    MAX_WORKERS_COUNT = worker_count


class WorkerProcess(protocol.ProcessProtocol):
    def __init__(self, service, runningImport=False):
        super().__init__()
        self.service = service
        self.runningImport = runningImport

    def connectionMade(self):
        self.pid = self.transport.pid
        self.service.registerWorker(self)

    def processEnded(self, status):
        self.service.unregisterWorker(self, status)

    def signal(self, signal):
        if self.transport:
            try:
                self.transport.signalProcess(signal)
            except ProcessExitedAlready:
                pass
            self.transport.reapProcess()


class WorkersService(service.Service):
    """
    Workers service.

    Manages the lifecycle of the workers.
    """

    def __init__(self, reactor, *, worker_count=None, worker_cmd=None):
        super().__init__()
        self.reactor = reactor
        self.stopping = False
        self.worker_count = worker_count
        if self.worker_count is None:
            self.worker_count = MAX_WORKERS_COUNT
        self.worker_cmd = worker_cmd
        if self.worker_cmd is None:
            self.worker_cmd = sys.argv[0]
        self.workers = {}

    def startService(self):
        """Start the workers."""
        super().startService()
        self.spawnWorkers()

    def stopService(self):
        """Stop the workers."""
        self.stopping = True
        # get a list of the workers since they might unregister while this is
        # running
        for pid, worker in list(self.workers.items()):
            log.msg("Killing worker pid:%d." % pid)
            worker.signal("KILL")

    def spawnWorkers(self):
        """Spawn the missing workers."""
        if self.stopping:
            # Don't spwan new workers if the service is stopping.
            return
        missing = self.worker_count - len(self.workers)
        if self.workers:
            runningImport = max(
                worker.runningImport for worker in self.workers.values()
            )
        else:
            runningImport = False
        for _ in range(missing):
            if not runningImport:
                self._spawnWorker(runningImport=True)
                runningImport = True
            else:
                self._spawnWorker()

    def registerWorker(self, worker):
        """Register the worker."""
        self.workers[worker.pid] = worker

    def unregisterWorker(self, worker, status):
        """Worker has died."""
        del self.workers[worker.pid]
        self.spawnWorkers()

    def termWorker(self, pid):
        """Terminate the worker."""
        worker = self.workers.get(pid, None)
        if worker:
            log.msg("Terminating worker pid:%d." % pid)
            worker.signal("TERM")

    def killWorker(self, pid):
        """Kill the worker."""
        worker = self.workers.get(pid, None)
        if worker:
            log.msg("Killing worker pid:%d." % pid)
            worker.signal("KILL")

    def _spawnWorker(self, runningImport=False):
        """Spawn a new worker."""
        worker = WorkerProcess(self, runningImport=runningImport)
        env = os.environ.copy()
        env["MAAS_REGIOND_PROCESS_MODE"] = "worker"
        env["MAAS_REGIOND_WORKER_COUNT"] = str(MAX_WORKERS_COUNT)
        if runningImport:
            env["MAAS_REGIOND_RUN_IMPORTER_SERVICE"] = "true"
        self.reactor.spawnProcess(
            worker,
            self.worker_cmd,
            [self.worker_cmd],
            env=env,
            childFDs={0: 0, 1: 1, 2: 2},
        )
