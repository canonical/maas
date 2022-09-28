# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ``provisioningserver.utils.arp``."""


from argparse import ArgumentParser
from datetime import datetime
import io
import json
import subprocess
from tempfile import NamedTemporaryFile
from textwrap import dedent
import time
from unittest.mock import Mock

from netaddr import EUI, IPAddress
from testtools.matchers import Equals, HasLength
from testtools.testcase import ExpectedException

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.utils import arp as arp_module
from provisioningserver.utils.arp import (
    add_arguments,
    ARP,
    ARP_OPERATION,
    run,
    SEEN_AGAIN_THRESHOLD,
    update_and_print_bindings,
    update_bindings_and_get_event,
)
from provisioningserver.utils.network import (
    format_eui,
    hex_str_to_bytes,
    ipv4_to_bytes,
)
from provisioningserver.utils.script import ActionScriptError


def make_arp_packet(
    sender_ip,
    sender_mac,
    target_ip,
    target_mac="00:00:00:00:00:00",
    op=ARP_OPERATION.REQUEST,
    hardware_type="0x0001",
    protocol="0x0800",
    hardware_length="0x06",
    protocol_length="0x04",
):
    # Concatenate a byte string with the specified values.
    # For ARP format, see: https://tools.ietf.org/html/rfc826
    arp_packet = (
        hex_str_to_bytes(hardware_type)
        + hex_str_to_bytes(protocol)
        + hex_str_to_bytes(hardware_length)
        + hex_str_to_bytes(protocol_length)
        + ARP_OPERATION(op)
        + hex_str_to_bytes(sender_mac)
        + ipv4_to_bytes(sender_ip)
        + hex_str_to_bytes(target_mac)
        + ipv4_to_bytes(target_ip)
    )
    return arp_packet


