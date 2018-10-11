# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the region controller service."""

__all__ = []

import random
from unittest.mock import (
    ANY,
    call,
    MagicMock,
    sentinel,
)

from crochet import wait_for
from maasserver import region_controller
from maasserver.models.config import Config
from maasserver.models.dnspublication import DNSPublication
from maasserver.models.rbacsync import RBACSync
from maasserver.models.resourcepool import ResourcePool
from maasserver.rbac import Resource
from maasserver.region_controller import (
    DNSReloadError,
    RegionControllerService,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.threads import deferToDatabase
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from testtools import ExpectedException
from testtools.matchers import MatchesStructure
from twisted.internet import reactor
from twisted.internet.defer import (
    fail,
    inlineCallbacks,
    succeed,
)
from twisted.names.dns import (
    A,
    Record_SOA,
    RRHeader,
    SOA,
)


wait_for_reactor = wait_for(30)  # 30 seconds.


class TestRegionControllerService(MAASServerTestCase):

    def make_service(self, listener):
        # Don't retry on failure or the tests will loop forever.
        return RegionControllerService(listener, retryOnFailure=False)

    def test_init_sets_properties(self):
        service = self.make_service(sentinel.listener)
        self.assertThat(
            service,
            MatchesStructure.byEquality(
                clock=reactor,
                processingDefer=None,
                needsDNSUpdate=False,
                postgresListener=sentinel.listener))

    @wait_for_reactor
    @inlineCallbacks
    def test_startService_registers_with_postgres_listener(self):
        listener = MagicMock()
        service = self.make_service(listener)
        service.startService()
        yield service.processingDefer
        self.assertThat(
            listener.register,
            MockCallsMatch(
                call("sys_dns", service.markDNSForUpdate),
                call("sys_proxy", service.markProxyForUpdate),
                call("sys_rbac", service.markRBACForUpdate)))

    @wait_for_reactor
    @inlineCallbacks
    def test_startService_calls_markDNSForUpdate(self):
        listener = MagicMock()
        service = self.make_service(listener)
        mock_markDNSForUpdate = self.patch(service, "markDNSForUpdate")
        service.startService()
        yield service.processingDefer
        self.assertThat(mock_markDNSForUpdate, MockCalledOnceWith(None, None))

    @wait_for_reactor
    @inlineCallbacks
    def test_startService_calls_markProxyForUpdate(self):
        listener = MagicMock()
        service = self.make_service(listener)
        mock_markProxyForUpdate = self.patch(service, "markProxyForUpdate")
        service.startService()
        yield service.processingDefer
        self.assertThat(
            mock_markProxyForUpdate, MockCalledOnceWith(None, None))

    @wait_for_reactor
    @inlineCallbacks
    def test_startService_calls_markRBACForUpdate(self):
        listener = MagicMock()
        service = self.make_service(listener)
        mock_markRBACForUpdate = self.patch(service, "markRBACForUpdate")
        service.startService()
        yield service.processingDefer
        self.assertThat(
            mock_markRBACForUpdate, MockCalledOnceWith(None, None))

    def test_stopService_calls_unregister_on_the_listener(self):
        listener = MagicMock()
        service = self.make_service(listener)
        service.stopService()
        self.assertThat(
            listener.unregister,
            MockCallsMatch(
                call("sys_dns", service.markDNSForUpdate),
                call("sys_proxy", service.markProxyForUpdate),
                call("sys_rbac", service.markRBACForUpdate)))

    @wait_for_reactor
    @inlineCallbacks
    def test_stopService_handles_canceling_processing(self):
        listener = MagicMock()
        service = self.make_service(listener)
        service.startProcessing()
        yield service.stopService()
        self.assertIsNone(service.processingDefer)

    def test_markDNSForUpdate_sets_needsDNSUpdate_and_starts_process(self):
        listener = MagicMock()
        service = self.make_service(listener)
        mock_startProcessing = self.patch(service, "startProcessing")
        service.markDNSForUpdate(None, None)
        self.assertTrue(service.needsDNSUpdate)
        self.assertThat(mock_startProcessing, MockCalledOnceWith())

    def test_markProxyForUpdate_sets_needsProxyUpdate_and_starts_process(self):
        listener = MagicMock()
        service = self.make_service(listener)
        mock_startProcessing = self.patch(service, "startProcessing")
        service.markProxyForUpdate(None, None)
        self.assertTrue(service.needsProxyUpdate)
        self.assertThat(mock_startProcessing, MockCalledOnceWith())

    def test_markRBACForUpdate_sets_needsRBACUpdate_and_starts_process(self):
        listener = MagicMock()
        service = self.make_service(listener)
        mock_startProcessing = self.patch(service, "startProcessing")
        service.markRBACForUpdate(None, None)
        self.assertTrue(service.needsRBACUpdate)
        self.assertThat(mock_startProcessing, MockCalledOnceWith())

    def test_startProcessing_doesnt_call_start_when_looping_call_running(self):
        service = self.make_service(sentinel.listener)
        mock_start = self.patch(service.processing, "start")
        service.processing.running = True
        service.startProcessing()
        self.assertThat(mock_start, MockNotCalled())

    def test_startProcessing_calls_start_when_looping_call_not_running(self):
        service = self.make_service(sentinel.listener)
        mock_start = self.patch(service.processing, "start")
        service.startProcessing()
        self.assertThat(
            mock_start,
            MockCalledOnceWith(0.1, now=False))

    @wait_for_reactor
    @inlineCallbacks
    def test_process_doesnt_update_zones_when_nothing_to_process(self):
        service = self.make_service(sentinel.listener)
        service.needsDNSUpdate = False
        mock_dns_update_all_zones = self.patch(
            region_controller, "dns_update_all_zones")
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(mock_dns_update_all_zones, MockNotCalled())

    @wait_for_reactor
    @inlineCallbacks
    def test_process_doesnt_proxy_update_config_when_nothing_to_process(self):
        service = self.make_service(sentinel.listener)
        service.needsProxyUpdate = False
        mock_proxy_update_config = self.patch(
            region_controller, "proxy_update_config")
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(mock_proxy_update_config, MockNotCalled())

    @wait_for_reactor
    @inlineCallbacks
    def test_process_doesnt_call_rbacSync_when_nothing_to_process(self):
        service = self.make_service(sentinel.listener)
        service.needsRBACUpdate = False
        mock_rbacSync = self.patch(service, "_rbacSync")
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(mock_rbacSync, MockNotCalled())

    @wait_for_reactor
    @inlineCallbacks
    def test_process_stops_processing(self):
        service = self.make_service(sentinel.listener)
        service.needsDNSUpdate = False
        service.startProcessing()
        yield service.processingDefer
        self.assertIsNone(service.processingDefer)

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_zones(self):
        service = self.make_service(sentinel.listener)
        service.needsDNSUpdate = True
        dns_result = (
            random.randint(1, 1000), [
                factory.make_name('domain')
                for _ in range(3)
            ])
        mock_dns_update_all_zones = self.patch(
            region_controller, "dns_update_all_zones")
        mock_dns_update_all_zones.return_value = dns_result
        mock_check_serial = self.patch(service, "_checkSerial")
        mock_check_serial.return_value = succeed(dns_result)
        mock_msg = self.patch(
            region_controller.log, "msg")
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(mock_dns_update_all_zones, MockCalledOnceWith())
        self.assertThat(mock_check_serial, MockCalledOnceWith(dns_result))
        self.assertThat(
            mock_msg,
            MockCalledOnceWith(
                "Reloaded DNS configuration; regiond started."))

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_proxy(self):
        service = self.make_service(sentinel.listener)
        service.needsProxyUpdate = True
        mock_proxy_update_config = self.patch(
            region_controller, "proxy_update_config")
        mock_proxy_update_config.return_value = succeed(None)
        mock_msg = self.patch(
            region_controller.log, "msg")
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(
            mock_proxy_update_config, MockCalledOnceWith(reload_proxy=True))
        self.assertThat(
            mock_msg,
            MockCalledOnceWith("Successfully configured proxy."))

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_rbac(self):
        service = self.make_service(sentinel.listener)
        service.needsRBACUpdate = True
        mock_rbacSync = self.patch(service, "_rbacSync")
        mock_rbacSync.return_value = []
        mock_msg = self.patch(
            region_controller.log, "msg")
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(
            mock_rbacSync, MockCalledOnceWith())
        self.assertThat(
            mock_msg,
            MockCalledOnceWith("Synced RBAC service; regiond started."))

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_zones_logs_failure(self):
        service = self.make_service(sentinel.listener)
        service.needsDNSUpdate = True
        mock_dns_update_all_zones = self.patch(
            region_controller, "dns_update_all_zones")
        mock_dns_update_all_zones.side_effect = factory.make_exception()
        mock_err = self.patch(
            region_controller.log, "err")
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(mock_dns_update_all_zones, MockCalledOnceWith())
        self.assertThat(
            mock_err,
            MockCalledOnceWith(ANY, "Failed configuring DNS."))

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_proxy_logs_failure(self):
        service = self.make_service(sentinel.listener)
        service.needsProxyUpdate = True
        mock_proxy_update_config = self.patch(
            region_controller, "proxy_update_config")
        mock_proxy_update_config.return_value = fail(factory.make_exception())
        mock_err = self.patch(
            region_controller.log, "err")
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(
            mock_proxy_update_config, MockCalledOnceWith(reload_proxy=True))
        self.assertThat(
            mock_err,
            MockCalledOnceWith(ANY, "Failed configuring proxy."))

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_rbac_logs_failure(self):
        service = self.make_service(sentinel.listener)
        service.needsRBACUpdate = True
        mock_rbacSync = self.patch(service, "_rbacSync")
        mock_rbacSync.side_effect = factory.make_exception()
        mock_err = self.patch(region_controller.log, "err")
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(
            mock_err,
            MockCalledOnceWith(ANY, "Failed syncing resources to RBAC."))

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_bind_proxy_and_rbac(self):
        service = self.make_service(sentinel.listener)
        service.needsDNSUpdate = True
        service.needsProxyUpdate = True
        service.needsRBACUpdate = True
        dns_result = (
            random.randint(1, 1000), [
                factory.make_name('domain')
                for _ in range(3)
            ])
        mock_dns_update_all_zones = self.patch(
            region_controller, "dns_update_all_zones")
        mock_dns_update_all_zones.return_value = dns_result
        mock_check_serial = self.patch(service, "_checkSerial")
        mock_check_serial.return_value = succeed(dns_result)
        mock_proxy_update_config = self.patch(
            region_controller, "proxy_update_config")
        mock_proxy_update_config.return_value = succeed(None)
        mock_rbacSync = self.patch(service, "_rbacSync")
        mock_rbacSync.return_value = None
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(
            mock_dns_update_all_zones, MockCalledOnceWith())
        self.assertThat(mock_check_serial, MockCalledOnceWith(dns_result))
        self.assertThat(
            mock_proxy_update_config, MockCalledOnceWith(reload_proxy=True))
        self.assertThat(
            mock_rbacSync, MockCalledOnceWith())

    def make_soa_result(self, serial):
        return RRHeader(
            type=SOA, cls=A, ttl=30, payload=Record_SOA(serial=serial))

    @wait_for_reactor
    def test__check_serial_doesnt_raise_error_on_successful_serial_match(self):
        service = self.make_service(sentinel.listener)
        result_serial = random.randint(1, 1000)
        formatted_serial = '{0:10d}'.format(result_serial)
        dns_names = [
            factory.make_name('domain')
            for _ in range(3)
        ]
        # Mock pause so test runs faster.
        self.patch(region_controller, "pause").return_value = succeed(None)
        mock_lookup = self.patch(service.dnsResolver, "lookupAuthority")
        mock_lookup.side_effect = [
            # First pass no results.
            succeed(([], [], [])),
            succeed(([], [], [])),
            succeed(([], [], [])),
            # First domain valid result.
            succeed(([self.make_soa_result(result_serial)], [], [])),
            succeed(([], [], [])),
            succeed(([], [], [])),
            # Second domain wrong serial.
            succeed(([self.make_soa_result(result_serial - 1)], [], [])),
            succeed(([], [], [])),
            # Third domain correct serial.
            succeed(([], [], [])),
            succeed(([self.make_soa_result(result_serial)], [], [])),
            # Second domain correct serial.
            succeed(([self.make_soa_result(result_serial)], [], [])),
        ]
        # Error should not be raised.
        return service._checkSerial((formatted_serial, dns_names))

    @wait_for_reactor
    @inlineCallbacks
    def test__check_serial_raise_error_after_30_tries(self):
        service = self.make_service(sentinel.listener)
        result_serial = random.randint(1, 1000)
        formatted_serial = '{0:10d}'.format(result_serial)
        dns_names = [
            factory.make_name('domain')
            for _ in range(3)
        ]
        # Mock pause so test runs faster.
        self.patch(region_controller, "pause").return_value = succeed(None)
        mock_lookup = self.patch(service.dnsResolver, "lookupAuthority")
        mock_lookup.side_effect = lambda *args: succeed(([], [], []))
        # Error should not be raised.
        with ExpectedException(DNSReloadError):
            yield service._checkSerial((formatted_serial, dns_names))

    @wait_for_reactor
    @inlineCallbacks
    def test__check_serial_handles_ValueError(self):
        service = self.make_service(sentinel.listener)
        result_serial = random.randint(1, 1000)
        formatted_serial = '{0:10d}'.format(result_serial)
        dns_names = [
            factory.make_name('domain')
            for _ in range(3)
        ]
        # Mock pause so test runs faster.
        self.patch(region_controller, "pause").return_value = succeed(None)
        mock_lookup = self.patch(service.dnsResolver, "lookupAuthority")
        mock_lookup.side_effect = ValueError()
        # Error should not be raised.
        with ExpectedException(DNSReloadError):
            yield service._checkSerial((formatted_serial, dns_names))

    @wait_for_reactor
    @inlineCallbacks
    def test__check_serial_handles_TimeoutError(self):
        service = self.make_service(sentinel.listener)
        result_serial = random.randint(1, 1000)
        formatted_serial = '{0:10d}'.format(result_serial)
        dns_names = [
            factory.make_name('domain')
            for _ in range(3)
        ]
        # Mock pause so test runs faster.
        self.patch(region_controller, "pause").return_value = succeed(None)
        mock_lookup = self.patch(service.dnsResolver, "lookupAuthority")
        mock_lookup.side_effect = TimeoutError()
        # Error should not be raised.
        with ExpectedException(DNSReloadError):
            yield service._checkSerial((formatted_serial, dns_names))

    def test__getRBACClient_returns_None_when_no_url(self):
        service = self.make_service(sentinel.listener)
        service.rbacClient = sentinel.client
        Config.objects.set_config('rbac_url', '')
        self.assertIsNone(service._getRBACClient())
        self.assertIsNone(service.rbacClient)

    def test__getRBACClient_creates_new_client_and_uses_it_again(self):
        self.patch(region_controller, 'get_auth_info')
        Config.objects.set_config('rbac_url', 'http://rbac.example.com')
        service = self.make_service(sentinel.listener)
        client = service._getRBACClient()
        self.assertIsNotNone(client)
        self.assertIs(client, service.rbacClient)
        self.assertIs(client, service._getRBACClient())

    def test__getRBACClient_creates_new_client_when_url_changes(self):
        self.patch(region_controller, 'get_auth_info')
        Config.objects.set_config('rbac_url', 'http://rbac.example.com')
        service = self.make_service(sentinel.listener)
        client = service._getRBACClient()
        Config.objects.set_config('rbac_url', 'http://other.example.com')
        new_client = service._getRBACClient()
        self.assertIsNotNone(new_client)
        self.assertIsNot(new_client, client)
        self.assertIs(new_client, service._getRBACClient())

    def test__getRBACClient_creates_new_client_when_auth_info_changes(self):
        mock_get_auth_info = self.patch(region_controller, 'get_auth_info')
        Config.objects.set_config('rbac_url', 'http://rbac.example.com')
        service = self.make_service(sentinel.listener)
        client = service._getRBACClient()
        mock_get_auth_info.return_value = MagicMock()
        new_client = service._getRBACClient()
        self.assertIsNotNone(new_client)
        self.assertIsNot(new_client, client)
        self.assertIs(new_client, service._getRBACClient())


class TestRegionControllerServiceTransactional(MAASTransactionServerTestCase):

    def make_resource_pools(self):
        rpools = [
            factory.make_ResourcePool()
            for _ in range(3)
        ]
        return rpools, [
            Resource(identifier=rpool.id, name=rpool.name)
            for rpool in ResourcePool.objects.all()
        ]

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_zones_logs_reason_for_single_update(self):
        # Create some fake serial updates with sources for the update.
        def _create_publications():
            return [
                DNSPublication.objects.create(
                    source=factory.make_name('reason'))
                for _ in range(2)
            ]

        publications = yield deferToDatabase(_create_publications)
        service = RegionControllerService(sentinel.listener)
        service.needsDNSUpdate = True
        service.previousSerial = publications[0].serial
        dns_result = (
            publications[-1].serial, [
                factory.make_name('domain')
                for _ in range(3)
            ])
        mock_dns_update_all_zones = self.patch(
            region_controller, "dns_update_all_zones")
        mock_dns_update_all_zones.return_value = dns_result
        mock_check_serial = self.patch(service, "_checkSerial")
        mock_check_serial.return_value = succeed(dns_result)
        mock_msg = self.patch(
            region_controller.log, "msg")
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(mock_dns_update_all_zones, MockCalledOnceWith())
        self.assertThat(mock_check_serial, MockCalledOnceWith(dns_result))
        self.assertThat(
            mock_msg,
            MockCalledOnceWith(
                "Reloaded DNS configuration; %s" % (
                    publications[-1].source)))

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_zones_logs_reason_for_multiple_updates(self):
        # Create some fake serial updates with sources for the update.
        def _create_publications():
            return [
                DNSPublication.objects.create(
                    source=factory.make_name('reason'))
                for _ in range(3)
            ]

        publications = yield deferToDatabase(_create_publications)
        service = RegionControllerService(sentinel.listener)
        service.needsDNSUpdate = True
        service.previousSerial = publications[0].serial
        dns_result = (
            publications[-1].serial, [
                factory.make_name('domain')
                for _ in range(3)
            ])
        mock_dns_update_all_zones = self.patch(
            region_controller, "dns_update_all_zones")
        mock_dns_update_all_zones.return_value = dns_result
        mock_check_serial = self.patch(service, "_checkSerial")
        mock_check_serial.return_value = succeed(dns_result)
        mock_msg = self.patch(
            region_controller.log, "msg")
        service.startProcessing()
        yield service.processingDefer
        expected_msg = "Reloaded DNS configuration: \n"
        expected_msg += '\n'.join(
            ' * %s' % publication.source
            for publication in reversed(publications[1:])
        )
        self.assertThat(mock_dns_update_all_zones, MockCalledOnceWith())
        self.assertThat(mock_check_serial, MockCalledOnceWith(dns_result))
        self.assertThat(
            mock_msg,
            MockCalledOnceWith(expected_msg))

    def test__rbacSync_returns_None_when_nothing_to_do(self):
        RBACSync.objects.clear()

        service = RegionControllerService(sentinel.listener)
        service.rbacInit = True
        self.assertIsNone(service._rbacSync())

    def test__rbacSync_returns_None_and_clears_sync_when_no_client(self):
        RBACSync.objects.create()

        service = RegionControllerService(sentinel.listener)
        self.assertIsNone(service._rbacSync())
        self.assertFalse(RBACSync.objects.exists())

    def test__rbacSync_syncs_on_init(self):
        RBACSync.objects.clear()
        _, resources = self.make_resource_pools()

        rbac_client = MagicMock()
        service = RegionControllerService(sentinel.listener)
        self.patch(service, '_getRBACClient').return_value = rbac_client

        self.assertEquals([], service._rbacSync())
        self.assertThat(
            rbac_client.update_resources,
            MockCalledOnceWith('resource-pool', updates=resources))
        self.assertFalse(RBACSync.objects.exists())

    def test__rbacSync_syncs_on_changes(self):
        RBACSync.objects.clear()
        _, resources = self.make_resource_pools()
        reasons = [
            sync.source
            for sync in RBACSync.objects.changes()
        ]

        rbac_client = MagicMock()
        service = RegionControllerService(sentinel.listener)
        self.patch(service, '_getRBACClient').return_value = rbac_client
        service.rbacInit = True

        self.assertEquals(reasons, service._rbacSync())
        self.assertThat(
            rbac_client.update_resources,
            MockCalledOnceWith('resource-pool', updates=resources))
        self.assertFalse(RBACSync.objects.exists())
