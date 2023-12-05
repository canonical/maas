# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Nginx fixture."""


import os

from maastesting.testcase import MAASTestCase
from provisioningserver.testing.nginxfixture import (
    NginxServer,
    NginxServerResources,
)


class TestNginxFixture(MAASTestCase):
    def test_config(self):
        # The configuration can be passed in.
        config = NginxServerResources()
        fixture = self.useFixture(NginxServer(config))
        self.assertIs(config, fixture.config)


class TestNginxServerResources(MAASTestCase):
    def test_defaults(self):
        with NginxServerResources() as resources:
            self.assertIsInstance(resources.homedir, str)
            self.assertIsInstance(resources.access_log_file, str)
            self.assertIsInstance(resources.error_log_file, str)
            self.assertIsInstance(resources.conf_file, str)
            self.assertIsInstance(resources.pid_file, str)

    def test_setUp_copies_executable(self):
        with NginxServerResources() as resources:
            self.assertTrue(os.path.isfile(resources.nginx_file))

    def test_setUp_creates_config_files(self):
        with NginxServerResources() as resources:
            with open(resources.conf_file, "r") as fh:
                contents = fh.read()
        self.assertIn(f"pid {resources.pid_file};", contents)

    def test_defaults_reallocated_after_teardown(self):
        seen_homedirs = set()
        resources = NginxServerResources()
        for _ in range(2):
            with resources:
                self.assertTrue(os.path.exists(resources.homedir))
                self.assertNotIn(resources.homedir, seen_homedirs)
                seen_homedirs.add(resources.homedir)