class TestARP(MAASTestCase):
    def test_operation_enum__str(self):
        self.expectThat(
            str(ARP_OPERATION(ARP_OPERATION.REQUEST)), Equals("1 (request)")
        )
        self.expectThat(
            str(ARP_OPERATION(ARP_OPERATION.REPLY)), Equals("2 (reply)")
        )
        self.expectThat(str(ARP_OPERATION(3)), Equals("3"))

    def test_operation_enum__bytes(self):
        self.expectThat(
            bytes(ARP_OPERATION(ARP_OPERATION.REQUEST)), Equals(b"\0\x01")
        )
        self.expectThat(
            bytes(ARP_OPERATION(ARP_OPERATION.REPLY)), Equals(b"\0\x02")
        )

    def test_operation_enum__radd(self):
        self.expectThat(
            b"\xff" + bytes(ARP_OPERATION(ARP_OPERATION.REPLY)) + b"\xff",
            Equals(b"\xff\0\x02\xff"),
        )

    def test_write(self):
        ts = int(time.time())
        expected_time = datetime.fromtimestamp(ts)
        pkt_sender_mac = "01:02:03:04:05:06"
        pkt_sender_ip = "192.168.0.1"
        pkt_target_ip = "192.168.0.2"
        pkt_target_mac = "00:00:00:00:00:00"
        eth_src = "02:03:04:05:06:07"
        eth_dst = "ff:ff:ff:ff:ff:ff"
        arp_packet = make_arp_packet(
            pkt_sender_ip, pkt_sender_mac, pkt_target_ip, pkt_target_mac
        )
        arp = ARP(
            arp_packet,
            time=ts,
            src_mac=hex_str_to_bytes(eth_src),
            dst_mac=hex_str_to_bytes(eth_dst),
            vid=100,
        )
        out = io.StringIO()
        arp.write(out)
        expected_output = dedent(
            """\
        ARP observed at {expected_time}:
           802.1q VLAN ID (VID): 100 (0x064)
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
        """
        )
        self.assertEqual(
            expected_output.format(**locals()).strip(),
            out.getvalue().strip(),
        )

    def test_is_valid__succeeds_for_normal_packet(self):
        arp_packet = make_arp_packet(
            "192.168.0.1", "01:02:03:04:05:06", "192.168.0.2"
        )
        arp = ARP(arp_packet)
        self.assertTrue(arp.is_valid())

    def test_is_valid__fails_for_invalid_packets(self):
        arp = ARP(b"\x00" * 28)
        self.assertFalse(arp.is_valid())
        arp = ARP(
            make_arp_packet(
                "192.168.0.1",
                "01:02:03:04:05:06",
                "192.168.0.2",
                hardware_type="0x0000",
            )
        )
        self.assertFalse(arp.is_valid())
        arp = ARP(
            make_arp_packet(
                "192.168.0.1",
                "01:02:03:04:05:06",
                "192.168.0.2",
                protocol="0x0000",
            )
        )
        self.assertFalse(arp.is_valid())
        arp = ARP(
            make_arp_packet(
                "192.168.0.1",
                "01:02:03:04:05:06",
                "192.168.0.2",
                hardware_length="0x00",
            )
        )
        self.assertFalse(arp.is_valid())
        arp = ARP(
            make_arp_packet(
                "192.168.0.1",
                "01:02:03:04:05:06",
                "192.168.0.2",
                protocol_length="0x00",
            )
        )
        self.assertFalse(arp.is_valid())

    def test_properties(self):
        pkt_sender_mac = "01:02:03:04:05:06"
        pkt_sender_ip = "192.168.0.1"
        pkt_target_ip = "192.168.0.2"
        pkt_target_mac = "00:00:00:00:00:00"
        eth_src = "02:03:04:05:06:07"
        eth_dst = "ff:ff:ff:ff:ff:ff"
        arp_packet = make_arp_packet(
            pkt_sender_ip, pkt_sender_mac, pkt_target_ip, pkt_target_mac
        )
        arp = ARP(
            arp_packet,
            src_mac=hex_str_to_bytes(eth_src),
            dst_mac=hex_str_to_bytes(eth_dst),
        )
        self.assertEqual(EUI(pkt_sender_mac), arp.source_eui)
        self.assertEqual(EUI(pkt_target_mac), arp.target_eui)
        self.assertEqual(IPAddress(pkt_sender_ip), arp.source_ip)
        self.assertEqual(IPAddress(pkt_target_ip), arp.target_ip)

    def test_bindings__returns_sender_for_request(self):
        pkt_sender_mac = "01:02:03:04:05:06"
        pkt_sender_ip = "192.168.0.1"
        pkt_target_ip = "192.168.0.2"
        pkt_target_mac = "00:00:00:00:00:00"
        arp = ARP(
            make_arp_packet(
                pkt_sender_ip,
                pkt_sender_mac,
                pkt_target_ip,
                pkt_target_mac,
                op=ARP_OPERATION.REQUEST,
            )
        )
        self.assertCountEqual(
            arp.bindings(), [(IPAddress(pkt_sender_ip), EUI(pkt_sender_mac))]
        )

    def test_bindings__returns_sender_and_target_for_reply(self):
        pkt_sender_mac = "01:02:03:04:05:06"
        pkt_sender_ip = "192.168.0.1"
        pkt_target_ip = "192.168.0.2"
        pkt_target_mac = "02:03:04:05:06:07"
        arp = ARP(
            make_arp_packet(
                pkt_sender_ip,
                pkt_sender_mac,
                pkt_target_ip,
                pkt_target_mac,
                op=ARP_OPERATION.REPLY,
            )
        )
        self.assertCountEqual(
            arp.bindings(),
            [
                (IPAddress(pkt_sender_ip), EUI(pkt_sender_mac)),
                (IPAddress(pkt_target_ip), EUI(pkt_target_mac)),
            ],
        )

    def test_bindings__skips_null_source_ip_for_request(self):
        pkt_sender_mac = "01:02:03:04:05:06"
        pkt_sender_ip = "0.0.0.0"
        pkt_target_ip = "192.168.0.2"
        pkt_target_mac = "00:00:00:00:00:00"
        arp = ARP(
            make_arp_packet(
                pkt_sender_ip,
                pkt_sender_mac,
                pkt_target_ip,
                pkt_target_mac,
                op=ARP_OPERATION.REQUEST,
            )
        )
        self.assertCountEqual(arp.bindings(), [])

    def test_bindings__skips_null_source_ip_in_reply(self):
        pkt_sender_mac = "01:02:03:04:05:06"
        pkt_sender_ip = "0.0.0.0"
        pkt_target_ip = "192.168.0.2"
        pkt_target_mac = "02:03:04:05:06:07"
        arp = ARP(
            make_arp_packet(
                pkt_sender_ip,
                pkt_sender_mac,
                pkt_target_ip,
                pkt_target_mac,
                op=ARP_OPERATION.REPLY,
            )
        )
        self.assertCountEqual(
            arp.bindings(), [(IPAddress(pkt_target_ip), EUI(pkt_target_mac))]
        )

    def test_bindings__skips_null_target_ip_in_reply(self):
        pkt_sender_mac = "01:02:03:04:05:06"
        pkt_sender_ip = "192.168.0.1"
        pkt_target_ip = "0.0.0.0"
        pkt_target_mac = "02:03:04:05:06:07"
        arp = ARP(
            make_arp_packet(
                pkt_sender_ip,
                pkt_sender_mac,
                pkt_target_ip,
                pkt_target_mac,
                op=ARP_OPERATION.REPLY,
            )
        )
        self.assertCountEqual(
            arp.bindings(), [(IPAddress(pkt_sender_ip), EUI(pkt_sender_mac))]
        )

    def test_bindings__skips_null_source_eui_for_request(self):
        pkt_sender_mac = "00:00:00:00:00:00"
        pkt_sender_ip = "192.168.0.1"
        pkt_target_ip = "192.168.0.2"
        pkt_target_mac = "00:00:00:00:00:00"
        arp = ARP(
            make_arp_packet(
                pkt_sender_ip,
                pkt_sender_mac,
                pkt_target_ip,
                pkt_target_mac,
                op=ARP_OPERATION.REQUEST,
            )
        )
        self.assertCountEqual(arp.bindings(), [])

    def test_bindings__skips_null_source_eui_in_reply(self):
        pkt_sender_mac = "00:00:00:00:00:00"
        pkt_sender_ip = "192.168.0.1"
        pkt_target_ip = "192.168.0.2"
        pkt_target_mac = "02:03:04:05:06:07"
        arp = ARP(
            make_arp_packet(
                pkt_sender_ip,
                pkt_sender_mac,
                pkt_target_ip,
                pkt_target_mac,
                op=ARP_OPERATION.REPLY,
            )
        )
        self.assertCountEqual(
            arp.bindings(), [(IPAddress(pkt_target_ip), EUI(pkt_target_mac))]
        )

    def test_bindings__skips_null_target_eui_in_reply(self):
        pkt_sender_mac = "01:02:03:04:05:06"
        pkt_sender_ip = "192.168.0.1"
        pkt_target_ip = "192.168.0.2"
        pkt_target_mac = "00:00:00:00:00:00"
        arp = ARP(
            make_arp_packet(
                pkt_sender_ip,
                pkt_sender_mac,
                pkt_target_ip,
                pkt_target_mac,
                op=ARP_OPERATION.REPLY,
            )
        )
        self.assertCountEqual(
            arp.bindings(), [(IPAddress(pkt_sender_ip), EUI(pkt_sender_mac))]
        )


