# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.dhcp.writer`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from argparse import ArgumentParser
from io import BytesIO
import os
from subprocess import (
    PIPE,
    Popen,
    )
import sys

from maastesting.matchers import ContainsAll
from maastesting.testcase import TestCase
import provisioningserver
from provisioningserver.dhcp import writer
from testtools.matchers import MatchesStructure


class TestScript(TestCase):
    """Test the DHCP configuration writer."""

    test_args = (
        '--subnet', 'subnet',
        '--subnet-mask', 'subnet-mask',
        '--next-server', 'next-server',
        '--broadcast-ip', 'broadcast-ip',
        '--dns-servers', 'dns-servers',
        '--router-ip', 'router-ip',
        '--ip-range-low', 'ip-range-low',
        '--ip-range-high', 'ip-range-high',
        '--omapi-key', 'omapi-key',
        )

    def test_script_executable(self):
        dev_root = os.path.join(
            os.path.dirname(provisioningserver.__file__),
            os.pardir, os.pardir)
        script = ["%s/bin/maas-provision" % dev_root, "generate-dhcp-config"]
        script.extend(self.test_args)
        cmd = Popen(
            script, stdout=PIPE, env=dict(PYTHONPATH=":".join(sys.path)))
        output, err = cmd.communicate()
        contains_all_params = ContainsAll(
            ['subnet', 'subnet-mask', 'next-server', 'broadcast-ip',
             'omapi-key', 'dns-servers', 'router-ip',
             'ip-range-low', 'ip-range-high'])
        self.assertThat(output, contains_all_params)

    def test_arg_setup(self):
        parser = ArgumentParser()
        writer.add_arguments(parser)
        args = parser.parse_args(self.test_args)
        self.assertThat(
            args, MatchesStructure.byEquality(
                subnet='subnet',
                subnet_mask='subnet-mask',
                next_server='next-server',
                broadcast_ip='broadcast-ip',
                dns_servers='dns-servers',
                router_ip='router-ip',
                omapi_key='omapi-key',
                ip_range_low='ip-range-low',
                ip_range_high='ip-range-high'))

    def test_run(self):
        self.patch(sys, "stdout", BytesIO())
        parser = ArgumentParser()
        writer.add_arguments(parser)
        args = parser.parse_args(self.test_args)
        writer.run(args)
        output = sys.stdout.getvalue()
        contains_all_params = ContainsAll([
            'subnet',
            'subnet-mask',
            'next-server',
            'broadcast-ip',
            'omapi-key',
            'dns-servers',
            'router-ip',
            'ip-range-low',
            'ip-range-high',
            ])
        self.assertThat(output, contains_all_params)

    def test_run_save_to_file(self):
        parser = ArgumentParser()
        writer.add_arguments(parser)
        outfile = os.path.join(self.make_dir(), "outfile.txt")
        args = parser.parse_args(
            self.test_args + ("--outfile", outfile))
        writer.run(args)
        with open(outfile, "rb") as stream:
            output = stream.read()
        contains_all_params = ContainsAll([
            'subnet',
            'subnet-mask',
            'next-server',
            'broadcast-ip',
            'omapi-key',
            'dns-servers',
            'router-ip',
            'ip-range-low',
            'ip-range-high',
            ])
        self.assertThat(output, contains_all_params)
