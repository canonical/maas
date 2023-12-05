# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the setup-dns command."""


from argparse import ArgumentParser
import io
import os

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.dns.commands.setup_dns import add_arguments, run
from provisioningserver.dns.config import (
    MAAS_NAMED_CONF_NAME,
    MAAS_RNDC_CONF_NAME,
)
from provisioningserver.dns.testing import (
    patch_dns_config_path,
    patch_zone_file_config_path,
)


class TestSetupCommand(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.output = io.StringIO()
        self.error_output = io.StringIO()
        self.parser = ArgumentParser()
        add_arguments(self.parser)

    def run_command(self, *args):
        parsed_args = self.parser.parse_args([*args])
        return run(parsed_args, stdout=self.output, stderr=self.error_output)

    def test_writes_configuration(self):
        dns_conf_dir = self.make_dir()
        patch_dns_config_path(self, dns_conf_dir)
        patch_zone_file_config_path(self, dns_conf_dir)
        self.run_command()
        named_config = os.path.join(dns_conf_dir, MAAS_NAMED_CONF_NAME)
        rndc_conf_path = os.path.join(dns_conf_dir, MAAS_RNDC_CONF_NAME)
        self.assertTrue(os.path.exists(rndc_conf_path))
        self.assertTrue(os.path.exists(named_config))

    def test_does_not_overwrite_config(self):
        dns_conf_dir = self.make_dir()
        zone_file_dir = self.make_dir()
        patch_dns_config_path(self, dns_conf_dir)
        patch_zone_file_config_path(self, zone_file_dir)
        random_content = factory.make_string()
        factory.make_file(
            location=dns_conf_dir,
            name=MAAS_NAMED_CONF_NAME,
            contents=random_content,
        )
        self.run_command("--no-clobber")
        with open(os.path.join(dns_conf_dir, MAAS_NAMED_CONF_NAME), "r") as fh:
            contents = fh.read()

        self.assertIn(random_content, contents)
