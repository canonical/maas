# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the omshell.py file."""

import base64
import subprocess
from textwrap import dedent
from unittest.mock import ANY, Mock

from testtools.matchers import MatchesStructure

from maastesting.factory import factory
from maastesting.fakemethod import FakeMethod
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.dhcp.omshell import generate_omapi_key, Omshell
from provisioningserver.utils.shell import ExternalProcessError


class TestOmshell(MAASTestCase):

    scenarios = (
        ("IPv4", {"ipv6": False, "port": 7911}),
        ("IPv6", {"ipv6": True, "port": 7912}),
    )

    def test_initialisation(self):
        server_address = factory.make_string()
        shared_key = factory.make_string()
        shell = Omshell(server_address, shared_key)
        self.assertThat(
            shell,
            MatchesStructure.byEquality(
                server_address=server_address, shared_key=shared_key
            ),
        )

    def test_try_connection_calls_omshell_correctly(self):
        server_address = factory.make_string()
        shell = Omshell(server_address, "", ipv6=self.ipv6)

        # Instead of calling a real omshell, we'll just record the
        # parameters passed to Popen.
        recorder = FakeMethod(result=(0, b"obj: <null>"))
        shell._run = recorder

        shell.try_connection()

        expected_script = dedent(
            """\
            server {server}
            port {port}
            connect
            """
        )
        expected_script = expected_script.format(
            server=server_address, port=self.port
        )

        # Check that the 'stdin' arg contains the correct set of
        # commands.
        self.assertEqual(
            [1, (expected_script.encode("utf-8"),)],
            [recorder.call_count, recorder.extract_args()[0]],
        )

    def test_try_connection_returns_True(self):
        server_address = factory.make_string()
        shell = Omshell(server_address, "", ipv6=self.ipv6)

        # Instead of calling a real omshell, we'll just record the
        # parameters passed to Popen.
        recorder = FakeMethod(result=(0, b"obj: <null>"))
        shell._run = recorder

        self.assertTrue(shell.try_connection())

    def test_try_connection_returns_False(self):
        server_address = factory.make_string()
        shell = Omshell(server_address, "", ipv6=self.ipv6)

        # Instead of calling a real omshell, we'll just record the
        # parameters passed to Popen.
        recorder = FakeMethod(result=(0, factory.make_bytes()))
        shell._run = recorder

        self.assertFalse(shell.try_connection())

    def test_create_calls_omshell_correctly(self):
        server_address = factory.make_string()
        shared_key = factory.make_string()
        ip_address = factory.make_ip_address(ipv6=self.ipv6)
        mac_address = factory.make_mac_address()
        shell = Omshell(server_address, shared_key, ipv6=self.ipv6)

        # Instead of calling a real omshell, we'll just record the
        # parameters passed to Popen.
        recorder = FakeMethod(result=(0, b"hardware-type"))
        shell._run = recorder

        shell.create(ip_address, mac_address)

        expected_script = dedent(
            """\
            server {server}
            port {port}
            key omapi_key {key}
            connect
            new host
            set ip-address = {ip}
            set hardware-address = {mac}
            set hardware-type = 1
            set name = "{name}"
            create
            """
        )
        expected_script = expected_script.format(
            server=server_address,
            port=self.port,
            key=shared_key,
            ip=ip_address,
            mac=mac_address,
            name=mac_address.replace(":", "-"),
        )

        # Check that the 'stdin' arg contains the correct set of
        # commands.
        self.assertEqual(
            [1, (expected_script.encode("utf-8"),)],
            [recorder.call_count, recorder.extract_args()[0]],
        )

    def test_create_raises_when_omshell_fails(self):
        # If the call to omshell doesn't result in output containing the
        # magic string 'hardware-type' it means the set of commands
        # failed.

        server_address = factory.make_string()
        shared_key = factory.make_string()
        ip_address = factory.make_ip_address(ipv6=self.ipv6)
        mac_address = factory.make_mac_address()
        shell = Omshell(server_address, shared_key, ipv6=self.ipv6)

        # Fake a call that results in a failure with random output.
        random_output = factory.make_bytes()
        recorder = FakeMethod(result=(0, random_output))
        shell._run = recorder

        exc = self.assertRaises(
            ExternalProcessError, shell.create, ip_address, mac_address
        )
        self.assertEqual(random_output, exc.output)

    def test_create_succeeds_when_host_map_already_exists(self):
        # To omshell, creating the same host map twice is an error.  But
        # Omshell.create swallows the error and makes it look like
        # success.
        params = {
            "ip": factory.make_ip_address(ipv6=self.ipv6),
            "mac": factory.make_mac_address(),
            "hostname": factory.make_name("hostname"),
        }
        shell = Omshell(
            factory.make_name("server"),
            factory.make_name("key"),
            ipv6=self.ipv6,
        )
        # This is the kind of error output we get if a host map has
        # already been created.
        error_output = (
            dedent(
                """\
            obj: host
            ip-address = %(ip)s
            hardware-address = %(mac)s
            name = "%(hostname)s"
            >
            can't open object: I/O error
            obj: host
            ip-address = %(ip)s
            hardware-address = %(mac)s
            name = "%(hostname)s"
            """
            )
            % params
        )
        shell._run = Mock(return_value=(0, error_output.encode("ascii")))
        shell.create(params["ip"], params["mac"])
        # The test is that we get here without error.
        pass

    def test_modify_calls_omshell_correctly(self):
        server_address = factory.make_string()
        shared_key = factory.make_string()
        ip_address = factory.make_ip_address(ipv6=self.ipv6)
        mac_address = factory.make_mac_address()
        shell = Omshell(server_address, shared_key, ipv6=self.ipv6)

        # Instead of calling a real omshell, we'll just record the
        # parameters passed to Popen.
        recorder = FakeMethod(result=(0, b"hardware-type"))
        shell._run = recorder

        shell.modify(ip_address, mac_address)

        expected_script = dedent(
            """\
            server {server}
            key omapi_key {key}
            connect
            new host
            set name = "{name}"
            open
            set ip-address = {ip}
            set hardware-address = {mac}
            set hardware-type = 1
            update
            """
        )
        expected_script = expected_script.format(
            server=server_address,
            key=shared_key,
            ip=ip_address,
            mac=mac_address,
            name=mac_address.replace(":", "-"),
        )

        # Check that the 'stdin' arg contains the correct set of
        # commands.
        self.assertEqual(
            [1, (expected_script.encode("utf-8"),)],
            [recorder.call_count, recorder.extract_args()[0]],
        )

    def test_modify_raises_when_omshell_fails(self):
        # If the call to omshell doesn't result in output containing the
        # magic string 'hardware-type' it means the set of commands
        # failed.

        server_address = factory.make_string()
        shared_key = factory.make_string()
        ip_address = factory.make_ip_address(ipv6=self.ipv6)
        mac_address = factory.make_mac_address()
        shell = Omshell(server_address, shared_key, ipv6=self.ipv6)

        # Fake a call that results in a failure with random output.
        random_output = factory.make_bytes()
        recorder = FakeMethod(result=(0, random_output))
        shell._run = recorder

        exc = self.assertRaises(
            ExternalProcessError, shell.modify, ip_address, mac_address
        )
        self.assertEqual(random_output, exc.output)

    def test_remove_calls_omshell_correctly(self):
        server_address = factory.make_string()
        shared_key = factory.make_string()
        mac_address = factory.make_mac_address()
        shell = Omshell(server_address, shared_key, ipv6=self.ipv6)

        # Instead of calling a real omshell, we'll just record the
        # parameters passed to Popen.
        recorder = FakeMethod(result=(0, b"thing1\nthing2\nobj: <null>"))
        shell._run = recorder

        shell.remove(mac_address)

        expected_script = dedent(
            """\
            server {server}
            port {port}
            key omapi_key {key}
            connect
            new host
            set name = "{mac}"
            open
            remove
            """
        ).format(
            server=server_address,
            port=self.port,
            key=shared_key,
            mac=mac_address.replace(":", "-"),
        )
        expected_results = (expected_script.encode("utf-8"),)

        # Check that the 'stdin' arg contains the correct set of
        # commands.
        self.assertEqual([expected_results], recorder.extract_args())

    def test_remove_raises_when_omshell_fails(self):
        # If the call to omshell doesn't result in output ending in the
        # text 'obj: <null>' we can be fairly sure this operation
        # failed.
        server_address = factory.make_string()
        shared_key = factory.make_string()
        ip_address = factory.make_ip_address(ipv6=self.ipv6)
        shell = Omshell(server_address, shared_key, ipv6=self.ipv6)

        # Fake a call that results in a failure with random output.
        random_output = factory.make_bytes()
        recorder = FakeMethod(result=(0, random_output))
        shell._run = recorder

        exc = self.assertRaises(
            subprocess.CalledProcessError, shell.remove, ip_address
        )
        self.assertEqual(random_output, exc.output)

    def test_remove_works_when_extraneous_blank_last_lines(self):
        # Sometimes omshell puts blank lines after the 'obj: <null>' so
        # we need to test that the code still works if that's the case.
        server_address = factory.make_string()
        shared_key = factory.make_string()
        ip_address = factory.make_ip_address(ipv6=self.ipv6)
        shell = Omshell(server_address, shared_key, ipv6=self.ipv6)

        # Fake a call that results in a something with our special output.
        output = b"\n> obj: <null>\n\n"
        self.patch(shell, "_run").return_value = (0, output)
        self.assertIsNone(shell.remove(ip_address))

    def test_remove_works_when_extraneous_gt_char_present(self):
        # Sometimes omshell puts a leading '>' character in responses.
        # We need to test that the code still works if that's the case.
        server_address = factory.make_string()
        shared_key = factory.make_string()
        ip_address = factory.make_ip_address(ipv6=self.ipv6)
        shell = Omshell(server_address, shared_key, ipv6=self.ipv6)

        # Fake a call that results in a something with our special output.
        output = b"\n>obj: <null>\n>\n"
        self.patch(shell, "_run").return_value = (0, output)
        self.assertIsNone(shell.remove(ip_address))

    def test_remove_works_when_object_already_removed(self):
        server_address = factory.make_string()
        shared_key = factory.make_string()
        ip_address = factory.make_ip_address(ipv6=self.ipv6)
        shell = Omshell(server_address, shared_key, ipv6=self.ipv6)

        output = b"obj: <null>\nobj: host\ncan't open object: not found\n"
        self.patch(shell, "_run").return_value = (0, output)
        self.assertIsNone(shell.remove(ip_address))


