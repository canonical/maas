# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.dhcp.writer`."""

__all__ = []

from argparse import ArgumentParser
import io
import os
from subprocess import (
    PIPE,
    Popen,
)
import sys

from maastesting import root
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from mock import Mock
from provisioningserver.dhcp import writer
from provisioningserver.dhcp.testing.config import make_subnet_config
from provisioningserver.utils.fs import read_text_file
from provisioningserver.utils.shell import select_c_utf8_locale
from testtools.matchers import (
    ContainsAll,
    MatchesStructure,
)


class TestScript(MAASTestCase):
    """Test the DHCP configuration writer."""

    def make_args(self, network=None):
        """Create a fake parameter for `run`, based on `network`."""
        settings = make_subnet_config(network)
        args = Mock()
        args.outfile = None
        args.omapi_key = factory.make_name('key')
        args.subnet = settings['subnet']
        args.interface = settings['interface']
        args.subnet_mask = settings['subnet_mask']
        args.broadcast_ip = settings['broadcast_ip']
        args.dns_servers = settings['dns_servers']
        args.ntp_server = settings['ntp_server']
        args.domain_name = settings['domain_name']
        args.router_ip = settings['router_ip']
        args.ip_range_low = settings['ip_range_low']
        args.ip_range_high = settings['ip_range_high']
        return args

    def test_script_executable(self):
        args = self.make_args()
        script = [
            "%s/bin/maas-provision" % root,
            "generate-dhcp-config",
            '--subnet', args.subnet,
            '--interface', args.interface,
            '--subnet-mask', args.subnet_mask,
            '--broadcast-ip', args.broadcast_ip,
            '--dns-servers', args.dns_servers,
            '--ntp-server', args.ntp_server,
            '--domain-name', args.domain_name,
            '--router-ip', args.router_ip,
            '--ip-range-low', args.ip_range_low,
            '--ip-range-high', args.ip_range_high,
            '--omapi-key', args.omapi_key,
            ]

        cmd = Popen(script, stdout=PIPE, env=select_c_utf8_locale())
        output, err = cmd.communicate()

        self.assertEqual(0, cmd.returncode, err)

        self.assertThat(output.decode("ascii"), ContainsAll([
            args.subnet,
            args.subnet_mask,
            args.broadcast_ip,
            args.omapi_key,
            args.dns_servers,
            args.ntp_server,
            args.domain_name,
            args.router_ip,
            args.ip_range_low,
            args.ip_range_high,
            ]))

    def test_arg_setup(self):
        test_args = (
            '--subnet', 'subnet',
            '--interface', 'eth0',
            '--subnet-mask', 'subnet-mask',
            '--broadcast-ip', 'broadcast-ip',
            '--dns-servers', 'dns-servers',
            '--ntp-server', 'ntp-server',
            '--domain-name', 'domain-name',
            '--router-ip', 'router-ip',
            '--ip-range-low', 'ip-range-low',
            '--ip-range-high', 'ip-range-high',
            '--omapi-key', 'omapi-key',
            )
        parser = ArgumentParser()
        writer.add_arguments(parser)
        args = parser.parse_args(test_args)
        self.assertThat(
            args, MatchesStructure.byEquality(
                subnet='subnet',
                interface='eth0',
                subnet_mask='subnet-mask',
                broadcast_ip='broadcast-ip',
                dns_servers='dns-servers',
                ntp_server='ntp-server',
                domain_name='domain-name',
                router_ip='router-ip',
                omapi_key='omapi-key',
                ip_range_low='ip-range-low',
                ip_range_high='ip-range-high'))

    def test_run(self):
        stdout = io.BytesIO()
        self.patch(sys, "stdout", io.TextIOWrapper(stdout, "utf-8"))
        args = self.make_args(factory.make_ipv4_network())

        writer.run(args)

        output = stdout.getvalue()
        contains_all_params = ContainsAll([
            args.subnet,
            args.interface,
            args.subnet_mask,
            args.broadcast_ip,
            args.omapi_key,
            args.dns_servers,
            args.ntp_server,
            args.domain_name,
            args.router_ip,
            args.ip_range_low,
            args.ip_range_high,
            ])
        self.assertThat(output.decode("ascii"), contains_all_params)

    def test_run_save_to_file(self):
        args = self.make_args()
        args.outfile = os.path.join(self.make_dir(), "outfile.txt")

        writer.run(args)

        self.assertThat(
            read_text_file(args.outfile),
            ContainsAll([
                args.subnet,
                args.interface,
                args.subnet_mask,
                args.broadcast_ip,
                args.omapi_key,
                args.dns_servers,
                args.ntp_server,
                args.domain_name,
                args.router_ip,
                args.ip_range_low,
                args.ip_range_high,
                ]))
