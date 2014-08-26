# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for periodic DHCP prober."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os

from apiclient.testing.credentials import make_api_credentials
from maastesting.factory import factory
from maastesting.matchers import (
    get_mock_calls,
    HasLength,
    MockCalledOnceWith,
    MockNotCalled,
    )
from mock import ANY
from provisioningserver import cache
from provisioningserver.auth import (
    NODEGROUP_UUID_CACHE_KEY,
    record_api_credentials,
    )
from provisioningserver.dhcp import dhcp_probe_service
from provisioningserver.dhcp.dhcp_probe_service import (
    PeriodicDHCPProbeService,
    )
from provisioningserver.testing.testcase import PservTestCase
from testtools.deferredruntest import AsynchronousDeferredRunTest
from twisted.internet import defer
from twisted.internet.task import Clock


class TestDHCPProbeService(PservTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def setUp(self):
        super(TestDHCPProbeService, self).setUp()
        self.cluster_uuid = factory.make_UUID()
        maas_url = 'http://%s.example.com/%s/' % (
            factory.make_name('host'),
            factory.make_string(),
            )
        api_credentials = make_api_credentials()

        cache.cache.set(NODEGROUP_UUID_CACHE_KEY, self.cluster_uuid)
        os.environ["MAAS_URL"] = maas_url
        cache.cache.set('api_credentials', ':'.join(api_credentials))

        self.knowledge = dict(
            api_credentials=api_credentials,
            maas_url=maas_url,
            nodegroup_uuid=self.cluster_uuid)

    def test_is_called_every_interval(self):
        clock = Clock()
        service = PeriodicDHCPProbeService(clock, self.cluster_uuid)

        # Avoid actually probing
        _probe_dhcp = self.patch(service, '_probe_dhcp')

        # Until the service has started, periodic_probe_dhcp() won't
        # be called.
        self.assertThat(_probe_dhcp, MockNotCalled())

        # The first call is issued at startup.
        service.startService()
        self.assertThat(_probe_dhcp, MockCalledOnceWith(ANY))

        # Wind clock forward one second less than the desired interval.
        clock.advance(service.check_interval - 1)

        # No more periodic calls made.
        self.assertEqual(1, len(get_mock_calls(_probe_dhcp)))

        # Wind clock forward one second, past the interval.
        clock.advance(1)

        # Now there were two calls.
        self.assertThat(get_mock_calls(_probe_dhcp), HasLength(2))

    def test_download_is_initiated_in_new_thread(self):
        clock = Clock()

        # We could patch out 'periodic_probe_task' instead here but this
        # is better because:
        # 1. The former requires spinning the reactor again before being
        #    able to test the result.
        # 2. This way there's no thread to clean up after the test.
        deferToThread = self.patch(dhcp_probe_service, 'deferToThread')
        deferToThread.return_value = defer.succeed(None)
        service = PeriodicDHCPProbeService(clock, self.cluster_uuid)
        service.startService()
        self.assertThat(
            deferToThread, MockCalledOnceWith(
                dhcp_probe_service.detect.periodic_probe_task,
                self.knowledge))

    def test_no_probe_if_api_credentials_not_set(self):
        record_api_credentials(None)
        clock = Clock()
        service = PeriodicDHCPProbeService(clock, self.cluster_uuid)
        _probe_dhcp = self.patch(service, '_probe_dhcp')
        service.startService()
        self.assertThat(_probe_dhcp, MockNotCalled())

    def test_logs_errors(self):
        clock = Clock()
        maaslog = self.patch(dhcp_probe_service, 'maaslog')
        service = PeriodicDHCPProbeService(clock, self.cluster_uuid)
        error_message = factory.make_string()
        self.patch(service, '_probe_dhcp').side_effect = Exception(
            error_message)
        service.startService()
        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "Unable to probe for rogue DHCP servers: %s" %
                error_message))
