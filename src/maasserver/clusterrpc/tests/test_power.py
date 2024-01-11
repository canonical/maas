# Copyright 2014-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import random
from unittest.mock import Mock

from twisted.internet import reactor
from twisted.internet.defer import fail, inlineCallbacks, succeed
from twisted.internet.task import deferLater

from maasserver.clusterrpc import power as power_module
from maasserver.clusterrpc.power import (
    pick_best_power_state,
    power_cycle,
    power_driver_check,
    power_off_node,
    power_on_node,
    power_query,
    power_query_all,
    set_boot_order,
)
from maasserver.enum import POWER_STATE
from maasserver.exceptions import PowerProblem
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for
from provisioningserver.rpc.cluster import (
    PowerCycle,
    PowerDriverCheck,
    PowerOff,
    PowerOn,
    PowerQuery,
    SetBootOrder,
)
from provisioningserver.rpc.exceptions import PowerActionAlreadyInProgress

wait_for_reactor = wait_for()


@transactional
def make_node_with_power_info():
    node = factory.make_Node()
    power_info = node.get_effective_power_info()
    return node, power_info


class TestPowerNode(MAASServerTestCase):
    """Tests for `power_on_node` and `power_off_node`."""

    scenarios = (
        ("PowerOn", {"power_func": power_on_node, "command": PowerOn}),
        ("PowerOff", {"power_func": power_off_node, "command": PowerOff}),
    )

    def test_powers_single_node(self):
        node = factory.make_Node()
        client = Mock()

        wait_for_reactor(self.power_func)(
            client,
            node.system_id,
            node.hostname,
            node.get_effective_power_info(),
        )

        power_info = node.get_effective_power_info()
        client.assert_called_once_with(
            self.command,
            system_id=node.system_id,
            hostname=node.hostname,
            power_type=power_info.power_type,
            context=power_info.power_parameters,
        )

    def test_raises_power_problem(self):
        node = factory.make_Node()
        client = Mock()
        client.return_value = fail(
            PowerActionAlreadyInProgress("Houston, we have a problem.")
        )

        with self.assertRaisesRegex(
            PowerProblem, "Houston, we have a problem."
        ):
            wait_for_reactor(self.power_func)(
                client,
                node.system_id,
                node.hostname,
                node.get_effective_power_info(),
            )


class TestPowerCycle(MAASServerTestCase):
    """Tests for `power_cycle`."""

    def test_power_cycles_single_node(self):
        node = factory.make_Node()
        client = Mock()

        wait_for_reactor(power_cycle)(
            client,
            node.system_id,
            node.hostname,
            node.get_effective_power_info(),
        )

        power_info = node.get_effective_power_info()
        client.assert_called_once_with(
            PowerCycle,
            system_id=node.system_id,
            hostname=node.hostname,
            power_type=power_info.power_type,
            context=power_info.power_parameters,
        )

    def test_raises_power_problem(self):
        node = factory.make_Node()
        client = Mock()
        client.return_value = fail(
            PowerActionAlreadyInProgress("Houston, we have a problem.")
        )

        with self.assertRaisesRegex(
            PowerProblem, "Houston, we have a problem."
        ):
            wait_for_reactor(power_cycle)(
                client,
                node.system_id,
                node.hostname,
                node.get_effective_power_info(),
            )


class TestPowerQuery(MAASServerTestCase):
    """Tests for `power_query`."""

    def test_power_querys_single_node(self):
        node = factory.make_Node()
        client = Mock()

        wait_for_reactor(power_query)(
            client,
            node.system_id,
            node.hostname,
            node.get_effective_power_info(),
        )

        power_info = node.get_effective_power_info()
        client.assert_called_once_with(
            PowerQuery,
            system_id=node.system_id,
            hostname=node.hostname,
            power_type=power_info.power_type,
            context=power_info.power_parameters,
        )


class TestPowerDriverCheck(MAASServerTestCase):
    """Tests for `power_driver_check`."""

    def test_handled(self):
        node = factory.make_Node()
        power_info = node.get_effective_power_info()
        client = Mock()

        wait_for_reactor(power_driver_check)(client, power_info.power_type)

        client.assert_called_once_with(
            PowerDriverCheck, power_type=power_info.power_type
        )


class TestPowerQueryAll(MAASTransactionServerTestCase):
    """Tests for `power_query_all`."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_PowerQuery_on_all_clients(self):
        node, power_info = yield deferToDatabase(make_node_with_power_info)

        successful_rack_ids = [
            factory.make_name("system_id") for _ in range(3)
        ]
        error_rack_ids = [factory.make_name("system_id") for _ in range(3)]
        failed_rack_ids = [factory.make_name("system_id") for _ in range(3)]
        clients = []
        power_states = []
        for rack_id in successful_rack_ids:
            power_state = random.choice([POWER_STATE.ON, POWER_STATE.OFF])
            power_states.append(power_state)
            client = Mock()
            client.ident = rack_id
            client.return_value = succeed({"state": power_state})
            clients.append(client)
        for rack_id in error_rack_ids:
            client = Mock()
            client.ident = rack_id
            client.return_value = succeed({"state": POWER_STATE.ERROR})
            clients.append(client)
        for rack_id in failed_rack_ids:
            client = Mock()
            client.ident = rack_id
            client.return_value = fail(factory.make_exception())
            clients.append(client)

        self.patch(power_module, "getAllClients").return_value = clients
        power_state, success_racks, failed_racks = yield power_query_all(
            node.system_id, node.hostname, power_info
        )

        self.assertEqual(pick_best_power_state(power_states), power_state)
        self.assertCountEqual(successful_rack_ids, success_racks)
        self.assertCountEqual(error_rack_ids + failed_rack_ids, failed_racks)

    @wait_for_reactor
    @inlineCallbacks
    def test_handles_timeout(self):
        node, power_info = yield deferToDatabase(make_node_with_power_info)

        def defer_way_later(*args, **kwargs):
            # Create a defer that will finish in 1 minute.
            return deferLater(reactor, 60 * 60, lambda: None)

        rack_id = factory.make_name("system_id")
        client = Mock()
        client.ident = rack_id
        client.side_effect = defer_way_later

        self.patch(power_module, "getAllClients").return_value = [client]
        power_state, success_racks, failed_racks = yield power_query_all(
            node.system_id, node.hostname, power_info, timeout=0.5
        )

        self.assertEqual(POWER_STATE.UNKNOWN, power_state)
        self.assertEqual(set(), success_racks)
        self.assertEqual({rack_id}, failed_racks)


class TestSetBootOrder(MAASTransactionServerTestCase):
    """Tests for `set_boot_order`."""

    @wait_for_reactor
    @inlineCallbacks
    def test_set_boot_order(self):
        client = Mock()
        node, power_info = yield deferToDatabase(make_node_with_power_info)
        order = list(range(5))

        yield set_boot_order(
            client, node.system_id, node.hostname, power_info, order
        )

        client.assert_called_once_with(
            SetBootOrder,
            system_id=node.system_id,
            hostname=node.hostname,
            power_type=power_info.power_type,
            context=power_info.power_parameters,
            order=order,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_set_boot_order_does_nothing(self):
        client = Mock()
        node, power_info = yield deferToDatabase(make_node_with_power_info)

        yield set_boot_order(
            client, node.system_id, node.hostname, power_info, []
        )

        client.assert_not_called()
