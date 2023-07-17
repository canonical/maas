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
    def __init__(self, service, worker_id: str, runningImport=False):
        super().__init__()
        self.service = service
        self.worker_id = worker_id
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

    @staticmethod
    def get_worker_ids() -> list[str]:
        return [str(worker_id) for worker_id in range(MAX_WORKERS_COUNT)]

    def __init__(self, reactor, *, worker_cmd=None):
        super().__init__()
        self.reactor = reactor
        self.stopping = False
        self.worker_cmd = worker_cmd
        if self.worker_cmd is None:
            self.worker_cmd = sys.argv[0]
        self.workers = {}
        self.missing_worker_ids = self.get_worker_ids()

    def startService(self):
        """Start the workers."""
        super().startService()
        self.spawnWorkers()

    def stopService(self):
        """Stop the workers."""
        self.stopping = True
        for pid, worker in self.workers.items():
            log.msg("Killing worker pid:%d." % pid)
            worker.signal("KILL")

    def spawnWorkers(self):
        """Spawn the missing workers."""
        if self.stopping:
            # Don't spwan new workers if the service is stopping.
            return
        if self.workers:
            runningImport = max(
                worker.runningImport for worker in self.workers.values()
            )
        else:
            runningImport = False

        # Work on a copy to avoid races
        for worker_id in list(self.missing_worker_ids):
            if not runningImport:
                self._spawnWorker(worker_id, runningImport=True)
                runningImport = True
            else:
                self._spawnWorker(worker_id)

    def registerWorker(self, worker):
        """Register the worker."""
        self.workers[worker.pid] = worker
        self.missing_worker_ids.remove(worker.worker_id)

    def unregisterWorker(self, worker, status):
        """Worker has died."""
        del self.workers[worker.pid]
        self.missing_worker_ids.append(worker.worker_id)
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

    def _spawnWorker(self, worker_id: str, runningImport: bool = False):
        """Spawn a new worker."""
        worker = WorkerProcess(
            self, worker_id=worker_id, runningImport=runningImport
        )
        env = os.environ.copy()
        env["MAAS_REGIOND_PROCESS_MODE"] = "worker"
        env["MAAS_REGIOND_WORKER_ID"] = worker_id
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
