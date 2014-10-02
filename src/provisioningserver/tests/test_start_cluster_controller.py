# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `start_cluster_controller` command."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from argparse import ArgumentParser
from collections import namedtuple
import httplib
from io import BytesIO
import json
from urllib2 import HTTPError

from apiclient.maas_client import MAASDispatcher
from apiclient.testing.django import parse_headers_and_body_with_django
from fixtures import EnvironmentVariableFixture
from maastesting.factory import factory
from provisioningserver import start_cluster_controller
from provisioningserver.testing.testcase import PservTestCase
from testtools.matchers import StartsWith

# Some tests in this file have to import methods from Django.  This causes
# Django to parse its settings file and, in Django 1.5+, assert that it
# contains a value for the setting 'SECRET_KEY'.
# The trick we use here is to use this very module as Django's settings
# module and define a value for 'SECRET_KEY'.
SECRET_KEY = 'bogus secret key'


class Sleeping(Exception):
    """Exception: `sleep` has been called."""


def make_url(name_hint='host'):
    return "http://%s.example.com/%s/" % (
        factory.make_name(name_hint),
        factory.make_name('path'),
        )


FakeArgs = namedtuple('FakeArgs', ['server_url'])


def make_args(server_url=None):
    if server_url is None:
        server_url = make_url('region')
    return FakeArgs(server_url)


class FakeURLOpenResponse:
    """Cheap simile of a `urlopen` result."""

    def __init__(self, content, status=httplib.OK):
        self._content = content
        self._status_code = status

    def read(self):
        return self._content

    def getcode(self):
        return self._status_code


class TestStartClusterController(PservTestCase):

    def setUp(self):
        super(TestStartClusterController, self).setUp()
        # Patch out anything that could be remotely harmful if we did it
        # accidentally in the test.  Make the really outrageous ones
        # raise exceptions.
        self.patch_autospec(
            start_cluster_controller, 'sleep').side_effect = Sleeping()
        get_uuid = self.patch_autospec(
            start_cluster_controller, 'get_cluster_uuid')
        get_uuid.return_value = factory.make_UUID()

    def make_connection_details(self):
        return {
            'BROKER_URL': make_url('broker'),
        }

    def parse_headers_and_body(self, headers, body):
        """Parse ingredients of a web request.

        The headers and body are as passed to :class:`MAASDispatcher`.
        """
        # Make Django STFU; just using Django's multipart code causes it to
        # pull in a settings module, and it will throw up if it can't.
        self.useFixture(
            EnvironmentVariableFixture(
                "DJANGO_SETTINGS_MODULE", __name__))

        post, files = parse_headers_and_body_with_django(headers, body)
        return post, files

    def prepare_response(self, http_code, content=""):
        """Prepare to return the given http response from API request."""
        fake = self.patch(MAASDispatcher, 'dispatch_query')
        fake.return_value = FakeURLOpenResponse(content, status=http_code)
        return fake

    def prepare_success_response(self):
        """Prepare to return connection details from API request."""
        details = self.make_connection_details()
        self.prepare_response(httplib.OK, json.dumps(details))
        return details

    def prepare_rejection_response(self):
        """Prepare to return "rejected" from API request."""
        self.prepare_response(httplib.FORBIDDEN)

    def prepare_pending_response(self):
        """Prepare to return "request pending" from API request."""
        self.prepare_response(httplib.ACCEPTED)

    def prepare_rpc_wait_response(self):
        """Prepare to return "waiting for RPC" from API request."""
        self.prepare_response(httplib.SERVICE_UNAVAILABLE)

    def test_run_command(self):
        # We can't really run the script, but we can verify that (with
        # the right system functions patched out) we can run it
        # directly.
        start_cluster_controller.sleep.side_effect = None
        self.prepare_success_response()
        parser = ArgumentParser()
        start_cluster_controller.add_arguments(parser)
        self.assertIsNone(
            start_cluster_controller.run(
                parser.parse_args((make_url(),))))

    def test_uses_given_url(self):
        url = make_url('region')
        self.prepare_success_response()
        start_cluster_controller.run(make_args(server_url=url))
        (args, kwargs) = MAASDispatcher.dispatch_query.call_args
        self.assertThat(args[0], StartsWith(url + 'api/1.0/nodegroups/'))

    def test_fails_if_declined(self):
        self.prepare_rejection_response()
        self.assertRaises(
            start_cluster_controller.ClusterControllerRejected,
            start_cluster_controller.run, make_args())

    def test_polls_while_pending(self):
        self.prepare_pending_response()
        self.assertRaises(
            Sleeping,
            start_cluster_controller.run, make_args())

    def test_polls_on_rpc_wait(self):
        self.prepare_rpc_wait_response()
        self.assertRaises(
            Sleeping,
            start_cluster_controller.run, make_args())

    def test_polls_on_unexpected_errors(self):
        self.patch(MAASDispatcher, 'dispatch_query').side_effect = HTTPError(
            make_url(), httplib.REQUEST_TIMEOUT, "Timeout.", '', BytesIO())
        self.assertRaises(
            Sleeping,
            start_cluster_controller.run, make_args())

    def test_register_passes_cluster_information(self):
        self.prepare_success_response()
        interface = {
            'interface': factory.make_name('eth'),
            'ip': factory.make_ipv4_address(),
            'subnet_mask': '255.255.255.0',
            }
        discover = self.patch(start_cluster_controller, 'discover_networks')
        discover.return_value = [interface]

        start_cluster_controller.register(make_url())

        (args, kwargs) = MAASDispatcher.dispatch_query.call_args
        headers, body = kwargs["headers"], kwargs["data"]
        post, files = self.parse_headers_and_body(headers, body)
        self.assertEqual([interface], json.loads(post['interfaces']))
        self.assertEqual(
            start_cluster_controller.get_cluster_uuid.return_value,
            post['uuid'])
