# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the region controller service."""

from operator import attrgetter
import random
from unittest import TestCase
from unittest.mock import ANY, call, MagicMock, sentinel

from twisted.internet import reactor
from twisted.internet.defer import fail, inlineCallbacks, succeed

from maasserver import eventloop, region_controller
from maasserver.models.rbacsync import RBAC_ACTION, RBACLastSync, RBACSync
from maasserver.models.resourcepool import ResourcePool
from maasserver.rbac import Resource, SyncConflictError
from maasserver.region_controller import RegionControllerService
from maasserver.secrets import SecretManager
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maastesting.crochet import wait_for
from provisioningserver.utils.events import Event

wait_for_reactor = wait_for()


class TestRegionControllerService(MAASServerTestCase):
    assertRaises = TestCase.assertRaises

    def make_service(self, listener=MagicMock(), dbtasks=MagicMock()):  # noqa: B008
        # Don't retry on failure or the tests will loop forever.
        return RegionControllerService(listener, dbtasks, retryOnFailure=False)

    def test_init_sets_properties(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        self.assertEqual(service.clock, reactor)
        self.assertIsNone(service.processingDefer)
        self.assertTrue(service.needsDNSUpdate)
        self.assertEqual(service.postgresListener, sentinel.listener)
        self.assertEqual(service.dbtasks, sentinel.dbtasks)

    @wait_for_reactor
    @inlineCallbacks
    def test_startService_registers_with_postgres_listener(self):
        listener = MagicMock()
        service = self.make_service(listener)
        service.startService()
        yield service.processingDefer
        listener.register.assert_has_calls(
            [
                call("sys_proxy", service.markProxyForUpdate),
                call("sys_rbac", service.markRBACForUpdate),
                call("sys_vault_migration", service.restartRegion),
            ]
        )

    def test_startService_markAllForUpdate_on_connect(self):
        listener = MagicMock()
        listener.events.connected = Event()
        service = self.make_service(listener)
        mock_mark_rbac_for_update = self.patch(service, "markRBACForUpdate")
        mock_mark_proxy_for_update = self.patch(service, "markProxyForUpdate")
        service.startService()
        service.postgresListener.events.connected.fire()
        mock_mark_rbac_for_update.assert_called_once()
        mock_mark_proxy_for_update.assert_called_once()

    def test_stopService_calls_unregister_on_the_listener(self):
        listener = MagicMock()
        service = self.make_service(listener)
        service.stopService()
        listener.unregister.assert_has_calls(
            [
                call("sys_proxy", service.markProxyForUpdate),
                call("sys_rbac", service.markRBACForUpdate),
                call("sys_vault_migration", service.restartRegion),
            ]
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_stopService_handles_canceling_processing(self):
        service = self.make_service()
        service.startProcessing()
        yield service.stopService()
        self.assertIsNone(service.processingDefer)

    def test_markProxyForUpdate_sets_needsProxyUpdate_and_starts_process(self):
        service = self.make_service()
        mock_startProcessing = self.patch(service, "startProcessing")
        service.markProxyForUpdate(None, None)
        self.assertTrue(service.needsProxyUpdate)
        mock_startProcessing.assert_called_once_with()

    def test_markRBACForUpdate_sets_needsRBACUpdate_and_starts_process(self):
        service = self.make_service()
        mock_startProcessing = self.patch(service, "startProcessing")
        service.markRBACForUpdate(None, None)
        self.assertTrue(service.needsRBACUpdate)
        mock_startProcessing.assert_called_once_with()

    def test_restart_region_restarts_eventloop(self):
        restart_mock = self.patch(eventloop, "restart")
        service = self.make_service()
        service.restartRegion("sys_vault_migration", "")
        restart_mock.assert_called_once()

    def test_startProcessing_doesnt_call_start_when_looping_call_running(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        mock_start = self.patch(service.processing, "start")
        service.processing.running = True
        service.startProcessing()
        mock_start.assert_not_called()

    def test_startProcessing_calls_start_when_looping_call_not_running(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        mock_start = self.patch(service.processing, "start")
        service.startProcessing()
        mock_start.assert_called_once_with(0.1, now=False)

    @wait_for_reactor
    @inlineCallbacks
    def test_process_doesnt_proxy_update_config_when_nothing_to_process(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        service.needsProxyUpdate = False
        mock_proxy_update_config = self.patch(
            region_controller, "proxy_update_config"
        )
        service.startProcessing()
        yield service.processingDefer
        mock_proxy_update_config.assert_not_called()

    @wait_for_reactor
    @inlineCallbacks
    def test_process_doesnt_call_rbacSync_when_nothing_to_process(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        service.needsRBACUpdate = False
        mock_rbacSync = self.patch(service, "_rbacSync")
        service.startProcessing()
        yield service.processingDefer
        mock_rbacSync.assert_not_called()

    @wait_for_reactor
    @inlineCallbacks
    def test_process_stops_processing(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        service.needsDNSUpdate = False
        service.startProcessing()
        yield service.processingDefer
        self.assertIsNone(service.processingDefer)

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_proxy(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        service.needsProxyUpdate = True
        mock_proxy_update_config = self.patch(
            region_controller, "proxy_update_config"
        )
        mock_proxy_update_config.return_value = succeed(None)
        mock_msg = self.patch(region_controller.log, "msg")
        service.startProcessing()
        yield service.processingDefer
        mock_proxy_update_config.assert_called_once_with(reload_proxy=True)
        mock_msg.assert_called_once_with("Successfully configured proxy.")

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_rbac(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        service.needsRBACUpdate = True
        mock_rbacSync = self.patch(service, "_rbacSync")
        mock_rbacSync.return_value = []
        mock_msg = self.patch(region_controller.log, "msg")
        service.startProcessing()
        yield service.processingDefer
        mock_rbacSync.assert_called_once_with()
        mock_msg.assert_called_once_with(
            "Synced RBAC service; regiond started."
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_proxy_logs_failure(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        service.needsProxyUpdate = True
        mock_proxy_update_config = self.patch(
            region_controller, "proxy_update_config"
        )
        mock_proxy_update_config.return_value = fail(factory.make_exception())
        mock_err = self.patch(region_controller.log, "err")
        service.startProcessing()
        yield service.processingDefer
        mock_proxy_update_config.assert_called_once_with(reload_proxy=True)
        mock_err.assert_called_once_with(ANY, "Failed configuring proxy.")

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_rbac_logs_failure(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        service.needsRBACUpdate = True
        mock_rbacSync = self.patch(service, "_rbacSync")
        mock_rbacSync.side_effect = factory.make_exception()
        mock_err = self.patch(region_controller.log, "err")
        service.startProcessing()
        yield service.processingDefer
        mock_err.assert_called_once_with(
            ANY, "Failed syncing resources to RBAC."
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_rbac_retries_with_delay(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
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
        mock_err.assert_called_once_with(
            ANY, "Failed syncing resources to RBAC."
        )
        mock_pause.assert_called_once_with(service.rbacRetryOnFailureDelay)

    @wait_for_reactor
    @inlineCallbacks
    def test_process_updates_proxy_and_rbac(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        service.needsProxyUpdate = True
        service.needsRBACUpdate = True
        mock_proxy_update_config = self.patch(
            region_controller, "proxy_update_config"
        )
        mock_proxy_update_config.return_value = succeed(None)
        mock_rbacSync = self.patch(service, "_rbacSync")
        mock_rbacSync.return_value = None
        service.startProcessing()
        yield service.processingDefer
        mock_proxy_update_config.assert_called_once_with(reload_proxy=True)
        mock_rbacSync.assert_called_once()

    def test_getRBACClient_returns_None_when_no_url(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        service.rbacClient = sentinel.client
        SecretManager().delete_secret("external-auth")
        self.assertIsNone(service._getRBACClient())
        self.assertIsNone(service.rbacClient)

    def test_getRBACClient_creates_new_client_and_uses_it_again(self):
        self.patch(region_controller, "service_layer")
        SecretManager().set_composite_secret(
            "external-auth", {"rbac-url": "http://rbac.example.com"}
        )
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        client = service._getRBACClient()
        self.assertIsNotNone(client)
        self.assertIs(client, service.rbacClient)
        self.assertIs(client, service._getRBACClient())

    def test_getRBACClient_creates_new_client_when_url_changes(self):
        self.patch(region_controller, "service_layer")
        SecretManager().set_composite_secret(
            "external-auth", {"rbac-url": "http://rbac.example.com"}
        )
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        client = service._getRBACClient()
        SecretManager().set_composite_secret(
            "external-auth", {"rbac-url": "http://other.example.com"}
        )
        new_client = service._getRBACClient()
        self.assertIsNotNone(new_client)
        self.assertIsNot(new_client, client)
        self.assertIs(new_client, service._getRBACClient())

    def test_getRBACClient_creates_new_client_when_auth_info_changes(self):
        mock_service_layer = self.patch(region_controller, "service_layer")
        SecretManager().set_composite_secret(
            "external-auth", {"rbac-url": "http://rbac.example.com"}
        )
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        client = service._getRBACClient()
        mock_service_layer.services.external_auth.get_auth_info.return_value = MagicMock()
        new_client = service._getRBACClient()
        self.assertIsNotNone(new_client)
        self.assertIsNot(new_client, client)
        self.assertIs(new_client, service._getRBACClient())

    def test_rbacNeedsFull(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
        changes = [
            RBACSync(action=RBAC_ACTION.ADD),
            RBACSync(action=RBAC_ACTION.UPDATE),
            RBACSync(action=RBAC_ACTION.REMOVE),
            RBACSync(action=RBAC_ACTION.FULL),
        ]
        self.assertTrue(service._rbacNeedsFull(changes))

    def test_rbacDifference(self):
        service = self.make_service(sentinel.listener, sentinel.dbtasks)
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

    def test_rbacSync_returns_None_when_nothing_to_do(self):
        RBACSync.objects.clear("resource-pool")

        service = RegionControllerService(sentinel.listener, sentinel.dbtasks)
        service.rbacInit = True
        self.assertIsNone(service._rbacSync())

    def test_rbacSync_returns_None_and_clears_sync_when_no_client(self):
        RBACSync.objects.create(resource_type="resource-pool")

        service = RegionControllerService(sentinel.listener, sentinel.dbtasks)
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
        service = RegionControllerService(sentinel.listener, sentinel.dbtasks)
        self.patch(service, "_getRBACClient").return_value = rbac_client

        self.assertEqual([], service._rbacSync())
        rbac_client.update_resources.assert_called_once_with(
            "resource-pool", updates=resources
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
        service = RegionControllerService(sentinel.listener, sentinel.dbtasks)
        self.patch(service, "_getRBACClient").return_value = rbac_client

        self.assertEqual([], service._rbacSync())
        rbac_client.update_resources.assert_called_once_with(
            "resource-pool", updates=resources
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
        service = RegionControllerService(sentinel.listener, sentinel.dbtasks)
        self.patch(service, "_getRBACClient").return_value = rbac_client
        service.rbacInit = True

        self.assertEqual(reasons, service._rbacSync())
        rbac_client.update_resources.assert_called_once_with(
            "resource-pool",
            updates=resources[1:],
            removals=set(),
            last_sync_id="a-b-c",
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
        service = RegionControllerService(sentinel.listener, sentinel.dbtasks)
        self.patch(service, "_getRBACClient").return_value = rbac_client
        service.rbacInit = True

        self.assertEqual(reasons, service._rbacSync())
        rbac_client.update_resources.assert_has_calls(
            [
                call(
                    "resource-pool",
                    updates=resources[1:],
                    removals=set(),
                    last_sync_id="a-b-c",
                ),
                call("resource-pool", updates=resources),
            ]
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
        service = RegionControllerService(sentinel.listener, sentinel.dbtasks)
        self.patch(service, "_getRBACClient").return_value = rbac_client
        service.rbacInit = True

        service._rbacSync()
        last_sync = RBACLastSync.objects.get()
        self.assertEqual(rbac_sync.id, last_sync.id)
        self.assertEqual(last_sync.resource_type, "resource-pool")
        self.assertEqual(last_sync.sync_id, "x-y-z")
