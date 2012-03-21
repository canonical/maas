# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `zeroconfservice`."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import itertools
import subprocess

from maasserver.zeroconfservice import ZeroconfService
from maastesting.factory import factory
from maastesting.testcase import TestCase
from testtools.content import text_content


class TestZeroconfService(TestCase):
    """Test :class:`ZeroconfService`.

    These tests will actually inject data in the system Avahi service. It
    would be nice to isolate it from the system Avahi service, but there's a
    lot of work involved in writing a private DBus session with a mock Avahi
    service on it, probably more than it's worth.
    """

    STYPE = '_maas_zeroconftest._tcp'

    count = itertools.count(1)

    def avahi_browse(self, service_type, timeout=3):
        """Return the list of published Avahi service through avahi-browse."""
        # Doing this from pure python would be a pain, as it would involve
        # running a glib mainloop. And stopping one is hard. Much easier to
        # kill an external process. This slows test, and could be fragile,
        # but it's the best I've come with.
        command = (
            'avahi-browse', '--no-db-lookup', '--parsable',
            '--terminate', service_type)
        browser = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = browser.communicate()
        self.addDetail("stdout", text_content(stdout))
        self.addDetail("stderr", text_content(stderr))
        names = []
        for record in stdout.splitlines():
            fields = record.split(';')
            names.append(fields[3])
        return names

    def getUniqueServiceNameAndPort(self):
        # getUniqueString() generates an invalid service name
        name = 'My-Test-Service-%d' % next(self.count)
        port = factory.getRandomPort()
        return name, port

    def test_publish(self):
        # Calling publish() should make the service name available
        # over Avahi.
        name, port = self.getUniqueServiceNameAndPort()
        service = ZeroconfService(name, port, self.STYPE)
        service.publish()
        # This will unregister the published name from Avahi.
        self.addCleanup(service.unpublish)
        services = self.avahi_browse(self.STYPE)
        self.assertIn(name, services)

    def test_unpublish(self):
        # Calling unpublish() should remove the published
        # service name from Avahi.
        name, port = self.getUniqueServiceNameAndPort()
        service = ZeroconfService(name, port, self.STYPE)
        service.publish()
        service.unpublish()
        services = self.avahi_browse(self.STYPE)
        self.assertNotIn(name, services)
