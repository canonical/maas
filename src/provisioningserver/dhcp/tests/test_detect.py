# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for dhcp/detect.py"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import os
import socket
import textwrap
import urllib2

from apiclient.maas_client import MAASClient
from apiclient.testing.credentials import make_api_credentials
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
import mock
from provisioningserver import cache
from provisioningserver.auth import (
    NODEGROUP_UUID_CACHE_KEY,
    record_api_credentials,
    )
from provisioningserver.dhcp.detect import (
    BOOTP_CLIENT_PORT,
    BOOTP_SERVER_PORT,
    determine_cluster_interfaces,
    DHCPDiscoverPacket,
    DHCPOfferPacket,
    get_interface_IP,
    get_interface_MAC,
    make_transaction_ID,
    periodic_probe_task,
    probe_interface,
    receive_offers,
    request_dhcp,
    udp_socket,
    update_region_controller,
    )
import provisioningserver.dhcp.detect as detect_module
from provisioningserver.testing.testcase import PservTestCase


class MakeTransactionID(MAASTestCase):
    """Tests for `make_transaction_ID`."""

    def test_produces_well_formed_ID(self):
        # The dhcp transaction should be 4 bytes long.
        transaction_id = make_transaction_ID()
        self.assertIsInstance(transaction_id, bytes)
        self.assertEqual(4, len(transaction_id))

    def test_randomises(self):
        self.assertNotEqual(
            make_transaction_ID(),
            make_transaction_ID())


class TestDHCPDiscoverPacket(MAASTestCase):

    def test_init_sets_transaction_ID(self):
        transaction_id = make_transaction_ID()
        self.patch(detect_module, 'make_transaction_ID').return_value = (
            transaction_id)

        discover = DHCPDiscoverPacket(factory.getRandomMACAddress())

        self.assertEqual(transaction_id, discover.transaction_ID)

    def test_init_sets_packed_mac(self):
        mac = factory.getRandomMACAddress()
        discover = DHCPDiscoverPacket(mac)
        self.assertEqual(
            discover.string_mac_to_packed(mac),
            discover.packed_mac)

    def test_init_sets_packet(self):
        discover = DHCPDiscoverPacket(factory.getRandomMACAddress())
        self.assertIsNotNone(discover.packet)

    def test_string_mac_to_packed(self):
        discover = DHCPDiscoverPacket
        expected = b"\x01\x22\x33\x99\xaa\xff"
        input = "01:22:33:99:aa:ff"
        self.assertEqual(expected, discover.string_mac_to_packed(input))

    def test__build(self):
        mac = factory.getRandomMACAddress()
        discover = DHCPDiscoverPacket(mac)
        discover._build()

        expected = (
            b'\x01\x01\x06\x00' + discover.transaction_ID +
            b'\x00\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00' +
            b'\x00\x00\x00\x00\x00\x00\x00\x00' +
            discover.packed_mac +
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' +
            b'\x00' * 67 +
            b'\x00' * 125 +
            b'\x63\x82\x53\x63\x35\x01\x01\x3d\x06' + discover.packed_mac +
            b'\x37\x03\x03\x01\x06\xff')

        self.assertEqual(expected, discover.packet)


class TestDHCPOfferPacket(MAASTestCase):

    def test_decodes_dhcp_server(self):
        buffer = b'\x00' * 245 + b'\x10\x00\x00\xaa'
        offer = DHCPOfferPacket(buffer)
        self.assertEqual('16.0.0.170', offer.dhcp_server_ID)


class TestGetInterfaceMAC(MAASTestCase):
    """Tests for `get_interface_MAC`."""

    def test_loopback_has_zero_MAC(self):
        # It's a lame test, but what other network interfaces can we reliably
        # test this on?
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.assertEqual('00:00:00:00:00:00', get_interface_MAC(sock, 'lo'))


