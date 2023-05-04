# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maascli.cli`."""

from argparse import Namespace
import http.client
from io import StringIO
import json
import os
from pathlib import Path
import sys
from unittest.mock import sentinel

from django.core import management
import httplib2

from apiclient.creds import convert_string_to_tuple
from maascli import cli, init, snap
from maascli.auth import UnexpectedResponse
from maascli.cli import CERTS_DIR
from maascli.config import ProfileConfig
from maascli.parser import ArgumentParser
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.testing.certificates import get_sample_cert

from .test_auth import make_credentials, make_options


class TestRegisterCommands(MAASTestCase):
    """Tests for registers CLI commands."""

    def test_registers_subparsers(self):
        parser = ArgumentParser()
        self.assertIsNone(parser._subparsers)
        cli.register_cli_commands(parser)
        self.assertIsNotNone(parser._subparsers)

    def test_subparsers_have_appropriate_execute_defaults(self):
        parser = ArgumentParser()
        cli.register_cli_commands(parser)
        self.assertIsInstance(
            parser.subparsers.choices["login"].get_default("execute"),
            cli.cmd_login,
        )

    def test_doesnt_call_load_regiond_commands_if_no_management(self):
        self.patch(cli, "get_django_management").return_value = None
        self.patch(
            cli, "is_maasserver_available"
        ).return_value = sentinel.pkg_util
        mock_load_regiond_commands = self.patch(cli, "load_regiond_commands")
        parser = ArgumentParser()
        cli.register_cli_commands(parser)
        mock_load_regiond_commands.assert_not_called()

    def test_doesnt_call_load_regiond_commands_if_no_maasserver(self):
        self.patch(
            cli, "get_django_management"
        ).return_value = sentinel.management
        self.patch(cli, "is_maasserver_available").return_value = None
        mock_load_regiond_commands = self.patch(cli, "load_regiond_commands")
        parser = ArgumentParser()
        cli.register_cli_commands(parser)
        mock_load_regiond_commands.assert_not_called()

    def test_calls_load_regiond_commands_when_management_and_maasserver(self):
        self.patch(
            cli, "get_django_management"
        ).return_value = sentinel.management
        self.patch(
            cli, "is_maasserver_available"
        ).return_value = sentinel.pkg_util
        mock_load_regiond_commands = self.patch(cli, "load_regiond_commands")
        parser = ArgumentParser()
        cli.register_cli_commands(parser)
        mock_load_regiond_commands.assert_called_once_with(
            sentinel.management, parser
        )

    def test_loads_all_regiond_commands(self):
        parser = ArgumentParser()
        cli.register_cli_commands(parser)
        for name, app, help_text in cli.REGIOND_COMMANDS:
            subparser = parser.subparsers.choices.get(name)
            # XXX: We use custom non-Django Command Management in order to follow
            # Canonical CLI Guidelines and have two-word commands having `-` delimiter.
            # But Django Management loads commands by module name, which has `_`
            klass = management.load_command_class(app, name.replace("-", "_"))
            if help_text is None:
                help_text = klass.help
            self.assertIsNotNone(subparser)
            self.assertEqual(help_text, subparser.description)

    def test_load_init_command_snap(self):
        environ = {"SNAP": "snap-path"}
        self.patch(os, "environ", environ)
        parser = ArgumentParser()
        cli.register_cli_commands(parser)
        subparser = parser.subparsers.choices.get("init")
        self.assertIsInstance(subparser.get_default("execute"), snap.cmd_init)

    def test_load_init_command_no_snap(self):
        environ = {}
        self.patch(os, "environ", environ)
        parser = ArgumentParser()
        cli.register_cli_commands(parser)
        subparser = parser.subparsers.choices.get("init")
        self.assertIsInstance(subparser.get_default("execute"), cli.cmd_init)

    def test_load_init_command_no_snap_no_maasserver(self):
        environ = {}
        self.patch(os, "environ", environ)
        self.patch(cli, "is_maasserver_available").return_value = None
        parser = ArgumentParser()
        cli.register_cli_commands(parser)
        subparser = parser.subparsers.choices.get("init")
        self.assertIsNone(subparser)

    def test_hidden_commands(self):
        environ = {"SNAP": "snap-path", "SNAP_COMMON": "snap-common"}
        self.patch(os, "environ", environ)
        stdout = self.patch(sys, "stdout", StringIO())
        parser = ArgumentParser()
        cli.register_cli_commands(parser)
        error = self.assertRaises(SystemExit, parser.parse_args, ["--help"])
        self.assertEqual(error.code, 0)
        self.assertNotIn("reconfigure-supervisord", stdout.getvalue())


