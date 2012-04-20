# Copyright 2005-2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the psmaas TAP."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from base64 import b64encode
from functools import partial
from getpass import getuser
import httplib
import os
from StringIO import StringIO
from textwrap import dedent
import xmlrpclib

import formencode
from maastesting.factory import factory
from maastesting.testcase import TestCase
from provisioningserver.plugin import (
    Config,
    Options,
    ProvisioningRealm,
    ProvisioningServiceMaker,
    SingleUsernamePasswordChecker,
    )
from provisioningserver.testing.fakecobbler import make_fake_cobbler_session
from testtools.deferredruntest import (
    assert_fails_with,
    AsynchronousDeferredRunTest,
    )
from testtools.matchers import (
    MatchesException,
    Raises,
    )
from twisted.application.internet import TCPServer
from twisted.application.service import MultiService
from twisted.cred.credentials import UsernamePassword
from twisted.cred.error import UnauthorizedLogin
from twisted.internet.defer import inlineCallbacks
from twisted.python.usage import UsageError
from twisted.web.guard import HTTPAuthSessionWrapper
from twisted.web.resource import IResource
from twisted.web.server import NOT_DONE_YET
from twisted.web.test.test_web import DummyRequest
import yaml


class TestConfig(TestCase):
    """Tests for `provisioningserver.plugin.Config`."""

    def test_defaults(self):
        mandatory = {
            'password': 'killing_joke',
            }
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
            'interface': '127.0.0.1',
            'port': 5241,
            'username': getuser(),
            }
        expected.update(mandatory)
        observed = Config.to_python(mandatory)
        self.assertEqual(expected, observed)

    def test_parse(self):
        # Configuration can be parsed from a snippet of YAML.
        observed = Config.parse(
            b'logfile: "/some/where.log"\n'
            b'password: "black_sabbath"\n'
            )
        self.assertEqual("/some/where.log", observed["logfile"])

    def test_load(self):
        # Configuration can be loaded and parsed from a file.
        config = dedent("""
            logfile: "/some/where.log"
            password: "megadeth"
            """)
        filename = self.make_file(name="config.yaml", contents=config)
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

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def setUp(self):
        super(TestProvisioningServiceMaker, self).setUp()
        self.tempdir = self.make_dir()

    def write_config(self, config):
        config.setdefault("password", factory.getRandomString())
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

    def test_makeService_api_requires_credentials(self):
        """
        The site service's /api resource requires credentials from clients.
        """
        options = Options()
        options["config-file"] = self.write_config({})
        service_maker = ProvisioningServiceMaker("Harry", "Hill")
        service = service_maker.makeService(options)
        self.assertIsInstance(service, MultiService)
        site_service = service.getServiceNamed("site")
        self.assertIsInstance(site_service, TCPServer)
        port, site = site_service.args
        self.assertIn("api", site.resource.listStaticNames())
        api = site.resource.getStaticEntity("api")
        # HTTPAuthSessionWrapper demands credentials from an HTTP request.
        self.assertIsInstance(api, HTTPAuthSessionWrapper)

    def exercise_api_credentials(self, config_file, username, password):
        """
        Create a new service with :class:`ProvisioningServiceMaker` and
        attempt to access the API with the given credentials.
        """
        options = Options()
        options["config-file"] = config_file
        service_maker = ProvisioningServiceMaker("Morecombe", "Wise")
        # Terminate the service in a fake Cobbler session.
        service_maker._makeCobblerSession = (
            lambda config: make_fake_cobbler_session())
        service = service_maker.makeService(options)
        port, site = service.getServiceNamed("site").args
        api = site.resource.getStaticEntity("api")
        # Create an XML-RPC request with valid credentials.
        request = DummyRequest([])
        request.method = "POST"
        request.content = StringIO(xmlrpclib.dumps((), "get_nodes"))
        request.prepath = ["api"]
        request.headers["authorization"] = (
            "Basic %s" % b64encode(b"%s:%s" % (username, password)))
        # The credential check and resource rendering is deferred, but
        # NOT_DONE_YET is returned from render(). The request signals
        # completion with the aid of notifyFinish().
        finished = request.notifyFinish()
        self.assertEqual(NOT_DONE_YET, api.render(request))
        return finished.addCallback(lambda ignored: request)

    @inlineCallbacks
    def test_makeService_api_accepts_valid_credentials(self):
        """
        The site service's /api resource accepts valid credentials.
        """
        config = {"username": "orange", "password": "goblin"}
        request = yield self.exercise_api_credentials(
            self.write_config(config), "orange", "goblin")
        # A valid XML-RPC response has been written.
        self.assertEqual(None, request.responseCode)  # None implies 200.
        xmlrpclib.loads(b"".join(request.written))

    @inlineCallbacks
    def test_makeService_api_rejects_invalid_credentials(self):
        """
        The site service's /api resource rejects invalid credentials.
        """
        config = {"username": "orange", "password": "goblin"}
        request = yield self.exercise_api_credentials(
            self.write_config(config), "abigail", "williams")
        # The request has not been authorized.
        self.assertEqual(httplib.UNAUTHORIZED, request.responseCode)


class TestSingleUsernamePasswordChecker(TestCase):
    """Tests for `SingleUsernamePasswordChecker`."""

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    @inlineCallbacks
    def test_requestAvatarId_okay(self):
        credentials = UsernamePassword("frank", "zappa")
        checker = SingleUsernamePasswordChecker("frank", "zappa")
        avatar = yield checker.requestAvatarId(credentials)
        self.assertEqual("frank", avatar)

    def test_requestAvatarId_bad(self):
        credentials = UsernamePassword("frank", "zappa")
        checker = SingleUsernamePasswordChecker("zap", "franka")
        d = checker.requestAvatarId(credentials)
        return assert_fails_with(d, UnauthorizedLogin)


class TestProvisioningRealm(TestCase):
    """Tests for `ProvisioningRealm`."""

    def test_requestAvatar_okay(self):
        resource = object()
        realm = ProvisioningRealm(resource)
        avatar = realm.requestAvatar(
            "irrelevant", "also irrelevant", IResource)
        self.assertEqual((IResource, resource, realm.noop), avatar)

    def test_requestAvatar_bad(self):
        # If IResource is not amongst the interfaces passed to requestAvatar,
        # NotImplementedError is raised.
        resource = object()
        realm = ProvisioningRealm(resource)
        self.assertRaises(
            NotImplementedError, realm.requestAvatar,
            "irrelevant", "also irrelevant")
