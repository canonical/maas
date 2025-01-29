# Copyright 2016-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Use the `PostgresListenerService` to test all of the triggers from for
`maasserver.triggers.system`"""


from datetime import timedelta
import random

from django.db import connection as db_connection
from django.utils import timezone
from netaddr import IPAddress
from twisted.internet.defer import (
    CancelledError,
    DeferredList,
    inlineCallbacks,
)

from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    IPRANGE_TYPE,
    RDNS_MODE,
)
from maasserver.models.config import Config
from maasserver.models.dnspublication import DNSPublication
from maasserver.models.interface import (
    Interface,
    PhysicalInterface,
    UnknownInterface,
)
from maasserver.models.signals.testing import SignalsDisabled
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASLegacyTransactionServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.triggers.system import register_system_triggers
from maasserver.triggers.testing import (
    DNSHelpersMixin,
    RBACHelpersMixin,
    TransactionalHelpersMixin,
)
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for
from provisioningserver.boot import BootMethodRegistry
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

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_publish_on_first_rpc_connection(self):
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
        yield self.capturePublication()

        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_region_rack_rpc_connection,
                {
                    "endpoint": region_process_endpoint,
                    "rack_controller": rack_controller,
                },
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            f"rack controller {rack_controller.hostname} connected",
            self.getCapturedPublication().source,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_no_dns_publish_on_second_rpc_connection(self):
        yield deferToDatabase(register_system_triggers)
        region = yield deferToDatabase(self.create_region_controller)
        region_process = yield deferToDatabase(
            self.create_region_controller_process, {"region": region}
        )
        region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint,
            {"process": region_process},
        )
        region_process_endpoint2 = yield deferToDatabase(
            self.create_region_controller_process_endpoint,
            {"process": region_process},
        )
        rack_controller = yield deferToDatabase(self.create_rack_controller)
        yield self.capturePublication()

        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_region_rack_rpc_connection,
                {
                    "endpoint": region_process_endpoint,
                    "rack_controller": rack_controller,
                },
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
            publication = self.getCapturedPublication()
            yield deferToDatabase(
                self.create_region_rack_rpc_connection,
                {
                    "endpoint": region_process_endpoint2,
                    "rack_controller": rack_controller,
                },
            )
        finally:
            yield listener.stopService()
        # Verify that the DNS publication has not changed.
        yield self.capturePublication()
        self.assertEqual(publication, self.getCapturedPublication())


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

    @wait_for_reactor
    @inlineCallbacks
    def test_dns_publish_when_no_connections(self):
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

        yield self.capturePublication()

        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            # Remove the connection on the region process.
            yield deferToDatabase(
                self.delete_region_rack_rpc_connection, connection.id
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f"rack controller {rack_controller.hostname} disconnected",
        )


class TestDHCPSubnetListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test for the DHCP triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_old_vlan_and_new_vlan(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack_1 = yield deferToDatabase(self.create_rack_controller)
        secondary_rack_1 = yield deferToDatabase(self.create_rack_controller)
        vlan_1 = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack_1,
                "secondary_rack": secondary_rack_1,
            },
        )
        primary_rack_2 = yield deferToDatabase(self.create_rack_controller)
        secondary_rack_2 = yield deferToDatabase(self.create_rack_controller)
        vlan_2 = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack_2,
                "secondary_rack": secondary_rack_2,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan_1})

        listener = self.make_listener_without_delay()
        primary_dv_1 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack_1.id,
            lambda *args: primary_dv_1.set(args),
        )
        secondary_dv_1 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack_1.id,
            lambda *args: secondary_dv_1.set(args),
        )
        primary_dv_2 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack_2.id,
            lambda *args: primary_dv_2.set(args),
        )
        secondary_dv_2 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack_2.id,
            lambda *args: secondary_dv_2.set(args),
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_subnet, subnet.id, {"vlan": vlan_2}
            )
            yield primary_dv_1.get(timeout=2)
            yield secondary_dv_1.get(timeout=2)
            yield primary_dv_1.get(timeout=2)
            yield secondary_dv_2.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_vlan_when_cidr_changes(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            network = factory.make_ip4_or_6_network()
            gateway_ip = yield deferToDatabase(
                factory.pick_ip_in_network, network
            )
            yield deferToDatabase(
                self.update_subnet,
                subnet.id,
                {"cidr": str(network.cidr), "gateway_ip": gateway_ip},
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_vlan_when_gateway_ip_changes(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            gateway_ip = yield deferToDatabase(
                factory.pick_ip_in_network,
                subnet.get_ipnetwork(),
                but_not=[subnet.gateway_ip],
            )
            yield deferToDatabase(
                self.update_subnet, subnet.id, {"gateway_ip": gateway_ip}
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_vlan_when_gateway_ip_is_set(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})
        # Make sure its empty. This test that it handles being set.
        yield deferToDatabase(
            self.update_subnet, subnet.id, {"gateway_ip": None}
        )

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            gateway_ip = yield deferToDatabase(
                factory.pick_ip_in_network, subnet.get_ipnetwork()
            )
            yield deferToDatabase(
                self.update_subnet, subnet.id, {"gateway_ip": gateway_ip}
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_vlan_when_gateway_ip_is_cleared(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_subnet, subnet.id, {"gateway_ip": None}
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_vlan_when_dns_servers_changes(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            dns_server = yield deferToDatabase(
                factory.pick_ip_in_network,
                subnet.get_ipnetwork(),
                but_not=subnet.dns_servers,
            )
            yield deferToDatabase(
                self.update_subnet, subnet.id, {"dns_servers": [dns_server]}
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_vlan_when_dns_servers_is_set(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})
        # Make sure its empty. This test that it handles being set.
        yield deferToDatabase(
            self.update_subnet, subnet.id, {"dns_servers": []}
        )

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            dns_server = yield deferToDatabase(
                factory.pick_ip_in_network,
                subnet.get_ipnetwork(),
                but_not=subnet.dns_servers,
            )
            yield deferToDatabase(
                self.update_subnet, subnet.id, {"dns_servers": [dns_server]}
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_vlan_when_dns_servers_is_cleared(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})
        dns_server = yield deferToDatabase(
            factory.pick_ip_in_network,
            subnet.get_ipnetwork(),
            but_not=subnet.dns_servers,
        )
        yield deferToDatabase(
            self.update_subnet, subnet.id, {"dns_servers": [dns_server]}
        )

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_subnet, subnet.id, {"dns_servers": []}
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_vlan_when_allow_dns_changes(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_subnet,
                subnet.id,
                {"allow_dns": not subnet.allow_dns},
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_vlan_when_managed_changes(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_subnet,
                subnet.id,
                {"managed": not subnet.managed},
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_vlan_when_disabled_boot_arches_changes(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            f"sys_dhcp_{primary_rack.id}", lambda *args: primary_dv.set(args)
        )
        listener.register(
            f"sys_dhcp_{secondary_rack.id}",
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        disabled_arches = random.sample(
            [
                boot_method.name
                for _, boot_method in BootMethodRegistry
                if boot_method.arch_octet or boot_method.path_prefix_http
            ],
            3,
        )
        try:
            yield deferToDatabase(
                self.update_subnet,
                subnet.id,
                {"disabled_boot_architectures": disabled_arches},
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_vlan_when_disabled_boot_arches_is_set(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})
        # Make sure its empty. This test that it handles being set.
        yield deferToDatabase(
            self.update_subnet, subnet.id, {"disabled_boot_architectures": []}
        )

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            f"sys_dhcp_{primary_rack.id}", lambda *args: primary_dv.set(args)
        )
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        disabled_arches = random.sample(
            [
                boot_method.name
                for _, boot_method in BootMethodRegistry
                if boot_method.arch_octet or boot_method.path_prefix_http
            ],
            3,
        )
        try:
            yield deferToDatabase(
                self.update_subnet,
                subnet.id,
                {"disabled_boot_architectures": disabled_arches},
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_vlan_when_disabled_boot_arches_is_cleared(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        disabled_arches = random.sample(
            [
                boot_method.name
                for _, boot_method in BootMethodRegistry
                if boot_method.arch_octet or boot_method.path_prefix_http
            ],
            3,
        )
        subnet = yield deferToDatabase(
            self.create_subnet,
            {"vlan": vlan, "disabled_boot_architectures": disabled_arches},
        )

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            f"sys_dhcp_{primary_rack.id}", lambda *args: primary_dv.set(args)
        )
        listener.register(
            f"sys_dhcp_{secondary_rack.id}",
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_subnet,
                subnet.id,
                {"disabled_boot_architectures": []},
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_vlan_when_subnet_deleted(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_subnet, subnet.id)
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()


class TestDHCPIPRangeListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test for the DHCP triggers code."""

    scenarios = (
        ("with_dhcp_relay", {"dhcp_relay": True}),
        ("without_dhcp_relay", {"dhcp_relay": False}),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_new_managed_dhcp_range(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        relay_vlan = None
        if self.dhcp_relay:
            relay_vlan = yield deferToDatabase(
                self.create_vlan, {"relay_vlan": vlan}
            )
        network = factory.make_ipv4_network()
        subnet = yield deferToDatabase(
            self.create_subnet,
            {
                "cidr": str(network.cidr),
                "vlan": relay_vlan if self.dhcp_relay else vlan,
            },
        )
        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            network = subnet.get_ipnetwork()
            start_ip = str(IPAddress(network.first + 2))
            end_ip = str(IPAddress(network.first + 3))
            yield deferToDatabase(
                self.create_iprange,
                {
                    "subnet": subnet,
                    "alloc_type": IPRANGE_TYPE.DYNAMIC,
                    "start_ip": start_ip,
                    "end_ip": end_ip,
                },
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_updated_managed_dhcp_range(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        relay_vlan = None
        if self.dhcp_relay:
            relay_vlan = yield deferToDatabase(
                self.create_vlan, {"relay_vlan": vlan}
            )
        network = factory.make_ipv4_network()
        subnet = yield deferToDatabase(
            self.create_subnet,
            {
                "cidr": str(network.cidr),
                "vlan": relay_vlan if self.dhcp_relay else vlan,
            },
        )
        network = subnet.get_ipnetwork()
        start_ip = str(IPAddress(network.first + 2))
        end_ip = str(IPAddress(network.first + 3))
        ip_range = yield deferToDatabase(
            self.create_iprange,
            {
                "subnet": subnet,
                "alloc_type": IPRANGE_TYPE.DYNAMIC,
                "start_ip": start_ip,
                "end_ip": end_ip,
            },
        )

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            end_ip = str(IPAddress(network.first + 4))
            yield deferToDatabase(
                self.update_iprange, ip_range.id, {"end_ip": end_ip}
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_updated_from_managed_to_other(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        relay_vlan = None
        if self.dhcp_relay:
            relay_vlan = yield deferToDatabase(
                self.create_vlan, {"relay_vlan": vlan}
            )
        network = factory.make_ipv4_network()
        subnet = yield deferToDatabase(
            self.create_subnet,
            {
                "cidr": str(network.cidr),
                "vlan": relay_vlan if self.dhcp_relay else vlan,
            },
        )
        network = subnet.get_ipnetwork()
        start_ip = str(IPAddress(network.first + 2))
        end_ip = str(IPAddress(network.first + 3))
        ip_range = yield deferToDatabase(
            self.create_iprange,
            {
                "subnet": subnet,
                "alloc_type": IPRANGE_TYPE.DYNAMIC,
                "start_ip": start_ip,
                "end_ip": end_ip,
            },
        )

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_iprange,
                ip_range.id,
                {"type": IPRANGE_TYPE.RESERVED},
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_updated_from_other_to_managed(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        relay_vlan = None
        if self.dhcp_relay:
            relay_vlan = yield deferToDatabase(
                self.create_vlan, {"relay_vlan": vlan}
            )
        network = factory.make_ipv4_network()
        subnet = yield deferToDatabase(
            self.create_subnet,
            {
                "cidr": str(network.cidr),
                "vlan": relay_vlan if self.dhcp_relay else vlan,
            },
        )
        network = subnet.get_ipnetwork()
        start_ip = str(IPAddress(network.first + 2))
        end_ip = str(IPAddress(network.first + 3))
        ip_range = yield deferToDatabase(
            self.create_iprange,
            {
                "subnet": subnet,
                "alloc_type": IPRANGE_TYPE.RESERVED,
                "start_ip": start_ip,
                "end_ip": end_ip,
            },
        )

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_iprange,
                ip_range.id,
                {"type": IPRANGE_TYPE.DYNAMIC},
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_deleting_range(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        relay_vlan = None
        if self.dhcp_relay:
            relay_vlan = yield deferToDatabase(
                self.create_vlan, {"relay_vlan": vlan}
            )
        network = factory.make_ipv4_network()
        subnet = yield deferToDatabase(
            self.create_subnet,
            {
                "cidr": str(network.cidr),
                "vlan": relay_vlan if self.dhcp_relay else vlan,
            },
        )
        network = subnet.get_ipnetwork()
        start_ip = str(IPAddress(network.first + 2))
        end_ip = str(IPAddress(network.first + 3))
        ip_range = yield deferToDatabase(
            self.create_iprange,
            {
                "subnet": subnet,
                "alloc_type": IPRANGE_TYPE.DYNAMIC,
                "start_ip": start_ip,
                "end_ip": end_ip,
            },
        )

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_iprange, ip_range.id)
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()


class TestDHCPStaticIPAddressListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test for the DHCP triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_new_staticipaddress(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})
        user = yield deferToDatabase(self.create_user)

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_staticipaddress,
                params={
                    "subnet": subnet,
                    "alloc_type": IPADDRESS_TYPE.USER_RESERVED,
                    "user": user,
                },
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_both_vlans_on_subnet_switch(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack_1 = yield deferToDatabase(self.create_rack_controller)
        secondary_rack_1 = yield deferToDatabase(self.create_rack_controller)
        vlan_1 = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack_1,
                "secondary_rack": secondary_rack_1,
            },
        )
        subnet_1 = yield deferToDatabase(self.create_subnet, {"vlan": vlan_1})
        primary_rack_2 = yield deferToDatabase(self.create_rack_controller)
        secondary_rack_2 = yield deferToDatabase(self.create_rack_controller)
        vlan_2 = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack_2,
                "secondary_rack": secondary_rack_2,
            },
        )
        subnet_2 = yield deferToDatabase(self.create_subnet, {"vlan": vlan_2})
        user = yield deferToDatabase(self.create_user)
        staticip = yield deferToDatabase(
            self.create_staticipaddress,
            {
                "subnet": subnet_1,
                "alloc_type": IPADDRESS_TYPE.USER_RESERVED,
                "user": user,
            },
        )

        listener = self.make_listener_without_delay()
        primary_dv_1 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack_1.id,
            lambda *args: primary_dv_1.set(args),
        )
        secondary_dv_1 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack_1.id,
            lambda *args: secondary_dv_1.set(args),
        )
        primary_dv_2 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack_2.id,
            lambda *args: primary_dv_2.set(args),
        )
        secondary_dv_2 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack_2.id,
            lambda *args: secondary_dv_2.set(args),
        )
        yield listener.startService()
        try:
            ip = yield deferToDatabase(factory.pick_ip_in_Subnet, subnet_2)
            yield deferToDatabase(
                self.update_staticipaddress,
                staticip.id,
                {"subnet": subnet_2, "ip": ip},
            )
            yield primary_dv_1.get(timeout=2)
            yield secondary_dv_1.get(timeout=2)
            yield primary_dv_2.get(timeout=2)
            yield secondary_dv_2.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_one_vlan_on_switch_subnet_on_same_vlan(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet_1 = yield deferToDatabase(self.create_subnet, {"vlan": vlan})
        subnet_2 = yield deferToDatabase(self.create_subnet, {"vlan": vlan})
        user = yield deferToDatabase(self.create_user)
        staticip = yield deferToDatabase(
            self.create_staticipaddress,
            {
                "subnet": subnet_1,
                "alloc_type": IPADDRESS_TYPE.USER_RESERVED,
                "user": user,
            },
        )

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            ip = yield deferToDatabase(factory.pick_ip_in_Subnet, subnet_2)
            yield deferToDatabase(
                self.update_staticipaddress,
                staticip.id,
                {"subnet": subnet_2, "ip": ip},
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_assigning_an_ip(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(
            self.create_interface, {"node": node, "vlan": vlan}
        )
        staticip = yield deferToDatabase(
            self.create_staticipaddress,
            {
                "subnet": subnet,
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "interface": interface,
                "ip": "",
            },
        )

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            ip = yield deferToDatabase(factory.pick_ip_in_Subnet, subnet)
            yield deferToDatabase(
                self.update_staticipaddress, staticip.id, {"ip": ip}
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_releasing_an_ip(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(
            self.create_interface, {"node": node, "vlan": vlan}
        )
        staticip = yield deferToDatabase(
            self.create_staticipaddress,
            {
                "subnet": subnet,
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "interface": interface,
            },
        )

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_staticipaddress, staticip.id, {"ip": ""}
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_changing_an_ip(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(
            self.create_interface, {"node": node, "vlan": vlan}
        )
        staticip = yield deferToDatabase(
            self.create_staticipaddress,
            {
                "subnet": subnet,
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "interface": interface,
            },
        )

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            ip = yield deferToDatabase(
                factory.pick_ip_in_Subnet, subnet, but_not=[staticip.ip]
            )
            yield deferToDatabase(
                self.update_staticipaddress, staticip.id, {"ip": ip}
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_delete_an_ip(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(
            self.create_interface, {"node": node, "vlan": vlan}
        )
        staticip = yield deferToDatabase(
            self.create_staticipaddress,
            {
                "subnet": subnet,
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "interface": interface,
            },
        )

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            ip = yield deferToDatabase(
                factory.pick_ip_in_Subnet, subnet, but_not=[staticip.ip]
            )
            yield deferToDatabase(
                self.update_staticipaddress, staticip.id, {"ip": ip}
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()


class TestDHCPInterfaceListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test for the DHCP triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_interface_name_change(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(
            self.create_interface, {"node": node, "vlan": vlan}
        )
        yield deferToDatabase(
            self.create_staticipaddress,
            {
                "subnet": subnet,
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "interface": interface,
            },
        )

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_interface,
                interface.id,
                {"name": factory.make_name("eth")},
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_mac_address_change(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(
            self.create_interface, {"node": node, "vlan": vlan}
        )
        yield deferToDatabase(
            self.create_staticipaddress,
            {
                "subnet": subnet,
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "interface": interface,
            },
        )

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_interface,
                interface.id,
                {"mac_address": factory.make_mac_address()},
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()


class TestDHCPNodeListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test for the DHCP triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_hostname_change(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan,
            {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            },
        )
        subnet = yield deferToDatabase(self.create_subnet, {"vlan": vlan})
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(
            self.create_interface, {"node": node, "vlan": vlan}
        )
        yield deferToDatabase(
            self.create_staticipaddress,
            {
                "subnet": subnet,
                "alloc_type": IPADDRESS_TYPE.AUTO,
                "interface": interface,
            },
        )

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: primary_dv.set(args)
        )
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args),
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_node,
                node.system_id,
                {"hostname": factory.make_name("host")},
            )
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()


class TestDHCPSnippetListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test for the DHCP triggers code."""

    scenarios = (
        ("with_dhcp_relay", {"dhcp_relay": True}),
        ("without_dhcp_relay", {"dhcp_relay": False}),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_global_dhcp_snippet_inserted(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan, {"dhcp_on": True, "primary_rack": primary_rack}
        )
        relay_vlan = None
        if self.dhcp_relay:
            relay_vlan = yield deferToDatabase(
                self.create_vlan, {"relay_vlan": vlan}
            )
        yield deferToDatabase(
            self.create_subnet,
            {"vlan": relay_vlan if self.dhcp_relay else vlan},
        )
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: dv.set(args)
        )
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_dhcp_snippet, {"enabled": True})
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_no_message_for_global_dhcp_snippet_inserted_when_disabled(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan, {"dhcp_on": True, "primary_rack": primary_rack}
        )
        relay_vlan = None
        if self.dhcp_relay:
            relay_vlan = yield deferToDatabase(
                self.create_vlan, {"relay_vlan": vlan}
            )
        yield deferToDatabase(
            self.create_subnet,
            {"vlan": relay_vlan if self.dhcp_relay else vlan},
        )
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: dv.set(args)
        )
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_dhcp_snippet, {"enabled": False})
            try:
                yield dv.get(timeout=1)
            except CancelledError:
                pass
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dhcp_snippet_inserted_with_subnet(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan, {"dhcp_on": True, "primary_rack": primary_rack}
        )
        relay_vlan = None
        if self.dhcp_relay:
            relay_vlan = yield deferToDatabase(
                self.create_vlan, {"relay_vlan": vlan}
            )
        subnet = yield deferToDatabase(
            self.create_subnet,
            {"vlan": relay_vlan if self.dhcp_relay else vlan},
        )
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: dv.set(args)
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_dhcp_snippet, {"enabled": True, "subnet": subnet}
            )
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dhcp_snippet_inserted_with_node(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan, {"dhcp_on": True, "primary_rack": primary_rack}
        )
        relay_vlan = None
        if self.dhcp_relay:
            relay_vlan = yield deferToDatabase(
                self.create_vlan, {"relay_vlan": vlan}
            )
        yield deferToDatabase(
            self.create_subnet,
            {"vlan": relay_vlan if self.dhcp_relay else vlan},
        )
        node = yield deferToDatabase(self.create_node)
        yield deferToDatabase(
            self.create_interface, {"node": node, "vlan": vlan}
        )
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: dv.set(args)
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_dhcp_snippet, {"enabled": True, "node": node}
            )
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dhcp_snippet_updated_value(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan, {"dhcp_on": True, "primary_rack": primary_rack}
        )
        relay_vlan = None
        if self.dhcp_relay:
            relay_vlan = yield deferToDatabase(
                self.create_vlan, {"relay_vlan": vlan}
            )
        yield deferToDatabase(
            self.create_subnet,
            {"vlan": relay_vlan if self.dhcp_relay else vlan},
        )
        dhcp_snippet = yield deferToDatabase(
            self.create_dhcp_snippet, {"enabled": True}
        )
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: dv.set(args)
        )
        yield listener.startService()
        try:
            new_value = yield deferToDatabase(
                dhcp_snippet.value.update, factory.make_string()
            )
            dhcp_snippet.value = new_value
            yield deferToDatabase(dhcp_snippet.save)
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_no_message_for_dhcp_snippet_updated_when_disabled(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan, {"dhcp_on": True, "primary_rack": primary_rack}
        )
        relay_vlan = None
        if self.dhcp_relay:
            relay_vlan = yield deferToDatabase(
                self.create_vlan, {"relay_vlan": vlan}
            )
        yield deferToDatabase(
            self.create_subnet,
            {"vlan": relay_vlan if self.dhcp_relay else vlan},
        )
        dhcp_snippet = yield deferToDatabase(
            self.create_dhcp_snippet, {"enabled": False}
        )
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: dv.set(args)
        )
        yield listener.startService()
        try:
            new_value = yield deferToDatabase(
                dhcp_snippet.value.update, factory.make_string()
            )
            dhcp_snippet.value = new_value
            yield deferToDatabase(dhcp_snippet.save)
            try:
                yield dv.get(timeout=1)
            except CancelledError:
                pass
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dhcp_snippet_updated_enabled(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan, {"dhcp_on": True, "primary_rack": primary_rack}
        )
        relay_vlan = None
        if self.dhcp_relay:
            relay_vlan = yield deferToDatabase(
                self.create_vlan, {"relay_vlan": vlan}
            )
        yield deferToDatabase(
            self.create_subnet,
            {"vlan": relay_vlan if self.dhcp_relay else vlan},
        )
        dhcp_snippet = yield deferToDatabase(
            self.create_dhcp_snippet, {"enabled": False}
        )
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: dv.set(args)
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_dhcp_snippet, dhcp_snippet.id, {"enabled": True}
            )
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dhcp_snippet_updated_description(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan, {"dhcp_on": True, "primary_rack": primary_rack}
        )
        relay_vlan = None
        if self.dhcp_relay:
            relay_vlan = yield deferToDatabase(
                self.create_vlan, {"relay_vlan": vlan}
            )
        yield deferToDatabase(
            self.create_subnet,
            {"vlan": relay_vlan if self.dhcp_relay else vlan},
        )
        dhcp_snippet = yield deferToDatabase(
            self.create_dhcp_snippet, {"enabled": True}
        )
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: dv.set(args)
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_dhcp_snippet,
                dhcp_snippet.id,
                {"description": factory.make_string()},
            )
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dhcp_snippet_updated_subnet(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan, {"dhcp_on": True, "primary_rack": primary_rack}
        )
        relay_vlan = None
        if self.dhcp_relay:
            relay_vlan = yield deferToDatabase(
                self.create_vlan, {"relay_vlan": vlan}
            )
        subnet = yield deferToDatabase(
            self.create_subnet,
            {"vlan": relay_vlan if self.dhcp_relay else vlan},
        )
        dhcp_snippet = yield deferToDatabase(
            self.create_dhcp_snippet, {"enabled": True}
        )
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: dv.set(args)
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_dhcp_snippet, dhcp_snippet.id, {"subnet": subnet}
            )
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dhcp_snippet_updated_node(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan, {"dhcp_on": True, "primary_rack": primary_rack}
        )
        relay_vlan = None
        if self.dhcp_relay:
            relay_vlan = yield deferToDatabase(
                self.create_vlan, {"relay_vlan": vlan}
            )
        yield deferToDatabase(
            self.create_subnet,
            {"vlan": relay_vlan if self.dhcp_relay else vlan},
        )
        node = yield deferToDatabase(self.create_node)
        yield deferToDatabase(
            self.create_interface, {"vlan": vlan, "node": node}
        )
        dhcp_snippet = yield deferToDatabase(
            self.create_dhcp_snippet, {"enabled": True}
        )
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: dv.set(args)
        )
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_dhcp_snippet, dhcp_snippet.id, {"node": node}
            )
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_global_dhcp_snippet_deleted(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan, {"dhcp_on": True, "primary_rack": primary_rack}
        )
        relay_vlan = None
        if self.dhcp_relay:
            relay_vlan = yield deferToDatabase(
                self.create_vlan, {"relay_vlan": vlan}
            )
        yield deferToDatabase(
            self.create_subnet,
            {"vlan": relay_vlan if self.dhcp_relay else vlan},
        )
        dhcp_snippet = yield deferToDatabase(
            self.create_dhcp_snippet, {"enabled": True}
        )
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: dv.set(args)
        )
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_dhcp_snippet, dhcp_snippet.id)
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_no_message_for_global_dhcp_snippet_deleted_when_disabled(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan, {"dhcp_on": True, "primary_rack": primary_rack}
        )
        relay_vlan = None
        if self.dhcp_relay:
            relay_vlan = yield deferToDatabase(
                self.create_vlan, {"relay_vlan": vlan}
            )
        yield deferToDatabase(
            self.create_subnet,
            {"vlan": relay_vlan if self.dhcp_relay else vlan},
        )
        dhcp_snippet = yield deferToDatabase(
            self.create_dhcp_snippet, {"enabled": False}
        )
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: dv.set(args)
        )
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_dhcp_snippet, dhcp_snippet.id)
            try:
                yield dv.get(timeout=1)
            except CancelledError:
                pass
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dhcp_snippet_with_subnet_deleted(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan, {"dhcp_on": True, "primary_rack": primary_rack}
        )
        relay_vlan = None
        if self.dhcp_relay:
            relay_vlan = yield deferToDatabase(
                self.create_vlan, {"relay_vlan": vlan}
            )
        subnet = yield deferToDatabase(
            self.create_subnet,
            {"vlan": relay_vlan if self.dhcp_relay else vlan},
        )
        dhcp_snippet = yield deferToDatabase(
            self.create_dhcp_snippet, {"enabled": True, "subnet": subnet}
        )
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: dv.set(args)
        )
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_dhcp_snippet, dhcp_snippet.id)
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dhcp_snippet_with_node_deleted(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(
            self.create_vlan, {"dhcp_on": True, "primary_rack": primary_rack}
        )
        relay_vlan = None
        if self.dhcp_relay:
            relay_vlan = yield deferToDatabase(
                self.create_vlan, {"relay_vlan": vlan}
            )
        yield deferToDatabase(
            self.create_subnet,
            {"vlan": relay_vlan if self.dhcp_relay else vlan},
        )
        node = yield deferToDatabase(self.create_node)
        yield deferToDatabase(
            self.create_interface, {"vlan": vlan, "node": node}
        )
        dhcp_snippet = yield deferToDatabase(
            self.create_dhcp_snippet, {"enabled": True, "node": node}
        )
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id, lambda *args: dv.set(args)
        )
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_dhcp_snippet, dhcp_snippet.id)
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()


class TestDHCPConfigNTPListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test for the DHCP triggers code.

    This tests the notifications issued by the database when NTP servers are
    reconfigured.
    """

    def set_ntp_servers(self, *servers):
        return deferToDatabase(
            Config.objects.set_config, "ntp_servers", " ".join(servers)
        )

    def clear_ntp_servers(self):
        return deferToDatabase(
            lambda: Config.objects.filter(name="ntp_servers").delete()
        )

    def make_racks(self):
        return [
            self.create_vlan(
                {
                    "dhcp_on": True,
                    "primary_rack": self.create_rack_controller(),
                    "secondary_rack": self.create_rack_controller(),
                }
            ),
            self.create_vlan(
                {
                    "dhcp_on": True,
                    "primary_rack": self.create_rack_controller(),
                    "secondary_rack": None,
                }
            ),
        ]

    def listen_for_sys_dhcp(self, *rack_ids):
        """Create a database listener for 'sys_dhcp_$id' for each rack.

        Return the listener and a mapping from the given rack IDs to the
        DeferredValues that will capture messages.
        """

        def dsetter(dv):
            return lambda *args: dv.set(args)

        dvalues = {rack_id: DeferredValue() for rack_id in rack_ids}
        listener = self.make_listener_without_delay()
        for rack_id, dv in dvalues.items():
            listener.register("sys_dhcp_%s" % rack_id, dsetter(dv))
        return listener, dvalues

    def wait_for_dvalues(self, dvalues):
        d = DeferredList(
            (dv.get(timeout=2) for dv in dvalues), consumeErrors=True
        )

        def unpack(results):
            # Return the first failure, if there is one. We do this in
            # preference to fireOnOneErrback=True because at this point we
            # know that all the Deferreds that went into the DeferredList have
            # fired; fireOnOneErrback may result in the test completing before
            # all have fired, about which the test runner will complain.
            for success, result in results:
                if not success:
                    return result

        return d.addCallback(unpack)

    @wait_for_reactor
    @inlineCallbacks
    def test_alerts_all_racks_when_ntp_server_set(self):
        yield self.clear_ntp_servers()
        yield deferToDatabase(register_system_triggers)

        vlan1, vlan2 = yield deferToDatabase(self.make_racks)
        listener, rack_dvs = self.listen_for_sys_dhcp(
            vlan1.primary_rack_id,
            vlan1.secondary_rack_id,
            vlan2.primary_rack_id,
        )

        yield listener.startService()
        try:
            yield self.set_ntp_servers(factory.make_hostname())
            yield self.wait_for_dvalues(rack_dvs.values())
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_alerts_all_racks_when_ntp_server_updated(self):
        yield self.set_ntp_servers("a." + factory.make_hostname())
        yield deferToDatabase(register_system_triggers)

        vlan1, vlan2 = yield deferToDatabase(self.make_racks)
        listener, rack_dvs = self.listen_for_sys_dhcp(
            vlan1.primary_rack_id,
            vlan1.secondary_rack_id,
            vlan2.primary_rack_id,
        )

        yield listener.startService()
        try:
            yield self.set_ntp_servers("b." + factory.make_hostname())
            yield self.wait_for_dvalues(rack_dvs.values())
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_alerts_all_racks_when_ntp_server_deleted(self):
        yield self.set_ntp_servers(factory.make_hostname())
        yield deferToDatabase(register_system_triggers)

        vlan1, vlan2 = yield deferToDatabase(self.make_racks)
        listener, rack_dvs = self.listen_for_sys_dhcp(
            vlan1.primary_rack_id,
            vlan1.secondary_rack_id,
            vlan2.primary_rack_id,
        )

        yield listener.startService()
        try:
            yield self.clear_ntp_servers()
            yield self.wait_for_dvalues(rack_dvs.values())
        finally:
            yield listener.stopService()


class TestDHCPConfigNTPExternalListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin
):
    """End-to-end test for the DHCP triggers code.

    This tests the notifications issued by the database when NTP is configured
    for external-only, or vice-versa.
    """

    def set_ntp_external_only(self, external_only):
        return deferToDatabase(
            Config.objects.set_config, "ntp_external_only", bool(external_only)
        )

    def clear_ntp_external_only(self):
        return deferToDatabase(
            lambda: Config.objects.filter(name="ntp_external_only").delete()
        )

    def make_racks(self):
        return [
            self.create_vlan(
                {
                    "dhcp_on": True,
                    "primary_rack": self.create_rack_controller(),
                    "secondary_rack": self.create_rack_controller(),
                }
            ),
            self.create_vlan(
                {
                    "dhcp_on": True,
                    "primary_rack": self.create_rack_controller(),
                    "secondary_rack": None,
                }
            ),
        ]

    def listen_for_sys_dhcp(self, *rack_ids):
        """Create a database listener for 'sys_dhcp_$id' for each rack.

        Return the listener and a mapping from the given rack IDs to the
        DeferredValues that will capture messages.
        """

        def dsetter(dv):
            return lambda *args: dv.set(args)

        dvalues = {rack_id: DeferredValue() for rack_id in rack_ids}
        listener = self.make_listener_without_delay()
        for rack_id, dv in dvalues.items():
            listener.register("sys_dhcp_%s" % rack_id, dsetter(dv))
        return listener, dvalues

    def wait_for_dvalues(self, dvalues):
        d = DeferredList(
            (dv.get(timeout=2) for dv in dvalues), consumeErrors=True
        )

        def unpack(results):
            # Return the first failure, if there is one. We do this in
            # preference to fireOnOneErrback=True because at this point we
            # know that all the Deferreds that went into the DeferredList have
            # fired; fireOnOneErrback may result in the test completing before
            # all have fired, about which the test runner will complain.
            for success, result in results:
                if not success:
                    return result

        return d.addCallback(unpack)

    @wait_for_reactor
    @inlineCallbacks
    def test_alerts_all_racks_when_ntp_external_only_set(self):
        yield self.clear_ntp_external_only()
        yield deferToDatabase(register_system_triggers)

        vlan1, vlan2 = yield deferToDatabase(self.make_racks)
        listener, rack_dvs = self.listen_for_sys_dhcp(
            vlan1.primary_rack_id,
            vlan1.secondary_rack_id,
            vlan2.primary_rack_id,
        )

        yield listener.startService()
        try:
            yield self.set_ntp_external_only(True)
            yield self.wait_for_dvalues(rack_dvs.values())
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_alerts_all_racks_when_ntp_external_only_updated(self):
        ntp_external_only = factory.pick_bool()
        yield self.set_ntp_external_only(ntp_external_only)
        yield deferToDatabase(register_system_triggers)

        vlan1, vlan2 = yield deferToDatabase(self.make_racks)
        listener, rack_dvs = self.listen_for_sys_dhcp(
            vlan1.primary_rack_id,
            vlan1.secondary_rack_id,
            vlan2.primary_rack_id,
        )

        yield listener.startService()
        try:
            yield self.set_ntp_external_only(not ntp_external_only)
            yield self.wait_for_dvalues(rack_dvs.values())
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_alerts_all_racks_when_ntp_server_deleted(self):
        ntp_external_only = factory.pick_bool()
        yield self.set_ntp_external_only(ntp_external_only)
        yield deferToDatabase(register_system_triggers)

        vlan1, vlan2 = yield deferToDatabase(self.make_racks)
        listener, rack_dvs = self.listen_for_sys_dhcp(
            vlan1.primary_rack_id,
            vlan1.secondary_rack_id,
            vlan2.primary_rack_id,
        )

        yield listener.startService()
        try:
            yield self.clear_ntp_external_only()
            yield self.wait_for_dvalues(rack_dvs.values())
        finally:
            yield listener.stopService()


class TestDNSDomainListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin, DNSHelpersMixin
):
    """End-to-end test for the DNS triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_domain_insert_authorative(self):
        yield deferToDatabase(register_system_triggers)
        yield self.capturePublication()
        name = factory.make_name("domain")
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_domain, {"name": name, "authoritative": True}
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            f"added zone {name}",
            self.getCapturedPublication().source,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_doesnt_send_message_for_domain_insert_not_authorative(self):
        yield deferToDatabase(register_system_triggers)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_domain, {"authoritative": False})
            with self.assertRaisesRegex(CancelledError, "^$"):
                yield dv.get(timeout=1)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_domain_update_now_authorative(self):
        yield deferToDatabase(register_system_triggers)
        domain = yield deferToDatabase(
            self.create_domain, {"authoritative": False}
        )
        domain_name = factory.make_name("domain")
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_domain,
                domain.id,
                {"name": domain_name, "authoritative": True},
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            f"added zone {domain_name}",
            self.getCapturedPublication().source,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_domain_update_no_longer_authorative(self):
        yield deferToDatabase(register_system_triggers)
        domain = yield deferToDatabase(
            self.create_domain, {"authoritative": True}
        )
        domain_name = factory.make_name("domain")
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_domain,
                domain.id,
                {"name": domain_name, "authoritative": False},
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            "removed zone %s" % domain_name,
            self.getCapturedPublication().source,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_domain_update(self):
        yield deferToDatabase(register_system_triggers)
        old_name = factory.make_name("domain")
        new_name = factory.make_name("domain")
        new_ttl = random.randint(100, 300)
        domain = yield deferToDatabase(
            self.create_domain, {"authoritative": True, "name": old_name}
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_domain,
                domain.id,
                {"name": new_name, "ttl": new_ttl},
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f"zone {old_name} renamed to {new_name} and ttl changed to {new_ttl}",
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_domain_delete(self):
        yield deferToDatabase(register_system_triggers)
        domain = yield deferToDatabase(self.create_domain)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_domain, domain.id)
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            "removed zone %s" % domain.name,
            self.getCapturedPublication().source,
        )


class TestDNSStaticIPAddressListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin, DNSHelpersMixin
):
    """End-to-end test for the DNS triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_doesnt_sends_message_for_update_on_node_alloc_type_no_ip(self):
        yield deferToDatabase(register_system_triggers)
        node = yield deferToDatabase(self.create_node_with_interface)
        sip = yield deferToDatabase(self.get_node_ip_address, node)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_staticipaddress,
                sip.id,
                {"alloc_type": IPADDRESS_TYPE.STICKY},
            )
            with self.assertRaisesRegex(CancelledError, "^$"):
                yield dv.get(timeout=1)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_update_on_node_alloc_type_with_ip(self):
        yield deferToDatabase(register_system_triggers)
        node = yield deferToDatabase(self.create_node_with_interface)
        sip = yield deferToDatabase(self.get_node_ip_address, node)
        new_ip = yield deferToDatabase(
            lambda sip: factory.pick_ip_in_Subnet(sip.subnet), sip
        )
        yield deferToDatabase(
            self.update_staticipaddress, sip.id, {"ip": new_ip}
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_staticipaddress,
                sip.id,
                {"alloc_type": IPADDRESS_TYPE.STICKY},
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            "ip %s alloc_type changed to 1" % new_ip,
            self.getCapturedPublication().source,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_update_on_node_ip(self):
        yield deferToDatabase(register_system_triggers)
        node = yield deferToDatabase(self.create_node_with_interface)
        sip = yield deferToDatabase(self.get_node_ip_address, node)
        new_ip = yield deferToDatabase(
            lambda sip: factory.pick_ip_in_Subnet(sip.subnet), sip
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_staticipaddress, sip.id, {"ip": new_ip}
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            "ip %s allocated" % new_ip,
            self.getCapturedPublication().source,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_update_on_node_ip_no_longer_temp(self):
        yield deferToDatabase(register_system_triggers)
        node = yield deferToDatabase(self.create_node_with_interface)
        sip = yield deferToDatabase(self.get_node_ip_address, node)
        new_ip = yield deferToDatabase(
            lambda sip: factory.pick_ip_in_Subnet(sip.subnet), sip
        )
        sip.ip = new_ip
        sip.temp_expires_on = timezone.now()
        yield deferToDatabase(sip.save)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_staticipaddress, sip.id, {"temp_expires_on": None}
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            "ip %s allocated" % new_ip,
            self.getCapturedPublication().source,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_update_on_node_ip_becoming_temp(self):
        yield deferToDatabase(register_system_triggers)
        node = yield deferToDatabase(self.create_node_with_interface)
        sip = yield deferToDatabase(self.get_node_ip_address, node)
        new_ip = yield deferToDatabase(
            lambda sip: factory.pick_ip_in_Subnet(sip.subnet), sip
        )
        sip.ip = new_ip
        sip.temp_expires_on = None
        yield deferToDatabase(sip.save)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_staticipaddress,
                sip.id,
                {"temp_expires_on": timezone.now()},
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            "ip %s released" % new_ip,
            self.getCapturedPublication().source,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_doesnt_send_message_for_non_authorative_domain(self):
        yield deferToDatabase(register_system_triggers)
        node = yield deferToDatabase(self.create_node_with_interface)
        domain = yield deferToDatabase(lambda node: node.domain, node)
        domain.authoritative = False
        yield deferToDatabase(lambda domain: domain.save(), domain)
        sip = yield deferToDatabase(self.get_node_ip_address, node)
        new_ip = yield deferToDatabase(
            lambda sip: factory.pick_ip_in_Subnet(sip.subnet), sip
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_staticipaddress, sip.id, {"ip": new_ip}
            )
            with self.assertRaisesRegex(CancelledError, "^$"):
                yield dv.get(timeout=1)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_update_on_dnsresource(self):
        yield deferToDatabase(register_system_triggers)
        domain = yield deferToDatabase(self.create_domain)
        dnsrr = yield deferToDatabase(
            self.create_dnsresource,
            {"domain": domain, "no_ip_addresses": True},
        )
        subnet = yield deferToDatabase(self.create_subnet)
        old_ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        sip = yield deferToDatabase(
            self.create_staticipaddress,
            {
                "alloc_type": IPADDRESS_TYPE.STICKY,
                "dnsresource": dnsrr,
                "subnet": subnet,
                "ip": old_ip,
            },
        )
        new_ip = factory.pick_ip_in_network(
            subnet.get_ipnetwork(), but_not=[old_ip]
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_staticipaddress, sip.id, {"ip": new_ip}
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            f"ip {old_ip} changed to {new_ip}",
            self.getCapturedPublication().source,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_doesnt_send_message_on_dnsresource_non_authorative(self):
        yield deferToDatabase(register_system_triggers)
        domain = yield deferToDatabase(
            self.create_domain, {"authoritative": False}
        )
        dnsrr = yield deferToDatabase(
            self.create_dnsresource,
            {"domain": domain, "no_ip_addresses": True},
        )
        subnet = yield deferToDatabase(self.create_subnet)
        old_ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        sip = yield deferToDatabase(
            self.create_staticipaddress,
            {
                "alloc_type": IPADDRESS_TYPE.STICKY,
                "dnsresource": dnsrr,
                "subnet": subnet,
                "ip": old_ip,
            },
        )
        new_ip = factory.pick_ip_in_network(
            subnet.get_ipnetwork(), but_not=[old_ip]
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_staticipaddress, sip.id, {"ip": new_ip}
            )
            with self.assertRaisesRegex(CancelledError, "^$"):
                yield dv.get(timeout=1)
        finally:
            yield listener.stopService()


class TestDNSInterfaceStaticIPAddressListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin, DNSHelpersMixin
):
    """End-to-end test for the DNS triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_interface_staticipaddress_link(self):
        yield deferToDatabase(register_system_triggers)
        interface = yield deferToDatabase(self.create_interface)
        node = yield deferToDatabase(
            lambda nic: nic.node_config.node, interface
        )
        subnet = yield deferToDatabase(self.create_subnet)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            sip = yield deferToDatabase(
                self.create_staticipaddress,
                {"interface": interface, "subnet": subnet},
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f"ip {sip.ip} connected to {node.hostname} on {interface.name}",
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_doesnt_send_message_for_nic_link_non_authorative_domain(self):
        yield deferToDatabase(register_system_triggers)
        domain = yield deferToDatabase(
            self.create_domain, {"authoritative": False}
        )
        node = yield deferToDatabase(self.create_node, {"domain": domain})
        interface = yield deferToDatabase(
            self.create_interface, {"node": node}
        )
        subnet = yield deferToDatabase(self.create_subnet)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_staticipaddress,
                {"interface": interface, "subnet": subnet},
            )
            with self.assertRaisesRegex(CancelledError, "^$"):
                yield dv.get(timeout=1)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_interface_staticipaddress_unlink(self):
        yield deferToDatabase(register_system_triggers)
        interface = yield deferToDatabase(self.create_interface)
        node = yield deferToDatabase(
            lambda nic: nic.node_config.node, interface
        )
        subnet = yield deferToDatabase(self.create_subnet)
        sip = yield deferToDatabase(
            self.create_staticipaddress,
            {"interface": interface, "subnet": subnet},
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_staticipaddress, sip.id)
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f"ip {sip.ip} disconnected from {node.hostname} on {interface.name}",
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_doesnt_send_message_for_nic_unlink_non_authorative_domain(self):
        yield deferToDatabase(register_system_triggers)
        domain = yield deferToDatabase(
            self.create_domain, {"authoritative": False}
        )
        node = yield deferToDatabase(self.create_node, {"domain": domain})
        interface = yield deferToDatabase(
            self.create_interface, {"node": node}
        )
        subnet = yield deferToDatabase(self.create_subnet)
        sip = yield deferToDatabase(
            self.create_staticipaddress,
            {"interface": interface, "subnet": subnet},
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_staticipaddress, sip.id)
            with self.assertRaisesRegex(CancelledError, "^$"):
                yield dv.get(timeout=1)
        finally:
            yield listener.stopService()


class TestDNSDNSResourceListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin, DNSHelpersMixin
):
    """End-to-end test for the DNS triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dnsresource_insert(self):
        yield deferToDatabase(register_system_triggers)
        domain = yield deferToDatabase(self.create_domain)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            # Pass ip_addresses=[] to avoid an extra .save() -- and thus an
            # UPDATE -- in the factory method.
            resource = yield deferToDatabase(
                self.create_dnsresource, {"domain": domain, "ip_addresses": []}
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            f"zone {domain.name} added resource {resource.name}",
            self.getCapturedPublication().source,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dnsresource_update(self):
        yield deferToDatabase(register_system_triggers)
        domain = yield deferToDatabase(self.create_domain)
        resource = yield deferToDatabase(
            self.create_dnsresource, {"domain": domain}
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            new_name = factory.make_name("resource")
            yield deferToDatabase(
                self.update_dnsresource, resource.id, {"name": new_name}
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            f"zone {domain.name} updated resource {new_name}",
            self.getCapturedPublication().source,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dnsresource_update_change_domain(self):
        yield deferToDatabase(register_system_triggers)
        domain = yield deferToDatabase(self.create_domain)
        resource = yield deferToDatabase(
            self.create_dnsresource, {"domain": domain}
        )
        new_domain = yield deferToDatabase(self.create_domain)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_dnsresource, resource.id, {"domain": new_domain}
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()

        def _validate_publications(
            resource_name, old_domain_name, new_domain_name
        ):
            sources = reversed(
                [
                    pub.source
                    for pub in DNSPublication.objects.order_by("-id")[:2]
                ]
            )
            self.assertEqual(
                list(sources),
                [
                    "zone %s removed resource %s"
                    % (old_domain_name, resource_name),
                    "zone %s added resource %s"
                    % (new_domain_name, resource_name),
                ],
            )

        yield deferToDatabase(
            _validate_publications, resource.name, domain.name, new_domain.name
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dnsresource_delete(self):
        yield deferToDatabase(register_system_triggers)
        domain = yield deferToDatabase(self.create_domain)
        resource = yield deferToDatabase(
            self.create_dnsresource, {"domain": domain}
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_dnsresource, resource.id)
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            f"zone {domain.name} removed resource {resource.name}",
            self.getCapturedPublication().source,
        )


class TestDNSDNSResourceStaticIPAddressListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin, DNSHelpersMixin
):
    """End-to-end test for the DNS triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dnsresource_staticipaddress_link(self):
        yield deferToDatabase(register_system_triggers)
        domain = yield deferToDatabase(self.create_domain)
        resource = yield deferToDatabase(
            self.create_dnsresource, {"domain": domain}
        )
        sip = yield deferToDatabase(self.create_staticipaddress)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(resource.ip_addresses.add, sip)
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f"ip {sip.ip} linked to resource {resource.name} on zone {domain.name}",
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dnsresource_staticipaddress_unlink(self):
        yield deferToDatabase(register_system_triggers)
        domain = yield deferToDatabase(self.create_domain)
        resource = yield deferToDatabase(
            self.create_dnsresource, {"domain": domain}
        )
        sip = yield deferToDatabase(self.create_staticipaddress)
        yield deferToDatabase(resource.ip_addresses.add, sip)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(resource.ip_addresses.remove, sip)
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f"ip {sip.ip} unlinked from resource {resource.name} on zone {domain.name}",
        )


class TestDNSDNSDataListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin, DNSHelpersMixin
):
    """End-to-end test for the DNS triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dnsdata_insert(self):
        yield deferToDatabase(register_system_triggers)
        domain = yield deferToDatabase(self.create_domain)
        resource = yield deferToDatabase(
            self.create_dnsresource, {"domain": domain}
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            data = yield deferToDatabase(
                self.create_dnsdata, {"dnsresource": resource}
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f"added {data.rrtype} to resource {resource.name} on zone {domain.name}",
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dnsdata_update(self):
        yield deferToDatabase(register_system_triggers)
        domain = yield deferToDatabase(self.create_domain)
        resource = yield deferToDatabase(
            self.create_dnsresource, {"domain": domain}
        )
        data = yield deferToDatabase(
            self.create_dnsdata,
            {
                "dnsresource": resource,
                "rrtype": "TXT",
                "rrdata": factory.make_name("txt"),
            },
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_dnsdata,
                data.id,
                {"rrdata": factory.make_name("txt")},
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f"updated {data.rrtype} in resource {resource.name} on zone {domain.name}",
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dnsdata_delete(self):
        yield deferToDatabase(register_system_triggers)
        domain = yield deferToDatabase(self.create_domain)
        resource = yield deferToDatabase(
            self.create_dnsresource, {"domain": domain}
        )
        data = yield deferToDatabase(
            self.create_dnsdata, {"dnsresource": resource}
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_dnsdata, data.id)
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f"removed {data.rrtype} from resource {resource.name} on zone {domain.name}",
        )


class TestDNSSubnetListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin, DNSHelpersMixin
):
    """End-to-end test for the DNS triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_subnet_insert(self):
        yield deferToDatabase(register_system_triggers)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            subnet = yield deferToDatabase(self.create_subnet)
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            "added subnet %s" % subnet.cidr,
            self.getCapturedPublication().source,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_doesnt_send_message_for_subnet_insert_disabled_rdns(self):
        yield deferToDatabase(register_system_triggers)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.create_subnet, {"rdns_mode": RDNS_MODE.DISABLED}
            )
            with self.assertRaisesRegex(CancelledError, "^$"):
                yield dv.get(timeout=1)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_subnet_cidr_update(self):
        yield deferToDatabase(register_system_triggers)
        subnet = yield deferToDatabase(self.create_subnet)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            network = factory.make_ip4_or_6_network()
            cidr_old, cidr_new = subnet.cidr, str(network.cidr)
            yield deferToDatabase(
                self.update_subnet,
                subnet.id,
                {
                    "cidr": cidr_new,
                    "gateway_ip": factory.pick_ip_in_network(network),
                    "dns_servers": [],
                },
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            f"subnet {cidr_old} changed to {cidr_new}",
            self.getCapturedPublication().source,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_subnet_rdns_mode_update(self):
        yield deferToDatabase(register_system_triggers)
        subnet = yield deferToDatabase(self.create_subnet)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            rdns_old = subnet.rdns_mode
            rdns_new = factory.pick_enum(RDNS_MODE, but_not=[rdns_old])
            yield deferToDatabase(
                self.update_subnet, subnet.id, {"rdns_mode": rdns_new}
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            f"subnet {subnet.cidr} rdns changed to {rdns_new}",
            self.getCapturedPublication().source,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_subnet_delete(self):
        yield deferToDatabase(register_system_triggers)
        subnet = yield deferToDatabase(self.create_subnet)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_subnet, subnet.id)
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            "removed subnet %s" % subnet.cidr,
            self.getCapturedPublication().source,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_doesnt_send_message_for_subnet_delete_disabled_rdns(self):
        yield deferToDatabase(register_system_triggers)
        subnet = yield deferToDatabase(
            self.create_subnet, {"rdns_mode": RDNS_MODE.DISABLED}
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_subnet, subnet.id)
            with self.assertRaisesRegex(CancelledError, "^$"):
                yield dv.get(timeout=1)
        finally:
            yield listener.stopService()


class TestDNSNodeListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin, DNSHelpersMixin
):
    """End-to-end test for the DNS triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_node_update_hostname(self):
        yield deferToDatabase(register_system_triggers)
        node = yield deferToDatabase(self.create_node)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            hostname_old = node.hostname
            hostname_new = factory.make_name("hostname")
            yield deferToDatabase(
                self.update_node, node.system_id, {"hostname": hostname_new}
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            f"node {hostname_old} changed hostname to {hostname_new}",
            self.getCapturedPublication().source,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_node_update_domain(self):
        yield deferToDatabase(register_system_triggers)
        node = yield deferToDatabase(self.create_node)
        domain = yield deferToDatabase(self.create_domain)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_node, node.system_id, {"domain": domain}
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            f"node {node.hostname} changed zone to {domain.name}",
            self.getCapturedPublication().source,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_node_delete(self):
        yield deferToDatabase(register_system_triggers)
        node = yield deferToDatabase(self.create_node)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_node, node.system_id)
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            "removed node %s" % node.hostname,
            self.getCapturedPublication().source,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_doesnt_send_message_for_delete_on_non_authorative_domain(self):
        yield deferToDatabase(register_system_triggers)
        domain = yield deferToDatabase(
            self.create_domain, {"authoritative": False}
        )
        node = yield deferToDatabase(self.create_node, {"domain": domain})
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_node, node.system_id)
            with self.assertRaisesRegex(CancelledError, "^$"):
                yield dv.get(timeout=1)
        finally:
            yield listener.stopService()


class TestDNSInterfaceListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin, DNSHelpersMixin
):
    """End-to-end test for the DNS triggers code."""

    @transactional
    def migrate_unknown_to_physical(self, id, node):
        nic = Interface.objects.get(id=id)
        nic.type = INTERFACE_TYPE.PHYSICAL
        nic.node_config = node.current_config
        nic.__class__ = PhysicalInterface
        nic.save()

    @transactional
    def migrate_physical_to_unknown(self, id):
        nic = Interface.objects.get(id=id)
        nic.type = INTERFACE_TYPE.UNKNOWN
        nic.node_config = None
        nic.__class__ = UnknownInterface
        nic.save()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_interface_update_name(self):
        yield deferToDatabase(register_system_triggers)
        interface = yield deferToDatabase(self.create_interface)
        node = yield deferToDatabase(
            lambda nic: nic.node_config.node, interface
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            name_old = interface.name
            name_new = factory.make_name("name")
            yield deferToDatabase(
                self.update_interface, interface.id, {"name": name_new}
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f"node {node.hostname} renamed interface {name_old} to {name_new}",
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_unknown_to_physical(self):
        yield deferToDatabase(register_system_triggers)
        interface = yield deferToDatabase(self.create_unknown_interface)
        node = yield deferToDatabase(self.create_node)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.migrate_unknown_to_physical, interface.id, node
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            f"node {node.hostname} added interface {interface.name}",
            self.getCapturedPublication().source,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_physical_to_unknown(self):
        yield deferToDatabase(register_system_triggers)
        interface = yield deferToDatabase(self.create_interface)
        node = yield deferToDatabase(
            lambda nic: nic.node_config.node, interface
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.migrate_physical_to_unknown, interface.id
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f"node {node.hostname} removed interface {interface.name}",
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_interface_changing_to_new_node(self):
        yield deferToDatabase(register_system_triggers)
        interface = yield deferToDatabase(self.create_interface)
        old_node = yield deferToDatabase(
            lambda nic: nic.node_config.node, interface
        )
        new_node = yield deferToDatabase(self.create_node)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_interface,
                interface.id,
                {"node_config": new_node.current_config},
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()

        def _validate_publications(nic_name, old_hostname, new_hostname):
            sources = reversed(
                [
                    pub.source
                    for pub in DNSPublication.objects.order_by("-id")[:2]
                ]
            )
            self.assertEqual(
                list(sources),
                [
                    f"node {old_hostname} removed interface {nic_name}",
                    f"node {new_hostname} added interface {nic_name}",
                ],
            )

        yield deferToDatabase(
            _validate_publications,
            interface.name,
            old_node.hostname,
            new_node.hostname,
        )


class TestDNSConfigListener(
    MAASTransactionServerTestCase, TransactionalHelpersMixin, DNSHelpersMixin
):
    """End-to-end test for the DNS triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_upstream_dns_insert(self):
        upstream_dns_new = factory.make_ip_address()
        yield deferToDatabase(register_system_triggers)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                Config.objects.set_config, "upstream_dns", upstream_dns_new
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f'configuration upstream_dns set to "{upstream_dns_new}"',
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_dnssec_validation_insert(self):
        yield deferToDatabase(register_system_triggers)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                Config.objects.set_config, "dnssec_validation", "no"
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            'configuration dnssec_validation set to "no"',
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_default_dns_ttl_insert(self):
        default_dns_ttl_new = random.randint(10, 1000)
        yield deferToDatabase(register_system_triggers)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                Config.objects.set_config,
                "default_dns_ttl",
                default_dns_ttl_new,
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f"configuration default_dns_ttl set to {default_dns_ttl_new}",
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_maas_internal_domain_insert(self):
        maas_internal_domain_new = factory.make_name("internal")
        yield deferToDatabase(register_system_triggers)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                Config.objects.set_config,
                "maas_internal_domain",
                maas_internal_domain_new,
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f'configuration maas_internal_domain set to "{maas_internal_domain_new}"',
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_dns_trusted_acl_insert(self):
        dns_trusted_acl_new = factory.make_name("internal")
        yield deferToDatabase(register_system_triggers)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                Config.objects.set_config,
                "dns_trusted_acl",
                dns_trusted_acl_new,
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f'configuration dns_trusted_acl set to "{dns_trusted_acl_new}"',
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_upstream_dns_update(self):
        upstream_dns_old = factory.make_ip_address()
        upstream_dns_new = factory.make_ip_address()
        yield deferToDatabase(register_system_triggers)
        yield deferToDatabase(
            Config.objects.set_config, "upstream_dns", upstream_dns_old
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                Config.objects.set_config, "upstream_dns", upstream_dns_new
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f'configuration upstream_dns changed to "{upstream_dns_new}"',
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_dnssec_validation_update(self):
        yield deferToDatabase(register_system_triggers)
        yield deferToDatabase(
            Config.objects.set_config, "dnssec_validation", "no"
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                Config.objects.set_config, "dnssec_validation", "yes"
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            'configuration dnssec_validation changed to "yes"',
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_default_dns_ttl_update(self):
        default_dns_ttl_old = random.randint(10, 1000)
        default_dns_ttl_new = random.randint(10, 1000)
        yield deferToDatabase(register_system_triggers)
        yield deferToDatabase(
            Config.objects.set_config, "default_dns_ttl", default_dns_ttl_old
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                Config.objects.set_config,
                "default_dns_ttl",
                default_dns_ttl_new,
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f"configuration default_dns_ttl changed to {default_dns_ttl_new}",
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_maas_internal_domain_update(self):
        maas_internal_domain_old = factory.make_name("internal")
        maas_internal_domain_new = factory.make_name("internal_new")
        yield deferToDatabase(register_system_triggers)
        yield deferToDatabase(
            Config.objects.set_config,
            "maas_internal_domain",
            maas_internal_domain_old,
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                Config.objects.set_config,
                "maas_internal_domain",
                maas_internal_domain_new,
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f'configuration maas_internal_domain changed to "{maas_internal_domain_new}"',
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_dns_trusted_acl_update(self):
        dns_trusted_acl_old = factory.make_name("internal")
        dns_trusted_acl_new = factory.make_name("internal_new")
        yield deferToDatabase(register_system_triggers)
        yield deferToDatabase(
            Config.objects.set_config, "dns_trusted_acl", dns_trusted_acl_old
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                Config.objects.set_config,
                "dns_trusted_acl",
                dns_trusted_acl_new,
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f'configuration dns_trusted_acl changed to "{dns_trusted_acl_new}"',
        )


class TestDNSConfigListenerLegacy(
    MAASLegacyTransactionServerTestCase,
    TransactionalHelpersMixin,
    DNSHelpersMixin,
):
    """Legacy end-to-end test for the DNS triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_windows_kms_host_insert(self):
        kms_host_new = factory.make_name("kms-host-new")
        yield deferToDatabase(register_system_triggers)
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                Config.objects.set_config, "windows_kms_host", kms_host_new
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f'configuration windows_kms_host set to "{kms_host_new}"',
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_windows_kms_host_update(self):
        kms_host_old = factory.make_name("kms-host-old")
        kms_host_new = factory.make_name("kms-host-new")
        yield deferToDatabase(register_system_triggers)
        yield deferToDatabase(
            Config.objects.set_config, "windows_kms_host", kms_host_old
        )
        yield self.capturePublication()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                Config.objects.set_config, "windows_kms_host", kms_host_new
            )
            yield dv.get(timeout=2)
            yield self.assertPublicationUpdated()
        finally:
            yield listener.stopService()
        self.assertEqual(
            self.getCapturedPublication().source,
            f'configuration windows_kms_host changed to "{kms_host_new}"',
        )


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
    def test_sends_message_for_subnet_allow_dns_update(self):
        yield deferToDatabase(register_system_triggers)
        subnet = yield deferToDatabase(
            self.create_subnet, {"allow_dns": False}
        )
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_subnet, subnet.id, {"allow_dns": True}
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
