# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Use the `PostgresListenerService` to test all of the triggers from for
`maasserver.triggers.system`"""

__all__ = []

from datetime import (
    datetime,
    timedelta,
)
import random

from crochet import wait_for
from django.db import connection as db_connection
from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    IPRANGE_TYPE,
    RDNS_MODE,
)
from maasserver.models.config import Config
from maasserver.models.interface import (
    Interface,
    PhysicalInterface,
    UnknownInterface,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.triggers.system import register_system_triggers
from maasserver.triggers.tests.helper import (
    DNSHelpersMixin,
    TransactionalHelpersMixin,
)
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from netaddr import IPAddress
from provisioningserver.utils.twisted import DeferredValue
from twisted.internet.defer import (
    CancelledError,
    inlineCallbacks,
)


wait_for_reactor = wait_for(30)  # 30 seconds.


class TestCoreRegionRackRPCConnectionInsertListener(
        MAASTransactionServerTestCase, TransactionalHelpersMixin):
    """End-to-end test for the core triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_alerts_region_process_and_sets_managing_process(self):
        yield deferToDatabase(register_system_triggers)
        region = yield deferToDatabase(self.create_region_controller)
        region_process = yield deferToDatabase(
            self.create_region_controller_process, {
                "region": region,
            })
        region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint, {
                "process": region_process,
            })
        rack_controller = yield deferToDatabase(self.create_rack_controller)

        process_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_core_%s" % region_process.id,
            lambda *args: process_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_region_rack_rpc_connection, {
                "endpoint": region_process_endpoint,
                "rack_controller": rack_controller,
            })
            yield process_dv.get(timeout=2)
            self.assertEqual((
                "sys_core_%s" % region_process.id,
                "watch_%s" % rack_controller.id),
                process_dv.value)
            rack_controller = yield deferToDatabase(
                self.reload_object, rack_controller)
            self.assertEqual(
                region_process.id, rack_controller.managing_process_id)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_picks_region_process_managing_the_least_num_of_racks(self):
        region = yield deferToDatabase(self.create_region_controller)
        # Create region process that has a connection to a rack controller
        # and is already managing it.
        managing_region_process = yield deferToDatabase(
            self.create_region_controller_process, {
                "region": region,
            })
        managing_region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint, {
                "process": managing_region_process,
            })
        rack_controller_connected = yield deferToDatabase(
            self.create_rack_controller, {
                "managing_process": managing_region_process
            })
        yield deferToDatabase(self.create_region_rack_rpc_connection, {
            "endpoint": managing_region_process_endpoint,
            "rack_controller": rack_controller_connected,
        })

        # Create a region process that is not managing a rack controller but
        # has connections to both rack controllers. When the trigger is create
        # and the last connection is added it will select the region process
        # with no connections.
        not_managing_region_process = yield deferToDatabase(
            self.create_region_controller_process, {
                "region": region,
            })
        not_managing_region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint, {
                "process": not_managing_region_process,
            })
        not_managed_rack_controller = yield deferToDatabase(
            self.create_rack_controller)
        yield deferToDatabase(self.create_region_rack_rpc_connection, {
            "endpoint": managing_region_process_endpoint,
            "rack_controller": not_managed_rack_controller,
        })

        # Now create the trigger so that it is actually ran.
        yield deferToDatabase(register_system_triggers)
        process_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_core_%s" % not_managing_region_process.id,
            lambda *args: process_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_region_rack_rpc_connection, {
                "endpoint": not_managing_region_process_endpoint,
                "rack_controller": not_managed_rack_controller,
            })
            yield process_dv.get(timeout=2)
            self.assertEqual((
                "sys_core_%s" % not_managing_region_process.id,
                "watch_%s" % not_managed_rack_controller.id),
                process_dv.value)
            not_managed_rack_controller = yield deferToDatabase(
                self.reload_object, not_managed_rack_controller)
            self.assertEqual(
                not_managing_region_process.id,
                not_managed_rack_controller.managing_process_id)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_selectes_new_region_process_when_managing_one_is_dead(self):
        region = yield deferToDatabase(self.create_region_controller)
        # Create region process that has a connection to a rack controller
        # and is already managing it.
        managing_region_process = yield deferToDatabase(
            self.create_region_controller_process, {
                "region": region,
            })
        managing_region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint, {
                "process": managing_region_process,
            })
        rack_controller_connected = yield deferToDatabase(
            self.create_rack_controller, {
                "managing_process": managing_region_process
            })
        yield deferToDatabase(self.create_region_rack_rpc_connection, {
            "endpoint": managing_region_process_endpoint,
            "rack_controller": rack_controller_connected,
        })

        # Create a dead region process that is managing a rack controller but
        # has connections to both rack controllers. When the trigger is create
        # and the last connection is added it will select the region process
        # with no connections.
        dead_region_process = yield deferToDatabase(
            self.create_region_controller_process, {
                "region": region,
                "updated": datetime.now() - timedelta(seconds=90),
            })
        dead_region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint, {
                "process": dead_region_process,
            })
        dead_managed_rack_controller = yield deferToDatabase(
            self.create_rack_controller, {
                "managing_process": dead_region_process,
            })
        yield deferToDatabase(self.create_region_rack_rpc_connection, {
            "endpoint": managing_region_process_endpoint,
            "rack_controller": dead_managed_rack_controller,
        })

        # Now create the trigger so that it is actually ran.
        yield deferToDatabase(register_system_triggers)
        process_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_core_%s" % managing_region_process.id,
            lambda *args: process_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_region_rack_rpc_connection, {
                "endpoint": dead_region_process_endpoint,
                "rack_controller": dead_managed_rack_controller,
            })
            yield process_dv.get(timeout=2)
            self.assertEqual((
                "sys_core_%s" % managing_region_process.id,
                "watch_%s" % dead_managed_rack_controller.id),
                process_dv.value)
            dead_managed_rack_controller = yield deferToDatabase(
                self.reload_object, dead_managed_rack_controller)
            self.assertEqual(
                managing_region_process.id,
                dead_managed_rack_controller.managing_process_id)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_rebalance_the_managing_process_for_the_rack_controller(self):
        region = yield deferToDatabase(self.create_region_controller)
        # Create a region process that is managing 5 rack controllers.
        overloaded_region_process = yield deferToDatabase(
            self.create_region_controller_process, {
                "region": region,
            })
        for _ in range(5):
            yield deferToDatabase(
                self.create_rack_controller, {
                    "managing_process": overloaded_region_process
                })

        # Create region process that has no managing rack controllers.
        region_process = yield deferToDatabase(
            self.create_region_controller_process, {
                "region": region,
            })
        region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint, {
                "process": region_process,
            })

        # Create the rack controller connected to the overloaded region
        # process.
        rack_controller = yield deferToDatabase(
            self.create_rack_controller, {
                "managing_process": overloaded_region_process,
            })
        overloaded_region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint, {
                "process": overloaded_region_process,
            })
        yield deferToDatabase(self.create_region_rack_rpc_connection, {
            "endpoint": overloaded_region_process_endpoint,
            "rack_controller": rack_controller,
        })

        # Now create the trigger so that it is actually ran.
        yield deferToDatabase(register_system_triggers)

        # Catch that unwatch is called on the overloaded region process and
        # watch is called on the other region process.
        listener = self.make_listener_without_delay()
        overloaded_dv = DeferredValue()
        listener.register(
            "sys_core_%s" % overloaded_region_process.id,
            lambda *args: overloaded_dv.set(args))
        process_dv = DeferredValue()
        listener.register(
            "sys_core_%s" % region_process.id,
            lambda *args: process_dv.set(args))
        yield listener.startService()
        try:
            # Create the connection that will balance the connection for
            # the client.
            yield deferToDatabase(self.create_region_rack_rpc_connection, {
                "endpoint": region_process_endpoint,
                "rack_controller": rack_controller,
            })
            yield overloaded_dv.get(timeout=2)
            yield process_dv.get(timeout=2)
            self.assertEqual((
                "sys_core_%s" % overloaded_region_process.id,
                "unwatch_%s" % rack_controller.id),
                overloaded_dv.value)
            self.assertEqual((
                "sys_core_%s" % region_process.id,
                "watch_%s" % rack_controller.id),
                process_dv.value)
            rack_controller = yield deferToDatabase(
                self.reload_object, rack_controller)
            self.assertEqual(
                region_process.id,
                rack_controller.managing_process_id)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_rebalance_doesnt_happen_when_less_than_half_conn(self):
        region = yield deferToDatabase(self.create_region_controller)
        # Create a region process that is managing 5 rack controllers.
        overloaded_region_process = yield deferToDatabase(
            self.create_region_controller_process, {
                "region": region,
            })
        for _ in range(5):
            yield deferToDatabase(
                self.create_rack_controller, {
                    "managing_process": overloaded_region_process
                })

        # Create the rack controller connected to the overloaded region
        # process.
        rack_controller = yield deferToDatabase(
            self.create_rack_controller, {
                "managing_process": overloaded_region_process,
            })
        overloaded_region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint, {
                "process": overloaded_region_process,
            })
        yield deferToDatabase(self.create_region_rack_rpc_connection, {
            "endpoint": overloaded_region_process_endpoint,
            "rack_controller": rack_controller,
        })

        # Create many more region processes where the rack controller is
        # not connected.
        region_processes = []
        region_process_endpoints = []
        for _ in range(4):
            process = yield deferToDatabase(
                self.create_region_controller_process, {
                    "region": region,
                })
            region_processes.append(process)
            endpoint = yield deferToDatabase(
                self.create_region_controller_process_endpoint, {
                    "process": process,
                })
            region_process_endpoints.append(endpoint)

        # Now create the trigger so that it is actually ran.
        yield deferToDatabase(register_system_triggers)

        # Create a new connection between the rack controller and the first
        # un-used region process. The managing rack controller should not
        # change because the rack controller is not connected to at least
        # half of the region processes.
        yield deferToDatabase(self.create_region_rack_rpc_connection, {
            "endpoint": region_process_endpoints[0],
            "rack_controller": rack_controller,
        })
        rack_controller = yield deferToDatabase(
            self.reload_object, rack_controller)
        self.assertEqual(
            overloaded_region_process.id,
            rack_controller.managing_process_id)


