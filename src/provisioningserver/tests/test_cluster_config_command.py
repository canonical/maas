# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `MAAS_URL` configuration update code."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = []

from argparse import ArgumentParser
from exceptions import SystemExit
from itertools import combinations
import pprint
import StringIO
import uuid

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from mock import (
    Mock,
    patch,
)
from provisioningserver import cluster_config_command
from provisioningserver.cluster_config import (
    CLUSTER_CONFIG,
    get_config_cluster_variable,
    set_config_cluster_variable,
)
from provisioningserver.config import UUID_NOT_SET
from provisioningserver.testing.config import ClusterConfigurationFixture
from testtools import ExpectedException


class TestAddArguments(MAASTestCase):

    def test_accepts_all_args(self):
        all_test_arguments = cluster_config_command.all_arguments

        default_arg_values = {
            '--region-url': None,
            '--uuid': None,
            '--init': False,
            '--tftp-port': None,
            '--tftp-root': None,
        }

        failures = {}

        # Try all cardinalities of combinations of arguments
        for r in range(len(all_test_arguments) + 1):
            for test_arg_names in combinations(all_test_arguments, r):
                test_values = {
                    '--region-url': factory.make_simple_http_url(),
                    '--uuid': unicode(uuid.uuid4()),
                    '--init': '',
                    '--tftp-port': unicode(factory.pick_port()),
                    '--tftp-root': factory.make_string(),
                }

                # Build a query dictionary for the given combination of args
                args_under_test = []
                for param_name in test_arg_names:
                    args_under_test.append(param_name)
                    if param_name != '--init':
                        args_under_test.append(test_values[param_name])

                parser = ArgumentParser()
                cluster_config_command.add_arguments(parser)

                # If both init and uuid are passed, argparse will generate
                # a nice ArgumentError exception, which unfortunately,
                # gets caught and sent to exit.
                if '--init' in test_arg_names and '--uuid' in test_arg_names:
                    expected_exception = ExpectedException(SystemExit, '2')
                    with expected_exception, patch('sys.stderr'):
                        parser.parse_known_args(args_under_test)

                else:
                    # Otherwise, parsed args with defaults as usual
                    observed_args = vars(
                        parser.parse_args(args_under_test))

                    expected_args = {}
                    for param_name in all_test_arguments:
                        parsed_param_name = param_name[2:].replace('-', '_')

                        if param_name not in test_arg_names:
                            expected_args[parsed_param_name] = \
                                default_arg_values[param_name]
                        else:
                            expected_args[parsed_param_name] = \
                                observed_args[parsed_param_name]

                    if expected_args != observed_args:
                        failures[unicode(test_arg_names)] = {
                            'expected_args': expected_args,
                            'observed_args': observed_args,
                        }

        error_message = StringIO.StringIO()
        error_message.write(
            "One or more key / value argument list(s)"
            "passed in the query string (expected_args)"
            "to the API do not match the values in "
            "the returned query string. This "
            "means that some arguments were "
            "dropped / added / changed by the "
            "the function, which is incorrect "
            "behavior. The list of incorrect "
            "arguments is as follows: \n")
        pp = pprint.PrettyPrinter(depth=3, stream=error_message)
        pp.pprint(failures)
        self.assertDictEqual({}, failures, error_message.getvalue())


