# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ``provisioningserver.utils.beaconing``."""

__all__ = []

from argparse import ArgumentParser
import io
import subprocess
from tempfile import NamedTemporaryFile
from unittest.mock import Mock

from bson import BSON
from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.utils import beaconing as beaconing_module
from provisioningserver.utils.beaconing import (
    add_arguments,
    BeaconingPacket,
    run,
)
from provisioningserver.utils.script import ActionScriptError
from testtools.testcase import ExpectedException


def make_beaconing_packet(payload):
    # Beaconing packets are BSON-encoded byte strings.
    beaconing_packet = BSON.encode(payload)
    return beaconing_packet


class TestBeaconingPacket(MAASTestCase):

    def test__is_valid__succeeds_for_valid_bson(self):
        packet = make_beaconing_packet({"testing": 123})
        beacon = BeaconingPacket(packet)
        self.assertTrue(beacon.valid)

    def test__is_valid__fails_for_invalid_bson(self):
        beacon = BeaconingPacket(b"\n\n\n\n")
        self.assertFalse(beacon.valid)


BEACON_PCAP = (
    b'\xd4\xc3\xb2\xa1\x02\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    b'\x00@\x00\x00\x01\x00\x00\x00v\xe19Y\xadF\x08\x00^\x00\x00\x00^\x00\x00'
    b'\x00\x01\x00^\x00\x00v\x00\x16>\x91zz\x08\x00E\x00\x00P\xe2E@\x00\x01'
    b'\x11\xe0\xce\xac\x10*\x02\xe0\x00\x00v\xda\xc2\x14x\x00<h(4\x00\x00\x00'
    b'\x02uuid\x00%\x00\x00\x0078d1a4f0-4ca4-11e7-b2bb-00163e917a7a\x00\x00')


class TestObserveBeaconsCommand(MAASTestCase):
    """Tests for `maas-rack observe-beacons`."""

    def test__requires_input_file(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args([])
        with ExpectedException(
                ActionScriptError, '.*Required argument: interface.*'):
            run(args)

    def test__calls_subprocess_for_interface(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args(['eth0'])
        popen = self.patch(beaconing_module.subprocess, 'Popen')
        popen.return_value.poll = Mock()
        popen.return_value.poll.return_value = None
        popen.return_value.stdout = io.BytesIO(BEACON_PCAP)
        output = io.StringIO()
        run(args, output=output)
        self.assertThat(
            popen,
            MockCalledOnceWith(
                ['sudo', '-n', '/usr/lib/maas/maas-beacon-monitor', 'eth0'],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE))

    def test__calls_subprocess_for_interface_sudo(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args(['eth0'])
        popen = self.patch(beaconing_module.subprocess, 'Popen')
        popen.return_value.poll = Mock()
        popen.return_value.poll.return_value = None
        popen.return_value.stdout = io.BytesIO(BEACON_PCAP)
        output = io.StringIO()
        run(args, output=output)
        self.assertThat(
            popen,
            MockCalledOnceWith(
                ['sudo', '-n', '/usr/lib/maas/maas-beacon-monitor', 'eth0'],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE))

    def test__checks_for_pipe(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args(['--input-file', '-'])
        output = io.StringIO()
        stdin = self.patch(beaconing_module.sys, 'stdin')
        stdin.return_value.fileno = Mock()
        fstat = self.patch(beaconing_module.os, 'fstat')
        fstat.return_value.st_mode = None
        stat = self.patch(beaconing_module.stat, 'S_ISFIFO')
        stat.return_value = False
        with ExpectedException(
                ActionScriptError, 'Expected stdin to be a pipe'):
            run(args, output=output)

    def test__allows_pipe_input(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args(['--input-file', '-'])
        output = io.StringIO()
        stdin = self.patch(beaconing_module.sys, 'stdin')
        stdin.return_value.fileno = Mock()
        fstat = self.patch(beaconing_module.os, 'fstat')
        fstat.return_value.st_mode = None
        stat = self.patch(beaconing_module.stat, 'S_ISFIFO')
        stat.return_value = True
        stdin_buffer = io.BytesIO(BEACON_PCAP)
        run(args, output=output, stdin_buffer=stdin_buffer)

    def test__allows_file_input(self):
        with NamedTemporaryFile('wb') as f:
            parser = ArgumentParser()
            add_arguments(parser)
            f.write(BEACON_PCAP)
            f.flush()
            args = parser.parse_args(['--input-file', f.name])
            output = io.StringIO()
            run(args, output=output)

    def test__raises_systemexit_observe_beaconing_return_code(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args(['eth0'])
        popen = self.patch(beaconing_module.subprocess, 'Popen')
        popen.return_value.poll = Mock()
        popen.return_value.poll.return_value = None
        popen.return_value.stdout = io.BytesIO(BEACON_PCAP)
        output = io.StringIO()
        observe_beaconing_packets = self.patch(
            beaconing_module, 'observe_beaconing_packets')
        observe_beaconing_packets.return_value = 37
        with ExpectedException(
                SystemExit, '.*37.*'):
            run(args, output=output)

    def test__raises_systemexit_poll_result(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args(['eth0'])
        popen = self.patch(beaconing_module.subprocess, 'Popen')
        popen.return_value.poll = Mock()
        popen.return_value.poll.return_value = None
        popen.return_value.stdout = io.BytesIO(BEACON_PCAP)
        output = io.StringIO()
        observe_beaconing_packets = self.patch(
            beaconing_module, 'observe_beaconing_packets')
        observe_beaconing_packets.return_value = None
        popen.return_value.poll = Mock()
        popen.return_value.poll.return_value = 42
        with ExpectedException(
                SystemExit, '.*42.*'):
            run(args, output=output)

    def test__sets_self_as_process_group_leader(self):
        exception_type = factory.make_exception_type()
        os = self.patch(beaconing_module, "os")
        os.setpgrp.side_effect = exception_type
        self.assertRaises(exception_type, run, [])
        self.assertThat(os.setpgrp, MockCalledOnceWith())
