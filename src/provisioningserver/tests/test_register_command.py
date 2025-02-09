# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for register command code."""

from argparse import ArgumentParser
import io
from itertools import combinations
import pprint
from unittest.mock import call, Mock

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver import register_command
from provisioningserver.config import ClusterConfiguration
from provisioningserver.security import to_hex
from provisioningserver.testing.config import ClusterConfigurationFixture
from provisioningserver.utils.env import MAAS_ID, MAAS_SHARED_SECRET
from provisioningserver.utils.shell import ExternalProcessError
from provisioningserver.utils.testing import MAASIDFixture


class TestAddArguments(MAASTestCase):
    def test_accepts_all_args(self):
        all_test_arguments = register_command.all_arguments

        default_arg_values = {"--url": None, "--secret": None}

        failures = {}

        # Try all cardinalities of combinations of arguments
        for r in range(len(all_test_arguments) + 1):
            for test_arg_names in combinations(all_test_arguments, r):
                test_values = {
                    "--url": factory.make_simple_http_url(),
                    "--secret": factory.make_name("secret"),
                }

                # Build a query dictionary for the given combination of args
                args_under_test = []
                for param_name in test_arg_names:
                    args_under_test.append(param_name)
                    args_under_test.append(test_values[param_name])

                parser = ArgumentParser()
                register_command.add_arguments(parser)

                observed_args = vars(parser.parse_args(args_under_test))

                expected_args = {}
                for param_name in all_test_arguments:
                    parsed_param_name = param_name[2:].replace("-", "_")

                    if param_name not in test_arg_names:
                        expected_args[parsed_param_name] = default_arg_values[
                            param_name
                        ]
                    else:
                        expected_args[parsed_param_name] = observed_args[
                            parsed_param_name
                        ]

                if expected_args != observed_args:
                    failures[str(test_arg_names)] = {
                        "expected_args": expected_args,
                        "observed_args": observed_args,
                    }

        error_message = io.StringIO()
        error_message.write(
            "One or more key / value argument list(s) passed in the query "
            "string (expected_args) to the API do not match the values in "
            "the returned query string. This means that some arguments were "
            "dropped / added / changed by the the function, which is "
            "incorrect behavior. The list of incorrect arguments is as "
            "follows: \n"
        )
        pp = pprint.PrettyPrinter(depth=3, stream=error_message)
        pp.pprint(failures)
        self.assertEqual({}, failures, error_message.getvalue())


