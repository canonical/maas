# Copyright 2016-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Use the `PostgresListenerService` to test all of the triggers from for
`maasserver.triggers.system`"""

from datetime import timedelta

from django.db import connection as db_connection
from django.utils import timezone
from twisted.internet.defer import inlineCallbacks

from maasserver.models.signals.testing import SignalsDisabled
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.triggers.system import register_system_triggers
from maasserver.triggers.testing import (
    DNSHelpersMixin,
    RBACHelpersMixin,
    TransactionalHelpersMixin,
)
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for
from provisioningserver.utils.twisted import DeferredValue

wait_for_reactor = wait_for()


class TestCoreRegionRackRPCConnectionInsertListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin, DNSHelpersMixin
):
    """End-to-end test for the core triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_alerts_region_process_and_sets_managing_process(self):
        yield deferToDatabase(register_system_triggers)
        region = yield deferToDatabase(self.create_region_controller)
        region_process = yield deferToDatabase(
            self.create_region_controller_process, {"region": region}
        )
        region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint,
            {"process": region_process},
        )
        rack_controller = yield deferToDatabase(self.create_rack_controller)

        process_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_core_%s" % region_process.id,
            lambda *args: process_dv.set(args),
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_region_rack_rpc_connection,
                {
                    "endpoint": region_process_endpoint,
                    "rack_controller": rack_controller,
                },
            )
            yield process_dv.get(timeout=2)
            self.assertEqual(
                (
                    "sys_core_%s" % region_process.id,
                    "watch_%s" % rack_controller.id,
                ),
                process_dv.value,
            )
            rack_controller = yield deferToDatabase(
                self.reload_object, rack_controller
            )
            self.assertEqual(
                region_process.id, rack_controller.managing_process_id
            )
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_picks_region_process_managing_the_least_num_of_racks(self):
        region = yield deferToDatabase(self.create_region_controller)
        # Create region process that has a connection to a rack controller
        # and is already managing it.
        managing_region_process = yield deferToDatabase(
            self.create_region_controller_process, {"region": region}
        )
        managing_region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint,
            {"process": managing_region_process},
        )
        rack_controller_connected = yield deferToDatabase(
            self.create_rack_controller,
            {"managing_process": managing_region_process},
        )
        yield deferToDatabase(
            self.create_region_rack_rpc_connection,
            {
                "endpoint": managing_region_process_endpoint,
                "rack_controller": rack_controller_connected,
            },
        )

        # Create a region process that is not managing a rack controller but
        # has connections to both rack controllers. When the trigger is create
        # and the last connection is added it will select the region process
        # with no connections.
        not_managing_region_process = yield deferToDatabase(
            self.create_region_controller_process, {"region": region}
        )
        not_managing_region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint,
            {"process": not_managing_region_process},
        )
        not_managed_rack_controller = yield deferToDatabase(
            self.create_rack_controller
        )
        yield deferToDatabase(
            self.create_region_rack_rpc_connection,
            {
                "endpoint": managing_region_process_endpoint,
                "rack_controller": not_managed_rack_controller,
            },
        )

        # Now create the trigger so that it is actually ran.
        yield deferToDatabase(register_system_triggers)
        process_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_core_%s" % not_managing_region_process.id,
            lambda *args: process_dv.set(args),
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_region_rack_rpc_connection,
                {
                    "endpoint": not_managing_region_process_endpoint,
                    "rack_controller": not_managed_rack_controller,
                },
            )
            yield process_dv.get(timeout=2)
            self.assertEqual(
                (
                    "sys_core_%s" % not_managing_region_process.id,
                    "watch_%s" % not_managed_rack_controller.id,
                ),
                process_dv.value,
            )
            not_managed_rack_controller = yield deferToDatabase(
                self.reload_object, not_managed_rack_controller
            )
            self.assertEqual(
                not_managing_region_process.id,
                not_managed_rack_controller.managing_process_id,
            )
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_selectes_new_region_process_when_managing_one_is_dead(self):
        region = yield deferToDatabase(self.create_region_controller)
        # Create region process that has a connection to a rack controller
        # and is already managing it.
        managing_region_process = yield deferToDatabase(
            self.create_region_controller_process, {"region": region}
        )
        managing_region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint,
            {"process": managing_region_process},
        )
        rack_controller_connected = yield deferToDatabase(
            self.create_rack_controller,
            {"managing_process": managing_region_process},
        )
        yield deferToDatabase(
            self.create_region_rack_rpc_connection,
            {
                "endpoint": managing_region_process_endpoint,
                "rack_controller": rack_controller_connected,
            },
        )

        # Create a dead region process that is managing a rack controller but
        # has connections to both rack controllers. When the trigger is create
        # and the last connection is added it will select the region process
        # with no connections.
        dead_region_process = yield deferToDatabase(
            self.create_region_controller_process,
            {
                "region": region,
                "updated": timezone.now() - timedelta(seconds=90),
            },
        )
        dead_region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint,
            {"process": dead_region_process},
        )
        dead_managed_rack_controller = yield deferToDatabase(
            self.create_rack_controller,
            {"managing_process": dead_region_process},
        )
        yield deferToDatabase(
            self.create_region_rack_rpc_connection,
            {
                "endpoint": managing_region_process_endpoint,
                "rack_controller": dead_managed_rack_controller,
            },
        )

        # Now create the trigger so that it is actually ran.
        yield deferToDatabase(register_system_triggers)
        process_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_core_%s" % managing_region_process.id,
            lambda *args: process_dv.set(args),
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_region_rack_rpc_connection,
                {
                    "endpoint": dead_region_process_endpoint,
                    "rack_controller": dead_managed_rack_controller,
                },
            )
            yield process_dv.get(timeout=2)
            self.assertEqual(
                (
                    "sys_core_%s" % managing_region_process.id,
                    "watch_%s" % dead_managed_rack_controller.id,
                ),
                process_dv.value,
            )
            dead_managed_rack_controller = yield deferToDatabase(
                self.reload_object, dead_managed_rack_controller
            )
            self.assertEqual(
                managing_region_process.id,
                dead_managed_rack_controller.managing_process_id,
            )
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_rebalance_the_managing_process_for_the_rack_controller(self):
        region = yield deferToDatabase(self.create_region_controller)
        # Create a region process that is managing 5 rack controllers.
        overloaded_region_process = yield deferToDatabase(
            self.create_region_controller_process, {"region": region}
        )
        for _ in range(5):
            yield deferToDatabase(
                self.create_rack_controller,
                {"managing_process": overloaded_region_process},
            )

        # Create region process that has no managing rack controllers.
        region_process = yield deferToDatabase(
            self.create_region_controller_process, {"region": region}
        )
        region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint,
            {"process": region_process},
        )

        # Create the rack controller connected to the overloaded region
        # process.
        rack_controller = yield deferToDatabase(
            self.create_rack_controller,
            {"managing_process": overloaded_region_process},
        )
        overloaded_region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint,
            {"process": overloaded_region_process},
        )
        yield deferToDatabase(
            self.create_region_rack_rpc_connection,
            {
                "endpoint": overloaded_region_process_endpoint,
                "rack_controller": rack_controller,
            },
        )

        # Now create the trigger so that it is actually ran.
        yield deferToDatabase(register_system_triggers)

        # Catch that unwatch is called on the overloaded region process and
        # watch is called on the other region process.
        listener = self.make_listener_without_delay()
        overloaded_dv = DeferredValue()
        listener.register(
            "sys_core_%s" % overloaded_region_process.id,
            lambda *args: overloaded_dv.set(args),
        )
        process_dv = DeferredValue()
        listener.register(
            "sys_core_%s" % region_process.id,
            lambda *args: process_dv.set(args),
        )
        yield listener.startService()
        try:
            # Create the connection that will balance the connection for
            # the client.
            yield deferToDatabase(
                self.create_region_rack_rpc_connection,
                {
                    "endpoint": region_process_endpoint,
                    "rack_controller": rack_controller,
                },
            )
            yield overloaded_dv.get(timeout=2)
            yield process_dv.get(timeout=2)
            self.assertEqual(
                (
                    "sys_core_%s" % overloaded_region_process.id,
                    "unwatch_%s" % rack_controller.id,
                ),
                overloaded_dv.value,
            )
            self.assertEqual(
                (
                    "sys_core_%s" % region_process.id,
                    "watch_%s" % rack_controller.id,
                ),
                process_dv.value,
            )
            rack_controller = yield deferToDatabase(
                self.reload_object, rack_controller
            )
            self.assertEqual(
                region_process.id, rack_controller.managing_process_id
            )
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_rebalance_doesnt_happen_when_less_than_half_conn(self):
        region = yield deferToDatabase(self.create_region_controller)
        # Create a region process that is managing 5 rack controllers.
        overloaded_region_process = yield deferToDatabase(
            self.create_region_controller_process, {"region": region}
        )
        for _ in range(5):
            yield deferToDatabase(
                self.create_rack_controller,
                {"managing_process": overloaded_region_process},
            )

        # Create the rack controller connected to the overloaded region
        # process.
        rack_controller = yield deferToDatabase(
            self.create_rack_controller,
            {"managing_process": overloaded_region_process},
        )
        overloaded_region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint,
            {"process": overloaded_region_process},
        )
        yield deferToDatabase(
            self.create_region_rack_rpc_connection,
            {
                "endpoint": overloaded_region_process_endpoint,
                "rack_controller": rack_controller,
            },
        )

        # Create many more region processes where the rack controller is
        # not connected.
        region_processes = []
        region_process_endpoints = []
        for _ in range(4):
            process = yield deferToDatabase(
                self.create_region_controller_process, {"region": region}
            )
            region_processes.append(process)
            endpoint = yield deferToDatabase(
                self.create_region_controller_process_endpoint,
                {"process": process},
            )
            region_process_endpoints.append(endpoint)

        # Now create the trigger so that it is actually ran.
        yield deferToDatabase(register_system_triggers)

        # Create a new connection between the rack controller and the first
        # un-used region process. The managing rack controller should not
        # change because the rack controller is not connected to at least
        # half of the region processes.
        yield deferToDatabase(
            self.create_region_rack_rpc_connection,
            {
                "endpoint": region_process_endpoints[0],
                "rack_controller": rack_controller,
            },
        )
        rack_controller = yield deferToDatabase(
            self.reload_object, rack_controller
        )
        self.assertEqual(
            overloaded_region_process.id, rack_controller.managing_process_id
        )


