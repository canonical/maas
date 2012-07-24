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

from subprocess import CalledProcessError

from maastesting.factory import factory
from maastesting.fakemethod import FakeMethod
from maastesting.testcase import TestCase
from provisioningserver.omshell import Omshell
from testtools.matchers import MatchesStructure


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
        # parameters passed to 'check_call'.
        recorder = FakeMethod(result=("hardware-type", None))
        self.patch(shell.proc, 'communicate', recorder)

        shell.create(ip_address, mac_address)

        expected_args = (
            "server %(server)s\n"
            "key omapi_key %(key)s\n"
            "connect\n"
            "new host\n"
            "set ip-address = %(ip)s\n"
            "set hardware-address = %(mac)s\n"
            "set name = %(ip)s\n"
            "create\n" % dict(
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
        recorder = FakeMethod(result=(random_output, None))
        self.patch(shell.proc, 'communicate', recorder)

        exc = self.assertRaises(
            CalledProcessError, shell.create, ip_address, mac_address)
        self.assertEqual(random_output, exc.output)

    def test_remove_calls_omshell_correctly(self):
        server_address = factory.getRandomString()
        shared_key = factory.getRandomString()
        ip_address = factory.getRandomIPAddress()
        shell = Omshell(server_address, shared_key)

        # Instead of calling a real omshell, we'll just record the
        # parameters passed to 'check_call'.
        recorder = FakeMethod(result=("thing1\nthing2\nobj: <null>", None))
        self.patch(shell.proc, 'communicate', recorder)

        shell.remove(ip_address)

        expected_args = (
            "server %(server)s\n"
            "key omapi_key %(key)s\n"
            "connect\n"
            "new host\n"
            "set name = %(ip)s\n"
            "open\n"
            "remove\n" % dict(
                server=server_address,
                key=shared_key,
                ip=ip_address),)

        # Check that the 'stdin' arg contains the correct set of
        # commands.
        self.assertEqual(
            [1, expected_args],
            [recorder.call_count, recorder.extract_args()[0]])

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
        recorder = FakeMethod(result=(random_output, None))
        self.patch(shell.proc, 'communicate', recorder)

        exc = self.assertRaises(
            CalledProcessError, shell.remove, ip_address)
        self.assertEqual(random_output, exc.output)
