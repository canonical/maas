# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the BIND fixture."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []


import os
from subprocess import (
    CalledProcessError,
    check_output,
    )

from maastesting.bindfixture import (
    BINDServer,
    BINDServerResources,
    )
from maastesting.testcase import TestCase
from testtools.matchers import (
    Contains,
    FileContains,
    FileExists,
    )
from testtools.testcase import gather_details


def dig_call(port=53, server='127.0.0.1', commands=None):
    """Call `dig` with the given command.

    Note that calling dig without a command will perform an NS
    query for "." (the root) which is useful to check if there
    is a running server.

    :param port: Port of the queried DNS server (defaults to 53).
    :param server: IP address of the queried DNS server (defaults
        to '127.0.0.1').
    :param commands: List of dig commands to run (defaults to None
        which will perform an NS query for "." (the root)).
    :return: The output as a string.
    :rtype: basestring
    """
    cmd = [
        'dig', '+time=10', '+tries=5', '@%s' % server, '-p',
        '%d' % port]
    if commands is not None:
        if not isinstance(commands, list):
            commands = (commands, )
        cmd.extend(commands)
    return check_output(cmd).strip()


class TestBINDFixture(TestCase):

    def test_start_check_shutdown(self):
        # The fixture correctly starts and stops BIND.
        with BINDServer() as fixture:
            try:
                result = dig_call(fixture.config.port)
                self.assertIn("Got answer", result)
            except Exception:
                # self.useFixture() is not being used because we want to
                # handle the fixture's lifecycle, so we must also be
                # responsible for propagating fixture details.
                gather_details(fixture.getDetails(), self.getDetails())
                raise
        error = self.assertRaises(
            CalledProcessError, dig_call, fixture.config.port)
        self.assertEqual(9, error.returncode)
        # return code 9 means timeout.

    def test_config(self):
        # The configuration can be passed in.
        config = BINDServerResources()
        fixture = self.useFixture(BINDServer(config))
        self.assertIs(config, fixture.config)


class TestBINDServerResources(TestCase):

    def test_defaults(self):
        with BINDServerResources() as resources:
            self.assertIsInstance(resources.port, int)
            self.assertIsInstance(resources.rndc_port, int)
            self.assertIsInstance(resources.homedir, basestring)
            self.assertIsInstance(resources.log_file, basestring)
            self.assertIsInstance(resources.named_file, basestring)
            self.assertIsInstance(resources.conf_file, basestring)
            self.assertIsInstance(
                resources.rndcconf_file, basestring)

    def test_setUp_copies_executable(self):
        with BINDServerResources() as resources:
            self.assertThat(resources.named_file, FileExists())

    def test_setUp_creates_config_files(self):
        with BINDServerResources() as resources:
            self.assertThat(
                resources.conf_file,
                FileContains(matcher=Contains(
                    b'listen-on port %s' % resources.port)))
            self.assertThat(
                resources.rndcconf_file,
                FileContains(matcher=Contains(
                    b'default-port %s' % (
                        resources.rndc_port))))

    def test_defaults_reallocated_after_teardown(self):
        seen_homedirs = set()
        resources = BINDServerResources()
        for i in range(2):
            with resources:
                self.assertTrue(os.path.exists(resources.homedir))
                self.assertNotIn(resources.homedir, seen_homedirs)
                seen_homedirs.add(resources.homedir)
