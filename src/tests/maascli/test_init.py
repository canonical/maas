# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
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


class TestCreateAdminAccount(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.parser = ArgumentParser()
        init.add_create_admin_options(self.parser)
        self.mock_call = self.patch(init.subprocess, "call")
        self.mock_print_msg = self.patch(init, "print_msg")
        self.maas_region_path = init.get_maas_region_bin_path()

    def test_no_options(self):
        options = self.parser.parse_args([])
        init.create_admin_account(options)
        self.mock_print_msg.assert_called_with("Create first admin account")
        self.mock_call.assert_called_with(
            [self.maas_region_path, "createadmin"]
        )

    def test_username(self):
        options = self.parser.parse_args(["--admin-username", "my-user"])
        init.create_admin_account(options)
        self.mock_print_msg.assert_called_with("Create first admin account")
        self.mock_call.assert_called_with(
            [self.maas_region_path, "createadmin", "--username", "my-user"]
        )

    def test_password(self):
        options = self.parser.parse_args(["--admin-password", "my-pass"])
        init.create_admin_account(options)
        self.mock_print_msg.assert_called_with("Create first admin account")
        self.mock_call.assert_called_with(
            [self.maas_region_path, "createadmin", "--password", "my-pass"]
        )

    def test_email(self):
        options = self.parser.parse_args(["--admin-email", "me@example.com"])
        init.create_admin_account(options)
        self.mock_print_msg.assert_called_with("Create first admin account")
        self.mock_call.assert_called_with(
            [self.maas_region_path, "createadmin", "--email", "me@example.com"]
        )

    def test_ssh_import(self):
        options = self.parser.parse_args(["--admin-ssh-import", "lp:me"])
        init.create_admin_account(options)
        self.mock_print_msg.assert_called_with("Create first admin account")
        self.mock_call.assert_called_with(
            [self.maas_region_path, "createadmin", "--ssh-import", "lp:me"]
        )

    def test_no_print_header(self):
        options = self.parser.parse_args(
            [
                "--admin-username",
                "my-user",
                "--admin-password",
                "my-pass",
                "--admin-email",
                "me@example.com",
            ]
        )
        init.create_admin_account(options)
        self.mock_print_msg.assert_not_called()


class TestPrintMsg(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.mock_print = self.patch(init, "print")

    def test_print_msg_empty_message(self):
        init.print_msg()
        self.mock_print.assert_called_with(
            "", end="\n", file=sys.stdout, flush=True
        )