class TestCoreRegionRackRPCConnectionDeleteListener(
        MAASTransactionServerTestCase, TransactionalHelpersMixin):
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
                    "maasserver_regionrackrpcconnection")

        yield deferToDatabase(drop_sys_core_rpc_insert_trigger)

        # Create a region process that is managing for a rack controller.
        region = yield deferToDatabase(self.create_region_controller)
        region_process = yield deferToDatabase(
            self.create_region_controller_process, {
                "region": region,
            })
        region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint, {
                "process": region_process,
            })
        rack_controller = yield deferToDatabase(
            self.create_rack_controller, {
                "managing_process": region_process
            })
        connection = yield deferToDatabase(
            self.create_region_rack_rpc_connection, {
                "endpoint": region_process_endpoint,
                "rack_controller": rack_controller,
            })

        # Create another process that has a connection to the rack controller.
        other_region = yield deferToDatabase(self.create_region_controller)
        other_region_process = yield deferToDatabase(
            self.create_region_controller_process, {
                "region": other_region,
            })
        other_region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint, {
                "process": other_region_process,
            })
        yield deferToDatabase(
            self.create_region_rack_rpc_connection, {
                "endpoint": other_region_process_endpoint,
                "rack_controller": rack_controller,
            })

        # Now create the trigger so that it is actually ran.
        yield deferToDatabase(register_system_triggers)

        # Catch that unwatch is called on the region process and
        # watch is called on the other region process.
        listener = self.make_listener_without_delay()
        process_dv = DeferredValue()
        listener.register(
            "sys_core_%s" % region_process.id,
            lambda *args: process_dv.set(args))
        other_process_dv = DeferredValue()
        listener.register(
            "sys_core_%s" % other_region_process.id,
            lambda *args: other_process_dv.set(args))
        yield listener.startService()
        try:
            # Remove the connection on the region process causing it to
            # set the other region process as the manager.
            yield deferToDatabase(
                self.delete_region_rack_rpc_connection, connection.id)
            yield process_dv.get(timeout=2)
            yield other_process_dv.get(timeout=2)
            self.assertEqual((
                "sys_core_%s" % region_process.id,
                "unwatch_%s" % rack_controller.id),
                process_dv.value)
            self.assertEqual((
                "sys_core_%s" % other_region_process.id,
                "watch_%s" % rack_controller.id),
                other_process_dv.value)
            rack_controller = yield deferToDatabase(
                self.reload_object, rack_controller)
            self.assertEqual(
                other_region_process.id,
                rack_controller.managing_process_id)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_clears_region_process_when_no_connections(self):
        # Create a region process that is managing for a rack controller.
        region = yield deferToDatabase(self.create_region_controller)
        region_process = yield deferToDatabase(
            self.create_region_controller_process, {
                "region": region,
            })
        region_process_endpoint = yield deferToDatabase(
            self.create_region_controller_process_endpoint, {
                "process": region_process,
            })
        rack_controller = yield deferToDatabase(
            self.create_rack_controller, {
                "managing_process": region_process
            })
        connection = yield deferToDatabase(
            self.create_region_rack_rpc_connection, {
                "endpoint": region_process_endpoint,
                "rack_controller": rack_controller,
            })

        # Now create the trigger so that it is actually ran.
        yield deferToDatabase(register_system_triggers)

        # Catch that unwatch is called on the region process and
        # watch is called on the other region process.
        listener = self.make_listener_without_delay()
        process_dv = DeferredValue()
        listener.register(
            "sys_core_%s" % region_process.id,
            lambda *args: process_dv.set(args))
        yield listener.startService()
        try:
            # Remove the connection on the region process causing it to
            # notify unwatch and remove the managing process.
            yield deferToDatabase(
                self.delete_region_rack_rpc_connection, connection.id)
            yield process_dv.get(timeout=2)
            self.assertEqual((
                "sys_core_%s" % region_process.id,
                "unwatch_%s" % rack_controller.id),
                process_dv.value)
            rack_controller = yield deferToDatabase(
                self.reload_object, rack_controller)
            self.assertIsNone(rack_controller.managing_process_id)
        finally:
            yield listener.stopService()


