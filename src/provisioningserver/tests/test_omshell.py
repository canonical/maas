# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the omshell.py file."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import os
from subprocess import CalledProcessError
import tempfile
from textwrap import dedent

from fixtures import TempDir
from maastesting.factory import factory
from maastesting.fakemethod import FakeMethod
from maastesting.testcase import TestCase
from provisioningserver import omshell
from provisioningserver.omshell import (
    generate_omapi_key,
    Omshell,
    )
from testtools.matchers import (
    EndsWith,
    MatchesStructure,
    )


class TestOmshell(TestCase):

    def test_initialisation(self):
        server_address = factory.getRandomString()
        shared_key = factory.getRandomString()
        shell = Omshell(server_address, shared_key)
        self.assertThat(
            shell, MatchesStructure.byEquality(
                server_address=server_address,
                shared_key=shared_key))

    def test_create_calls_omshell_correctly(self):
        server_address = factory.getRandomString()
        shared_key = factory.getRandomString()
        ip_address = factory.getRandomIPAddress()
        mac_address = factory.getRandomMACAddress()
        shell = Omshell(server_address, shared_key)

        # Instead of calling a real omshell, we'll just record the
        # parameters passed to Popen.
        recorder = FakeMethod(result=(0, "hardware-type"))
        shell._run = recorder

        shell.create(ip_address, mac_address)

        expected_args = (dedent("""\
            server {server}
            key omapi_key {key}
            connect
            new host
            set ip-address = {ip}
            set hardware-address = {mac}
            set name = {ip}
            create
            """).format(
                server=server_address,
                key=shared_key,
                ip=ip_address,
                mac=mac_address),)

        # Check that the 'stdin' arg contains the correct set of
        # commands.
        self.assertEqual(
            [1, expected_args],
            [recorder.call_count, recorder.extract_args()[0]])

    def test_create_raises_when_omshell_fails(self):
        # If the call to omshell doesn't result in output containing the
        # magic string 'hardware-type' it means the set of commands
        # failed.

        server_address = factory.getRandomString()
        shared_key = factory.getRandomString()
        ip_address = factory.getRandomIPAddress()
        mac_address = factory.getRandomMACAddress()
        shell = Omshell(server_address, shared_key)

        # Fake a call that results in a failure with random output.
        random_output = factory.getRandomString()
        recorder = FakeMethod(result=(0, random_output))
        shell._run = recorder

        exc = self.assertRaises(
            CalledProcessError, shell.create, ip_address, mac_address)
        self.assertEqual(random_output, exc.output)

    def test_remove_calls_omshell_correctly(self):
        server_address = factory.getRandomString()
        shared_key = factory.getRandomString()
        ip_address = factory.getRandomIPAddress()
        shell = Omshell(server_address, shared_key)

        # Instead of calling a real omshell, we'll just record the
        # parameters passed to Popen.
        recorder = FakeMethod(result=(0, "thing1\nthing2\nobj: <null>"))
        shell._run = recorder

        shell.remove(ip_address)

        expected_args = (dedent("""\
            server {server}
            key omapi_key {key}
            connect
            new host
            set name = {ip}
            open
            remove
            """).format(
                server=server_address,
                key=shared_key,
                ip=ip_address),)

        # Check that the 'stdin' arg contains the correct set of
        # commands.
        self.assertEqual([expected_args], recorder.extract_args())

    def test_remove_raises_when_omshell_fails(self):
        # If the call to omshell doesn't result in output ending in the
        # text 'obj: <null>' we can be fairly sure this operation
        # failed.
        server_address = factory.getRandomString()
        shared_key = factory.getRandomString()
        ip_address = factory.getRandomIPAddress()
        shell = Omshell(server_address, shared_key)

        # Fake a call that results in a failure with random output.
        random_output = factory.getRandomString()
        recorder = FakeMethod(result=(0, random_output))
        shell._run = recorder

        exc = self.assertRaises(
            CalledProcessError, shell.remove, ip_address)
        self.assertEqual(random_output, exc.output)


class Test_generate_omapi_key(TestCase):
    """Tests for omshell.generate_omapi_key"""

    def test_generate_omapi_key_returns_a_key(self):
        key = generate_omapi_key()
        # Could test for != None here, but the keys end in == for a 512
        # bit length key, so that's a better check that the script was
        # actually run and produced output.
        self.assertThat(key, EndsWith("=="))

    def test_generate_omapi_key_leaves_no_temp_files(self):
        tmpdir = self.useFixture(TempDir()).path
        # Make mkdtemp() in omshell nest all directories within tmpdir.
        self.patch(tempfile, 'tempdir', tmpdir)
        generate_omapi_key()
        self.assertEqual([], os.listdir(tmpdir))

    def test_generate_omapi_key_raises_assertionerror_on_no_output(self):
        self.patch(omshell, 'call_dnssec_keygen', FakeMethod())
        self.assertRaises(AssertionError, generate_omapi_key)

    def test_generate_omapi_key_raises_assertionerror_on_bad_output(self):
        def returns_junk(tmpdir):
            key_name = factory.getRandomString()
            factory.make_file(tmpdir, "%s.private" % key_name)
            return key_name

        self.patch(omshell, 'call_dnssec_keygen', returns_junk)
        self.assertRaises(AssertionError, generate_omapi_key)
