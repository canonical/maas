# Copyright 2022-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock, PropertyMock

from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import Clock

from maastesting import get_testing_timeout
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.rpc import connectionpool as connectionpoolModule
from provisioningserver.rpc.connectionpool import ConnectionPool

TIMEOUT = get_testing_timeout()


class TestConnectionPool(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_setitem_sets_item_in_connections(self):
        cp = ConnectionPool(Clock(), Mock())
        key = Mock()
        val = Mock()
        cp[key] = val
        self.assertEqual(cp.connections, {key: val})

    def test_getitem_gets_item_in_connections(self):
        cp = ConnectionPool(Clock(), Mock())
        key = Mock()
        val = Mock()
        cp[key] = val
        self.assertEqual(cp.connections[key], cp[key])

    def test_len_gets_length_of_connections(self):
        cp = ConnectionPool(Clock(), Mock())
        key = Mock()
        val = Mock()
        cp[key] = [val]
        self.assertEqual(len(cp), len(cp.get_all_connections()))

    def test_delitem_removes_item_from_connections(self):
        cp = ConnectionPool(Clock(), Mock())
        key = Mock()
        val = Mock()
        cp[key] = val
        self.assertEqual(cp.connections[key], val)
        del cp[key]
        self.assertIsNone(cp.connections.get(key))

    def test_contains_returns_if_key_in_connections(self):
        cp = ConnectionPool(Clock(), Mock())
        key = Mock()
        val = Mock()
        cp[key] = val
        self.assertEqual(key in cp, key in cp.connections)

    def test_compare_ConnectionPool_equal_to_compare_connections(self):
        cp = ConnectionPool(Clock(), Mock())
        self.assertEqual(cp, cp.connections)
        self.assertEqual(cp, {})

    def test_is_staged(self):
        cp = ConnectionPool(Clock(), Mock())
        eventloop1 = Mock()
        eventloop2 = Mock()
        cp.try_connections[eventloop1] = Mock()
        self.assertTrue(cp.is_staged(eventloop1))
        self.assertFalse(cp.is_staged(eventloop2))

    def test_get_staged_connection(self):
        cp = ConnectionPool(Clock(), Mock())
        eventloop = Mock()
        connection = Mock()
        cp.try_connections[eventloop] = connection
        self.assertEqual(cp.get_staged_connection(eventloop), connection)

    def test_get_staged_connections(self):
        cp = ConnectionPool(Clock(), Mock())
        eventloop = Mock()
        connection = Mock()
        cp.try_connections[eventloop] = connection
        self.assertEqual(cp.get_staged_connections(), {eventloop: connection})

    def test_get_connection(self):
        cp = ConnectionPool(Clock(), Mock())
        eventloops = [Mock() for _ in range(3)]
        cp.connections = {
            eventloop: [Mock() for _ in range(2)] for eventloop in eventloops
        }
        self.assertIn(cp.get_connection(eventloops[0]), cp[eventloops[0]])

    def test_get_random_connection(self):
        cp = ConnectionPool(Clock(), Mock())
        eventloops = [Mock() for _ in range(3)]
        cp.connections = {
            eventloop: [Mock() for _ in range(2)] for eventloop in eventloops
        }
        self.assertIn(
            cp.get_connection(eventloops[0]),
            [conn for conn_list in cp.values() for conn in conn_list],
        )

    def test_get_all_connections(self):
        cp = ConnectionPool(Clock(), Mock())
        eventloops = [Mock() for _ in range(3)]
        cp.connections = {
            eventloops[0]: [Mock()],
            eventloops[1]: [Mock()],
            eventloops[2]: [Mock()],
        }

        self.assertCountEqual(
            cp.get_all_connections(),
            [conn for conn_list in cp.values() for conn in conn_list],
        )

    @inlineCallbacks
    def test_connect(self):
        clock = Clock()
        connection = Mock()
        service = Mock()
        cp = ConnectionPool(clock, service)
        connectProtocol = self.patch(connectionpoolModule, "connectProtocol")
        connectProtocol.return_value = connection
        result = yield cp.connect("an-event-loop", ("a.example.com", 1111))
        self.assertEqual(len(connectProtocol.call_args_list), 1)
        connectProtocol.assert_called_once()
        args = connectProtocol.call_args.args
        self.assertEqual(args[0]._host, "a.example.com")
        self.assertEqual(args[0]._port, 1111)
        self.assertEqual(args[1].address, ("a.example.com", 1111))
        self.assertEqual(args[1].eventloop, "an-event-loop")
        self.assertEqual(args[1].service, service)
        self.assertEqual(result, connection)

    def test_drop_connection(self):
        connection = Mock()
        cp = ConnectionPool(Clock(), Mock())
        cp.disconnect(connection)
        connection.transport.loseConnection.assert_called_once_with()

    def test_drop_connection_if_connection_already_dropped(self):
        connection = Mock()
        type(connection).transport = PropertyMock(return_value=None)
        cp = ConnectionPool(Clock(), Mock())
        try:
            cp.disconnect(connection)
        except Exception:
            self.fail(
                "The connection was already dropped and the disconnect function raised an unexpected exception."
            )

    def test_add_connection_adds_the_staged_connection(self):
        eventloop = Mock()
        connection = Mock()
        cp = ConnectionPool(Clock(), Mock())
        cp.try_connections = {eventloop: connection}
        cp.add_connection(eventloop, connection)
        self.assertIn(connection, cp.get_all_connections())
        self.assertEqual(cp.try_connections, {})

    def test_remove_connection_removes_connection_from_pool(self):
        eventloop = Mock()
        connection = Mock()
        cp = ConnectionPool(Clock(), Mock())
        cp.connections[eventloop] = [connection]
        cp.remove_connection(eventloop, connection)
        self.assertEqual(cp.connections, {})
