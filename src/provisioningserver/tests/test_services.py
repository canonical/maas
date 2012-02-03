# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.services`."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import os
import signal
import sys

from fixtures import TempDir
from oops_twisted import OOPSObserver
from provisioningserver.services import (
    LogService,
    OOPSService,
    )
from testtools import TestCase
from testtools.content import content_from_file
from testtools.deferredruntest import AsynchronousDeferredRunTest
from twisted.application.service import MultiService
from twisted.python.log import (
    FileLogObserver,
    theLogPublisher,
    )
from twisted.python.logfile import LogFile


class TestServicesBase:

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def setUp(self):
        super(TestServicesBase, self).setUp()
        self.observers = theLogPublisher.observers[:]
        self.services = MultiService()
        self.services.privilegedStartService()
        self.services.startService()

    def tearDown(self):
        super(TestServicesBase, self).tearDown()
        d = self.services.stopService()
        # The log file must be read in right after services have stopped,
        # before the temporary directory where the log lives is removed.
        d.addBoth(lambda ignore: self.addDetailFromLog())
        d.addBoth(lambda ignore: self.assertNoObserversLeftBehind())
        return d

    def addDetailFromLog(self):
        content = content_from_file(self.log_filename, buffer_now=True)
        self.addDetail("log", content)

    def assertNoObserversLeftBehind(self):
        self.assertEqual(self.observers, theLogPublisher.observers)


class TestLogService(TestServicesBase, TestCase):
    """Tests for `provisioningserver.services.LogService`."""

    def test_log_to_stdout(self):
        log_service = LogService("-")
        log_service.setServiceParent(self.services)
        self.assertIsInstance(log_service.observer, FileLogObserver)
        self.assertEqual("-", log_service.filename)
        self.assertEqual(sys.stdout, log_service.logfile)
        # The SIGUSR1 signal handler is untouched.
        self.assertEqual(
            signal.getsignal(signal.SIGUSR1),
            signal.SIG_DFL)

    def test_log_to_file(self):
        tempdir = self.useFixture(TempDir()).path
        log_filename = os.path.join(tempdir, "test.log")
        log_service = LogService(log_filename)
        log_service.setServiceParent(self.services)
        self.assertIsInstance(log_service.observer, FileLogObserver)
        self.assertEqual(log_filename, log_service.filename)
        self.assertIsInstance(log_service.logfile, LogFile)
        self.assertEqual(log_filename, log_service.logfile.path)
        # The SIGUSR1 signal handler is set.
        self.assertEqual(
            signal.getsignal(signal.SIGUSR1),
            log_service._signal_handler)


class TestOOPSService(TestServicesBase, TestCase):
    """Tests for `provisioningserver.services.OOPSService`."""

    def setUp(self):
        super(TestOOPSService, self).setUp()
        # OOPSService relies upon LogService.
        self.tempdir = self.useFixture(TempDir()).path
        self.log_filename = os.path.join(self.tempdir, "test.log")
        self.log_service = LogService(self.log_filename)
        self.log_service.setServiceParent(self.services)

    def test_minimal(self):
        oops_service = OOPSService(self.log_service, None, None)
        oops_service.setServiceParent(self.services)
        observer = oops_service.observer
        self.assertIsInstance(observer, OOPSObserver)
        self.assertEqual([], observer.config.publishers)
        self.assertEqual({}, observer.config.template)

    def test_with_all_params(self):
        oops_dir = os.path.join(self.tempdir, "oops")
        oops_service = OOPSService(self.log_service, oops_dir, "Sidebottom")
        oops_service.setServiceParent(self.services)
        observer = oops_service.observer
        self.assertIsInstance(observer, OOPSObserver)
        self.assertEqual(1, len(observer.config.publishers))
        self.assertEqual(
            {"reporter": "Sidebottom"},
            observer.config.template)
