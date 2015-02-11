# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for provisioningserver.rpc.service"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random
import socket
import subprocess

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTwistedRunTest
from mock import Mock
from provisioningserver.rpc import service
from provisioningserver.rpc.service import (
    _connect_check,
    _service_action,
    connect_check,
    service_action,
    )
from provisioningserver.testing.testcase import PservTestCase
from twisted.internet import defer


class TestServiceAction(PservTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    @defer.inlineCallbacks
    def test__connect_check_calls__service_check_using_deferToThread(self):
        deferToThread = self.patch(service, 'deferToThread')
        deferToThread.return_value = defer.succeed(None)
        service_name = factory.make_name('service')
        action = factory.make_name('action')
        yield service_action(service_name, action)
        self.assertThat(
            deferToThread, MockCalledOnceWith(
                _service_action, service_name))


class TestInternalServiceAction(PservTestCase):

    def test___service_check_runs_command(self):
        service_name = factory.make_name('service')
        action = factory.make_name('action')
        output = factory.make_name('output')
        fake_popen = self.patch(service, 'Popen')
        fake_process = Mock()
        fake_popen.return_value = fake_process
        fake_process.communicate = Mock(
            return_value=(output, factory.make_name()))
        fake_process.wait = Mock(return_value=0)
        result = _service_action(service_name, action)
        self.assertEqual((True, output), result)
        self.assertThat(
            fake_popen, MockCalledOnceWith(
                ['service', service_name, action],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, close_fds=True))


class TestConnectCheck(PservTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    @defer.inlineCallbacks
    def test__connect_check_calls__service_check_using_deferToThread(self):
        deferToThread = self.patch(service, 'deferToThread')
        deferToThread.return_value = defer.succeed(None)
        host = factory.make_name()
        port = random.randint(2, 2000)
        yield connect_check(port, host)
        self.assertThat(
            deferToThread, MockCalledOnceWith(
                _connect_check, port, host))


class TestInternalConnectCheck(PservTestCase):

    def test___connect_check_reports_open_port(self):
        self.patch(service, 'socket')
        result = _connect_check(12, 'localhost')
        self.assertEqual(result, (True, ''))

    def test___connect_check_reports_closed_port(self):
        exception_name = factory.make_name()
        fake_connect = Mock()
        fake_connect.connect = Mock(
            side_effect=Exception(exception_name))
        fake_socket = self.patch(service, 'socket')
        fake_socket.return_value = fake_connect
        port = random.randint(1, 2000)
        result = _connect_check(port, 'localhost')
        self.assertThat(
            fake_socket,
            MockCalledOnceWith(socket.AF_INET, socket.SOCK_STREAM))
        self.assertThat(
            fake_connect.connect,
            MockCalledOnceWith(("localhost", port)))
        self.assertEqual(
            result,
            (
                False,
                exception_name,
            )
        )
