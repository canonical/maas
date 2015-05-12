# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
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

from maastesting.testcase import MAASTwistedRunTest
from testtools.content import content_from_file
from twisted.application.service import MultiService
from twisted.python.log import theLogPublisher


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