class TestUpdateMaasClusterConf(MAASTestCase):

    def setUp(self):
        super(TestUpdateMaasClusterConf, self).setUp()
        self.useFixture(ClusterConfigurationFixture())

    def make_args(self, **kwargs):
        args = Mock()
        args.__dict__.update(kwargs)
        return args

    def test_config_set_maas_url_sets_url(self):
        expected = factory.make_simple_http_url()
        cluster_config_command.run(self.make_args(region_url=expected))
        observed = get_config_cluster_variable(CLUSTER_CONFIG.DB_maas_url)
        self.assertEqual(expected, observed)

    def test_config_set_maas_url_without_setting_does_nothing(self):
        expected = get_config_cluster_variable(CLUSTER_CONFIG.DB_maas_url)
        cluster_config_command.run(self.make_args(region_url=None))
        observed = get_config_cluster_variable(CLUSTER_CONFIG.DB_maas_url)
        self.assertEqual(expected, observed)

    def test_config_set_cluster_uuid_sets_cluster_uuid(self):
        expected = unicode(uuid.uuid4())
        cluster_config_command.run(self.make_args(uuid=expected))
        observed = get_config_cluster_variable(CLUSTER_CONFIG.DB_cluster_uuid)
        self.assertEqual(expected, observed)

    def get_parsed_uuid_from_config(self):
        observed = get_config_cluster_variable(CLUSTER_CONFIG.DB_cluster_uuid)
        try:
            parsed_observed = unicode(uuid.UUID(observed))
        except:
            parsed_observed = None

        return (parsed_observed, observed)

    def test_config_set_cluster_uuid_without_setting_does_nothing(self):
        expected_previous_value = unicode(uuid.uuid4())
        set_config_cluster_variable(
            CLUSTER_CONFIG.DB_cluster_uuid, expected_previous_value)
        observed_previous_value = get_config_cluster_variable(
            CLUSTER_CONFIG.DB_cluster_uuid)
        self.assertEqual(expected_previous_value, observed_previous_value)

        cluster_config_command.run(self.make_args(uuid=None))

        parsed_observed, observed = self.get_parsed_uuid_from_config()
        self.assertEqual(parsed_observed, observed)
        self.assertEqual(parsed_observed, expected_previous_value)

    def test_config_init_creates_initial_cluster_id(self):
        observed_default = get_config_cluster_variable(
            CLUSTER_CONFIG.DB_cluster_uuid)
        self.assertEqual(UUID_NOT_SET, observed_default)

        cluster_config_command.run(self.make_args(init=True))

        expected, observed = self.get_parsed_uuid_from_config()
        self.assertEqual(expected, observed)

    def test_config_init_when_already_configured_does_nothing(self):
        expected_previous_value = unicode(uuid.uuid4())
        set_config_cluster_variable(
            CLUSTER_CONFIG.DB_cluster_uuid, expected_previous_value)
        observed_previous_value = get_config_cluster_variable(
            CLUSTER_CONFIG.DB_cluster_uuid)
        self.assertEqual(expected_previous_value, observed_previous_value)

        cluster_config_command.run(self.make_args(init=True))

        parsed_observed, observed = self.get_parsed_uuid_from_config()
        self.assertEqual(parsed_observed, observed)
        self.assertEqual(parsed_observed, expected_previous_value)

    def test_config_set_tftp_port_sets_tftp_port(self):
        expected = factory.pick_port()
        cluster_config_command.run(self.make_args(tftp_port=expected))
        observed = get_config_cluster_variable(CLUSTER_CONFIG.DB_tftpport)
        self.assertEqual(expected, observed)

    def test_config_set_tftp_port_without_setting_does_nothing(self):
        expected = get_config_cluster_variable(CLUSTER_CONFIG.DB_tftpport)
        cluster_config_command.run(self.make_args(tftp_port=None))
        observed = get_config_cluster_variable(CLUSTER_CONFIG.DB_tftpport)
        self.assertEqual(expected, observed)

    def test_config_set_tftp_port_sets_tftp_root(self):
        expected = self.make_dir()
        cluster_config_command.run(self.make_args(tftp_root=expected))
        observed = get_config_cluster_variable(
            CLUSTER_CONFIG.DB_tftp_resource_root)
        self.assertEqual(expected, observed)

    def test_config_set_tftp_root_without_setting_does_nothing(self):
        expected = get_config_cluster_variable(
            CLUSTER_CONFIG.DB_tftp_resource_root)
        cluster_config_command.run(self.make_args(tftp_root=None))
        observed = get_config_cluster_variable(
            CLUSTER_CONFIG.DB_tftp_resource_root)

        self.assertEqual(expected, observed)