class TestDHCPVLANListener(
        MAASTransactionServerTestCase, TransactionalHelpersMixin):
    """End-to-end test for the DHCP triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_primary_when_turned_on(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan)

        primary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_vlan, vlan.id, {
                "dhcp_on": True,
                "primary_rack": primary_rack,
            })
            yield primary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_primary_and_secondary_when_turned_on(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan)

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_vlan, vlan.id, {
                "dhcp_on": True,
                "primary_rack": primary_rack,
                "secondary_rack": secondary_rack,
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_both_when_secondary_set(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
        })

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_vlan, vlan.id, {
                "secondary_rack": secondary_rack,
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_both_when_secondary_cleared(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        old_secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": old_secondary_rack,
        })

        primary_dv = DeferredValue()
        old_secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % old_secondary_rack.id,
            lambda *args: old_secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_vlan, vlan.id, {
                "secondary_rack": None,
            })
            yield primary_dv.get(timeout=2)
            yield old_secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_old_primary_when_turned_off(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
        })

        primary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_vlan, vlan.id, {
                "dhcp_on": False,
                "primary_rack": None,
            })
            yield primary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_primary_and_secondary_when_turned_off(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_vlan, vlan.id, {
                "dhcp_on": False,
                "primary_rack": None,
                "secondary_rack": None,
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_old_and_new_primary_when_changed(self):
        yield deferToDatabase(register_system_triggers)
        old_primary_rack = yield deferToDatabase(self.create_rack_controller)
        new_primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": old_primary_rack,
        })

        old_primary_dv = DeferredValue()
        new_primary_rack_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % old_primary_rack.id,
            lambda *args: old_primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % new_primary_rack.id,
            lambda *args: new_primary_rack_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_vlan, vlan.id, {
                "primary_rack": new_primary_rack,
            })
            yield old_primary_dv.get(timeout=2)
            yield new_primary_rack_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_old_and_new_secondary_when_changed(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        old_secondary_rack = yield deferToDatabase(self.create_rack_controller)
        new_secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": old_secondary_rack,
        })

        primary_dv = DeferredValue()
        old_secondary_dv = DeferredValue()
        new_secondary_rack_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % old_secondary_rack.id,
            lambda *args: old_secondary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % new_secondary_rack.id,
            lambda *args: new_secondary_rack_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_vlan, vlan.id, {
                "secondary_rack": new_secondary_rack,
            })
            yield primary_dv.get(timeout=2)
            yield old_secondary_dv.get(timeout=2)
            yield new_secondary_rack_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_old_and_new_pimary_and_secondary(self):
        yield deferToDatabase(register_system_triggers)
        old_primary_rack = yield deferToDatabase(self.create_rack_controller)
        new_primary_rack = yield deferToDatabase(self.create_rack_controller)
        old_secondary_rack = yield deferToDatabase(self.create_rack_controller)
        new_secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": old_primary_rack,
            "secondary_rack": old_secondary_rack,
        })

        old_primary_dv = DeferredValue()
        new_primary_rack_dv = DeferredValue()
        old_secondary_dv = DeferredValue()
        new_secondary_rack_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % old_primary_rack.id,
            lambda *args: old_primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % new_primary_rack.id,
            lambda *args: new_primary_rack_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % old_secondary_rack.id,
            lambda *args: old_secondary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % new_secondary_rack.id,
            lambda *args: new_secondary_rack_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_vlan, vlan.id, {
                "primary_rack": new_primary_rack,
                "secondary_rack": new_secondary_rack,
            })
            yield old_primary_dv.get(timeout=2)
            yield new_primary_rack_dv.get(timeout=2)
            yield old_secondary_dv.get(timeout=2)
            yield new_secondary_rack_dv.get(timeout=2)
        finally:
            yield listener.stopService()


class TestDHCPSubnetListener(
        MAASTransactionServerTestCase, TransactionalHelpersMixin):
    """End-to-end test for the DHCP triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_old_vlan_and_new_vlan(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack_1 = yield deferToDatabase(self.create_rack_controller)
        secondary_rack_1 = yield deferToDatabase(self.create_rack_controller)
        vlan_1 = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack_1,
            "secondary_rack": secondary_rack_1,
        })
        primary_rack_2 = yield deferToDatabase(self.create_rack_controller)
        secondary_rack_2 = yield deferToDatabase(self.create_rack_controller)
        vlan_2 = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack_2,
            "secondary_rack": secondary_rack_2,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan_1,
        })

        listener = self.make_listener_without_delay()
        primary_dv_1 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack_1.id,
            lambda *args: primary_dv_1.set(args))
        secondary_dv_1 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack_1.id,
            lambda *args: secondary_dv_1.set(args))
        primary_dv_2 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack_2.id,
            lambda *args: primary_dv_2.set(args))
        secondary_dv_2 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack_2.id,
            lambda *args: secondary_dv_2.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_subnet, subnet.id, {
                "vlan": vlan_2,
            })
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            network = factory.make_ip4_or_6_network()
            gateway_ip = yield deferToDatabase(
                factory.pick_ip_in_network, network)
            yield deferToDatabase(self.update_subnet, subnet.id, {
                "cidr": str(network.cidr),
                "gateway_ip": gateway_ip,
            })
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            gateway_ip = yield deferToDatabase(
                factory.pick_ip_in_network, subnet.get_ipnetwork(),
                but_not=[subnet.gateway_ip])
            yield deferToDatabase(self.update_subnet, subnet.id, {
                "gateway_ip": gateway_ip,
            })
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        # Make sure its empty. This test that it handles being set.
        yield deferToDatabase(self.update_subnet, subnet.id, {
            "gateway_ip": None,
        })

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            gateway_ip = yield deferToDatabase(
                factory.pick_ip_in_network, subnet.get_ipnetwork())
            yield deferToDatabase(self.update_subnet, subnet.id, {
                "gateway_ip": gateway_ip,
            })
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_subnet, subnet.id, {
                "gateway_ip": None,
            })
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            dns_server = yield deferToDatabase(
                factory.pick_ip_in_network, subnet.get_ipnetwork(),
                but_not=subnet.dns_servers)
            yield deferToDatabase(self.update_subnet, subnet.id, {
                "dns_servers": [dns_server],
            })
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        # Make sure its empty. This test that it handles being set.
        yield deferToDatabase(self.update_subnet, subnet.id, {
            "dns_servers": [],
        })

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            dns_server = yield deferToDatabase(
                factory.pick_ip_in_network, subnet.get_ipnetwork(),
                but_not=subnet.dns_servers)
            yield deferToDatabase(self.update_subnet, subnet.id, {
                "dns_servers": [dns_server],
            })
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        dns_server = yield deferToDatabase(
            factory.pick_ip_in_network, subnet.get_ipnetwork(),
            but_not=subnet.dns_servers)
        yield deferToDatabase(self.update_subnet, subnet.id, {
            "dns_servers": [dns_server],
        })

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_subnet, subnet.id, {
                "dns_servers": [],
            })
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })

        primary_dv = DeferredValue()
        secondary_dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_subnet, subnet.id)
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()


