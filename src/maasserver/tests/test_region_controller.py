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
from maasserver.models.dnspublication import DNSPublication
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

    def test_init_sets_properties(self):
        service = RegionControllerService(sentinel.listener)
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
        service = RegionControllerService(listener)
        service.startService()
        yield service.processingDefer
        self.assertThat(
            listener.register,
            MockCallsMatch(
                call("sys_dns", service.markDNSForUpdate),
                call("sys_proxy", service.markProxyForUpdate)))

    @wait_for_reactor
    @inlineCallbacks
    def test_startService_calls_markDNSForUpdate(self):
        listener = MagicMock()
        service = RegionControllerService(listener)
        mock_markDNSForUpdate = self.patch(service, "markDNSForUpdate")
        service.startService()
        yield service.processingDefer
        self.assertThat(mock_markDNSForUpdate, MockCalledOnceWith(None, None))

    @wait_for_reactor
    @inlineCallbacks
    def test_startService_calls_markProxyForUpdate(self):
        listener = MagicMock()
        service = RegionControllerService(listener)
        mock_markProxyForUpdate = self.patch(service, "markProxyForUpdate")
        service.startService()
        yield service.processingDefer
        self.assertThat(
            mock_markProxyForUpdate, MockCalledOnceWith(None, None))

    def test_stopService_calls_unregister_on_the_listener(self):
        listener = MagicMock()
        service = RegionControllerService(listener)
        service.stopService()
        self.assertThat(
            listener.unregister,
            MockCallsMatch(
                call("sys_dns", service.markDNSForUpdate),
                call("sys_proxy", service.markProxyForUpdate)))

    @wait_for_reactor
    @inlineCallbacks
    def test_stopService_handles_canceling_processing(self):
        listener = MagicMock()
        service = RegionControllerService(listener)
        service.startProcessing()
        yield service.stopService()
        self.assertIsNone(service.processingDefer)

    def test_markDNSForUpdate_sets_needsDNSUpdate_and_starts_process(self):
        listener = MagicMock()
        service = RegionControllerService(listener)
        mock_startProcessing = self.patch(service, "startProcessing")
        service.markDNSForUpdate(None, None)
        self.assertTrue(service.needsDNSUpdate)
        self.assertThat(mock_startProcessing, MockCalledOnceWith())

    def test_markProxyForUpdate_sets_needsProxyUpdate_and_starts_process(self):
        listener = MagicMock()
        service = RegionControllerService(listener)
        mock_startProcessing = self.patch(service, "startProcessing")
        service.markProxyForUpdate(None, None)
        self.assertTrue(service.needsProxyUpdate)
        self.assertThat(mock_startProcessing, MockCalledOnceWith())

    def test_startProcessing_doesnt_call_start_when_looping_call_running(self):
        service = RegionControllerService(sentinel.listener)
        mock_start = self.patch(service.processing, "start")
        service.processing.running = True
        service.startProcessing()
        self.assertThat(mock_start, MockNotCalled())

    def test_startProcessing_calls_start_when_looping_call_not_running(self):
        service = RegionControllerService(sentinel.listener)
        mock_start = self.patch(service.processing, "start")
        service.startProcessing()
        self.assertThat(
            mock_start,
            MockCalledOnceWith(0.1, now=False))

    @wait_for_reactor
    @inlineCallbacks
    def test_process_doesnt_update_zones_when_nothing_to_process(self):
        service = RegionControllerService(sentinel.listener)
        service.needsDNSUpdate = False
        mock_dns_update_all_zones = self.patch(
            region_controller, "dns_update_all_zones")
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(mock_dns_update_all_zones, MockNotCalled())

    @wait_for_reactor
    @inlineCallbacks
    def test_process_doesnt_proxy_update_config_when_nothing_to_process(self):
        service = RegionControllerService(sentinel.listener)
        service.needsProxyUpdate = False
        mock_proxy_update_config = self.patch(
            region_controller, "proxy_update_config")
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(mock_proxy_update_config, MockNotCalled())

    @wait_for_reactor
    @inlineCallbacks
    def test_process_stops_processing(self):
        service = RegionControllerService(sentinel.listener)
        service.needsDNSUpdate = False
        service.startProcessing()
        yield service.processingDefer
        self.assertIsNone(service.processingDefer)

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_zones(self):
        service = RegionControllerService(sentinel.listener)
        service.needsDNSUpdate = True
        dns_result = (
            random.randint(1, 1000), True, [
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
    def test_process_zones_kills_bind_on_failed_reload(self):
        service = RegionControllerService(sentinel.listener)
        service.needsDNSUpdate = True
        service.retryOnFailure = True
        dns_result_0 = (
            random.randint(1, 1000), False, [
                factory.make_name('domain')
                for _ in range(3)
            ])
        dns_result_1 = (dns_result_0[0], True, dns_result_0[2])
        mock_dns_update_all_zones = self.patch(
            region_controller, "dns_update_all_zones")
        mock_dns_update_all_zones.side_effect = [dns_result_0, dns_result_1]

        service._checkSerialCalled = False
        orig_checkSerial = service._checkSerial

        def _checkSerial(result):
            if service._checkSerialCalled:
                return dns_result_1
            service._checkSerialCalled = True
            return orig_checkSerial(result)

        mock_check_serial = self.patch(service, "_checkSerial")
        mock_check_serial.side_effect = _checkSerial
        mock_killService = self.patch(
            region_controller.service_monitor, 'killService')
        mock_killService.return_value = succeed(None)
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(
            mock_dns_update_all_zones, MockCallsMatch(call(), call()))
        self.assertThat(
            mock_check_serial,
            MockCallsMatch(call(dns_result_0), call(dns_result_1)))
        self.assertThat(
            mock_killService, MockCalledOnceWith("bind9"))

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_proxy(self):
        service = RegionControllerService(sentinel.listener)
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
    def test_process_updates_zones_logs_failure(self):
        service = RegionControllerService(sentinel.listener)
        service.needsDNSUpdate = True
        service.retryOnFailure = False
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
        service = RegionControllerService(sentinel.listener)
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
    def test_process_updates_bind_and_proxy(self):
        service = RegionControllerService(sentinel.listener)
        service.needsDNSUpdate = True
        service.needsProxyUpdate = True
        dns_result = (
            random.randint(1, 1000), True, [
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
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(
            mock_dns_update_all_zones, MockCalledOnceWith())
        self.assertThat(mock_check_serial, MockCalledOnceWith(dns_result))
        self.assertThat(
            mock_proxy_update_config, MockCalledOnceWith(reload_proxy=True))

    def make_soa_result(self, serial):
        return RRHeader(
            type=SOA, cls=A, ttl=30, payload=Record_SOA(serial=serial))

    @wait_for_reactor
    def test__check_serial_doesnt_raise_error_on_successful_serial_match(self):
        service = RegionControllerService(sentinel.listener)
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
        return service._checkSerial((formatted_serial, True, dns_names))

    @wait_for_reactor
    @inlineCallbacks
    def test__check_serial_raise_error_after_30_tries(self):
        service = RegionControllerService(sentinel.listener)
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
            yield service._checkSerial((formatted_serial, True, dns_names))

    @wait_for_reactor
    @inlineCallbacks
    def test__check_serial_handles_ValueError(self):
        service = RegionControllerService(sentinel.listener)
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
            yield service._checkSerial((formatted_serial, True, dns_names))

    @wait_for_reactor
    @inlineCallbacks
    def test__check_serial_handles_TimeoutError(self):
        service = RegionControllerService(sentinel.listener)
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
            yield service._checkSerial((formatted_serial, True, dns_names))


class TestRegionControllerServiceTransactional(MAASTransactionServerTestCase):

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
            publications[-1].serial, True, [
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
            publications[-1].serial, True, [
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
