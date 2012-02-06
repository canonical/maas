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
import os
from unittest import skip

from fixtures import TempDir
from provisioningserver.plugin import (
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


class TestOptions(TestCase):
    """Tests for `provisioningserver.plugin.Options`."""

    def test_defaults(self):
        options = Options()
        expected = {
            "brokerhost": "127.0.0.1",
            "brokerpassword": None,
            "brokerport": 5672,
            "brokeruser": None,
            "brokervhost": "/",
            "logfile": "provisioningserver.log",
            "oops-dir": None,
            "oops-reporter": "MAAS-PS",
            "port": 8001,
            }
        self.assertEqual(expected, options.defaults)

    def check_exception(self, options, message, *arguments):
        # Check that a UsageError is raised when parsing options.
        self.assertThat(
            partial(options.parseOptions, arguments),
            Raises(MatchesException(UsageError, message)))

    @skip(
        "RabbitMQ is not yet a required component "
        "of a running MaaS installation.")
    def test_option_brokeruser_required(self):
        options = Options()
        self.check_exception(
            options,
            "--brokeruser must be specified")

    @skip(
        "RabbitMQ is not yet a required component "
        "of a running MaaS installation.")
    def test_option_brokerpassword_required(self):
        options = Options()
        self.check_exception(
            options,
            "--brokerpassword must be specified",
            "--brokeruser", "Bob")

    def test_parse_minimal_options(self):
        options = Options()
        # The minimal set of options that must be provided.
        arguments = []
        options.parseOptions(arguments)  # No error.

    def test_parse_int_options(self):
        # Some options are converted to ints.
        options = Options()
        arguments = [
            "--brokerpassword", "Hoskins",
            "--brokerport", "4321",
            "--brokeruser", "Bob",
            "--port", "3456",
            ]
        options.parseOptions(arguments)
        self.assertEqual(4321, options["brokerport"])
        self.assertEqual(3456, options["port"])

    def test_parse_broken_int_options(self):
        # An error is raised if the integer options do not contain integers.
        options = Options()
        arguments = [
            "--brokerpassword", "Hoskins",
            "--brokerport", "Jr.",
            "--brokeruser", "Bob",
            ]
        self.assertRaises(
            UsageError, options.parseOptions, arguments)

    def test_oops_dir_without_reporter(self):
        # It is an error to omit the OOPS reporter if directory is specified.
        options = Options()
        arguments = [
            "--brokerpassword", "Hoskins",
            "--brokeruser", "Bob",
            "--oops-dir", "/some/where",
            "--oops-reporter", "",
            ]
        expected = MatchesException(
            UsageError, "A reporter must be supplied")
        self.assertThat(
            partial(options.parseOptions, arguments),
            Raises(expected))


class TestProvisioningServiceMaker(TestCase):
    """Tests for `provisioningserver.plugin.ProvisioningServiceMaker`."""

    def get_log_file(self):
        return os.path.join(
            self.useFixture(TempDir()).path,
            "provisioningserver.log")

    def test_init(self):
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        self.assertEqual("Harry", service_maker.tapname)
        self.assertEqual("Hill", service_maker.description)

    def test_makeService(self):
        """
        Only the site service is created when no options are given.
        """
        options = Options()
        options["logfile"] = self.get_log_file()
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        service = service_maker.makeService(options, _set_proc_title=False)
        self.assertIsInstance(service, MultiService)
        self.assertSequenceEqual(
            ["log", "oops", "site"],
            sorted(service.namedServices))
        self.assertEqual(
            len(service.namedServices), len(service.services),
            "Not all services are named.")
        site_service = service.getServiceNamed("site")
        self.assertEqual(options["port"], site_service.args[0])

    def test_makeService_with_broker(self):
        """
        The log, oops, site, and amqp services are created when the broker
        user and password options are given.
        """
        options = Options()
        options["brokerpassword"] = "Hoskins"
        options["brokeruser"] = "Bob"
        options["logfile"] = self.get_log_file()
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        service = service_maker.makeService(options, _set_proc_title=False)
        self.assertIsInstance(service, MultiService)
        self.assertSequenceEqual(
            ["amqp", "log", "oops", "site"],
            sorted(service.namedServices))
        self.assertEqual(
            len(service.namedServices), len(service.services),
            "Not all services are named.")
        amqp_client_service = service.getServiceNamed("amqp")
        self.assertEqual(options["brokerhost"], amqp_client_service.args[0])
        self.assertEqual(options["brokerport"], amqp_client_service.args[1])
        site_service = service.getServiceNamed("site")
        self.assertEqual(options["port"], site_service.args[0])
