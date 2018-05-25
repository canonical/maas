# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""HTTP image service.

Runs multiple child process to serve the HTTP.
"""

__all__ = [
    "HTTPImageService",
    ]

import os
import sys

from provisioningserver.logger import LegacyLogger
from twisted.application import service
from twisted.internet import protocol
from twisted.internet.process import ProcessExitedAlready


log = LegacyLogger()


class HTTPImageProcess(protocol.ProcessProtocol):

    def __init__(self, service):
        super(HTTPImageProcess, self).__init__()
        self.service = service

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


class HTTPImageService(service.Service, object):
    """
    HTTP image service.

    Manages the lifecycle of the HTTP image workers.
    """

    def __init__(self, reactor, worker_count, *, worker_cmd=None):
        super(HTTPImageService, self).__init__()
        self.reactor = reactor
        self.stopping = False
        self.worker_count = worker_count
        if self.worker_count < 1:
            raise ValueError("worker_count must be greater than 1.")
        self.worker_cmd = worker_cmd
        if self.worker_cmd is None:
            self.worker_cmd = sys.argv[0]
        self.workers = {}

    def startService(self):
        """Start the workers."""
        super(HTTPImageService, self).startService()
        self.spawnWorkers()

    def stopService(self):
        """Stop the workers."""
        self.stopping = True
        for pid, worker in self.workers.items():
            log.msg("Killing HTTP worker pid:%d." % pid)
            worker.signal("KILL")

    def spawnWorkers(self):
        """Spawn the missing workers."""
        if self.stopping:
            # Don't spwan new workers if the service is stopping.
            return
        missing = self.worker_count - len(self.workers)
        for _ in range(missing):
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
            log.msg("Terminating HTTP worker pid:%d." % pid)
            worker.signal("TERM")

    def killWorker(self, pid):
        """Kill the worker."""
        worker = self.workers.get(pid, None)
        if worker:
            log.msg("Killing HTTP worker pid:%d." % pid)
            worker.signal("KILL")

    def _spawnWorker(self, runningImport=False):
        """Spawn a new worker."""
        worker = HTTPImageProcess(self)
        env = os.environ.copy()
        env['MAAS_RACKD_PROCESS_MODE'] = 'http'
        self.reactor.spawnProcess(
            worker, self.worker_cmd, [self.worker_cmd],
            env=env, childFDs={0: 0, 1: 1, 2: 2})
