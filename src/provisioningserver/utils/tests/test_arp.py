# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ``provisioningserver.utils.pcap``."""

__all__ = []

from datetime import datetime
import io
import json
from textwrap import dedent
import time

from maastesting.testcase import MAASTestCase
from netaddr import (
    EUI,
    IPAddress,
)
from provisioningserver.utils.arp import (
    ARP,
    ARP_OPERATION,
    bytes_to_hex,
    bytes_to_int,
    format_eui,
    hex_str_to_bytes,
    ipv4_to_bytes,
    SEEN_AGAIN_THRESHOLD,
    update_and_print_bindings,
    update_bindings_and_get_event,
)
from testtools.matchers import (
    Equals,
    HasLength,
)


class TestConversionFunctions(MAASTestCase):

    def test__bytes_to_hex(self):
        self.assertThat(bytes_to_hex(b'\x01\xff'), Equals(b'01ff'))
        self.assertThat(bytes_to_hex(b'\x00\x01\xff'), Equals(b'0001ff'))

    def test__bytes_to_int(self):
        self.assertThat(bytes_to_int(b'\xff\xff'), Equals(65535))
        self.assertThat(bytes_to_int(b'\xff\xff\xff'), Equals(16777215))
        self.assertThat(
            bytes_to_int(b'\xff\xff\xff\xff\xff\xff'), Equals(281474976710655))

    def test__hex_str_to_bytes(self):
        self.assertThat(hex_str_to_bytes('0x0000'), Equals(b'\x00\x00'))
        self.assertThat(hex_str_to_bytes('ff:ff'), Equals(b'\xff\xff'))
        self.assertThat(hex_str_to_bytes('ff ff  '), Equals(b'\xff\xff'))
        self.assertThat(hex_str_to_bytes('  ff-ff'), Equals(b'\xff\xff'))
        self.assertThat(hex_str_to_bytes('ff-ff'), Equals(b'\xff\xff'))
        self.assertThat(hex_str_to_bytes('0xffff'), Equals(b'\xff\xff'))
        self.assertThat(hex_str_to_bytes(' 0xffff'), Equals(b'\xff\xff'))
        self.assertThat(
            hex_str_to_bytes('01:02:03:04:05:06'),
            Equals(b'\x01\x02\x03\x04\x05\x06'))
        self.assertThat(
            hex_str_to_bytes('0A:0B:0C:0D:0E:0F'),
            Equals(b'\x0a\x0b\x0c\x0d\x0e\x0f'))
        self.assertThat(
            hex_str_to_bytes('0a:0b:0c:0d:0e:0f'),
            Equals(b'\x0a\x0b\x0c\x0d\x0e\x0f'))

    def test__format_eui(self):
        self.assertThat(
            format_eui(EUI('0A-0B-0C-0D-0E-0F')), Equals("0a:0b:0c:0d:0e:0f"))


def make_arp_packet(
        sender_ip, sender_mac, target_ip, target_mac='00:00:00:00:00:00',
        op=ARP_OPERATION.REQUEST, hardware_type='0x0001', protocol='0x0800',
        hardware_length='0x06', protocol_length='0x04'):
    # Concatenate a byte string with the specified values.
    # For ARP format, see: https://tools.ietf.org/html/rfc826
    arp_packet = (
        hex_str_to_bytes(hardware_type) +
        hex_str_to_bytes(protocol) +
        hex_str_to_bytes(hardware_length) +
        hex_str_to_bytes(protocol_length) +
        ARP_OPERATION(op) +
        hex_str_to_bytes(sender_mac) +
        ipv4_to_bytes(sender_ip) +
        hex_str_to_bytes(target_mac) +
        ipv4_to_bytes(target_ip)
    )
    return arp_packet


