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

from apiclient.testing.credentials import make_api_credentials
from fixtures import EnvironmentVariableFixture
from maastesting import testcase
from maastesting.factory import factory
from provisioningserver.auth import (
    record_api_credentials,
    record_nodegroup_uuid,
    )
from provisioningserver.testing.worker_cache import WorkerCacheFixture
from twisted.internet import reactor
from twisted.python import threadable


class PservTestCase(testcase.MAASTestCase):

    def setUp(self):
        super(PservTestCase, self).setUp()
        self.useFixture(WorkerCacheFixture())

    def make_maas_url(self):
        return 'http://127.0.0.1/%s' % factory.make_name('path')

    def set_maas_url(self):
        self.useFixture(
            EnvironmentVariableFixture("MAAS_URL", self.make_maas_url()))

    def set_api_credentials(self):
        record_api_credentials(':'.join(make_api_credentials()))

    def set_node_group_uuid(self):
        nodegroup_uuid = factory.make_name('nodegroupuuid')
        record_nodegroup_uuid(nodegroup_uuid)

    def set_secrets(self):
        """Setup all secrets that we would get from refresh_secrets."""
        self.set_maas_url()
        self.set_api_credentials()
        self.set_node_group_uuid()

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
