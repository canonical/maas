# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the omshell.py file."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from itertools import product
import os
import subprocess
import tempfile
from textwrap import dedent

from maastesting.factory import factory
from maastesting.fakemethod import FakeMethod
from maastesting.fixtures import TempDirectory
from maastesting.testcase import MAASTestCase
from mock import (
    ANY,
    Mock,
    )
from provisioningserver import omshell
import provisioningserver.omshell
from provisioningserver.omshell import (
    call_dnssec_keygen,
    generate_omapi_key,
    Omshell,
    )
from provisioningserver.utils import ExternalProcessError
from testtools.matchers import (
    EndsWith,
    MatchesStructure,
    )


class TestOmshell(MAASTestCase):

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

        expected_script = dedent("""\
            server {server}
            key omapi_key {key}
            connect
            new host
            set ip-address = {ip}
            set hardware-address = {mac}
            set hardware-type = 1
            set name = "{ip}"
            create
            """)
        expected_script = expected_script.format(
            server=server_address, key=shared_key, ip=ip_address,
            mac=mac_address)

        # Check that the 'stdin' arg contains the correct set of
        # commands.
        self.assertEqual(
            [1, (expected_script,)],
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
            ExternalProcessError, shell.create, ip_address, mac_address)
        self.assertEqual(random_output, exc.output)

    def test_create_succeeds_when_host_map_already_exists(self):
        # To omshell, creating the same host map twice is an error.  But
        # Omshell.create swallows the error and makes it look like
        # success.
        params = {
            'ip': factory.getRandomIPAddress(),
            'mac': factory.getRandomMACAddress(),
            'hostname': factory.make_name('hostname')
        }
        shell = Omshell(factory.make_name('server'), factory.make_name('key'))
        # This is the kind of error output we get if a host map has
        # already been created.
        error_output = dedent("""\
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
            """) % params
        shell._run = Mock(return_value=(0, error_output))
        shell.create(params['ip'], params['mac'])
        # The test is that we get here without error.
        pass

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

        expected_script = dedent("""\
            server {server}
            key omapi_key {key}
            connect
            new host
            set name = "{ip}"
            open
            remove
            """)
        expected_script = expected_script.format(
            server=server_address, key=shared_key, ip=ip_address)

        # Check that the 'stdin' arg contains the correct set of
        # commands.
        self.assertEqual([(expected_script,)], recorder.extract_args())

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
            subprocess.CalledProcessError, shell.remove, ip_address)
        self.assertEqual(random_output, exc.output)


class Test_generate_omapi_key(MAASTestCase):
    """Tests for omshell.generate_omapi_key"""

    def test_generate_omapi_key_returns_a_key(self):
        key = generate_omapi_key()
        # Could test for != None here, but the keys end in == for a 512
        # bit length key, so that's a better check that the script was
        # actually run and produced output.
        self.assertThat(key, EndsWith("=="))

    def test_generate_omapi_key_leaves_no_temp_files(self):
        tmpdir = self.useFixture(TempDirectory()).path
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

    def test_run_repeated_keygen(self):
        bad_patterns = {
            "+no", "/no", "no+", "no/",
            "+NO", "/NO", "NO+", "NO/",
            }
        bad_patterns_templates = {
            "foo%sbar", "one\ntwo\n%s\nthree\n", "%s",
            }
        # Test that a known bad key is ignored and we generate a new one
        # to replace it.
        bad_keys = {
            # This key is known to fail with omshell.
            "YXY5pr+No/8NZeodSd27wWbI8N6kIjMF/nrnFIlPwVLuByJKkQcBRtfDrD"
            "LLG2U9/ND7/bIlJxEGTUnyipffHQ==",
            }
        # Fabricate a range of keys containing the known-bad pattern.
        bad_keys.update(
            template % pattern for template, pattern in product(
                bad_patterns_templates, bad_patterns))
        # An iterator that we can exhaust without mutating bad_keys.
        iter_bad_keys = iter(bad_keys)
        # Reference to the original parse_key_value_file, before we patch.
        parse_key_value_file = provisioningserver.omshell.parse_key_value_file

        # Patch parse_key_value_file to return each of the known-bad keys
        # we've created, followed by reverting to its usual behaviour.
        def side_effect(*args, **kwargs):
            try:
                return {'Key': next(iter_bad_keys)}
            except StopIteration:
                return parse_key_value_file(*args, **kwargs)

        mock = self.patch(provisioningserver.omshell, 'parse_key_value_file')
        mock.side_effect = side_effect

        # generate_omapi_key() does not return a key known to be bad.
        self.assertNotIn(generate_omapi_key(), bad_keys)


class TestCallDnsSecKeygen(MAASTestCase):
    """Tests for omshell.call_dnssec_keygen."""

    def test_runs_external_script(self):
        check_output = self.patch(subprocess, 'check_output')
        target_dir = self.make_dir()
        path = os.environ.get("PATH", "").split(os.pathsep)
        path.append("/usr/sbin")
        call_dnssec_keygen(target_dir)
        check_output.assert_called_once_with(
            ['dnssec-keygen', '-r', '/dev/urandom', '-a', 'HMAC-MD5',
             '-b', '512', '-n', 'HOST', '-K', target_dir, '-q', 'omapi_key'],
            env=ANY)