class TestGetInterfaceIP(MAASTestCase):
    """Tests for `get_interface_IP`."""

    def test_loopback_has_localhost_address(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.assertEqual('127.0.0.1', get_interface_IP(sock, 'lo'))


def patch_socket(testcase):
    """Patch `socket.socket` to return a mock."""
    sock = mock.MagicMock()
    testcase.patch(socket, 'socket', mock.MagicMock(return_value=sock))
    return sock


class TestUDPSocket(MAASTestCase):
    """Tests for `udp_socket`."""

    def test_yields_open_socket(self):
        patch_socket(self)
        with udp_socket() as sock:
            socket_calls = list(socket.socket.mock_calls)
            close_calls = list(sock.close.mock_calls)
        self.assertEqual(
            [mock.call(socket.AF_INET, socket.SOCK_DGRAM)],
            socket_calls)
        self.assertEqual([], close_calls)

    def test_closes_socket_on_exit(self):
        patch_socket(self)
        with udp_socket() as sock:
            pass
        self.assertEqual([mock.call()], sock.close.mock_calls)

    def test_sets_reuseaddr(self):
        patch_socket(self)
        with udp_socket() as sock:
            pass
        self.assertEqual(
            [mock.call(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)],
            sock.setsockopt.mock_calls)


class TestRequestDHCP(MAASTestCase):
    """Tests for `request_dhcp`."""

    def patch_interface_MAC(self):
        """Patch `get_interface_MAC` to return a fixed value."""
        mac = factory.getRandomMACAddress()
        self.patch(detect_module, 'get_interface_MAC').return_value = mac
        return mac

    def patch_interface_IP(self):
        """Patch `get_interface_IP` to return a fixed value."""
        ip = factory.getRandomIPAddress()
        self.patch(detect_module, 'get_interface_IP').return_value = ip
        return ip

    def patch_transaction_ID(self):
        """Patch `make_transaction_ID` to return a fixed value."""
        transaction_id = make_transaction_ID()
        self.patch(
            detect_module, 'make_transaction_ID').return_value = transaction_id
        return transaction_id

    def test_sends_discover_packet(self):
        sock = patch_socket(self)
        self.patch_interface_MAC()
        self.patch_interface_IP()
        interface = factory.make_name('interface')

        request_dhcp(interface)

        [call] = sock.sendto.mock_calls
        _, args, _ = call
        self.assertEqual(
            ('<broadcast>', BOOTP_SERVER_PORT),
            args[1])

    def test_returns_transaction_id(self):
        patch_socket(self)
        self.patch_interface_MAC()
        self.patch_interface_IP()
        transaction_id = self.patch_transaction_ID()
        interface = factory.make_name('interface')

        self.assertEqual(transaction_id, request_dhcp(interface))


class FakePacketReceiver:
    """Fake callable to substitute for a socket's `recv`.

    Returns the given packets on successive calls.  When it runs out,
    raises a timeout.
    """

    def __init__(self, packets=None):
        if packets is None:
            packets = []
        self.calls = []
        self.packets = list(packets)

    def __call__(self, recv_size):
        self.calls.append(recv_size)
        if len(self.packets) == 0:
            raise socket.timeout()
        else:
            return self.packets.pop(0)


class TestReceiveOffers(MAASTestCase):
    """Tests for `receive_offers`."""

    def patch_recv(self, sock, num_packets=0):
        """Patch up socket's `recv` to return `num_packets` arbitrary packets.

        After that, further calls to `recv` will raise a timeout.
        """
        packets = [factory.getRandomBytes() for _ in range(num_packets)]
        receiver = FakePacketReceiver(packets)
        self.patch(sock, 'recv', receiver)
        return receiver

    def patch_offer_packet(self):
        """Patch a mock `DHCPOfferPacket`."""
        transaction_id = factory.getRandomBytes(4)
        packet = mock.MagicMock()
        packet.transaction_ID = transaction_id
        packet.dhcp_server_ID = factory.getRandomIPAddress()
        self.patch(detect_module, 'DHCPOfferPacket').return_value = packet
        return packet

    def test_receives_from_socket(self):
        sock = patch_socket(self)
        receiver = self.patch_recv(sock)
        transaction_id = self.patch_offer_packet().transaction_ID

        receive_offers(transaction_id)

        self.assertEqual(
            [mock.call(socket.AF_INET, socket.SOCK_DGRAM)],
            socket.socket.mock_calls)
        self.assertEqual(
            [mock.call(('', BOOTP_CLIENT_PORT))],
            sock.bind.mock_calls)
        self.assertEqual([1024], receiver.calls)

    def test_returns_empty_if_nothing_received(self):
        sock = patch_socket(self)
        self.patch_recv(sock)
        transaction_id = self.patch_offer_packet().transaction_ID

        self.assertEqual(set(), receive_offers(transaction_id))

    def test_processes_offer(self):
        sock = patch_socket(self)
        self.patch_recv(sock, 1)
        packet = self.patch_offer_packet()

        self.assertEqual(
            {packet.dhcp_server_ID},
            receive_offers(packet.transaction_ID))

    def test_ignores_other_transactions(self):
        sock = patch_socket(self)
        self.patch_recv(sock, 1)
        self.patch_offer_packet()
        other_transaction_id = factory.getRandomBytes(4)

        self.assertEqual(set(), receive_offers(other_transaction_id))

    def test_propagates_errors_other_than_timeout(self):
        class InducedError(Exception):
            """Deliberately induced error for testing."""

        sock = patch_socket(self)
        sock.recv = mock.MagicMock(side_effect=InducedError)

        self.assertRaises(
            InducedError,
            receive_offers, factory.getRandomBytes(4))


class MockResponse:
    # This implements just enough to look lke a urllib2 response object.
    def __init__(self, code=None, response=None):
        if code is None:
            code = httplib.OK
        self.code = code
        if response is None:
            response = ""
        self.response = response

    def getcode(self):
        return self.code

    def read(self):
        return self.response


class TestPeriodicTask(PservTestCase):

    def setUp(self):
        # Initialise the knowledge cache.
        super(TestPeriodicTask, self).setUp()
        uuid = factory.getRandomUUID()
        maas_url = 'http://%s.example.com/%s/' % (
            factory.make_name('host'),
            factory.getRandomString(),
            )
        api_credentials = make_api_credentials()

        cache.cache.set(NODEGROUP_UUID_CACHE_KEY, uuid)
        os.environ["MAAS_URL"] = maas_url
        cache.cache.set('api_credentials', ':'.join(api_credentials))

        self.knowledge = dict(
            nodegroup_uuid=uuid,
            api_credentials=api_credentials,
            maas_url=maas_url)

    def make_fake_interfaces_response(self, interfaces_pairs):
        stanzas = []
        for interfaces_pair in interfaces_pairs:
            stanza = textwrap.dedent("""
                {{
                    "ip_range_high": null,
                    "ip_range_low": null,
                    "broadcast_ip": null,
                    "ip": "{1}",
                    "subnet_mask": "255.255.255.0",
                    "management": 0,
                    "interface": "{0}"
                }}""").format(*interfaces_pair)
            stanzas.append(stanza)
        interfaces_json = "["
        interfaces_json += ",".join(stanzas)
        interfaces_json += "]"
        return interfaces_json

    def patch_fake_interfaces_list(self, interfaces_pairs):
        # Set up the api client to return a fake set of interfaces.
        # Determine_cluster_interfaces calls the API to discover what
        # interfaces are available, so any test code that calls it
        # should first call this helper to set up the required fake response.
        interfaces_json = self.make_fake_interfaces_response(interfaces_pairs)
        self.patch(MAASClient, 'get').return_value = MockResponse(
            httplib.OK, interfaces_json)

    def test_determine_cluster_interfaces_returns_interface_names(self):
        eth0_addr = factory.getRandomIPAddress()
        wlan0_addr = factory.getRandomIPAddress()
        self.patch_fake_interfaces_list(
            [("eth0", eth0_addr), ("wlan0", wlan0_addr)])
        self.assertEqual(
            [("eth0", eth0_addr), ("wlan0", wlan0_addr)],
            determine_cluster_interfaces(self.knowledge))

    def test_probe_interface_returns_empty_set_when_nothing_detected(self):
        eth0_addr = factory.getRandomIPAddress()
        self.patch_fake_interfaces_list([("eth0", eth0_addr)])
        self.patch(detect_module, 'probe_dhcp').return_value = set()
        interfaces = determine_cluster_interfaces(self.knowledge)
        results = probe_interface(*interfaces[0])
        self.assertEqual(set(), results)

    def test_probe_interface_returns_populated_set(self):
        # Test that the detected DHCP server is returned.
        eth0_addr = factory.getRandomIPAddress()
        self.patch_fake_interfaces_list([("eth0", eth0_addr)])
        self.patch(
            detect_module, 'probe_dhcp').return_value = {'10.2.2.2'}
        interfaces = determine_cluster_interfaces(self.knowledge)
        results = probe_interface(*interfaces[0])
        self.assertEqual({'10.2.2.2'}, results)

    def test_probe_interface_filters_interface_own_ip(self):
        # Test that the interface shows the detected DHCP server except
        # if it is the same IP as the interface's.
        eth0_addr = factory.getRandomIPAddress()
        self.patch_fake_interfaces_list([("eth0", eth0_addr)])
        detected_dhcp = eth0_addr
        self.patch(detect_module, 'probe_dhcp').return_value = {detected_dhcp}
        interfaces = determine_cluster_interfaces(self.knowledge)
        results = probe_interface(*interfaces[0])
        self.assertEqual(set(), results)

    def test_determine_cluster_interfaces_catchs_HTTPError_in_MASClient(self):
        self.patch(MAASClient, 'get').side_effect = urllib2.HTTPError(
            mock.sentinel, mock.sentinel, mock.sentinel,
            mock.sentinel, mock.sentinel)
        mocked_logging = self.patch(detect_module.logger, 'error')
        determine_cluster_interfaces(self.knowledge)
        mocked_logging.assert_called_once()

    def test_determine_cluster_interfaces_catches_URLError_in_MASClient(self):
        self.patch(MAASClient, 'get').side_effect = urllib2.URLError(
            mock.sentinel.arg1)
        mocked_logging = self.patch(detect_module.logger, 'error')
        determine_cluster_interfaces(self.knowledge)
        mocked_logging.assert_called_once()

    def test_determine_cluster_interfaces_catches_non_OK_response(self):
        self.patch(MAASClient, 'get').return_value = MockResponse(
            httplib.NOT_FOUND, "error text")
        mocked_logging = self.patch(detect_module.logger, 'error')
        determine_cluster_interfaces(self.knowledge)
        mocked_logging.assert_called_once()

    def test_update_region_controller_sets_detected_dhcp(self):
        mocked_put = self.patch(MAASClient, 'put')
        mocked_put.return_value = MockResponse()
        detected_server = factory.getRandomIPAddress()
        update_region_controller(self.knowledge, "eth0", detected_server)
        mocked_put.assert_called_once_with(
            'api/1.0/nodegroups/%s/interfaces/eth0/' % self.knowledge[
                'nodegroup_uuid'],
            foreign_dhcp_ip=detected_server)

    def test_update_region_controller_clears_detected_dhcp(self):
        mocked_put = self.patch(MAASClient, 'put')
        mocked_put.return_value = MockResponse()
        detected_server = None
        update_region_controller(self.knowledge, "eth0", detected_server)
        mocked_put.assert_called_once_with(
            'api/1.0/nodegroups/%s/interfaces/eth0/' % self.knowledge[
                'nodegroup_uuid'],
            foreign_dhcp_ip='')

    def test_update_region_controller_catches_HTTPError_in_MAASClient(self):
        self.patch(MAASClient, 'put').side_effect = urllib2.HTTPError(
            mock.sentinel, mock.sentinel, mock.sentinel,
            mock.sentinel, mock.sentinel)
        mocked_logging = self.patch(detect_module.logger, 'error')
        update_region_controller(self.knowledge, "eth0", None)
        mocked_logging.assert_called_once()

    def test_update_region_controller_catches_URLError_in_MAASClient(self):
        self.patch(MAASClient, 'put').side_effect = urllib2.URLError(
            mock.sentinel.arg1)
        mocked_logging = self.patch(detect_module.logger, 'error')
        update_region_controller(self.knowledge, "eth0", None)
        mocked_logging.assert_called_once()

    def test_update_region_controller_catches_non_OK_response(self):
        mock_response = MockResponse(httplib.NOT_FOUND, "error text")
        self.patch(MAASClient, 'put').return_value = mock_response
        mocked_logging = self.patch(detect_module.logger, 'error')
        update_region_controller(self.knowledge, "eth0", None)
        mocked_logging.assert_called_once_with(
            mock.ANY, mock_response.getcode(), mock_response.read())

    def test_periodic_probe_task_exits_with_not_enough_knowledge(self):
        mocked = self.patch(detect_module, 'determine_cluster_interfaces')
        record_api_credentials(None)
        periodic_probe_task()
        self.assertFalse(mocked.called)

    def test_periodic_probe_task_exits_if_no_interfaces(self):
        mocked = self.patch(detect_module, 'probe_interface')
        self.patch(
            detect_module, 'determine_cluster_interfaces').return_value = None
        periodic_probe_task()
        self.assertFalse(mocked.called)

    def test_periodic_probe_task_updates_region_with_detected_server(self):
        eth0_addr = factory.getRandomIPAddress()
        wlan0_addr = factory.getRandomIPAddress()
        detected_server = factory.getRandomIPAddress()
        self.patch_fake_interfaces_list(
            [("eth0", eth0_addr), ("wlan0", wlan0_addr)])
        self.patch(
            detect_module, 'probe_dhcp').return_value = {detected_server}
        mocked_update = self.patch(detect_module, 'update_region_controller')
        periodic_probe_task()
        calls = [
            mock.call(self.knowledge, 'eth0', detected_server),
            mock.call(self.knowledge, 'wlan0', detected_server),
            ]
        mocked_update.assert_has_calls(calls, any_order=True)

    def test_periodic_probe_task_updates_region_with_no_detected_server(self):
        eth0_addr = factory.getRandomIPAddress()
        wlan0_addr = factory.getRandomIPAddress()
        self.patch_fake_interfaces_list(
            [("eth0", eth0_addr), ("wlan0", wlan0_addr)])
        self.patch(
            detect_module, 'probe_dhcp').return_value = set()
        mocked_update = self.patch(detect_module, 'update_region_controller')
        periodic_probe_task()
        calls = [
            mock.call(self.knowledge, 'eth0', None),
            mock.call(self.knowledge, 'wlan0', None),
            ]
        mocked_update.assert_has_calls(calls, any_order=True)