class TestARP(MAASTestCase):

    def test__operation_enum__str(self):
        self.expectThat(str(
            ARP_OPERATION(ARP_OPERATION.REQUEST)), Equals("1 (request)"))
        self.expectThat(str(
            ARP_OPERATION(ARP_OPERATION.REPLY)), Equals("2 (reply)"))
        self.expectThat(str(ARP_OPERATION(3)), Equals("3"))

    def test__operation_enum__bytes(self):
        self.expectThat(bytes(
            ARP_OPERATION(ARP_OPERATION.REQUEST)), Equals(b'\0\x01'))
        self.expectThat(bytes(
            ARP_OPERATION(ARP_OPERATION.REPLY)), Equals(b'\0\x02'))

    def test__operation_enum__radd(self):
        self.expectThat(
            b'\xff' + bytes(ARP_OPERATION(ARP_OPERATION.REPLY)) + b'\xff',
            Equals(b'\xff\0\x02\xff'))

    def test__write(self):
        ts = int(time.time())
        expected_time = datetime.fromtimestamp(ts)
        pkt_sender_mac = '01:02:03:04:05:06'
        pkt_sender_ip = '192.168.0.1'
        pkt_target_ip = '192.168.0.2'
        pkt_target_mac = '00:00:00:00:00:00'
        eth_src = '02:03:04:05:06:07'
        eth_dst = 'ff:ff:ff:ff:ff:ff'
        arp_packet = make_arp_packet(
            pkt_sender_ip, pkt_sender_mac, pkt_target_ip, pkt_target_mac)
        arp = ARP(
            arp_packet, time=ts, src_mac=hex_str_to_bytes(eth_src),
            dst_mac=hex_str_to_bytes(eth_dst))
        out = io.StringIO()
        arp.write(out)
        expected_output = dedent("""\
        ARP observed at {expected_time}:
                Ethernet source: {eth_src}
           Ethernet destination: {eth_dst}
                  Hardware type: 0x0001
                  Protocol type: 0x0800
        Hardware address length: 6
        Protocol address length: 4
                      Operation: 1 (request)
        Sender hardware address: {pkt_sender_mac}
        Sender protocol address: {pkt_sender_ip}
        Target hardware address: {pkt_target_mac}
        Target protocol address: {pkt_target_ip}
        """)
        self.assertThat(
            out.getvalue().strip(),
            Equals(expected_output.format(**locals()).strip()))

    def test__is_valid__succeeds_for_normal_packet(self):
        arp_packet = make_arp_packet(
            '192.168.0.1', '01:02:03:04:05:06', '192.168.0.2')
        arp = ARP(arp_packet)
        self.assertTrue(arp.is_valid())

    def test__is_valid__fails_for_invalid_packets(self):
        arp = ARP(b'\x00' * 28)
        self.assertFalse(arp.is_valid())
        arp = ARP(make_arp_packet(
            '192.168.0.1', '01:02:03:04:05:06', '192.168.0.2',
            hardware_type='0x0000'))
        self.assertFalse(arp.is_valid())
        arp = ARP(make_arp_packet(
            '192.168.0.1', '01:02:03:04:05:06', '192.168.0.2',
            protocol='0x0000'))
        self.assertFalse(arp.is_valid())
        arp = ARP(make_arp_packet(
            '192.168.0.1', '01:02:03:04:05:06', '192.168.0.2',
            hardware_length='0x00'))
        self.assertFalse(arp.is_valid())
        arp = ARP(make_arp_packet(
            '192.168.0.1', '01:02:03:04:05:06', '192.168.0.2',
            protocol_length='0x00'))
        self.assertFalse(arp.is_valid())

    def test__properties(self):
        pkt_sender_mac = '01:02:03:04:05:06'
        pkt_sender_ip = '192.168.0.1'
        pkt_target_ip = '192.168.0.2'
        pkt_target_mac = '00:00:00:00:00:00'
        eth_src = '02:03:04:05:06:07'
        eth_dst = 'ff:ff:ff:ff:ff:ff'
        arp_packet = make_arp_packet(
            pkt_sender_ip, pkt_sender_mac, pkt_target_ip, pkt_target_mac)
        arp = ARP(
            arp_packet, src_mac=hex_str_to_bytes(eth_src),
            dst_mac=hex_str_to_bytes(eth_dst))
        self.assertThat(arp.source_eui, Equals(EUI(pkt_sender_mac)))
        self.assertThat(arp.target_eui, Equals(EUI(pkt_target_mac)))
        self.assertThat(arp.source_ip, Equals(IPAddress(pkt_sender_ip)))
        self.assertThat(arp.target_ip, Equals(IPAddress(pkt_target_ip)))

    def test__bindings__returns_sender_for_request(self):
        pkt_sender_mac = '01:02:03:04:05:06'
        pkt_sender_ip = '192.168.0.1'
        pkt_target_ip = '192.168.0.2'
        pkt_target_mac = '00:00:00:00:00:00'
        arp = ARP(make_arp_packet(
            pkt_sender_ip, pkt_sender_mac, pkt_target_ip, pkt_target_mac,
            op=ARP_OPERATION.REQUEST))
        self.assertItemsEqual(
            arp.bindings(), [(IPAddress(pkt_sender_ip), EUI(pkt_sender_mac))])

    def test__bindings__returns_sender_and_target_for_reply(self):
        pkt_sender_mac = '01:02:03:04:05:06'
        pkt_sender_ip = '192.168.0.1'
        pkt_target_ip = '192.168.0.2'
        pkt_target_mac = '02:03:04:05:06:07'
        arp = ARP(make_arp_packet(
            pkt_sender_ip, pkt_sender_mac, pkt_target_ip, pkt_target_mac,
            op=ARP_OPERATION.REPLY))
        self.assertItemsEqual(
            arp.bindings(), [
                (IPAddress(pkt_sender_ip), EUI(pkt_sender_mac)),
                (IPAddress(pkt_target_ip), EUI(pkt_target_mac))
            ])

    def test__bindings__skips_null_source_ip_for_request(self):
        pkt_sender_mac = '01:02:03:04:05:06'
        pkt_sender_ip = '0.0.0.0'
        pkt_target_ip = '192.168.0.2'
        pkt_target_mac = '00:00:00:00:00:00'
        arp = ARP(make_arp_packet(
            pkt_sender_ip, pkt_sender_mac, pkt_target_ip, pkt_target_mac,
            op=ARP_OPERATION.REQUEST))
        self.assertItemsEqual(arp.bindings(), [])

    def test__bindings__skips_null_source_ip_in_reply(self):
        pkt_sender_mac = '01:02:03:04:05:06'
        pkt_sender_ip = '0.0.0.0'
        pkt_target_ip = '192.168.0.2'
        pkt_target_mac = '02:03:04:05:06:07'
        arp = ARP(make_arp_packet(
            pkt_sender_ip, pkt_sender_mac, pkt_target_ip, pkt_target_mac,
            op=ARP_OPERATION.REPLY))
        self.assertItemsEqual(
            arp.bindings(), [(IPAddress(pkt_target_ip), EUI(pkt_target_mac))])

    def test__bindings__skips_null_target_ip_in_reply(self):
        pkt_sender_mac = '01:02:03:04:05:06'
        pkt_sender_ip = '192.168.0.1'
        pkt_target_ip = '0.0.0.0'
        pkt_target_mac = '02:03:04:05:06:07'
        arp = ARP(make_arp_packet(
            pkt_sender_ip, pkt_sender_mac, pkt_target_ip, pkt_target_mac,
            op=ARP_OPERATION.REPLY))
        self.assertItemsEqual(
            arp.bindings(), [(IPAddress(pkt_sender_ip), EUI(pkt_sender_mac))])


