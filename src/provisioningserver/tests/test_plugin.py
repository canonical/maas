# Copyright 2005-2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the psmaas TAP."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from functools import partial
from getpass import getuser
import os

from fixtures import TempDir
import formencode
from provisioningserver.plugin import (
    Config,
    Options,
    ProvisioningServiceMaker,
    )
from testtools import TestCase
from testtools.matchers import (
    MatchesException,
    Raises,
    )
from twisted.application.service import MultiService
from twisted.python.usage import UsageError
import yaml


class TestConfig(TestCase):
    """Tests for `provisioningserver.plugin.Config`."""

    def test_defaults(self):
        expected = {
            'broker': {
                'host': 'localhost',
                'port': 5673,
                'username': getuser(),
                'password': 'test',
                'vhost': '/',
                },
            'cobbler': {
                'url': 'http://localhost/cobbler_api',
                'username': getuser(),
                'password': 'test',
                },
            'logfile': 'pserv.log',
            'oops': {
                'directory': '',
                'reporter': '',
                },
            'port': 5241,
            'interface': '127.0.0.1',
            }
        observed = Config.to_python({})
        self.assertEqual(expected, observed)

    def test_parse(self):
        # Configuration can be parsed from a snippet of YAML.
        observed = Config.parse(b'logfile: "/some/where.log"')
        self.assertEqual("/some/where.log", observed["logfile"])

    def test_load(self):
        # Configuration can be loaded and parsed from a file.
        filename = os.path.join(
            self.useFixture(TempDir()).path, "config.yaml")
        with open(filename, "wb") as stream:
            stream.write(b'logfile: "/some/where.log"')
        observed = Config.load(filename)
        self.assertEqual("/some/where.log", observed["logfile"])

    def test_load_example(self):
        # The example configuration can be loaded and validated.
        filename = os.path.join(
            os.path.dirname(__file__), os.pardir,
            os.pardir, os.pardir, "etc", "pserv.yaml")
        Config.load(filename)

    def test_oops_directory_without_reporter(self):
        # It is an error to omit the OOPS reporter if directory is specified.
        config = (
            'oops:\n'
            '  directory: /tmp/oops\n'
            )
        expected = MatchesException(
            formencode.Invalid, "oops: You must give a value for reporter")
        self.assertThat(
            partial(Config.parse, config),
            Raises(expected))


class TestOptions(TestCase):
    """Tests for `provisioningserver.plugin.Options`."""

    def test_defaults(self):
        options = Options()
        expected = {"config-file": "pserv.yaml"}
        self.assertEqual(expected, options.defaults)

    def check_exception(self, options, message, *arguments):
        # Check that a UsageError is raised when parsing options.
        self.assertThat(
            partial(options.parseOptions, arguments),
            Raises(MatchesException(UsageError, message)))

    def test_parse_minimal_options(self):
        options = Options()
        # The minimal set of options that must be provided.
        arguments = []
        options.parseOptions(arguments)  # No error.


class TestProvisioningServiceMaker(TestCase):
    """Tests for `provisioningserver.plugin.ProvisioningServiceMaker`."""

    def setUp(self):
        super(TestProvisioningServiceMaker, self).setUp()
        self.tempdir = self.useFixture(TempDir()).path

    def write_config(self, config):
        config_filename = os.path.join(self.tempdir, "config.yaml")
        with open(config_filename, "wb") as stream:
            yaml.dump(config, stream)
        return config_filename

    def test_init(self):
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        self.assertEqual("Harry", service_maker.tapname)
        self.assertEqual("Hill", service_maker.description)

    def test_makeService(self):
        """
        Only the site service is created when no options are given.
        """
        options = Options()
        options["config-file"] = self.write_config({})
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        service = service_maker.makeService(options)
        self.assertIsInstance(service, MultiService)
        self.assertSequenceEqual(
            ["log", "oops", "site"],
            sorted(service.namedServices))
        self.assertEqual(
            len(service.namedServices), len(service.services),
            "Not all services are named.")

    def test_makeService_with_broker(self):
        """
        The log, oops, site, and amqp services are created when the broker
        user and password options are given.
        """
        options = Options()
        options["config-file"] = self.write_config(
            {"broker": {"username": "Bob", "password": "Hoskins"}})
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        service = service_maker.makeService(options)
        self.assertIsInstance(service, MultiService)
        self.assertSequenceEqual(
            ["amqp", "log", "oops", "site"],
            sorted(service.namedServices))
        self.assertEqual(
            len(service.namedServices), len(service.services),
            "Not all services are named.")