class TestLogin(MAASTestCase):
    def test_cmd_login_ensures_valid_apikey(self):
        parser = ArgumentParser()
        options = make_options()
        check_key = self.patch(cli, "check_valid_apikey")
        check_key.return_value = False
        login = cli.cmd_login(parser)
        error = self.assertRaises(SystemExit, login, options)
        self.assertEqual("The MAAS server rejected your API key.", str(error))
        check_key.assert_called_once_with(
            options.url,
            convert_string_to_tuple(options.credentials),
            options.cacerts,
            options.insecure,
        )

    def test_cmd_login_raises_unexpected_error_when_validating_apikey(self):
        parser = ArgumentParser()
        options = make_options()
        check_key = self.patch(cli, "check_valid_apikey")
        check_key_error_message = factory.make_name("error")
        check_key_error = UnexpectedResponse(check_key_error_message)
        check_key.side_effect = check_key_error
        login = cli.cmd_login(parser)
        error = self.assertRaises(SystemExit, login, options)
        self.assertEqual(check_key_error_message, str(error))

    def test_print_whats_next(self):
        profile = {
            "name": factory.make_name("profile"),
            "url": factory.make_name("url"),
        }
        stdout = self.patch(sys, "stdout", StringIO())
        cli.cmd_login.print_whats_next(profile)
        output = stdout.getvalue()
        self.assertIn(
            f"You are now logged in to the MAAS server at {profile['url']}",
            output,
        )
        self.assertIn(f"maas {profile['name']} --help", output)

    def test_cmd_login_raises_error_when_cacerts_and_insecure_specified(self):
        parser = ArgumentParser()
        options = Namespace(
            insecure=True,
            cacerts="cacerts.pem",
        )
        login = cli.cmd_login(parser)
        self.assertRaises(SystemExit, login, options)

    def test_cmd_login_stores_provided_cacerts_in_profile(self):
        sample_cert = get_sample_cert()
        cert_path, _ = sample_cert.tempfiles()
        parser = ArgumentParser()
        credentials = ":".join(make_credentials())
        url = "https://example.com/api/2.0/"
        profile_name = "test_with_cacerts_in_profile"
        options = Namespace(
            credentials=credentials,
            execute=None,
            insecure=False,
            profile_name=profile_name,
            url=url,
            cacerts=open(cert_path),
        )

        check_key = self.patch(cli, "check_valid_apikey")
        check_key.return_value = True

        fetch_description = self.patch(cli, "fetch_api_description")
        fetch_description.return_value = {}

        content = factory.make_name("content")
        mock_request = self.patch(httplib2.Http, "request")
        response = httplib2.Response({})
        response["status"] = http.client.OK
        mock_request.return_value = response, json.dumps(content)

        login = cli.cmd_login(parser)
        login(options)
        with ProfileConfig.open() as config:
            self.assertEqual(
                sample_cert.certificate_pem(), config[profile_name]["cacerts"]
            )
            del config[profile_name]


class TestCmdInit(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.parser = ArgumentParser()
        self.cmd = cli.cmd_init(self.parser)
        self.maas_region_path = init.get_maas_region_bin_path()
        self.call_mock = self.patch(init.subprocess, "call")
        self.check_output_mock = self.patch(init.subprocess, "check_output")
        self.check_output_mock.return_value = json.dumps(
            {"external_auth_url": ""}
        )
        # avoid printouts
        self.mock_stdout = self.patch(init.sys, "stdout", StringIO())
        self.mock_stderr = self.patch(init.sys, "stderr", StringIO())

    def test_defaults(self):
        options = self.parser.parse_args([])
        self.assertFalse(options.skip_admin)
        self.assertIsNone(options.admin_username)
        self.assertIsNone(options.admin_password)
        self.assertIsNone(options.admin_email)
        self.assertIsNone(options.admin_ssh_import)
        self.assertIsNone(options.candid_agent_file)
        self.assertIsNone(options.rbac_url)

    def test_init_maas_calls_subcommands(self):
        options = self.parser.parse_args([])
        self.cmd(options)
        configauth_call, createadmin_call = self.call_mock.mock_calls
        _, args1, kwargs1 = configauth_call
        _, args2, kwargs2 = createadmin_call
        self.assertEqual(([self.maas_region_path, "configauth"],), args1)
        self.assertEqual({}, kwargs1)
        self.assertEqual(([self.maas_region_path, "createadmin"],), args2)
        self.assertEqual({}, kwargs2)


class TestReconfigureSupervisord(MAASTestCase):
    def test_cmd_configure_supervisord(self):
        self.patch(snap, "get_current_mode").return_value = "region+rack"
        mock_render_supervisord = self.patch(snap, "render_supervisord")
        mock_sighup_supervisord = self.patch(snap, "sighup_supervisord")
        parser = ArgumentParser()
        cmd = snap.cmd_reconfigure_supervisord(parser)
        cmd(parser.parse_args([]))
        mock_render_supervisord.assert_called_once_with("region+rack")
        mock_sighup_supervisord.assert_called_once()


class TestLogout(MAASTestCase):
    def test_cmd_logout_cleans_profile_cacerts(self):
        parser = ArgumentParser()
        profile_name = "test"
        options = Namespace(profile_name=profile_name)

        ProfileConfig.create_database(Path("~/.maascli.db").expanduser())

        if not CERTS_DIR.exists():
            CERTS_DIR.mkdir()
        cacerts_path = CERTS_DIR / (profile_name + ".pem")
        cacerts_path.touch()
        logout = cli.cmd_logout(parser)
        logout(options)
        self.assertFalse(cacerts_path.exists())