class TestRegisterMAASRack(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(ClusterConfigurationFixture())
        self.mock_call_and_check = self.patch_autospec(
            register_command, "call_and_check"
        )

    def make_args(self, **kwargs):
        args = Mock()
        args.__dict__.update(kwargs)
        return args

    def test_sets_url(self):
        secret = factory.make_bytes()
        expected_url = factory.make_simple_http_url()
        register_command.run(
            self.make_args(url=expected_url, secret=to_hex(secret))
        )
        with ClusterConfiguration.open() as config:
            observed = config.maas_url
        self.assertEqual([expected_url], observed)

    def test_prompts_user_for_url(self):
        expected_url = factory.make_simple_http_url()
        secret = factory.make_bytes()

        stdin = self.patch(register_command, "stdin")
        stdin.isatty.return_value = True

        input_ = self.patch(register_command, "input")
        input_.return_value = expected_url

        register_command.run(self.make_args(url=None, secret=to_hex(secret)))
        with ClusterConfiguration.open() as config:
            observed = config.maas_url

        input_.assert_called_once_with("MAAS region controller URL: ")
        self.assertEqual([expected_url], observed)

    def test_sets_secret(self):
        url = factory.make_simple_http_url()
        secret = to_hex(factory.make_bytes())
        register_command.run(self.make_args(url=url, secret=secret))
        self.assertEqual(MAAS_SHARED_SECRET.path.read_text(), secret)

    def test_prompts_user_for_secret(self):
        url = factory.make_simple_http_url()
        previous_value = to_hex(factory.make_bytes())
        MAAS_SHARED_SECRET.set(previous_value)
        InstallSharedSecretScript_mock = self.patch(
            register_command, "InstallSharedSecretScript"
        )
        args = self.make_args(url=url, secret=None)
        register_command.run(args)
        self.assertEqual(previous_value, MAAS_SHARED_SECRET.path.read_text())
        InstallSharedSecretScript_mock.run.assert_called_once_with(args)

    def test_errors_out_when_piped_stdin_and_url_not_supplied(self):
        args = self.make_args(url=None)
        stdin = self.patch(register_command, "stdin")
        stdin.isatty.return_value = False
        self.assertRaises(SystemExit, register_command.run, args)

    def test_crashes_on_eoferror(self):
        args = self.make_args(url=None)
        stdin = self.patch(register_command, "stdin")
        stdin.isatty.return_value = True
        input_ = self.patch(register_command, "input")
        input_.side_effect = EOFError
        self.assertRaises(SystemExit, register_command.run, args)

    def test_crashes_on_keyboardinterrupt(self):
        args = self.make_args(url=None)
        stdin = self.patch(register_command, "stdin")
        stdin.isatty.return_value = True
        input_ = self.patch(register_command, "input")
        input_.side_effect = KeyboardInterrupt
        self.assertRaises(KeyboardInterrupt, register_command.run, args)

    def test_restarts_maas_rackd_service(self):
        url = factory.make_simple_http_url()
        secret = factory.make_bytes()
        register_command.run(self.make_args(url=url, secret=to_hex(secret)))
        self.mock_call_and_check.assert_has_calls(
            [
                call(["systemctl", "stop", "maas-rackd"]),
                call(["systemctl", "enable", "maas-rackd"]),
                call(["systemctl", "start", "maas-rackd"]),
            ],
        )

    def test_deletes_maas_id_file(self):
        self.useFixture(MAASIDFixture(factory.make_string()))
        url = factory.make_simple_http_url()
        secret = factory.make_bytes()
        register_command.run(self.make_args(url=url, secret=to_hex(secret)))
        self.assertIsNone(MAAS_ID.get())

    def test_show_service_stop_error(self):
        url = factory.make_simple_http_url()
        secret = factory.make_bytes()
        register_command.run(self.make_args(url=url, secret=to_hex(secret)))
        mock_call_and_check = self.patch(register_command, "call_and_check")
        mock_call_and_check.side_effect = [
            ExternalProcessError(1, "systemctl stop", "mock error"),
            call(),
            call(),
        ]
        mock_stderr = self.patch(register_command.stderr, "write")
        self.assertRaises(
            SystemExit,
            register_command.run,
            self.make_args(url=url, secret=to_hex(secret)),
        )
        mock_stderr.assert_has_calls(
            [
                call("Unable to stop maas-rackd service."),
                call("\n"),
                call("Failed with error: mock error."),
                call("\n"),
            ],
        )

    def test_show_service_enable_error(self):
        url = factory.make_simple_http_url()
        secret = factory.make_bytes()
        register_command.run(self.make_args(url=url, secret=to_hex(secret)))
        mock_call_and_check = self.patch(register_command, "call_and_check")
        mock_call_and_check.side_effect = [
            call(),
            ExternalProcessError(1, "systemctl enable", "mock error"),
            call(),
        ]
        mock_stderr = self.patch(register_command.stderr, "write")
        self.assertRaises(
            SystemExit,
            register_command.run,
            self.make_args(url=url, secret=to_hex(secret)),
        )
        mock_stderr.assert_has_calls(
            [
                call("Unable to enable and start the maas-rackd service."),
                call("\n"),
                call("Failed with error: mock error."),
                call("\n"),
            ]
        )

    def test_show_service_start_error(self):
        url = factory.make_simple_http_url()
        secret = factory.make_bytes()
        register_command.run(self.make_args(url=url, secret=to_hex(secret)))
        mock_call_and_check = self.patch(register_command, "call_and_check")
        mock_call_and_check.side_effect = [
            call(),
            call(),
            ExternalProcessError(1, "systemctl start", "mock error"),
        ]
        mock_stderr = self.patch(register_command.stderr, "write")
        self.assertRaises(
            SystemExit,
            register_command.run,
            self.make_args(url=url, secret=to_hex(secret)),
        )
        mock_stderr.assert_has_calls(
            [
                call("Unable to enable and start the maas-rackd service."),
                call("\n"),
                call("Failed with error: mock error."),
                call("\n"),
            ]
        )