class Test_Omshell_nullify_lease(MAASTestCase):
    """Tests for Omshell.nullify_lease"""

    scenarios = (
        ("IPv4", {"ipv6": False, "port": 7911}),
        ("IPv6", {"ipv6": True, "port": 7912}),
    )

    def test_calls_omshell_correctly(self):
        server_address = factory.make_string()
        shared_key = factory.make_string()
        ip_address = factory.make_ip_address(ipv6=self.ipv6)
        shell = Omshell(server_address, shared_key, ipv6=self.ipv6)

        # Instead of calling a real omshell, we'll just record the
        # parameters passed to Popen.
        run = self.patch(shell, "_run")
        run.return_value = (0, b"\nends = 00:00:00:00")
        expected_script = dedent(
            """\
            server {server}
            port {port}
            key omapi_key {key}
            connect
            new lease
            set ip-address = {ip}
            open
            set ends = 00:00:00:00
            update
            """
        )
        expected_script = expected_script.format(
            server=server_address,
            port=self.port,
            key=shared_key,
            ip=ip_address,
        )
        shell.nullify_lease(ip_address)
        self.assertThat(
            run, MockCalledOnceWith(expected_script.encode("utf-8"))
        )

    def test_considers_nonexistent_lease_a_success(self):
        server_address = factory.make_string()
        shared_key = factory.make_string()
        ip_address = factory.make_ip_address(ipv6=self.ipv6)
        shell = Omshell(server_address, shared_key, ipv6=self.ipv6)

        output = (
            b"obj: <null>\nobj: lease\nobj: lease\n"
            b"can't open object: not found\nobj: lease\n"
        )
        self.patch(shell, "_run").return_value = (0, output)
        shell.nullify_lease(ip_address)  # No exception.
        self.assertThat(shell._run, MockCalledOnceWith(ANY))

    def test_catches_invalid_error(self):
        server_address = factory.make_string()
        shared_key = factory.make_string()
        ip_address = factory.make_ip_address(ipv6=self.ipv6)
        shell = Omshell(server_address, shared_key, ipv6=self.ipv6)

        output = b"obj: <null>\nobj: lease\ninvalid value."
        self.patch(shell, "_run").return_value = (0, output)
        self.assertRaises(
            ExternalProcessError, shell.nullify_lease, ip_address
        )

    def test_catches_failed_update(self):
        server_address = factory.make_string()
        shared_key = factory.make_string()
        ip_address = factory.make_ip_address(ipv6=self.ipv6)
        shell = Omshell(server_address, shared_key, ipv6=self.ipv6)

        # make "ends" different to what we asked, so the post-run check
        # should fail.
        output = dedent(
            """\
            obj: <null>
            obj: lease
            obj: lease
            ip-address = 0a:00:00:72
            state = 00:00:00:01
            subnet = 00:00:00:03
            pool = 00:00:00:04
            hardware-address = 00:16:3e:06:45:5e
            hardware-type = 00:00:00:01
            ends = 00:00:00:FF
            starts = "T@v'"
            tstp = 54:41:1e:e7
            tsfp = 00:00:00:00
            atsfp = 00:00:00:00
            cltt = "T@v'"
            flags = 00
            """
        ).encode("ascii")
        self.patch(shell, "_run").return_value = (0, output)
        self.assertRaises(
            ExternalProcessError, shell.nullify_lease, ip_address
        )


class Test_generate_omapi_key(MAASTestCase):
    def test_generate_key(self):
        key = generate_omapi_key()
        self.assertEqual(len(base64.decodebytes(key.encode("ascii"))), 64)
