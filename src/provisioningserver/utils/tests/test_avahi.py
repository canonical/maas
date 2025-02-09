# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ``provisioningserver.utils.avahi``."""

from argparse import ArgumentParser
from contextlib import contextmanager
import io
import json
import subprocess
from tempfile import NamedTemporaryFile
import time

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils import avahi as avahi_module
from provisioningserver.utils.avahi import (
    add_arguments,
    parse_avahi_event,
    run,
    unescape_avahi_service_name,
)


class TestUnescapeAvahiServiceName(MAASTestCase):
    def test_converts_escaped_decimal_characters(self):
        result = unescape_avahi_service_name(
            "HP\\032Color\\032LaserJet\\032CP2025dn\\032\\040test\\041"
        )
        self.assertEqual("HP Color LaserJet CP2025dn (test)", result)

    def test_converts_escaped_backslash(self):
        result = unescape_avahi_service_name("\\\\\\\\samba\\\\share")
        self.assertEqual("\\\\samba\\share", result)

    def test_converts_escaped_dot(self):
        result = unescape_avahi_service_name("example\\.com")
        self.assertEqual("example.com", result)

    def test_converts_all_types_of_escape_sequences(self):
        result = unescape_avahi_service_name(
            "HP\\032Color\\032LaserJet\\032at"
            "\\032\\\\\\\\printers\\\\color\\032\\040example\\.com\\041"
        )
        self.assertEqual(
            "HP Color LaserJet at \\\\printers\\color (example.com)",
            result,
        )


class TestParseAvahiEvent(MAASTestCase):
    def test_parses_browser_new_event(self):
        input = (
            b"+;eth0;IPv4"
            b";HP\\032Color\\032LaserJet\\032CP2025dn\\032\\040test\\041;"
            b"_http._tcp;local"
        )
        event = parse_avahi_event(input)
        self.assertEqual(
            event,
            {
                "event": "BROWSER_NEW",
                "interface": "eth0",
                "protocol": "IPv4",
                "service_name": "HP Color LaserJet CP2025dn (test)",
                "type": "_http._tcp",
                "domain": "local",
            },
        )

    def test_parses_browser_removed_event(self):
        input = (
            b"-;eth0;IPv4"
            b";HP\\032Color\\032LaserJet\\032CP2025dn\\032\\040test\\041;"
            b"_http._tcp;local"
        )
        event = parse_avahi_event(input)
        self.assertEqual(
            event,
            {
                "event": "BROWSER_REMOVED",
                "interface": "eth0",
                "protocol": "IPv4",
                "service_name": "HP Color LaserJet CP2025dn (test)",
                "type": "_http._tcp",
                "domain": "local",
            },
        )

    def test_parses_resolver_found_event(self):
        input = (
            b"=;eth0;IPv4"
            b";HP\\032Color\\032LaserJet\\032CP2025dn\\032\\040test\\041;"
            b"_http._tcp;local;"
            b"printer.local;"
            b"192.168.0.222;"
            b"80;"
            b'"priority=50" "rp=RAW"'
        )
        event = parse_avahi_event(input)
        self.assertEqual(
            event,
            {
                "event": "RESOLVER_FOUND",
                "interface": "eth0",
                "protocol": "IPv4",
                "service_name": "HP Color LaserJet CP2025dn (test)",
                "type": "_http._tcp",
                "domain": "local",
                "address": "192.168.0.222",
                "fqdn": "printer.local",
                "hostname": "printer",
                "port": "80",
                "txt": b'"priority=50" "rp=RAW"',
            },
        )

    def test_parses_txt_binary(self):
        input = (
            b"=;eth0;IPv4"
            b";HP\\032Color\\032LaserJet\\032CP2025dn\\032\\040test\\041;"
            b"_http._tcp;local;"
            b"printer.local;"
            b"192.168.0.222;"
            b"80;"
            b'"BluetoothAddress=\xc8i\xcdB\xe2\x09"'
        )
        event = parse_avahi_event(input)
        self.assertEqual(
            b'"BluetoothAddress=\xc8i\xcdB\xe2\x09"', event["txt"]
        )

    def test_returns_none_for_malformed_input(self):
        self.assertIsNone(parse_avahi_event(b";;;"))


def observe_mdns(*, input, output, verbose=False):
    """Print avahi hostname bindings on stdout.

    This is a backwards-compatibility shim to aid testing.
    """

    @contextmanager
    def reader():
        yield input

    return avahi_module._observe_mdns(reader(), output, verbose=verbose)


