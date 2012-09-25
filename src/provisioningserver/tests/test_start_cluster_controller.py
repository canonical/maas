# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `start_cluster_controller` command."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from argparse import ArgumentParser
from collections import namedtuple
import httplib
from io import BytesIO
import json
from urllib2 import (
    HTTPError,
    URLError,
    )

from apiclient.maas_client import MAASDispatcher
from apiclient.testing.django import parse_headers_and_body_with_django
from fixtures import EnvironmentVariableFixture
from maastesting.factory import factory
from provisioningserver import start_cluster_controller
from provisioningserver.testing.testcase import PservTestCase


class Sleeping(Exception):
    """Exception: `sleep` has been called."""


class Executing(Exception):
    """Exception: an attempt has been made to start another process.

    It would be inadvisable for tests in this test case to attempt to start
    a real celeryd, so we want to know when it tries.
    """


FakeArgs = namedtuple('FakeArgs', ['server_url'])


class FakeURLOpenResponse:
    """Cheap simile of a `urlopen` result."""

    def __init__(self, content, status=httplib.OK):
        self._content = content
        self._status_code = status

    def read(self):
        return self._content

    def getcode(self):
        return self._status_code


def make_url(name_hint='host'):
    return "http://%s.example.com/%s/" % (
        factory.make_name(name_hint),
        factory.make_name('path'),
        )


class TestStartClusterController(PservTestCase):

    def setUp(self):
        super(TestStartClusterController, self).setUp()
        self.patch(start_cluster_controller, 'sleep').side_effect = Sleeping()
        self.patch(start_cluster_controller, 'Popen').side_effect = (
            Executing())

    def make_connection_details(self):
        return {
            'BROKER_URL': make_url('broker'),
        }

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

    def test_run_command(self):
        # We can't really run the script, but we can verify that (with
        # the right system functions patched out) we can run it
        # directly.
        self.patch(start_cluster_controller, 'Popen')
        self.patch(start_cluster_controller, 'sleep')
        self.prepare_success_response()
        parser = ArgumentParser()
        start_cluster_controller.add_arguments(parser)
        start_cluster_controller.run(parser.parse_args((make_url(), )))
        self.assertNotEqual(0, start_cluster_controller.Popen.call_count)

    def test_uses_given_url(self):
        url = make_url('region')
        self.patch(start_cluster_controller, 'start_up')
        self.prepare_success_response()
        start_cluster_controller.run(FakeArgs(url))
        (args, kwargs) = MAASDispatcher.dispatch_query.call_args
        self.assertEqual(url + 'api/1.0/nodegroups', args[0])

    def test_fails_if_declined(self):
        self.patch(start_cluster_controller, 'start_up')
        self.prepare_rejection_response()
        self.assertRaises(
            start_cluster_controller.ClusterControllerRejected,
            start_cluster_controller.run, FakeArgs(make_url()))
        self.assertItemsEqual([], start_cluster_controller.start_up.calls_list)

    def test_polls_while_pending(self):
        self.patch(start_cluster_controller, 'start_up')
        self.prepare_pending_response()
        self.assertRaises(
            Sleeping,
            start_cluster_controller.run, FakeArgs(make_url()))
        self.assertItemsEqual([], start_cluster_controller.start_up.calls_list)

    def test_polls_on_unexpected_errors(self):
        self.patch(start_cluster_controller, 'start_up')
        self.patch(MAASDispatcher, 'dispatch_query').side_effect = HTTPError(
            make_url(), httplib.REQUEST_TIMEOUT, "Timeout.", '', BytesIO())
        self.assertRaises(
            Sleeping,
            start_cluster_controller.run, FakeArgs(make_url()))
        self.assertItemsEqual([], start_cluster_controller.start_up.calls_list)

    def test_starts_up_once_accepted(self):
        self.patch(start_cluster_controller, 'start_up')
        connection_details = self.prepare_success_response()
        server_url = make_url()
        start_cluster_controller.run(FakeArgs(server_url))
        start_cluster_controller.start_up.assert_called_once_with(
            server_url, connection_details)

    def test_start_up_calls_refresh_secrets(self):
        url = make_url('region')
        connection_details = self.make_connection_details()
        self.patch(start_cluster_controller, 'Popen')
        self.patch(start_cluster_controller, 'sleep')
        self.prepare_response('OK', httplib.OK)

        start_cluster_controller.start_up(url, connection_details)

        (args, kwargs) = MAASDispatcher.dispatch_query.call_args
        self.assertEqual(url + 'api/1.0/nodegroups', args[0])
        self.assertEqual('POST', kwargs['method'])

        # Make Django STFU; just using Django's multipart code causes it to
        # pull in a settings module, and it will throw up if it can't.
        self.useFixture(
            EnvironmentVariableFixture(
                "DJANGO_SETTINGS_MODULE", __name__))

        headers, body = kwargs["headers"], kwargs["data"]
        post, files = parse_headers_and_body_with_django(headers, body)
        self.assertEqual("refresh_workers", post["op"])

    def test_start_up_ignores_failure_on_refresh_secrets(self):
        self.patch(start_cluster_controller, 'Popen')
        self.patch(start_cluster_controller, 'sleep')
        self.patch(MAASDispatcher, 'dispatch_query').side_effect = URLError(
            "Simulated HTTP failure.")

        start_cluster_controller.start_up(
            make_url(), self.make_connection_details())

        self.assertNotEqual(0, start_cluster_controller.Popen.call_count)
