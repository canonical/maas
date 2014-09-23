# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Provisioningserver-specific test-case classes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'PservTestCase',
    ]

from fixtures import EnvironmentVariableFixture
from maastesting import testcase
from maastesting.factory import factory
from twisted.internet import reactor
from twisted.python import threadable


class PservTestCase(testcase.MAASTestCase):

    def make_maas_url(self):
        return 'http://127.0.0.1/%s' % factory.make_name('path')

    def set_maas_url(self):
        self.useFixture(
            EnvironmentVariableFixture("MAAS_URL", self.make_maas_url()))

    def register_as_io_thread(self):
        """Make the current thread the IO thread.

        When pretending to be the reactor, by using clocks and suchlike,
        register the current thread as the reactor thread, a.k.a. the IO
        thread, to ensure correct operation from things like the `synchronous`
        and `asynchronous` decorators.

        Do not use this when the reactor is running.
        """
        self.assertFalse(
            reactor.running, "Do not use this to change the IO thread "
            "while the reactor is running.")
        self.addCleanup(setattr, threadable, "ioThread", threadable.ioThread)
        threadable.ioThread = threadable.getThreadID()