class TestDHCPIPRangeListener(
        MAASTransactionServerTestCase, TransactionalHelpersMixin):
    """End-to-end test for the DHCP triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_new_managed_dhcp_range(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        network = factory.make_ipv4_network()
        subnet = yield deferToDatabase(self.create_subnet, {
            "cidr": str(network.cidr),
            "vlan": vlan,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            network = subnet.get_ipnetwork()
            start_ip = str(IPAddress(network.first + 2))
            end_ip = str(IPAddress(network.first + 3))
            yield deferToDatabase(self.create_iprange, {
                "subnet": subnet,
                "type": IPRANGE_TYPE.DYNAMIC,
                "start_ip": start_ip,
                "end_ip": end_ip,
            })
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        network = factory.make_ipv4_network()
        subnet = yield deferToDatabase(self.create_subnet, {
            "cidr": str(network.cidr),
            "vlan": vlan,
        })
        network = subnet.get_ipnetwork()
        start_ip = str(IPAddress(network.first + 2))
        end_ip = str(IPAddress(network.first + 3))
        ip_range = yield deferToDatabase(self.create_iprange, {
            "subnet": subnet,
            "type": IPRANGE_TYPE.DYNAMIC,
            "start_ip": start_ip,
            "end_ip": end_ip,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            end_ip = str(IPAddress(network.first + 4))
            yield deferToDatabase(self.update_iprange, ip_range.id, {
                "end_ip": end_ip,
            })
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        network = factory.make_ipv4_network()
        subnet = yield deferToDatabase(self.create_subnet, {
            "cidr": str(network.cidr),
            "vlan": vlan,
        })
        network = subnet.get_ipnetwork()
        start_ip = str(IPAddress(network.first + 2))
        end_ip = str(IPAddress(network.first + 3))
        ip_range = yield deferToDatabase(self.create_iprange, {
            "subnet": subnet,
            "type": IPRANGE_TYPE.DYNAMIC,
            "start_ip": start_ip,
            "end_ip": end_ip,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_iprange, ip_range.id, {
                "type": IPRANGE_TYPE.RESERVED,
            })
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        network = factory.make_ipv4_network()
        subnet = yield deferToDatabase(self.create_subnet, {
            "cidr": str(network.cidr),
            "vlan": vlan,
        })
        network = subnet.get_ipnetwork()
        start_ip = str(IPAddress(network.first + 2))
        end_ip = str(IPAddress(network.first + 3))
        ip_range = yield deferToDatabase(self.create_iprange, {
            "subnet": subnet,
            "type": IPRANGE_TYPE.RESERVED,
            "start_ip": start_ip,
            "end_ip": end_ip,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_iprange, ip_range.id, {
                "type": IPRANGE_TYPE.DYNAMIC,
            })
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        network = factory.make_ipv4_network()
        subnet = yield deferToDatabase(self.create_subnet, {
            "cidr": str(network.cidr),
            "vlan": vlan,
        })
        network = subnet.get_ipnetwork()
        start_ip = str(IPAddress(network.first + 2))
        end_ip = str(IPAddress(network.first + 3))
        ip_range = yield deferToDatabase(self.create_iprange, {
            "subnet": subnet,
            "type": IPRANGE_TYPE.DYNAMIC,
            "start_ip": start_ip,
            "end_ip": end_ip,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_iprange, ip_range.id)
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()


class TestDHCPStaticIPAddressListener(
        MAASTransactionServerTestCase, TransactionalHelpersMixin):
    """End-to-end test for the DHCP triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_new_staticipaddress(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        user = yield deferToDatabase(self.create_user)

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_staticipaddress, {
                "subnet": subnet,
                "alloc_type": IPADDRESS_TYPE.USER_RESERVED,
                "user": user,
            })
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
        vlan_1 = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack_1,
            "secondary_rack": secondary_rack_1,
        })
        subnet_1 = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan_1,
        })
        primary_rack_2 = yield deferToDatabase(self.create_rack_controller)
        secondary_rack_2 = yield deferToDatabase(self.create_rack_controller)
        vlan_2 = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack_2,
            "secondary_rack": secondary_rack_2,
        })
        subnet_2 = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan_2,
        })
        user = yield deferToDatabase(self.create_user)
        staticip = yield deferToDatabase(self.create_staticipaddress, {
            "subnet": subnet_1,
            "alloc_type": IPADDRESS_TYPE.USER_RESERVED,
            "user": user,
        })

        listener = self.make_listener_without_delay()
        primary_dv_1 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack_1.id,
            lambda *args: primary_dv_1.set(args))
        secondary_dv_1 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack_1.id,
            lambda *args: secondary_dv_1.set(args))
        primary_dv_2 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack_2.id,
            lambda *args: primary_dv_2.set(args))
        secondary_dv_2 = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack_2.id,
            lambda *args: secondary_dv_2.set(args))
        yield listener.startService()
        try:
            ip = yield deferToDatabase(factory.pick_ip_in_Subnet, subnet_2)
            yield deferToDatabase(self.update_staticipaddress, staticip.id, {
                "subnet": subnet_2,
                "ip": ip,
            })
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet_1 = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        subnet_2 = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        user = yield deferToDatabase(self.create_user)
        staticip = yield deferToDatabase(self.create_staticipaddress, {
            "subnet": subnet_1,
            "alloc_type": IPADDRESS_TYPE.USER_RESERVED,
            "user": user,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            ip = yield deferToDatabase(factory.pick_ip_in_Subnet, subnet_2)
            yield deferToDatabase(self.update_staticipaddress, staticip.id, {
                "subnet": subnet_2,
                "ip": ip,
            })
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(self.create_interface, {
            "node": node,
            "vlan": vlan,
        })
        staticip = yield deferToDatabase(self.create_staticipaddress, {
            "subnet": subnet,
            "alloc_type": IPADDRESS_TYPE.AUTO,
            "interface": interface,
            "ip": "",
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            ip = yield deferToDatabase(factory.pick_ip_in_Subnet, subnet)
            yield deferToDatabase(self.update_staticipaddress, staticip.id, {
                "ip": ip,
            })
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(self.create_interface, {
            "node": node,
            "vlan": vlan,
        })
        staticip = yield deferToDatabase(self.create_staticipaddress, {
            "subnet": subnet,
            "alloc_type": IPADDRESS_TYPE.AUTO,
            "interface": interface,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_staticipaddress, staticip.id, {
                "ip": "",
            })
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(self.create_interface, {
            "node": node,
            "vlan": vlan,
        })
        staticip = yield deferToDatabase(self.create_staticipaddress, {
            "subnet": subnet,
            "alloc_type": IPADDRESS_TYPE.AUTO,
            "interface": interface,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            ip = yield deferToDatabase(
                factory.pick_ip_in_Subnet, subnet, but_not=[staticip.ip])
            yield deferToDatabase(self.update_staticipaddress, staticip.id, {
                "ip": ip,
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_delet_an_ip(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(self.create_interface, {
            "node": node,
            "vlan": vlan,
        })
        staticip = yield deferToDatabase(self.create_staticipaddress, {
            "subnet": subnet,
            "alloc_type": IPADDRESS_TYPE.AUTO,
            "interface": interface,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            ip = yield deferToDatabase(
                factory.pick_ip_in_Subnet, subnet, but_not=[staticip.ip])
            yield deferToDatabase(self.update_staticipaddress, staticip.id, {
                "ip": ip,
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()


class TestDHCPInterfaceListener(
        MAASTransactionServerTestCase, TransactionalHelpersMixin):
    """End-to-end test for the DHCP triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_interface_name_change(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(self.create_interface, {
            "node": node,
            "vlan": vlan,
        })
        yield deferToDatabase(self.create_staticipaddress, {
            "subnet": subnet,
            "alloc_type": IPADDRESS_TYPE.AUTO,
            "interface": interface,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_interface, interface.id, {
                "name": factory.make_name("eth"),
            })
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(self.create_interface, {
            "node": node,
            "vlan": vlan,
        })
        yield deferToDatabase(self.create_staticipaddress, {
            "subnet": subnet,
            "alloc_type": IPADDRESS_TYPE.AUTO,
            "interface": interface,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_interface, interface.id, {
                "mac_address": factory.make_mac_address(),
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()


class TestDHCPNodeListener(
        MAASTransactionServerTestCase, TransactionalHelpersMixin):
    """End-to-end test for the DHCP triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_hostname_change(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        secondary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
            "secondary_rack": secondary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        node = yield deferToDatabase(self.create_node)
        interface = yield deferToDatabase(self.create_interface, {
            "node": node,
            "vlan": vlan,
        })
        yield deferToDatabase(self.create_staticipaddress, {
            "subnet": subnet,
            "alloc_type": IPADDRESS_TYPE.AUTO,
            "interface": interface,
        })

        listener = self.make_listener_without_delay()
        primary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: primary_dv.set(args))
        secondary_dv = DeferredValue()
        listener.register(
            "sys_dhcp_%s" % secondary_rack.id,
            lambda *args: secondary_dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_node, node.system_id, {
                "hostname": factory.make_name("host"),
            })
            yield primary_dv.get(timeout=2)
            yield secondary_dv.get(timeout=2)
        finally:
            yield listener.stopService()


class TestDHCPSnippetListener(
        MAASTransactionServerTestCase, TransactionalHelpersMixin):
    """End-to-end test for the DHCP triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_global_dhcp_snippet_inserted(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
        })
        yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_dhcp_snippet, {
                "enabled": True,
            })
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_no_message_for_global_dhcp_snippet_inserted_when_disabled(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
        })
        yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_dhcp_snippet, {
                "enabled": False,
            })
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_dhcp_snippet, {
                "enabled": True,
                "subnet": subnet,
            })
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dhcp_snippet_inserted_with_node(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
        })
        yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        node = yield deferToDatabase(self.create_node)
        yield deferToDatabase(self.create_interface, {
            "node": node,
            "vlan": vlan,
        })
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_dhcp_snippet, {
                "enabled": True,
                "node": node,
            })
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dhcp_snippet_updated_value(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
        })
        yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        dhcp_snippet = yield deferToDatabase(self.create_dhcp_snippet, {
            "enabled": True,
        })
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: dv.set(args))
        yield listener.startService()
        try:
            new_value = yield deferToDatabase(
                dhcp_snippet.value.update, factory.make_string())
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
        })
        yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        dhcp_snippet = yield deferToDatabase(self.create_dhcp_snippet, {
            "enabled": False,
        })
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: dv.set(args))
        yield listener.startService()
        try:
            new_value = yield deferToDatabase(
                dhcp_snippet.value.update, factory.make_string())
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
        })
        yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        dhcp_snippet = yield deferToDatabase(self.create_dhcp_snippet, {
            "enabled": False,
        })
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_dhcp_snippet, dhcp_snippet.id, {
                "enabled": True,
            })
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dhcp_snippet_updated_description(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
        })
        yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        dhcp_snippet = yield deferToDatabase(self.create_dhcp_snippet, {
            "enabled": True,
        })
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_dhcp_snippet, dhcp_snippet.id, {
                "description": factory.make_string(),
            })
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dhcp_snippet_updated_subnet(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        dhcp_snippet = yield deferToDatabase(self.create_dhcp_snippet, {
            "enabled": True,
        })
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_dhcp_snippet, dhcp_snippet.id, {
                "subnet": subnet,
            })
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dhcp_snippet_updated_node(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
        })
        yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        node = yield deferToDatabase(self.create_node)
        yield deferToDatabase(self.create_interface, {
            "vlan": vlan,
            "node": node,
        })
        dhcp_snippet = yield deferToDatabase(self.create_dhcp_snippet, {
            "enabled": True,
        })
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_dhcp_snippet, dhcp_snippet.id, {
                "node": node,
            })
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_global_dhcp_snippet_deleted(self):
        yield deferToDatabase(register_system_triggers)
        primary_rack = yield deferToDatabase(self.create_rack_controller)
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
        })
        yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        dhcp_snippet = yield deferToDatabase(self.create_dhcp_snippet, {
            "enabled": True,
        })
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: dv.set(args))
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
        })
        yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        dhcp_snippet = yield deferToDatabase(self.create_dhcp_snippet, {
            "enabled": False,
        })
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: dv.set(args))
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
        })
        subnet = yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        dhcp_snippet = yield deferToDatabase(self.create_dhcp_snippet, {
            "enabled": True,
            "subnet": subnet,
        })
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: dv.set(args))
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
        vlan = yield deferToDatabase(self.create_vlan, {
            "dhcp_on": True,
            "primary_rack": primary_rack,
        })
        yield deferToDatabase(self.create_subnet, {
            "vlan": vlan,
        })
        node = yield deferToDatabase(self.create_node)
        yield deferToDatabase(self.create_interface, {
            "vlan": vlan,
            "node": node,
        })
        dhcp_snippet = yield deferToDatabase(self.create_dhcp_snippet, {
            "enabled": True,
            "node": node,
        })
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dhcp_%s" % primary_rack.id,
            lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_dhcp_snippet, dhcp_snippet.id)
            yield dv.get(timeout=2)
        finally:
            yield listener.stopService()


class TestDNSDomainListener(
        MAASTransactionServerTestCase, TransactionalHelpersMixin,
        DNSHelpersMixin):
    """End-to-end test for the DNS triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_domain_insert(self):
        yield deferToDatabase(register_system_triggers)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_domain)
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_domain_update(self):
        yield deferToDatabase(register_system_triggers)
        domain = yield deferToDatabase(self.create_domain)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_domain, domain.id, {
                "name": factory.make_name("domain"),
            })
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_domain_delete(self):
        yield deferToDatabase(register_system_triggers)
        domain = yield deferToDatabase(self.create_domain)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_domain, domain.id)
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()


class TestDNSStaticIPAddressListener(
        MAASTransactionServerTestCase, TransactionalHelpersMixin,
        DNSHelpersMixin):
    """End-to-end test for the DNS triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_staticipaddress_update(self):
        yield deferToDatabase(register_system_triggers)
        sip = yield deferToDatabase(self.create_staticipaddress)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_staticipaddress, sip.id, {
                "alloc_type": IPADDRESS_TYPE.STICKY,
            })
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()


class TestDNSInterfaceStaticIPAddressListener(
        MAASTransactionServerTestCase, TransactionalHelpersMixin,
        DNSHelpersMixin):
    """End-to-end test for the DNS triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_interface_staticipaddress_link(self):
        yield deferToDatabase(register_system_triggers)
        interface = yield deferToDatabase(self.create_interface)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_staticipaddress, {
                "interface": interface,
            })
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_interface_staticipaddress_unlink(self):
        yield deferToDatabase(register_system_triggers)
        interface = yield deferToDatabase(self.create_interface)
        sip = yield deferToDatabase(self.create_staticipaddress, {
            "interface": interface,
        })
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_staticipaddress, sip.id)
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()


class TestDNSDNSResourceListener(
        MAASTransactionServerTestCase, TransactionalHelpersMixin,
        DNSHelpersMixin):
    """End-to-end test for the DNS triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dnsresource_insert(self):
        yield deferToDatabase(register_system_triggers)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_dnsresource)
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dnsresource_update(self):
        yield deferToDatabase(register_system_triggers)
        resource = yield deferToDatabase(self.create_dnsresource)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_dnsresource, resource.id, {
                "name": factory.make_name("resource"),
            })
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dnsresource_delete(self):
        yield deferToDatabase(register_system_triggers)
        resource = yield deferToDatabase(self.create_dnsresource)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_dnsresource, resource.id)
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()


class TestDNSDNSResourceStaticIPAddressListener(
        MAASTransactionServerTestCase, TransactionalHelpersMixin,
        DNSHelpersMixin):
    """End-to-end test for the DNS triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dnsresource_staticipaddress_link(self):
        yield deferToDatabase(register_system_triggers)
        resource = yield deferToDatabase(self.create_dnsresource)
        sip = yield deferToDatabase(self.create_staticipaddress)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(resource.ip_addresses.add, sip)
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dnsresource_staticipaddress_unlink(self):
        yield deferToDatabase(register_system_triggers)
        resource = yield deferToDatabase(self.create_dnsresource)
        sip = yield deferToDatabase(self.create_staticipaddress)
        yield deferToDatabase(resource.ip_addresses.add, sip)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(resource.ip_addresses.remove, sip)
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()


class TestDNSDNSDataListener(
        MAASTransactionServerTestCase, TransactionalHelpersMixin,
        DNSHelpersMixin):
    """End-to-end test for the DNS triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dnsdata_insert(self):
        yield deferToDatabase(register_system_triggers)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_dnsdata)
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dnsdata_update(self):
        yield deferToDatabase(register_system_triggers)
        data = yield deferToDatabase(self.create_dnsdata, {
            "rrtype": "TXT",
            "rrdata": factory.make_name("txt"),
        })
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_dnsdata, data.id, {
                "rrdata": factory.make_name("txt"),
            })
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_dnsdata_delete(self):
        yield deferToDatabase(register_system_triggers)
        data = yield deferToDatabase(self.create_dnsdata)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_dnsdata, data.id)
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()


class TestDNSSubnetListener(
        MAASTransactionServerTestCase, TransactionalHelpersMixin,
        DNSHelpersMixin):
    """End-to-end test for the DNS triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_subnet_insert(self):
        yield deferToDatabase(register_system_triggers)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.create_subnet)
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_subnet_cidr_update(self):
        yield deferToDatabase(register_system_triggers)
        subnet = yield deferToDatabase(self.create_subnet)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            network = factory.make_ip4_or_6_network()
            yield deferToDatabase(self.update_subnet, subnet.id, {
                "cidr": str(network.cidr),
                "gateway_ip": factory.pick_ip_in_network(network),
                "dns_servers": [],
            })
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_subnet_rdns_mode_update(self):
        yield deferToDatabase(register_system_triggers)
        subnet = yield deferToDatabase(self.create_subnet)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_subnet, subnet.id, {
                "rdns_mode": factory.pick_enum(
                    RDNS_MODE, but_not=[subnet.rdns_mode]),
            })
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_subnet_delete(self):
        yield deferToDatabase(register_system_triggers)
        subnet = yield deferToDatabase(self.create_subnet)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_subnet, subnet.id)
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()


class TestDNSNodeListener(
        MAASTransactionServerTestCase, TransactionalHelpersMixin,
        DNSHelpersMixin):
    """End-to-end test for the DNS triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_node_update_hostname(self):
        yield deferToDatabase(register_system_triggers)
        node = yield deferToDatabase(self.create_node)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_node, node.system_id, {
                "hostname": factory.make_name("hostname"),
            })
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_node_update_domain(self):
        yield deferToDatabase(register_system_triggers)
        node = yield deferToDatabase(self.create_node)
        domain = yield deferToDatabase(self.create_domain)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_node, node.system_id, {
                "domain": domain,
            })
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_node_delete(self):
        yield deferToDatabase(register_system_triggers)
        node = yield deferToDatabase(self.create_node)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.delete_node, node.system_id)
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()


class TestDNSInterfaceListener(
        MAASTransactionServerTestCase, TransactionalHelpersMixin,
        DNSHelpersMixin):
    """End-to-end test for the DNS triggers code."""

    @transactional
    def migrate_unknown_to_physical(self, id, node):
        nic = Interface.objects.get(id=id)
        nic.type = INTERFACE_TYPE.PHYSICAL
        nic.node = node
        nic.__class__ = PhysicalInterface
        nic.save()

    @transactional
    def migrate_physical_to_unknown(self, id):
        nic = Interface.objects.get(id=id)
        nic.type = INTERFACE_TYPE.UNKNOWN
        nic.node = None
        nic.__class__ = UnknownInterface
        nic.save()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_interface_update_name(self):
        yield deferToDatabase(register_system_triggers)
        interface = yield deferToDatabase(self.create_interface)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.update_interface, interface.id, {
                "name": factory.make_name("name"),
            })
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_unknown_to_physical(self):
        yield deferToDatabase(register_system_triggers)
        interface = yield deferToDatabase(self.create_unknown_interface)
        node = yield deferToDatabase(self.create_node)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.migrate_unknown_to_physical, interface.id, node)
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_physical_to_unknown(self):
        yield deferToDatabase(register_system_triggers)
        interface = yield deferToDatabase(self.create_interface)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.migrate_physical_to_unknown, interface.id)
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_interface_changing_to_new_node(self):
        yield deferToDatabase(register_system_triggers)
        interface = yield deferToDatabase(self.create_interface)
        node = yield deferToDatabase(self.create_node)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                self.update_interface, interface.id, {"node": node})
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()


class TestDNSConfigListener(
        MAASTransactionServerTestCase, TransactionalHelpersMixin,
        DNSHelpersMixin):
    """End-to-end test for the DNS triggers code."""

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_upstream_dns_insert(self):
        yield deferToDatabase(register_system_triggers)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                Config.objects.set_config,
                "upstream_dns", factory.make_ip_address())
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_default_dns_ttl_insert(self):
        yield deferToDatabase(register_system_triggers)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                Config.objects.set_config,
                "default_dns_ttl", random.randint(10, 1000))
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_windows_kms_host_insert(self):
        yield deferToDatabase(register_system_triggers)
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                Config.objects.set_config,
                "windows_kms_host", factory.make_name("kms"))
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_upstream_dns_update(self):
        yield deferToDatabase(register_system_triggers)
        yield deferToDatabase(
            Config.objects.set_config,
            "upstream_dns", factory.make_ip_address())
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                Config.objects.set_config,
                "upstream_dns", factory.make_ip_address())
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_default_dns_ttl_update(self):
        yield deferToDatabase(register_system_triggers)
        yield deferToDatabase(
            Config.objects.set_config,
            "default_dns_ttl", random.randint(10, 1000))
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                Config.objects.set_config,
                "default_dns_ttl", random.randint(10, 1000))
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_message_for_config_windows_kms_host_update(self):
        yield deferToDatabase(register_system_triggers)
        yield deferToDatabase(
            Config.objects.set_config,
            "windows_kms_host", factory.make_name("kms"))
        zone_serial = yield self.get_zone_serial_current()
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register(
            "sys_dns", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(
                Config.objects.set_config,
                "windows_kms_host", factory.make_name("kms"))
            yield dv.get(timeout=2)
            yield self.assertZoneSerialIncrement(zone_serial)
        finally:
            yield listener.stopService()
