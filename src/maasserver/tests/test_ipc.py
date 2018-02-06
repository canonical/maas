# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.ipc`"""

__all__ = []

import os
import random
from unittest.mock import MagicMock

from crochet import wait_for
from fixtures import EnvironmentVariableFixture
from maasserver.ipc import (
    get_ipc_socket_path,
    IPCMasterService,
    IPCWorkerService,
)
from maasserver.testing.factory import factory
from maastesting.fixtures import TempDirectory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.twisted import DeferredValue
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks


wait_for_reactor = wait_for(30)  # 30 seconds.


class TestGetIPCSocketPath(MAASTestCase):

    def test__returns_ipc_socket_env(self):
        path = factory.make_name('path')
        self.useFixture(
            EnvironmentVariableFixture('MAAS_IPC_SOCKET_PATH', path))
        self.assertEquals(path, get_ipc_socket_path())

    def test__returns_ipc_from_maas_root(self):
        path = factory.make_name('path')
        self.useFixture(
            EnvironmentVariableFixture('MAAS_ROOT', path))
        self.assertEquals(
            os.path.join(path, 'maas-regiond.sock'), get_ipc_socket_path())

    def test__returns_ipc_at_default_location(self):
        self.useFixture(
            EnvironmentVariableFixture('MAAS_ROOT', None))
        self.assertEquals(
            '/var/lib/maas/maas-regiond.sock', get_ipc_socket_path())


class TestIPCCommunication(MAASTestCase):

    def setUp(self):
        super(TestIPCCommunication, self).setUp()
        self.ipc_path = os.path.join(
            self.useFixture(TempDirectory()).path, 'maas-regiond.sock')

    def make_IPCMasterService(self, workers=None):
        master = IPCMasterService(
            reactor, workers=workers, socket_path=self.ipc_path)

        dv_connected = DeferredValue()
        original_registerWorker = master.registerWorker

        def mock_registerWorker(*args, **kwargs):
            original_registerWorker(*args, **kwargs)
            dv_connected.set(None)

        new_registerWorker = self.patch(master, 'registerWorker')
        new_registerWorker.side_effect = mock_registerWorker

        dv_disconnected = DeferredValue()
        original_unregisterWorker = master.unregisterWorker

        def mock_unregisterWorker(*args, **kwargs):
            original_unregisterWorker(*args, **kwargs)
            dv_disconnected.set(None)

        new_unregisterWorker = self.patch(master, 'unregisterWorker')
        new_unregisterWorker.side_effect = mock_unregisterWorker

        return master, dv_connected, dv_disconnected

    @wait_for_reactor
    @inlineCallbacks
    def test_worker_registers_and_deregisters(self):
        pid = random.randint(1, 512)
        self.patch(os, 'getpid').return_value = pid
        master, connected, disconnected = self.make_IPCMasterService()
        yield master.startService()
        worker = IPCWorkerService(reactor, socket_path=self.ipc_path)
        yield worker.startService()

        yield connected.get(timeout=2)
        self.assertIn(pid, master.connections)

        yield worker.stopService()

        yield disconnected.get(timeout=2)
        self.assertEquals({}, master.connections)

        yield master.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_master_calls_killWorker_on_deregister(self):
        pid = random.randint(1, 512)
        self.patch(os, 'getpid').return_value = pid
        workers = MagicMock()
        master, connected, disconnected = self.make_IPCMasterService(
            workers=workers)
        yield master.startService()
        worker = IPCWorkerService(reactor, socket_path=self.ipc_path)
        yield worker.startService()

        yield connected.get(timeout=2)
        yield worker.stopService()
        yield disconnected.get(timeout=2)
        yield master.stopService()

        self.assertThat(workers.killWorker, MockCalledOnceWith(pid))
