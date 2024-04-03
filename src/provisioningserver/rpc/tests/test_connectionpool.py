# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock, PropertyMock

from twisted.internet.defer import inlineCallbacks, succeed
from twisted.internet.endpoints import TCP6ClientEndpoint
from twisted.internet.task import Clock

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from maastesting.twisted import extract_result
from provisioningserver.rpc import connectionpool as connectionpoolModule
from provisioningserver.rpc import exceptions
from provisioningserver.rpc.clusterservice import ClusterClient
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

    def test__reap_extra_connection_reaps_a_non_busy_connection(self):
        cp = ConnectionPool(Clock(), Mock())
        eventloop = Mock()
        connection = Mock()
        connection.in_use = False
        cp[eventloop] = [connection]
        disconnect = self.patch(cp, "disconnect")
        cp._reap_extra_connection(eventloop, connection)
        self.assertEqual(len(cp), 0)
        disconnect.assert_called_once_with(connection)

    def test__reap_extra_connection_waits_for_a_busy_connection(self):
        clock = Clock()
        cp = ConnectionPool(clock, Mock())
        eventloop = Mock()
        connection = Mock()
        connection.in_use = True
        cp[eventloop] = [connection]
        self.patch(cp, "disconnect")
        cp._reap_extra_connection(eventloop, connection)
        self.assertIn(eventloop, clock.calls[0].args)
        self.assertIn(connection, clock.calls[0].args)
        self.assertEqual(
            "_reap_extra_connection", clock.calls[0].func.__name__
        )
        self.assertEqual(cp._keepalive, clock.calls[0].time)

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

    def test_scale_up_connections_adds_a_connection(self):
        cp = ConnectionPool(Clock(), Mock(), max_conns=2)
        eventloop = Mock()
        address = (factory.make_ip_address(), 5240)
        service = Mock()

        @inlineCallbacks
        def mock_service_add_connection(ev, conn):
            yield cp.add_connection(ev, conn)

        service.add_connection = mock_service_add_connection

        connection1 = ClusterClient(address, eventloop, service)
        connection2 = ClusterClient(address, eventloop, service)
        connect = self.patch(cp, "connect")

        @inlineCallbacks
        def call_connectionMade(*args, **kwargs):
            yield connection2.connectionMade()
            return connection2

        connect.side_effect = call_connectionMade

        authRegion = self.patch(connection2, "authenticateRegion")
        authRegion.return_value = succeed(True)
        register = self.patch(connection2, "registerRackWithRegion")

        def set_ident(*args, **kwargs):
            connection2.localIdent = factory.make_name()
            return succeed(True)

        register.side_effect = set_ident
        cp[eventloop] = [connection1]
        cp.scale_up_connections()
        self.assertCountEqual(cp[eventloop], [connection1, connection2])

    def test_scale_up_connections_raises_MaxConnectionsOpen_when_cannot_create_another(
        self,
    ):
        cp = ConnectionPool(Clock(), Mock())
        eventloop = Mock()
        connection1 = Mock()
        connection2 = Mock()
        connect = self.patch(cp, "connect")
        connect.return_value = succeed(connection2)
        cp[eventloop] = [connection1]
        self.assertRaises(
            exceptions.MaxConnectionsOpen,
            extract_result,
            cp.scale_up_connections(),
        )

    def test_scale_up_connections_registers_the_new_connection_with_the_region(
        self,
    ):
        cp = ConnectionPool(Clock(), Mock(), max_conns=2)
        eventloop = Mock()
        address = (factory.make_ip_address(), 5240)
        service = Mock()
        connection1 = ClusterClient(address, eventloop, service)
        connection2 = ClusterClient(address, eventloop, service)
        connect = self.patch(cp, "connect")

        def call_connectionMade(*args, **kwargs):
            connection2.connectionMade()
            return succeed(connection2)

        connect.side_effect = call_connectionMade

        authRegion = self.patch(connection2, "authenticateRegion")
        authRegion.return_value = succeed(True)
        register = self.patch(connection2, "registerRackWithRegion")

        def set_ident(*args, **kwargs):
            connection2.localIdent = factory.make_name()
            return succeed(True)

        register.side_effect = set_ident

        cp[eventloop] = [connection1]
        cp.scale_up_connections()
        self.assertIsNotNone(connection2.localIdent)

    def test_get_connection(self):
        cp = ConnectionPool(Clock(), Mock(), max_idle_conns=2, max_conns=2)
        eventloops = [Mock() for _ in range(3)]
        cp.connections = {
            eventloop: [Mock() for _ in range(2)] for eventloop in eventloops
        }
        self.assertIn(cp.get_connection(eventloops[0]), cp[eventloops[0]])

    def test_get_random_connection(self):
        cp = ConnectionPool(Clock(), Mock(), max_idle_conns=2, max_conns=2)
        eventloops = [Mock() for _ in range(3)]
        cp.connections = {
            eventloop: [Mock() for _ in range(2)] for eventloop in eventloops
        }
        self.assertIn(
            cp.get_connection(eventloops[0]),
            [conn for conn_list in cp.values() for conn in conn_list],
        )

    def test_get_random_free_connection_returns_a_free_connection(self):
        cp = ConnectionPool(Clock(), Mock())
        eventloops = [Mock() for _ in range(3)]

        def _create_conn(in_use):
            conn = Mock()
            conn.in_use = in_use
            return conn

        cp.connections = {
            eventloops[0]: [_create_conn(True)],
            eventloops[1]: [_create_conn(False)],
            eventloops[2]: [_create_conn(True)],
        }
        conn = cp.get_random_free_connection()
        self.assertIn(conn, cp[eventloops[1]])

    def test_get_random_free_connection_raises_AllConnectionsBusy_when_there_are_no_free_connections(
        self,
    ):
        cp = ConnectionPool(Clock(), Mock())
        eventloops = [Mock() for _ in range(3)]

        def _create_conn(in_use):
            conn = Mock()
            conn.in_use = in_use
            return conn

        cp.connections = {
            eventloops[0]: [_create_conn(True)],
            eventloops[1]: [_create_conn(True)],
            eventloops[2]: [_create_conn(True)],
        }

        self.assertRaises(
            exceptions.AllConnectionsBusy, cp.get_random_free_connection
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

    def test_get_all_free_connections(self):
        cp = ConnectionPool(Clock(), Mock(), max_conns=2)
        eventloops = [Mock() for _ in range(3)]

        def _create_conn(in_use):
            conn = Mock()
            conn.in_use = in_use
            return conn

        cp.connections = {
            eventloops[0]: [_create_conn(True), _create_conn(False)],
            eventloops[1]: [_create_conn(True)],
            eventloops[2]: [_create_conn(False)],
        }

        self.assertCountEqual(
            cp.get_all_free_connections(),
            [
                conn
                for conn_list in cp.values()
                for conn in conn_list
                if not conn.in_use
            ],
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
        connectProtocol.called_once_with(
            TCP6ClientEndpoint(reactor=clock, host="a.example.com", port=1111),
            ClusterClient(
                address=("a.example.com", 1111),
                eventloop="an-event-loop",
                service=service,
            ),
        )
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

    @inlineCallbacks
    def test_add_connection_adds_the_staged_connection(self):
        eventloop = Mock()
        connection = Mock()
        cp = ConnectionPool(Clock(), Mock())
        cp.try_connections = {eventloop: connection}
        yield cp.add_connection(eventloop, connection)
        self.assertIn(connection, cp.get_all_connections())

    def test_remove_connection_removes_connection_from_pool(self):
        eventloop = Mock()
        connection = Mock()
        cp = ConnectionPool(Clock(), Mock())
        cp.connections[eventloop] = [connection]
        cp.remove_connection(eventloop, connection)
        self.assertEqual(cp.connections, {})