class TestUpdateBindingsAndGetEvent(MAASTestCase):

    def test__new_binding(self):
        bindings = {}
        ip = IPAddress("192.168.0.1")
        mac = EUI("00:01:02:03:04:05")
        event = update_bindings_and_get_event(
            bindings, ip, mac, 0)
        self.assertThat(bindings, Equals({
            ip: {"mac": mac, "time": 0}
        }))
        self.assertThat(event, Equals(dict(
            event="NEW", ip=str(ip), mac=format_eui(mac), time=0
        )))

    def test__refreshed_binding(self):
        bindings = {}
        ip = IPAddress("192.168.0.1")
        mac = EUI("00:01:02:03:04:05")
        update_bindings_and_get_event(
            bindings, ip, mac, 0)
        event = update_bindings_and_get_event(
            bindings, ip, mac, SEEN_AGAIN_THRESHOLD)
        self.assertThat(bindings, Equals({
            ip: {"mac": mac, "time": SEEN_AGAIN_THRESHOLD}
        }))
        self.assertThat(event, Equals(dict(
            event="REFRESHED", ip=str(ip), mac=format_eui(mac),
            time=SEEN_AGAIN_THRESHOLD
        )))

    def test__refreshed_binding_within_threshold_does_not_emit_event(self):
        bindings = {}
        ip = IPAddress("192.168.0.1")
        mac = EUI("00:01:02:03:04:05")
        update_bindings_and_get_event(
            bindings, ip, mac, 0)
        event = update_bindings_and_get_event(
            bindings, ip, mac, 1)
        self.assertThat(bindings, Equals({
            ip: {"mac": mac, "time": 0}
        }))
        self.assertIsNone(event)

    def test__moved_binding(self):
        bindings = {}
        ip = IPAddress("192.168.0.1")
        mac1 = EUI("00:01:02:03:04:05")
        mac2 = EUI("02:03:04:05:06:07")
        update_bindings_and_get_event(
            bindings, ip, mac1, 0)
        event = update_bindings_and_get_event(
            bindings, ip, mac2, 1)
        self.assertThat(bindings, Equals({
            ip: {"mac": mac2, "time": 1}
        }))
        self.assertThat(event, Equals(dict(
            event="MOVED", ip=str(ip), mac=format_eui(mac2),
            time=1, previous_mac=format_eui(mac1)
        )))


