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

import os

from maastesting.matchers import ContainsAll
from maastesting.testcase import TestCase
from provisioningserver.dhcp.writer import DHCPConfigWriter
from testtools.matchers import MatchesStructure


class TestDHCPConfigWriter(TestCase):
    """Test `DHCPConfigWriter`."""

    def test_arg_setup(self):
        writer = DHCPConfigWriter()
        test_args = [
            '--subnet', 'subnet',
            '--subnet-mask', 'subnet-mask',
            '--next-server', 'next-server',
            '--broadcast-address', 'broadcast-address',
            '--dns-servers', 'dns-servers',
            '--gateway', 'gateway',
            '--low-range', 'low-range',
            '--high-range', 'high-range',
            '--out-file', 'out-file',
            ]
        args = writer.parse_args(test_args)

        self.assertThat(
            args, MatchesStructure.byEquality(
                subnet='subnet',
                subnet_mask='subnet-mask',
                next_server='next-server',
                broadcast_address='broadcast-address',
                dns_servers='dns-servers',
                gateway='gateway',
                low_range='low-range',
                high_range='high-range',
                out_file='out-file'))

    def test_generate(self):
        writer = DHCPConfigWriter()
        test_args = [
            '--subnet', 'subnet',
            '--subnet-mask', 'subnet-mask',
            '--next-server', 'next-server',
            '--broadcast-address', 'broadcast-address',
            '--dns-servers', 'dns-servers',
            '--gateway', 'gateway',
            '--low-range', 'low-range',
            '--high-range', 'high-range',
            ]
        args = writer.parse_args(test_args)
        output = writer.generate(args)

        contains_all_params = ContainsAll(
            ['subnet', 'subnet-mask', 'next-server', 'broadcast-address',
            'dns-servers', 'gateway', 'low-range', 'high-range'])
        self.assertThat(output, contains_all_params)

    def test_run_with_file_output(self):
        temp_dir = self.make_dir()
        outfile = os.path.join(temp_dir, "outfile")
        writer = DHCPConfigWriter()
        test_args = [
            '--subnet', 'subnet',
            '--subnet-mask', 'subnet-mask',
            '--next-server', 'next-server',
            '--broadcast-address', 'broadcast-address',
            '--dns-servers', 'dns-servers',
            '--gateway', 'gateway',
            '--low-range', 'low-range',
            '--high-range', 'high-range',
            '--out-file', outfile,
            ]
        writer.run(test_args)

        self.assertTrue(os.path.exists(outfile))
