# Copyright 2012-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maascli.init`."""

import sys

from maascli import init
from maascli.parser import ArgumentParser
from maastesting.testcase import MAASTestCase


class TestCreateAdminOptions(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.parser = ArgumentParser()
        init.add_create_admin_options(self.parser)

    def test_create_admin_options_empty(self):
        options = self.parser.parse_args([])
        self.assertIsNone(options.admin_username)
        self.assertIsNone(options.admin_password)
        self.assertIsNone(options.admin_email)
        self.assertIsNone(options.admin_ssh_import)

    def test_create_admin_options_username(self):
        options = self.parser.parse_args(["--admin-username", "my-username"])
        self.assertEqual("my-username", options.admin_username)

    def test_create_admin_options_password(self):
        options = self.parser.parse_args(["--admin-password", "my-password"])
        self.assertEqual("my-password", options.admin_password)

    def test_create_admin_options_email(self):
        options = self.parser.parse_args(["--admin-email", "my@example.com"])
        self.assertEqual("my@example.com", options.admin_email)

    def test_create_admin_options_ssh_import(self):
        options = self.parser.parse_args(["--admin-ssh-import", "lp:me"])
        self.assertEqual("lp:me", options.admin_ssh_import)


class TestPrintMsg(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.mock_print = self.patch(init, "print")

    def test_print_msg_empty_message(self):
        init.print_msg()
        self.mock_print.assert_called_with(
            "", end="\n", file=sys.stdout, flush=True
        )