class TestUpdateBindingsAndGetEvent(MAASTestCase):
    def test_new_binding(self):
        bindings = {}
        ip = IPAddress("192.168.0.1")
        mac = EUI("00:01:02:03:04:05")
        vid = None
        event = update_bindings_and_get_event(bindings, vid, ip, mac, 0)
        self.assertEqual({(vid, ip): {"mac": mac, "time": 0}}, bindings)
        self.assertThat(
            event,
            Equals(
                dict(
                    event="NEW",
                    ip=str(ip),
                    mac=format_eui(mac),
                    time=0,
                    vid=vid,
                )
            ),
        )

    def test_new_bindings_with_vid(self):
        bindings = {}
        ip = IPAddress("192.168.0.1")
        mac = EUI("00:01:02:03:04:05")
        vid = None
        event = update_bindings_and_get_event(bindings, vid, ip, mac, 0)
        self.assertEqual({(vid, ip): {"mac": mac, "time": 0}}, bindings)
        self.assertThat(
            event,
            Equals(
                dict(
                    event="NEW",
                    ip=str(ip),
                    mac=format_eui(mac),
                    time=0,
                    vid=vid,
                )
            ),
        )
        vid = 4095
        event = update_bindings_and_get_event(bindings, vid, ip, mac, 0)
        self.assertThat(
            bindings,
            Equals(
                {
                    (None, ip): {"mac": mac, "time": 0},
                    (4095, ip): {"mac": mac, "time": 0},
                }
            ),
        )
        self.assertThat(
            event,
            Equals(
                dict(
                    event="NEW",
                    ip=str(ip),
                    mac=format_eui(mac),
                    time=0,
                    vid=vid,
                )
            ),
        )

    def test_refreshed_binding(self):
        bindings = {}
        ip = IPAddress("192.168.0.1")
        mac = EUI("00:01:02:03:04:05")
        vid = None
        update_bindings_and_get_event(bindings, vid, ip, mac, 0)
        event = update_bindings_and_get_event(
            bindings, vid, ip, mac, SEEN_AGAIN_THRESHOLD
        )
        self.assertEqual(
            {(vid, ip): {"mac": mac, "time": SEEN_AGAIN_THRESHOLD}},
            bindings,
        )
        self.assertThat(
            event,
            Equals(
                dict(
                    event="REFRESHED",
                    ip=str(ip),
                    mac=format_eui(mac),
                    time=SEEN_AGAIN_THRESHOLD,
                    vid=vid,
                )
            ),
        )

    def test_refreshed_binding_within_threshold_does_not_emit_event(self):
        bindings = {}
        ip = IPAddress("192.168.0.1")
        mac = EUI("00:01:02:03:04:05")
        vid = None
        update_bindings_and_get_event(bindings, vid, ip, mac, 0)
        event = update_bindings_and_get_event(bindings, vid, ip, mac, 1)
        self.assertEqual({(vid, ip): {"mac": mac, "time": 0}}, bindings)
        self.assertIsNone(event)

    def test_moved_binding(self):
        bindings = {}
        ip = IPAddress("192.168.0.1")
        mac1 = EUI("00:01:02:03:04:05")
        mac2 = EUI("02:03:04:05:06:07")
        vid = None
        update_bindings_and_get_event(bindings, vid, ip, mac1, 0)
        event = update_bindings_and_get_event(bindings, vid, ip, mac2, 1)
        self.assertEqual({(vid, ip): {"mac": mac2, "time": 1}}, bindings)
        self.assertThat(
            event,
            Equals(
                dict(
                    event="MOVED",
                    ip=str(ip),
                    mac=format_eui(mac2),
                    time=1,
                    previous_mac=format_eui(mac1),
                    vid=vid,
                )
            ),
        )


