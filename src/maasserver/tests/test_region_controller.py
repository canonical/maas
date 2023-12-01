# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the region controller service."""


from operator import attrgetter
import random
from unittest.mock import ANY, call, MagicMock, sentinel

from testtools import ExpectedException
from testtools.matchers import MatchesStructure
from twisted.internet import reactor
from twisted.internet.defer import fail, inlineCallbacks, succeed
from twisted.names.dns import A, Record_SOA, RRHeader, SOA

from maasserver import eventloop, region_controller
from maasserver.models.dnspublication import DNSPublication
from maasserver.models.rbacsync import RBAC_ACTION, RBACLastSync, RBACSync
from maasserver.models.resourcepool import ResourcePool
from maasserver.rbac import Resource, SyncConflictError
from maasserver.region_controller import (
    DNSReloadError,
    RegionControllerService,
)
from maasserver.secrets import SecretManager
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from provisioningserver.dns.config import DynamicDNSUpdate
from provisioningserver.utils.events import Event

wait_for_reactor = wait_for()


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
                needsDNSUpdate=True,
                postgresListener=sentinel.listener,
            ),
        )

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
                call("sys_dns_updates", service.queueDynamicDNSUpdate),
                call("sys_proxy", service.markProxyForUpdate),
                call("sys_rbac", service.markRBACForUpdate),
                call("sys_vault_migration", service.restartRegion),
            ),
        )

    def test_startService_markAllForUpdate_on_connect(self):
        listener = MagicMock()
        listener.events.connected = Event()
        service = self.make_service(listener)
        mock_mark_dns_for_update = self.patch(service, "markDNSForUpdate")
        mock_mark_rbac_for_update = self.patch(service, "markRBACForUpdate")
        mock_mark_proxy_for_update = self.patch(service, "markProxyForUpdate")
        service.startService()
        service.postgresListener.events.connected.fire()
        mock_mark_dns_for_update.assert_called_once()
        mock_mark_rbac_for_update.assert_called_once()
        mock_mark_proxy_for_update.assert_called_once()

    def test_stopService_calls_unregister_on_the_listener(self):
        listener = MagicMock()
        service = self.make_service(listener)
        service.stopService()
        self.assertThat(
            listener.unregister,
            MockCallsMatch(
                call("sys_dns", service.markDNSForUpdate),
                call("sys_proxy", service.markProxyForUpdate),
                call("sys_rbac", service.markRBACForUpdate),
                call("sys_vault_migration", service.restartRegion),
            ),
        )

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

    def test_restart_region_restarts_eventloop(self):
        restart_mock = self.patch(eventloop, "restart")
        service = self.make_service(MagicMock())
        service.restartRegion("sys_vault_migration", "")
        restart_mock.assert_called_once()

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
        self.assertThat(mock_start, MockCalledOnceWith(0.1, now=False))

    @wait_for_reactor
    @inlineCallbacks
    def test_reload_dns_on_start(self):
        service = self.make_service(sentinel.listener)
        mock_dns_update_all_zones = self.patch(
            region_controller, "dns_update_all_zones"
        )
        mock_dns_update_all_zones.returnValue = (
            random.randint(1, 1000),
            True,
            [factory.make_name("domain") for _ in range(3)],
        )
        service.startProcessing()
        yield service.processingDefer
        mock_dns_update_all_zones.assert_called_once()
        self.assertFalse(service.needsDNSUpdate)
        self.assertFalse(service._dns_requires_full_reload)

    @wait_for_reactor
    @inlineCallbacks
    def test_process_doesnt_update_zones_when_nothing_to_process(self):
        service = self.make_service(sentinel.listener)
        service.needsDNSUpdate = False
        mock_dns_update_all_zones = self.patch(
            region_controller, "dns_update_all_zones"
        )
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(mock_dns_update_all_zones, MockNotCalled())

    @wait_for_reactor
    @inlineCallbacks
    def test_process_doesnt_proxy_update_config_when_nothing_to_process(self):
        service = self.make_service(sentinel.listener)
        service.needsProxyUpdate = False
        mock_proxy_update_config = self.patch(
            region_controller, "proxy_update_config"
        )
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
            random.randint(1, 1000),
            True,
            [factory.make_name("domain") for _ in range(3)],
        )
        mock_dns_update_all_zones = self.patch(
            region_controller, "dns_update_all_zones"
        )
        mock_dns_update_all_zones.return_value = dns_result
        mock_check_serial = self.patch(service, "_checkSerial")
        mock_check_serial.return_value = succeed(dns_result)
        mock_msg = self.patch(region_controller.log, "msg")
        service.startProcessing()
        yield service.processingDefer
        mock_dns_update_all_zones.assert_called_once_with(
            dynamic_updates=[], requires_reload=True
        )
        self.assertThat(mock_check_serial, MockCalledOnceWith(dns_result))
        self.assertThat(
            mock_msg,
            MockCalledOnceWith("Reloaded DNS configuration; regiond started."),
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_process_zones_kills_bind_on_failed_reload(self):
        service = self.make_service(sentinel.listener)
        service.needsDNSUpdate = True
        service.retryOnFailure = True
        dns_result_0 = (
            random.randint(1, 1000),
            False,
            [factory.make_name("domain") for _ in range(3)],
        )
        dns_result_1 = (dns_result_0[0], True, dns_result_0[2])
        mock_dns_update_all_zones = self.patch(
            region_controller, "dns_update_all_zones"
        )
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
            region_controller.service_monitor, "killService"
        )
        mock_killService.return_value = succeed(None)
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(
            mock_dns_update_all_zones,
            MockCallsMatch(
                call(dynamic_updates=[], requires_reload=True),
                call(dynamic_updates=[], requires_reload=False),
            ),
        )
        self.assertThat(
            mock_check_serial,
            MockCallsMatch(call(dns_result_0), call(dns_result_1)),
        )
        self.assertThat(mock_killService, MockCalledOnceWith("bind9"))

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_proxy(self):
        service = self.make_service(sentinel.listener)
        service.needsProxyUpdate = True
        mock_proxy_update_config = self.patch(
            region_controller, "proxy_update_config"
        )
        mock_proxy_update_config.return_value = succeed(None)
        mock_msg = self.patch(region_controller.log, "msg")
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(
            mock_proxy_update_config, MockCalledOnceWith(reload_proxy=True)
        )
        self.assertThat(
            mock_msg, MockCalledOnceWith("Successfully configured proxy.")
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_rbac(self):
        service = self.make_service(sentinel.listener)
        service.needsRBACUpdate = True
        mock_rbacSync = self.patch(service, "_rbacSync")
        mock_rbacSync.return_value = []
        mock_msg = self.patch(region_controller.log, "msg")
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(mock_rbacSync, MockCalledOnceWith())
        self.assertThat(
            mock_msg,
            MockCalledOnceWith("Synced RBAC service; regiond started."),
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_zones_logs_failure(self):
        service = self.make_service(sentinel.listener)
        service.needsDNSUpdate = True
        mock_dns_update_all_zones = self.patch(
            region_controller, "dns_update_all_zones"
        )
        mock_dns_update_all_zones.side_effect = factory.make_exception()
        mock_err = self.patch(region_controller.log, "err")
        service.startProcessing()
        yield service.processingDefer
        mock_dns_update_all_zones.assert_called_once_with(
            dynamic_updates=[], requires_reload=True
        )
        self.assertThat(
            mock_err, MockCalledOnceWith(ANY, "Failed configuring DNS.")
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_proxy_logs_failure(self):
        service = self.make_service(sentinel.listener)
        service.needsProxyUpdate = True
        mock_proxy_update_config = self.patch(
            region_controller, "proxy_update_config"
        )
        mock_proxy_update_config.return_value = fail(factory.make_exception())
        mock_err = self.patch(region_controller.log, "err")
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(
            mock_proxy_update_config, MockCalledOnceWith(reload_proxy=True)
        )
        self.assertThat(
            mock_err, MockCalledOnceWith(ANY, "Failed configuring proxy.")
        )

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
            MockCalledOnceWith(ANY, "Failed syncing resources to RBAC."),
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_rbac_retries_with_delay(self):
        service = self.make_service(sentinel.listener)
        service.needsRBACUpdate = True
        service.retryOnFailure = True
        service.rbacRetryOnFailureDelay = random.randint(1, 10)
        mock_rbacSync = self.patch(service, "_rbacSync")
        mock_rbacSync.side_effect = [factory.make_exception(), None]
        mock_err = self.patch(region_controller.log, "err")
        mock_pause = self.patch(region_controller, "pause")
        mock_pause.return_value = succeed(None)
        service.startProcessing()
        yield service.processingDefer
        self.assertThat(
            mock_err,
            MockCalledOnceWith(ANY, "Failed syncing resources to RBAC."),
        )
        self.assertThat(
            mock_pause, MockCalledOnceWith(service.rbacRetryOnFailureDelay)
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_bind_proxy_and_rbac(self):
        service = self.make_service(sentinel.listener)
        service.needsDNSUpdate = True
        service.needsProxyUpdate = True
        service.needsRBACUpdate = True
        dns_result = (
            random.randint(1, 1000),
            True,
            [factory.make_name("domain") for _ in range(3)],
        )
        mock_dns_update_all_zones = self.patch(
            region_controller, "dns_update_all_zones"
        )
        mock_dns_update_all_zones.return_value = dns_result
        mock_check_serial = self.patch(service, "_checkSerial")
        mock_check_serial.return_value = succeed(dns_result)
        mock_proxy_update_config = self.patch(
            region_controller, "proxy_update_config"
        )
        mock_proxy_update_config.return_value = succeed(None)
        mock_rbacSync = self.patch(service, "_rbacSync")
        mock_rbacSync.return_value = None
        service.startProcessing()
        yield service.processingDefer
        mock_dns_update_all_zones.assert_called_once_with(
            dynamic_updates=[], requires_reload=True
        )
        mock_proxy_update_config.assert_called_once_with(reload_proxy=True)
        mock_rbacSync.assert_called_once()

    def make_soa_result(self, serial):
        return RRHeader(
            type=SOA, cls=A, ttl=30, payload=Record_SOA(serial=serial)
        )

    @wait_for_reactor
    def test_check_serial_doesnt_raise_error_on_successful_serial_match(self):
        service = self.make_service(sentinel.listener)
        result_serial = random.randint(1, 1000)
        formatted_serial = f"{result_serial:10d}"
        dns_names = [factory.make_name("domain") for _ in range(3)]
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
    def test_check_serial_raise_error_after_30_tries(self):
        service = self.make_service(sentinel.listener)
        result_serial = random.randint(1, 1000)
        formatted_serial = f"{result_serial:10d}"
        dns_names = [factory.make_name("domain") for _ in range(3)]
        # Mock pause so test runs faster.
        self.patch(region_controller, "pause").return_value = succeed(None)
        mock_lookup = self.patch(service.dnsResolver, "lookupAuthority")
        mock_lookup.side_effect = lambda *args: succeed(([], [], []))
        # Error should not be raised.
        with ExpectedException(DNSReloadError):
            yield service._checkSerial((formatted_serial, True, dns_names))

    @wait_for_reactor
    @inlineCallbacks
    def test_check_serial_handles_ValueError(self):
        service = self.make_service(sentinel.listener)
        result_serial = random.randint(1, 1000)
        formatted_serial = f"{result_serial:10d}"
        dns_names = [factory.make_name("domain") for _ in range(3)]
        # Mock pause so test runs faster.
        self.patch(region_controller, "pause").return_value = succeed(None)
        mock_lookup = self.patch(service.dnsResolver, "lookupAuthority")
        mock_lookup.side_effect = ValueError()
        # Error should not be raised.
        with ExpectedException(DNSReloadError):
            yield service._checkSerial((formatted_serial, True, dns_names))

    @wait_for_reactor
    @inlineCallbacks
    def test_check_serial_handles_TimeoutError(self):
        service = self.make_service(sentinel.listener)
        result_serial = random.randint(1, 1000)
        formatted_serial = f"{result_serial:10d}"
        dns_names = [factory.make_name("domain") for _ in range(3)]
        # Mock pause so test runs faster.
        self.patch(region_controller, "pause").return_value = succeed(None)
        mock_lookup = self.patch(service.dnsResolver, "lookupAuthority")
        mock_lookup.side_effect = TimeoutError()
        # Error should not be raised.
        with ExpectedException(DNSReloadError):
            yield service._checkSerial((formatted_serial, True, dns_names))

    def test_getRBACClient_returns_None_when_no_url(self):
        service = self.make_service(sentinel.listener)
        service.rbacClient = sentinel.client
        SecretManager().delete_secret("external-auth")
        self.assertIsNone(service._getRBACClient())
        self.assertIsNone(service.rbacClient)

    def test_getRBACClient_creates_new_client_and_uses_it_again(self):
        self.patch(region_controller, "get_auth_info")
        SecretManager().set_composite_secret(
            "external-auth", {"rbac-url": "http://rbac.example.com"}
        )
        service = self.make_service(sentinel.listener)
        client = service._getRBACClient()
        self.assertIsNotNone(client)
        self.assertIs(client, service.rbacClient)
        self.assertIs(client, service._getRBACClient())

    def test_getRBACClient_creates_new_client_when_url_changes(self):
        self.patch(region_controller, "get_auth_info")
        SecretManager().set_composite_secret(
            "external-auth", {"rbac-url": "http://rbac.example.com"}
        )
        service = self.make_service(sentinel.listener)
        client = service._getRBACClient()
        SecretManager().set_composite_secret(
            "external-auth", {"rbac-url": "http://other.example.com"}
        )
        new_client = service._getRBACClient()
        self.assertIsNotNone(new_client)
        self.assertIsNot(new_client, client)
        self.assertIs(new_client, service._getRBACClient())

    def test_getRBACClient_creates_new_client_when_auth_info_changes(self):
        mock_get_auth_info = self.patch(region_controller, "get_auth_info")
        SecretManager().set_composite_secret(
            "external-auth", {"rbac-url": "http://rbac.example.com"}
        )
        service = self.make_service(sentinel.listener)
        client = service._getRBACClient()
        mock_get_auth_info.return_value = MagicMock()
        new_client = service._getRBACClient()
        self.assertIsNotNone(new_client)
        self.assertIsNot(new_client, client)
        self.assertIs(new_client, service._getRBACClient())

    def test_rbacNeedsFull(self):
        service = self.make_service(sentinel.listener)
        changes = [
            RBACSync(action=RBAC_ACTION.ADD),
            RBACSync(action=RBAC_ACTION.UPDATE),
            RBACSync(action=RBAC_ACTION.REMOVE),
            RBACSync(action=RBAC_ACTION.FULL),
        ]
        self.assertTrue(service._rbacNeedsFull(changes))

    def test_rbacDifference(self):
        service = self.make_service(sentinel.listener)
        changes = [
            RBACSync(
                action=RBAC_ACTION.UPDATE, resource_id=1, resource_name="r-1"
            ),
            RBACSync(
                action=RBAC_ACTION.ADD, resource_id=2, resource_name="r-2"
            ),
            RBACSync(
                action=RBAC_ACTION.UPDATE, resource_id=3, resource_name="r-3"
            ),
            RBACSync(
                action=RBAC_ACTION.REMOVE, resource_id=1, resource_name="r-1"
            ),
            RBACSync(
                action=RBAC_ACTION.UPDATE,
                resource_id=3,
                resource_name="r-3-updated",
            ),
            RBACSync(
                action=RBAC_ACTION.ADD, resource_id=4, resource_name="r-4"
            ),
            RBACSync(
                action=RBAC_ACTION.REMOVE, resource_id=4, resource_name="r-4"
            ),
        ]
        self.assertEqual(
            (
                [
                    Resource(identifier=2, name="r-2"),
                    Resource(identifier=3, name="r-3-updated"),
                ],
                {1},
            ),
            service._rbacDifference(changes),
        )


class TestRegionControllerServiceTransactional(MAASTransactionServerTestCase):
    def make_resource_pools(self):
        rpools = [factory.make_ResourcePool() for _ in range(3)]
        return (
            rpools,
            sorted(
                (
                    Resource(identifier=rpool.id, name=rpool.name)
                    for rpool in ResourcePool.objects.all()
                ),
                key=attrgetter("identifier"),
            ),
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_zones_logs_reason_for_single_update(self):
        # Create some fake serial updates with sources for the update.
        def _create_publications():
            return [
                DNSPublication.objects.create(
                    source=factory.make_name("reason")
                )
                for _ in range(2)
            ]

        publications = yield deferToDatabase(_create_publications)
        service = RegionControllerService(sentinel.listener)
        service.needsDNSUpdate = True
        service.previousSerial = publications[0].serial
        dns_result = (
            publications[-1].serial,
            True,
            [factory.make_name("domain") for _ in range(3)],
        )
        mock_dns_update_all_zones = self.patch(
            region_controller, "dns_update_all_zones"
        )
        mock_dns_update_all_zones.return_value = dns_result
        mock_check_serial = self.patch(service, "_checkSerial")
        mock_check_serial.return_value = succeed(dns_result)
        mock_msg = self.patch(region_controller.log, "msg")
        service.startProcessing()
        yield service.processingDefer
        mock_dns_update_all_zones.assert_called_once_with(
            dynamic_updates=[], requires_reload=True
        )
        self.assertThat(mock_check_serial, MockCalledOnceWith(dns_result))
        self.assertThat(
            mock_msg,
            MockCalledOnceWith(
                "Reloaded DNS configuration; %s" % (publications[-1].source)
            ),
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_zones_logs_reason_for_multiple_updates(self):
        # Create some fake serial updates with sources for the update.
        def _create_publications():
            return [
                DNSPublication.objects.create(
                    source=factory.make_name("reason")
                )
                for _ in range(3)
            ]

        publications = yield deferToDatabase(_create_publications)
        service = RegionControllerService(sentinel.listener)
        service.needsDNSUpdate = True
        service.previousSerial = publications[0].serial
        dns_result = (
            publications[-1].serial,
            True,
            [factory.make_name("domain") for _ in range(3)],
        )
        mock_dns_update_all_zones = self.patch(
            region_controller, "dns_update_all_zones"
        )
        mock_dns_update_all_zones.return_value = dns_result
        mock_check_serial = self.patch(service, "_checkSerial")
        mock_check_serial.return_value = succeed(dns_result)
        mock_msg = self.patch(region_controller.log, "msg")
        service.startProcessing()
        yield service.processingDefer
        expected_msg = "Reloaded DNS configuration: \n"
        expected_msg += "\n".join(
            " * %s" % publication.source
            for publication in reversed(publications[1:])
        )
        mock_dns_update_all_zones.assert_called_once_with(
            dynamic_updates=[], requires_reload=True
        )
        self.assertThat(mock_check_serial, MockCalledOnceWith(dns_result))
        self.assertThat(mock_msg, MockCalledOnceWith(expected_msg))

    def test_rbacSync_returns_None_when_nothing_to_do(self):
        RBACSync.objects.clear("resource-pool")

        service = RegionControllerService(sentinel.listener)
        service.rbacInit = True
        self.assertIsNone(service._rbacSync())

    def test_rbacSync_returns_None_and_clears_sync_when_no_client(self):
        RBACSync.objects.create(resource_type="resource-pool")

        service = RegionControllerService(sentinel.listener)
        self.assertIsNone(service._rbacSync())
        self.assertFalse(RBACSync.objects.exists())

    def test_rbacSync_syncs_on_full_change(self):
        _, resources = self.make_resource_pools()
        RBACSync.objects.clear("resource-pool")
        RBACSync.objects.clear("")
        RBACSync.objects.create(
            resource_type="", resource_name="", source="test"
        )

        rbac_client = MagicMock()
        rbac_client.update_resources.return_value = "x-y-z"
        service = RegionControllerService(sentinel.listener)
        self.patch(service, "_getRBACClient").return_value = rbac_client

        self.assertEqual([], service._rbacSync())
        self.assertThat(
            rbac_client.update_resources,
            MockCalledOnceWith("resource-pool", updates=resources),
        )
        self.assertFalse(RBACSync.objects.exists())
        last_sync = RBACLastSync.objects.get()
        self.assertEqual(last_sync.resource_type, "resource-pool")
        self.assertEqual(last_sync.sync_id, "x-y-z")

    def test_rbacSync_syncs_on_init(self):
        RBACSync.objects.clear("resource-pool")
        _, resources = self.make_resource_pools()

        rbac_client = MagicMock()
        rbac_client.update_resources.return_value = "x-y-z"
        service = RegionControllerService(sentinel.listener)
        self.patch(service, "_getRBACClient").return_value = rbac_client

        self.assertEqual([], service._rbacSync())
        self.assertThat(
            rbac_client.update_resources,
            MockCalledOnceWith("resource-pool", updates=resources),
        )
        self.assertFalse(RBACSync.objects.exists())
        last_sync = RBACLastSync.objects.get()
        self.assertEqual(last_sync.resource_type, "resource-pool")
        self.assertEqual(last_sync.sync_id, "x-y-z")

    def test_rbacSync_syncs_on_changes(self):
        RBACLastSync.objects.create(
            resource_type="resource-pool", sync_id="a-b-c"
        )
        RBACSync.objects.clear("resource-pool")
        _, resources = self.make_resource_pools()
        reasons = [
            sync.source for sync in RBACSync.objects.changes("resource-pool")
        ]

        rbac_client = MagicMock()
        rbac_client.update_resources.return_value = "x-y-z"
        service = RegionControllerService(sentinel.listener)
        self.patch(service, "_getRBACClient").return_value = rbac_client
        service.rbacInit = True

        self.assertEqual(reasons, service._rbacSync())
        self.assertThat(
            rbac_client.update_resources,
            MockCalledOnceWith(
                "resource-pool",
                updates=resources[1:],
                removals=set(),
                last_sync_id="a-b-c",
            ),
        )
        self.assertFalse(RBACSync.objects.exists())
        last_sync = RBACLastSync.objects.get()
        self.assertEqual(last_sync.resource_type, "resource-pool")
        self.assertEqual(last_sync.sync_id, "x-y-z")

    def test_rbacSync_syncs_all_on_conflict(self):
        RBACLastSync.objects.create(
            resource_type="resource-pool", sync_id="a-b-c"
        )
        RBACSync.objects.clear("resource-pool")
        _, resources = self.make_resource_pools()
        reasons = [
            sync.source for sync in RBACSync.objects.changes("resource-pool")
        ]

        rbac_client = MagicMock()
        rbac_client.update_resources.side_effect = [
            SyncConflictError(),
            "x-y-z",
        ]
        service = RegionControllerService(sentinel.listener)
        self.patch(service, "_getRBACClient").return_value = rbac_client
        service.rbacInit = True

        self.assertEqual(reasons, service._rbacSync())
        self.assertThat(
            rbac_client.update_resources,
            MockCallsMatch(
                call(
                    "resource-pool",
                    updates=resources[1:],
                    removals=set(),
                    last_sync_id="a-b-c",
                ),
                call("resource-pool", updates=resources),
            ),
        )
        self.assertFalse(RBACSync.objects.exists())
        last_sync = RBACLastSync.objects.get()
        self.assertEqual(last_sync.resource_type, "resource-pool")
        self.assertEqual(last_sync.sync_id, "x-y-z")

    def test_rbacSync_update_sync_id(self):
        rbac_sync = RBACLastSync.objects.create(
            resource_type="resource-pool", sync_id="a-b-c"
        )
        RBACSync.objects.clear("resource-pool")
        _, resources = self.make_resource_pools()

        rbac_client = MagicMock()
        rbac_client.update_resources.return_value = "x-y-z"
        service = RegionControllerService(sentinel.listener)
        self.patch(service, "_getRBACClient").return_value = rbac_client
        service.rbacInit = True

        service._rbacSync()
        last_sync = RBACLastSync.objects.get()
        self.assertEqual(rbac_sync.id, last_sync.id)
        self.assertEqual(last_sync.resource_type, "resource-pool")
        self.assertEqual(last_sync.sync_id, "x-y-z")

    @wait_for_reactor
    @inlineCallbacks
    def test_queueDynamicDNSUpdate_queues_in_separate_list_while_update_in_progress(
        self,
    ):
        domain = yield deferToDatabase(factory.make_Domain)
        update_result = (random.randint(0, 10), True, [domain.name])
        record = yield deferToDatabase(factory.make_DNSResource, domain=domain)
        service = RegionControllerService(sentinel.listener)

        update_zones = self.patch(region_controller, "dns_update_all_zones")
        update_zones.return_value = update_result
        check_serial = self.patch(service, "_checkSerial")
        check_serial.return_value = succeed(update_result)

        service._dns_update_in_progress = True
        yield service.queueDynamicDNSUpdate(
            factory.make_name(),
            f"INSERT {domain.name} {record.name} A 30 10.10.10.10",
        )
        self.assertCountEqual(service._dns_updates, [])
        self.assertCountEqual(
            service._queued_updates,
            [
                DynamicDNSUpdate(
                    operation="INSERT",
                    name=f"{record.name}.{domain.name}",
                    zone=domain.name,
                    rectype="A",
                    ttl=30,
                    answer="10.10.10.10",
                )
            ],
        )
        service.needsDNSUpdate = True
        yield service.process()
        self.assertCountEqual(
            service._dns_updates,
            [
                DynamicDNSUpdate(
                    operation="INSERT",
                    name=f"{record.name}.{domain.name}",
                    zone=domain.name,
                    rectype="A",
                    ttl=30,
                    answer="10.10.10.10",
                )
            ],
        )
        self.assertCountEqual(service._queued_updates, [])

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_is_set_to_update_when_queued_updates_are_present(self):
        domain = yield deferToDatabase(factory.make_Domain)
        update_result = (random.randint(0, 10), True, [domain.name])
        record = yield deferToDatabase(factory.make_DNSResource, domain=domain)
        service = RegionControllerService(sentinel.listener)

        update_zones = self.patch(region_controller, "dns_update_all_zones")
        update_zones.return_value = update_result
        check_serial = self.patch(service, "_checkSerial")
        check_serial.return_value = succeed(update_result)

        service._dns_update_in_progress = True
        yield service.queueDynamicDNSUpdate(
            factory.make_name(),
            f"INSERT {domain.name} {record.name} A 30 10.10.10.10",
        )
        self.assertCountEqual(service._dns_updates, [])
        expected_updates = [
            DynamicDNSUpdate(
                operation="INSERT",
                name=f"{record.name}.{domain.name}",
                zone=domain.name,
                rectype="A",
                ttl=30,
                answer="10.10.10.10",
            )
        ]
        self.assertCountEqual(
            service._queued_updates,
            expected_updates,
        )
        service.needsDNSUpdate = True

        # 3 times, first to queue the update, second to process the update,
        # third to ensure it doesn't flag for update without updates queued
        for i in range(3):
            if i == 2:
                # should fail on assert that the loop is running when stopping
                try:
                    yield service.process()
                except AssertionError:
                    pass
            else:
                yield service.process()

        update_zones.assert_has_calls(
            [
                call(dynamic_updates=[], requires_reload=True),
                call(dynamic_updates=expected_updates, requires_reload=False),
            ]
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_check_serial_is_skipped_if_a_newer_serial_exists(self):
        domain = yield deferToDatabase(factory.make_Domain)
        update_result = (random.randint(0, 10), True, [domain.name])
        service = RegionControllerService(sentinel.listener)

        query = self.patch(service.dnsResolver, "lookupAuthority")

        service._dns_latest_serial = update_result[0] + 1

        yield service._checkSerial(update_result)

        query.assert_not_called()

    def test_queueDynamicDNSUpdate_can_be_called_synchronously(self):
        domain = factory.make_Domain()
        update_result = (random.randint(0, 10), True, [domain.name])
        record1 = factory.make_DNSResource(domain=domain)
        record2 = factory.make_DNSResource(domain=domain)
        service = RegionControllerService(sentinel.listener)

        update_zones = self.patch(region_controller, "dns_update_all_zones")
        update_zones.return_value = update_result
        check_serial = self.patch(service, "_checkSerial")
        check_serial.return_value = succeed(update_result)

        for _ in range(3):
            service.queueDynamicDNSUpdate(
                factory.make_name(),
                f"INSERT {domain.name} {record1.name} A 30 1.1.1.1",
            )
            service.queueDynamicDNSUpdate(
                factory.make_name(),
                f"INSERT {domain.name} {record2.name} A 30 2.2.2.2",
            )
            service.queueDynamicDNSUpdate(
                factory.make_name(),
                f"DELETE {domain.name} {record1.name} A 30 1.1.1.1",
            )
            service.queueDynamicDNSUpdate(
                factory.make_name(),
                f"DELETE {domain.name} {record2.name} A 30 2.2.2.2",
            )

        self.assertCountEqual(
            service._dns_updates,
            [
                DynamicDNSUpdate(
                    operation="INSERT",
                    name=f"{record1.name}.{domain.name}",
                    zone=domain.name,
                    rectype="A",
                    ttl=30,
                    answer="1.1.1.1",
                ),
                DynamicDNSUpdate(
                    operation="INSERT",
                    name=f"{record2.name}.{domain.name}",
                    zone=domain.name,
                    rectype="A",
                    ttl=30,
                    answer="2.2.2.2",
                ),
                DynamicDNSUpdate(
                    operation="DELETE",
                    name=f"{record1.name}.{domain.name}",
                    zone=domain.name,
                    rectype="A",
                    ttl=None,
                    answer="1.1.1.1",
                ),
                DynamicDNSUpdate(
                    operation="DELETE",
                    name=f"{record2.name}.{domain.name}",
                    zone=domain.name,
                    rectype="A",
                    ttl=None,
                    answer="2.2.2.2",
                ),
                DynamicDNSUpdate(
                    operation="INSERT",
                    name=f"{record1.name}.{domain.name}",
                    zone=domain.name,
                    rectype="A",
                    ttl=30,
                    answer="1.1.1.1",
                ),
                DynamicDNSUpdate(
                    operation="INSERT",
                    name=f"{record2.name}.{domain.name}",
                    zone=domain.name,
                    rectype="A",
                    ttl=30,
                    answer="2.2.2.2",
                ),
                DynamicDNSUpdate(
                    operation="DELETE",
                    name=f"{record1.name}.{domain.name}",
                    zone=domain.name,
                    rectype="A",
                    ttl=None,
                    answer="1.1.1.1",
                ),
                DynamicDNSUpdate(
                    operation="DELETE",
                    name=f"{record2.name}.{domain.name}",
                    zone=domain.name,
                    rectype="A",
                    ttl=None,
                    answer="2.2.2.2",
                ),
                DynamicDNSUpdate(
                    operation="INSERT",
                    name=f"{record1.name}.{domain.name}",
                    zone=domain.name,
                    rectype="A",
                    ttl=30,
                    answer="1.1.1.1",
                ),
                DynamicDNSUpdate(
                    operation="INSERT",
                    name=f"{record2.name}.{domain.name}",
                    zone=domain.name,
                    rectype="A",
                    ttl=30,
                    answer="2.2.2.2",
                ),
                DynamicDNSUpdate(
                    operation="DELETE",
                    name=f"{record1.name}.{domain.name}",
                    zone=domain.name,
                    rectype="A",
                    ttl=None,
                    answer="1.1.1.1",
                ),
                DynamicDNSUpdate(
                    operation="DELETE",
                    name=f"{record2.name}.{domain.name}",
                    zone=domain.name,
                    rectype="A",
                    ttl=None,
                    answer="2.2.2.2",
                ),
            ],
        )
