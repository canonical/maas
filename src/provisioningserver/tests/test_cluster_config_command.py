# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for configuration update code."""


from argparse import ArgumentParser
import io
from itertools import combinations
import pprint
from unittest.mock import Mock, patch
import uuid

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver import cluster_config_command
from provisioningserver.config import ClusterConfiguration
from provisioningserver.testing.config import ClusterConfigurationFixture


class TestAddArguments(MAASTestCase):
    def test_accepts_all_args(self):
        all_test_arguments = cluster_config_command.all_arguments

        default_arg_values = {
            "--region-url": None,
            "--uuid": None,
            "--init": False,
            "--tftp-port": None,
            "--tftp-root": None,
            "--debug": None,
        }

        failures = {}

        # Try all cardinalities of combinations of arguments
        for r in range(len(all_test_arguments) + 1):
            for test_arg_names in combinations(all_test_arguments, r):
                test_values = {
                    "--region-url": factory.make_simple_http_url(),
                    "--uuid": str(uuid.uuid4()),
                    "--init": "",
                    "--tftp-port": str(factory.pick_port()),
                    "--tftp-root": factory.make_string(),
                    "--debug": str(factory.pick_bool()),
                }

                # Build a query dictionary for the given combination of args
                args_under_test = []
                for param_name in test_arg_names:
                    args_under_test.append(param_name)
                    if param_name != "--init":
                        args_under_test.append(test_values[param_name])

                parser = ArgumentParser()
                cluster_config_command.add_arguments(parser)

                # If both init and uuid are passed, argparse will generate
                # a nice ArgumentError exception, which unfortunately,
                # gets caught and sent to exit.
                if "--init" in test_arg_names and "--uuid" in test_arg_names:
                    with self.assertRaisesRegex(SystemExit, "2"), patch(
                        "sys.stderr"
                    ):
                        parser.parse_known_args(args_under_test)

                else:
                    # Otherwise, parsed args with defaults as usual
                    observed_args = vars(parser.parse_args(args_under_test))

                    expected_args = {}
                    for param_name in all_test_arguments:
                        parsed_param_name = param_name[2:].replace("-", "_")

                        if param_name not in test_arg_names:
                            expected_args[
                                parsed_param_name
                            ] = default_arg_values[param_name]
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
            "One or more key / value argument list(s)"
            "passed in the query string (expected_args)"
            "to the API do not match the values in "
            "the returned query string. This "
            "means that some arguments were "
            "dropped / added / changed by the "
            "the function, which is incorrect "
            "behavior. The list of incorrect "
            "arguments is as follows: \n"
        )
        pp = pprint.PrettyPrinter(depth=3, stream=error_message)
        pp.pprint(failures)
        self.assertDictEqual({}, failures, error_message.getvalue())


class TestUpdateMaasClusterConf(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(ClusterConfigurationFixture())

    def make_args(self, **kwargs):
        args = Mock()
        args.__dict__.update(kwargs)
        return args

    def test_config_set_maas_url_sets_url(self):
        expected = factory.make_simple_http_url()
        cluster_config_command.run(self.make_args(region_url=expected))
        with ClusterConfiguration.open() as config:
            observed = config.maas_url
        self.assertEqual([expected], observed)

    def test_config_set_maas_url_without_setting_does_nothing(self):
        with ClusterConfiguration.open() as config:
            expected = config.maas_url
        cluster_config_command.run(self.make_args(region_url=None))
        with ClusterConfiguration.open() as config:
            observed = config.maas_url
        self.assertEqual(expected, observed)

    def test_config_set_tftp_port_sets_tftp_port(self):
        expected = factory.pick_port()
        cluster_config_command.run(self.make_args(tftp_port=expected))
        with ClusterConfiguration.open() as config:
            observed = config.tftp_port
        self.assertEqual(expected, observed)

    def test_config_set_tftp_port_without_setting_does_nothing(self):
        with ClusterConfiguration.open() as config:
            expected = config.tftp_port
        cluster_config_command.run(self.make_args(tftp_port=None))
        with ClusterConfiguration.open() as config:
            observed = config.tftp_port
        self.assertEqual(expected, observed)

    def test_config_set_tftp_root_sets_tftp_root(self):
        expected = self.make_dir()
        cluster_config_command.run(self.make_args(tftp_root=expected))
        with ClusterConfiguration.open() as config:
            observed = config.tftp_root
        self.assertEqual(expected, observed)

    def test_config_set_tftp_root_without_setting_does_nothing(self):
        with ClusterConfiguration.open() as config:
            expected = config.tftp_root
        cluster_config_command.run(self.make_args(tftp_root=None))
        with ClusterConfiguration.open() as config:
            observed = config.tftp_root
        self.assertEqual(expected, observed)

    def test_config_set_debug_sets_debug(self):
        expected = factory.pick_bool()
        cluster_config_command.run(self.make_args(debug=expected))
        with ClusterConfiguration.open() as config:
            observed = config.debug
        self.assertEqual(expected, observed)

    def test_config_set_debug_without_setting_does_nothing(self):
        with ClusterConfiguration.open() as config:
            expected = config.debug
        cluster_config_command.run(self.make_args(debug=None))
        with ClusterConfiguration.open() as config:
            observed = config.debug
        self.assertEqual(expected, observed)