class FakeARP:
    """Fake ARP packet used for testing the processing of bindings."""

    def __init__(self, mock_bindings, time=0, vid=None):
        self.mock_bindings = mock_bindings
        self.time = time
        self.vid = vid

    def bindings(self):
        yield from self.mock_bindings


class TestUpdateAndPrintBindings(MAASTestCase):
    def test_prints_bindings_in_json_format(self):
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
        self.assertEqual(
            {(None, ip): {"mac": mac2, "time": SEEN_AGAIN_THRESHOLD}},
            bindings,
        )
        output = io.StringIO(out.getvalue())
        lines = output.readlines()
        self.assertThat(lines, HasLength(3))
        line1 = json.loads(lines[0])
        self.assertThat(
            line1,
            Equals(
                {
                    "ip": str(ip),
                    "mac": format_eui(mac1),
                    "time": 0,
                    "event": "NEW",
                    "vid": None,
                }
            ),
        )
        line2 = json.loads(lines[1])
        self.assertThat(
            line2,
            Equals(
                {
                    "ip": str(ip),
                    "mac": format_eui(mac2),
                    "previous_mac": format_eui(mac1),
                    "time": 0,
                    "event": "MOVED",
                    "vid": None,
                }
            ),
        )
        line3 = json.loads(lines[2])
        self.assertThat(
            line3,
            Equals(
                {
                    "ip": str(ip),
                    "mac": format_eui(mac2),
                    "time": SEEN_AGAIN_THRESHOLD,
                    "event": "REFRESHED",
                    "vid": None,
                }
            ),
        )


# Test data expected from an input PCAP file.
test_input = (
    b"\xd4\xc3\xb2\xa1\x02\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"@\x00\x00\x00\x01\x00\x00\x00*\xdc\xa0W\x9e+\x03\x00<\x00\x00\x00"
    b"<\x00\x00\x00\x80\xfa[\x0cFN\x00$\xa5\xaf$\x85\x08\x06\x00\x01"
    b"\x08\x00\x06\x04\x00\x01\x00$\xa5\xaf$\x85\xac\x10*\x01\x00\x00\x00\x00"
    b"\x00\x00\xac\x10*m\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00*\xdc\xa0W\xbb+\x03\x00*\x00\x00\x00"
    b"*\x00\x00\x00\x00$\xa5\xaf$\x85\x80\xfa[\x0cFN\x08\x06\x00\x01"
    b"\x08\x00\x06\x04\x00\x02\x80\xfa[\x0cFN\xac\x10*m\x00$\xa5\xaf"
    b"$\x85\xac\x10*\x01"
)


