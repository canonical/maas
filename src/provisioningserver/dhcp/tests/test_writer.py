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
from os import path
import sys

from maastesting.matchers import ContainsAll
from maastesting.testcase import TestCase
from provisioningserver.dhcp import writer
from testtools.matchers import MatchesStructure


class TestScript(TestCase):
    """Test the DHCP configuration writer."""

    test_args = (
        '--subnet', 'subnet',
        '--subnet-mask', 'subnet-mask',
        '--next-server', 'next-server',
        '--broadcast-address', 'broadcast-address',
        '--dns-servers', 'dns-servers',
        '--gateway', 'gateway',
        '--low-range', 'low-range',
        '--high-range', 'high-range',
        )

    def test_arg_setup(self):
        parser = ArgumentParser()
        writer.add_arguments(parser)
        args = parser.parse_args(self.test_args)
        self.assertThat(
            args, MatchesStructure.byEquality(
                subnet='subnet',
                subnet_mask='subnet-mask',
                next_server='next-server',
                broadcast_address='broadcast-address',
                dns_servers='dns-servers',
                gateway='gateway',
                low_range='low-range',
                high_range='high-range'))

    def test_run(self):
        self.patch(sys, "stdout", BytesIO())
        parser = ArgumentParser()
        writer.add_arguments(parser)
        args = parser.parse_args(self.test_args)
        writer.run(args)
        output = sys.stdout.getvalue()
        contains_all_params = ContainsAll(
            ['subnet', 'subnet-mask', 'next-server', 'broadcast-address',
             'dns-servers', 'gateway', 'low-range', 'high-range'])
        self.assertThat(output, contains_all_params)

    def test_run_save_to_file(self):
        parser = ArgumentParser()
        writer.add_arguments(parser)
        outfile = path.join(self.make_dir(), "outfile.txt")
        args = parser.parse_args(
            self.test_args + ("--outfile", outfile))
        writer.run(args)
        with open(outfile, "rb") as stream:
            output = stream.read()
        contains_all_params = ContainsAll(
            ['subnet', 'subnet-mask', 'next-server', 'broadcast-address',
             'dns-servers', 'gateway', 'low-range', 'high-range'])
        self.assertThat(output, contains_all_params)