class FakeARP:
    """Fake ARP packet used for testing the processing of bindings."""

    def __init__(self, mock_bindings, time=0):
        self.mock_bindings = mock_bindings
        self.time = time

    def bindings(self):
        for binding in self.mock_bindings:
            yield binding


class TestUpdateAndPrintBindings(MAASTestCase):

    def test__prints_bindings_in_json_format(self):
        bindings = {}
        ip = IPAddress("192.168.0.1")
        mac1 = EUI("00:01:02:03:04:05")
        mac2 = EUI("02:03:04:05:06:07")
        # Need to test with three bindings so that we ensure we cover JSON
        # output for NEW, MOVED, and REFRESHED. Two packets is sufficient
        # to test all three. (Though it would be three packets in real life,
        # it's better to test it this way, since some packets *do* have two
        # bindings.)
        arp1 = FakeARP([(ip, mac1), (ip, mac2)])
        arp2 = FakeARP([(ip, mac2)], time=SEEN_AGAIN_THRESHOLD)
        out = io.StringIO()
        update_and_print_bindings(bindings, arp1, out)
        update_and_print_bindings(bindings, arp2, out)
        self.assertThat(bindings, Equals({
            ip: {"mac": mac2, "time": SEEN_AGAIN_THRESHOLD}
        }))
        output = io.StringIO(out.getvalue())
        lines = output.readlines()
        self.assertThat(lines, HasLength(3))
        line1 = json.loads(lines[0])
        self.assertThat(line1, Equals({
            "ip": str(ip),
            "mac": format_eui(mac1),
            "time": 0,
            "event": "NEW"
        }))
        line2 = json.loads(lines[1])
        self.assertThat(line2, Equals({
            "ip": str(ip),
            "mac": format_eui(mac2),
            "previous_mac": format_eui(mac1),
            "time": 0,
            "event": "MOVED"
        }))
        line3 = json.loads(lines[2])
        self.assertThat(line3, Equals({
            "ip": str(ip),
            "mac": format_eui(mac2),
            "time": SEEN_AGAIN_THRESHOLD,
            "event": "REFRESHED"
        }))