class TestObserveARPCommand(MAASTestCase):
    """Tests for `maas-rack observe-arp`."""

    def test_requires_input_file(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args([])
        with ExpectedException(
            ActionScriptError, ".*Required argument: interface.*"
        ):
            run(args)

    def test_calls_subprocess_for_interface(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args(["eth0"])
        popen = self.patch(arp_module.subprocess, "Popen")
        popen.return_value.poll = Mock()
        popen.return_value.poll.return_value = None
        popen.return_value.stdout = io.BytesIO(test_input)
        output = io.StringIO()
        run(args, output=output)
        self.assertThat(
            popen,
            MockCalledOnceWith(
                ["sudo", "-n", "/usr/lib/maas/network-monitor", "eth0"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
            ),
        )

    def test_calls_subprocess_for_interface_sudo(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args(["eth0"])
        popen = self.patch(arp_module.subprocess, "Popen")
        popen.return_value.poll = Mock()
        popen.return_value.poll.return_value = None
        popen.return_value.stdout = io.BytesIO(test_input)
        output = io.StringIO()
        run(args, output=output)
        self.assertThat(
            popen,
            MockCalledOnceWith(
                ["sudo", "-n", "/usr/lib/maas/network-monitor", "eth0"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
            ),
        )

    def test_checks_for_pipe(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args(["--input-file", "-"])
        output = io.StringIO()
        stdin = self.patch(arp_module.sys, "stdin")
        stdin.return_value.fileno = Mock()
        fstat = self.patch(arp_module.os, "fstat")
        fstat.return_value.st_mode = None
        stat = self.patch(arp_module.stat, "S_ISFIFO")
        stat.return_value = False
        with ExpectedException(
            ActionScriptError, "Expected stdin to be a pipe"
        ):
            run(args, output=output)

    def test_allows_pipe_input(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args(["--input-file", "-"])
        output = io.StringIO()
        stdin = self.patch(arp_module.sys, "stdin")
        stdin.return_value.fileno = Mock()
        fstat = self.patch(arp_module.os, "fstat")
        fstat.return_value.st_mode = None
        stat = self.patch(arp_module.stat, "S_ISFIFO")
        stat.return_value = True
        stdin_buffer = io.BytesIO(test_input)
        run(args, output=output, stdin_buffer=stdin_buffer)

    def test_allows_file_input(self):
        with NamedTemporaryFile("wb") as f:
            parser = ArgumentParser()
            add_arguments(parser)
            f.write(test_input)
            f.flush()
            args = parser.parse_args(["--input-file", f.name])
            output = io.StringIO()
            run(args, output=output)

    def test_raises_systemexit_observe_arp_return_code(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args(["eth0"])
        popen = self.patch(arp_module.subprocess, "Popen")
        popen.return_value.poll = Mock()
        popen.return_value.poll.return_value = None
        popen.return_value.stdout = io.BytesIO(test_input)
        output = io.StringIO()
        observe_arp_packets = self.patch(arp_module, "observe_arp_packets")
        observe_arp_packets.return_value = 37
        with ExpectedException(SystemExit, ".*37.*"):
            run(args, output=output)

    def test_raises_systemexit_poll_result(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args(["eth0"])
        popen = self.patch(arp_module.subprocess, "Popen")
        popen.return_value.poll = Mock()
        popen.return_value.poll.return_value = None
        popen.return_value.stdout = io.BytesIO(test_input)
        output = io.StringIO()
        observe_arp_packets = self.patch(arp_module, "observe_arp_packets")
        observe_arp_packets.return_value = None
        popen.return_value.poll = Mock()
        popen.return_value.poll.return_value = 42
        with ExpectedException(SystemExit, ".*42.*"):
            run(args, output=output)

    def test_sets_self_as_process_group_leader(self):
        exception_type = factory.make_exception_type()
        os = self.patch(arp_module, "os")
        os.setpgrp.side_effect = exception_type
        self.assertRaises(exception_type, run, [])
        self.assertThat(os.setpgrp, MockCalledOnceWith())