class TestCoreRegionRackRPCConnectionDeleteListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin, DNSHelpersMixin
):
    """End-to-end test for the core triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_picks_new_region_process_when_connection_is_removed(self):
        # This test is very picky and no trigger on the RegionRackRPCConnection
        # can already exists or it will break the test. We forcibly remove
        # that trigger, just for this test. MAASTransactionServerTestCase does
        # not clear the triggeres between test runs. This test will pass
        # in isolation but will fail otherwise without this initial operation.
        @transactional
        def drop_sys_core_rpc_insert_trigger():
            with db_connection.cursor() as cursor:
                cursor.execute(
                    "DROP TRIGGER IF EXISTS "
                    "regionrackrpcconnection_sys_core_rpc_insert ON "
                    "maasserver_regionrackrpcconnection"
                )

        yield deferToDatabase(drop_sys_core_rpc_insert_trigger)

        # Create a region process that is managing for a rack controller.
        region = yield deferToDatabase(self.create_region_controller)
        region_process = yield deferToDatabase(
            self.create_region_controller_process, {"region": region}
        )
        region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint,
            {"process": region_process},
        )
        rack_controller = yield deferToDatabase(
            self.create_rack_controller, {"managing_process": region_process}
        )
        connection = yield deferToDatabase(
            self.create_region_rack_rpc_connection,
            {
                "endpoint": region_process_endpoint,
                "rack_controller": rack_controller,
            },
        )

        # Create another process that has a connection to the rack controller.
        other_region = yield deferToDatabase(self.create_region_controller)
        other_region_process = yield deferToDatabase(
            self.create_region_controller_process, {"region": other_region}
        )
        other_region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint,
            {"process": other_region_process},
        )
        yield deferToDatabase(
            self.create_region_rack_rpc_connection,
            {
                "endpoint": other_region_process_endpoint,
                "rack_controller": rack_controller,
            },
        )

        # Now create the trigger so that it is actually ran.
        yield deferToDatabase(register_system_triggers)

        # Catch that unwatch is called on the region process and
        # watch is called on the other region process.
        listener = self.make_listener_without_delay()
        process_dv = DeferredValue()
        listener.register(
            "sys_core_%s" % region_process.id,
            lambda *args: process_dv.set(args),
        )
        other_process_dv = DeferredValue()
        listener.register(
            "sys_core_%s" % other_region_process.id,
            lambda *args: other_process_dv.set(args),
        )
        yield listener.startService()
        try:
            # Remove the connection on the region process causing it to
            # set the other region process as the manager.
            yield deferToDatabase(
                self.delete_region_rack_rpc_connection, connection.id
            )
            yield process_dv.get(timeout=2)
            yield other_process_dv.get(timeout=2)
            self.assertEqual(
                (
                    "sys_core_%s" % region_process.id,
                    "unwatch_%s" % rack_controller.id,
                ),
                process_dv.value,
            )
            self.assertEqual(
                (
                    "sys_core_%s" % other_region_process.id,
                    "watch_%s" % rack_controller.id,
                ),
                other_process_dv.value,
            )
            rack_controller = yield deferToDatabase(
                self.reload_object, rack_controller
            )
            self.assertEqual(
                other_region_process.id, rack_controller.managing_process_id
            )
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_clears_region_process_when_no_connections(self):
        # Create a region process that is managing for a rack controller.
        region = yield deferToDatabase(self.create_region_controller)
        region_process = yield deferToDatabase(
            self.create_region_controller_process, {"region": region}
        )
        region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint,
            {"process": region_process},
        )
        rack_controller = yield deferToDatabase(
            self.create_rack_controller, {"managing_process": region_process}
        )
        connection = yield deferToDatabase(
            self.create_region_rack_rpc_connection,
            {
                "endpoint": region_process_endpoint,
                "rack_controller": rack_controller,
            },
        )

        # Now create the trigger so that it is actually ran.
        yield deferToDatabase(register_system_triggers)

        # Catch that unwatch is called on the region process and
        # watch is called on the other region process.
        listener = self.make_listener_without_delay()
        process_dv = DeferredValue()
        listener.register(
            "sys_core_%s" % region_process.id,
            lambda *args: process_dv.set(args),
        )
        yield listener.startService()
        try:
            # Remove the connection on the region process causing it to
            # notify unwatch and remove the managing process.
            yield deferToDatabase(
                self.delete_region_rack_rpc_connection, connection.id
            )
            yield process_dv.get(timeout=2)
            self.assertEqual(
                (
                    "sys_core_%s" % region_process.id,
                    "unwatch_%s" % rack_controller.id,
                ),
                process_dv.value,
            )
            rack_controller = yield deferToDatabase(
                self.reload_object, rack_controller
            )
            self.assertIsNone(rack_controller.managing_process_id)
        finally:
            yield listener.stopService()


class TestProxyListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test for the proxy triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_subnet_insert(self):
        yield deferToDatabase(register_system_triggers)
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_proxy", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_subnet)
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_subnet_cidr_update(self):
        yield deferToDatabase(register_system_triggers)
        subnet = yield deferToDatabase(self.create_subnet)
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_proxy", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            network = factory.make_ip4_or_6_network()
            yield deferToDatabase(
                self.update_subnet,
                subnet.id,
                {
                    "cidr": str(network.cidr),
                    "gateway_ip": factory.pick_ip_in_network(network),
                    "dns_servers": [],
                },
            )
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_subnet_allow_proxy_update(self):
        yield deferToDatabase(register_system_triggers)
        subnet = yield deferToDatabase(
            self.create_subnet, {"allow_proxy": False}
        )
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_proxy", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_subnet, subnet.id, {"allow_proxy": True}
            )
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_subnet_delete(self):
        yield deferToDatabase(register_system_triggers)
        subnet = yield deferToDatabase(self.create_subnet)
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_proxy", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_subnet, subnet.id)
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_insert_enable_proxy(self):
        yield deferToDatabase(register_system_triggers)
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_proxy", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_config, "enable_proxy", True)
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_insert_use_peer_proxy(self):
        yield deferToDatabase(register_system_triggers)
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_proxy", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_config, "use_peer_proxy", True)
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_insert_prefer_v4_proxy(self):
        yield deferToDatabase(register_system_triggers)
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_proxy", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_config, "prefer_v4_proxy", True)
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_insert_maas_proxy_port(self):
        yield deferToDatabase(register_system_triggers)
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_proxy", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_config, "maas_proxy_port", 9000)
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_insert_http_proxy(self):
        self.useFixture(SignalsDisabled("bootsources"))
        yield deferToDatabase(register_system_triggers)
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_proxy", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_config, "http_proxy", "http://proxy.example.com"
            )
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_update_enable_proxy(self):
        yield deferToDatabase(register_system_triggers)
        yield deferToDatabase(self.create_config, "enable_proxy", True)
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_proxy", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.set_config, "enable_proxy", False)
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_update_use_peer_proxy(self):
        yield deferToDatabase(register_system_triggers)
        yield deferToDatabase(self.create_config, "use_peer_proxy", True)
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_proxy", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.set_config, "use_peer_proxy", False)
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_update_prefer_v4_proxy(self):
        yield deferToDatabase(register_system_triggers)
        yield deferToDatabase(self.create_config, "prefer_v4_proxy", True)
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_proxy", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.set_config, "prefer_v4_proxy", False)
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_update_maas_proxy_port(self):
        yield deferToDatabase(register_system_triggers)
        yield deferToDatabase(self.create_config, "maas_proxy_port", 8000)
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_proxy", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.set_config, "maas_proxy_port", 9000)
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_update_http_proxy(self):
        self.useFixture(SignalsDisabled("bootsources"))
        yield deferToDatabase(register_system_triggers)
        yield deferToDatabase(
            self.create_config, "http_proxy", "http://proxy1.example.com"
        )
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_proxy", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.set_config, "http_proxy", "http://proxy2.example.com"
            )
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()


class TestRBACResourcePoolListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin, RBACHelpersMixin
):
    """End-to-end test for the resource pool RBAC triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_resource_pool_insert(self):
        yield deferToDatabase(register_system_triggers)
        yield self.captureSynced()
        name = factory.make_name("pool")
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_rbac", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            pool = yield deferToDatabase(
                self.create_resource_pool, {"name": name}
            )
            yield dv.get(timeout=2)
            yield self.assertSynced()
        finally:
            yield listener.stopService()
        change = self.getCapturedSynced()
        self.assertEqual("added resource pool %s" % name, change.source)
        self.assertEqual("add", change.action)
        self.assertEqual("resource-pool", change.resource_type)
        self.assertEqual(pool.id, change.resource_id)
        self.assertEqual(name, change.resource_name)

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_resource_pool_update(self):
        yield deferToDatabase(register_system_triggers)
        pool = yield deferToDatabase(self.create_resource_pool, {})
        pool_name = factory.make_name("pool")
        yield self.captureSynced()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_rbac", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_resource_pool, pool.id, {"name": pool_name}
            )
            yield dv.get(timeout=2)
            yield self.assertSynced()
        finally:
            yield listener.stopService()
        change = self.getCapturedSynced()
        self.assertEqual(
            f"renamed resource pool {pool.name} to {pool_name}",
            change.source,
        )
        self.assertEqual("update", change.action)
        self.assertEqual("resource-pool", change.resource_type)
        self.assertEqual(pool.id, change.resource_id)
        self.assertEqual(pool_name, change.resource_name)

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_resource_pool_delete(self):
        yield deferToDatabase(register_system_triggers)
        pool = yield deferToDatabase(self.create_resource_pool)
        yield self.captureSynced()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_rbac", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_resource_pool, pool.id)
            yield dv.get(timeout=2)
            yield self.assertSynced()
        finally:
            yield listener.stopService()
        change = self.getCapturedSynced()
        self.assertEqual("removed resource pool %s" % pool.name, change.source)
        self.assertEqual("remove", change.action)
        self.assertEqual("resource-pool", change.resource_type)
        self.assertEqual(pool.id, change.resource_id)
        self.assertEqual(pool.name, change.resource_name)