class TestObserveMDNS(MAASTestCase):
    def test_prints_event_json_in_verbose_mode(self):
        out = io.StringIO()
        input = (
            b"+;eth0;IPv4"
            b";HP\\032Color\\032LaserJet\\032CP2025dn\\032\\040test\\041;"
            b"_http._tcp;local\n"
        )
        expected_result = {
            "event": "BROWSER_NEW",
            "interface": "eth0",
            "protocol": "IPv4",
            "service_name": "HP Color LaserJet CP2025dn (test)",
            "type": "_http._tcp",
            "domain": "local",
        }
        observe_mdns(verbose=True, input=[input], output=out)
        output = io.StringIO(out.getvalue())
        lines = output.readlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(expected_result, json.loads(lines[0]))

    def test_skips_unimportant_events_without_verbose_enabled(self):
        out = io.StringIO()
        input = (
            b"+;eth0;IPv4"
            b";HP\\032Color\\032LaserJet\\032CP2025dn\\032\\040test\\041;"
            b"_http._tcp;local\n"
        )
        observe_mdns(verbose=False, input=[input], output=out)
        output = io.StringIO(out.getvalue())
        lines = output.readlines()
        self.assertEqual(len(lines), 0)

    def test_non_verbose_removes_redundant_events_and_outputs_summary(self):
        out = io.StringIO()
        input = (
            b"=;eth0;IPv4"
            b";HP\\032Color\\032LaserJet\\032CP2025dn\\032\\040test\\041;"
            b"_http._tcp;local;"
            b"printer.local;"
            b"192.168.0.222;"
            b"80;"
            b'"priority=50" "rp=RAW"\n'
        )
        observe_mdns(verbose=False, input=[input, input], output=out)
        output = io.StringIO(out.getvalue())
        lines = output.readlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(
            json.loads(lines[0]),
            {
                "interface": "eth0",
                "address": "192.168.0.222",
                "hostname": "printer",
            },
        )

    def test_non_verbose_removes_waits_before_emitting_duplicate_entry(self):
        out = io.StringIO()
        input = (
            b"=;eth0;IPv4"
            b";HP\\032Color\\032LaserJet\\032CP2025dn\\032\\040test\\041;"
            b"_http._tcp;local;"
            b"printer.local;"
            b"192.168.0.222;"
            b"80;"
            b'"priority=50" "rp=RAW"\n'
        )
        # If we see the same entry 3 times over the course of 15 minutes, we
        # should only see output two out of the three times.
        self.patch(time, "monotonic").side_effect = (100.0, 200.0, 900.0)
        observe_mdns(verbose=False, input=[input, input, input], output=out)
        output = io.StringIO(out.getvalue())
        lines = output.readlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(
            json.loads(lines[0]),
            {
                "interface": "eth0",
                "address": "192.168.0.222",
                "hostname": "printer",
            },
        )
        self.assertEqual(
            json.loads(lines[1]),
            {
                "interface": "eth0",
                "address": "192.168.0.222",
                "hostname": "printer",
            },
        )


class TestObserveMDNSCommand(MAASTestCase):
    """Tests for `maas-rack observe-mdns`."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_input_bytes = (
            b"=;eth0;IPv4"
            b";HP\\032Color\\032LaserJet\\032CP2025dn\\032\\040test\\041;"
            b"_http._tcp;local;"
            b"printer.local;"
            b"192.168.0.222;"
            b"80;"
            b'"priority=50" "rp=RAW"\n'
        )

    def test_calls_subprocess_by_default(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args([])
        popen = self.patch(avahi_module.subprocess, "Popen")
        popen.return_value.stdout = io.BytesIO(self.test_input_bytes)
        popen.return_value.wait.return_value = 0
        popen.return_value.returncode = 0
        output = io.StringIO()
        run(args, output=output)
        popen.assert_called_once_with(
            [
                "/usr/bin/avahi-browse",
                "--all",
                "--resolve",
                "--no-db-lookup",
                "--parsable",
                "--no-fail",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
        )

    def test_allows_pipe_input(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args(["--input-file", "-"])
        output = io.StringIO()
        run(args, output=output, stdin=[self.test_input_bytes])
        self.assertGreater(len(output.getvalue()), 0)

    def test_allows_file_input(self):
        with NamedTemporaryFile("wb") as f:
            parser = ArgumentParser()
            add_arguments(parser)
            f.write(self.test_input_bytes)
            f.flush()
            args = parser.parse_args(["--input-file", f.name])
            output = io.StringIO()
            run(args, output=output)

    def test_raises_systemexit(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args([])
        popen = self.patch(avahi_module.subprocess, "Popen")
        popen.return_value.wait.return_value = 42
        popen.return_value.returncode = 42
        popen.return_value.stdout = io.BytesIO(self.test_input_bytes)
        output = io.StringIO()
        with self.assertRaisesRegex(SystemExit, ".*42.*"):
            run(args, output=output)

    def test_sets_self_as_process_group_leader(self):
        exception_type = factory.make_exception_type()
        os = self.patch(avahi_module, "os")
        os.setpgrp.side_effect = exception_type
        self.assertRaises(exception_type, run, [])
        os.setpgrp.assert_called_once_with()
