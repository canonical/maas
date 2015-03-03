# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for extra services in `provisioningserver.plugin`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import signal
import sys

from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
    )
from provisioningserver.plugin import LogService
from testtools.content import content_from_file
from twisted.application.service import MultiService
from twisted.python.log import (
    FileLogObserver,
    theLogPublisher,
    )
from twisted.python.logfile import LogFile


class TestServicesBase:

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

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


class TestLogService(TestServicesBase, MAASTestCase):
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
        log_filename = self.make_file(name="test.log")
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
