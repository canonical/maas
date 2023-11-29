# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `describe` view."""


import http.client
from urllib.parse import urlparse

from django.test.client import RequestFactory
from django.urls import get_script_prefix, reverse, set_script_prefix
from testscenarios import multiply_scenarios

from maasserver.api.doc import get_api_description
from maasserver.api.doc_handler import describe
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maastesting.testcase import MAASTestCase


class TestDescribe(APITestCase.ForAnonymousAndUserAndAdmin):
    """Tests for the `describe` view."""

    def test_describe_returns_json(self):
        response = self.client.get(reverse("describe"))
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIsNotNone(response.json())

    def test_describe(self):
        response = self.client.get(reverse("describe"))
        description = json_load_bytes(response.content)
        self.assertSetEqual(
            {"doc", "handlers", "resources", "hash"}, set(description)
        )
        self.assertIsInstance(description["handlers"], list)

    def test_describe_hash_is_the_api_hash(self):
        response = self.client.get(reverse("describe"))
        description = json_load_bytes(response.content)
        self.assertEqual(description["hash"], get_api_description()["hash"])


class TestDescribeAbsoluteURIs(MAASTestCase):
    """Tests for the `describe` view's URI manipulation."""

    scenarios_schemes = (
        ("http", dict(scheme="http")),
        ("https", dict(scheme="https")),
    )

    scenarios_paths = (
        ("script-at-root", dict(script_name="", path_info="")),
        ("script-below-root-1", dict(script_name="/foo/bar", path_info="")),
        ("script-below-root-2", dict(script_name="/foo", path_info="/bar")),
    )

    scenarios = multiply_scenarios(scenarios_schemes, scenarios_paths)

    def make_params(self):
        """Create parameters for http request, based on current scenario."""
        return {
            "PATH_INFO": self.path_info,
            "SCRIPT_NAME": self.script_name,
            "SERVER_NAME": factory.make_name("server").lower(),
            "wsgi.url_scheme": self.scheme,
        }

    def get_description(self, params):
        """GET the API description (at a random API path), as JSON."""
        path = "/%s/describe" % factory.make_name("path")
        request = RequestFactory().get(path, **params)
        response = describe(request)
        self.assertEqual(
            http.client.OK,
            response.status_code,
            "API description failed with code %s:\n%s"
            % (response.status_code, response.content),
        )
        return json_load_bytes(response.content)

    def patch_script_prefix(self, script_name):
        """Patch up Django's and Piston's notion of the script_name prefix.

        This manipulates how Piston gets Django's version of script_name
        which it needs so that it can prefix script_name to URL paths.
        """
        # clear the cached API description since the following patching causes
        # changes in the handlers URIs
        get_api_description.cache_clear()
        # Patching up get_script_prefix doesn't seem to do the trick,
        # and patching it in the right module requires unwarranted
        # intimacy with Piston.  So just go through the proper call and
        # set the prefix.  But clean this up after the test or it will
        # break other tests!
        original_prefix = get_script_prefix()
        self.addCleanup(set_script_prefix, original_prefix)
        set_script_prefix(script_name)

    def test_handler_uris_are_absolute(self):
        params = self.make_params()
        server = params["SERVER_NAME"]

        # Without this, the test wouldn't be able to detect accidental
        # duplication of the script_name portion of the URL path:
        # /MAAS/MAAS/api/...
        self.patch_script_prefix(self.script_name)

        description = self.get_description(params)
        resources = description["resources"]

        self.assertNotEqual([], resources)
        for resource in resources:
            anon_response = resource["anon"]
            auth_response = resource["auth"]

            if anon_response is None:
                matcher = auth_response
            else:
                matcher = anon_response
            url = urlparse(matcher["uri"])
            self.assertEqual(url.scheme, self.scheme)
            self.assertEqual(url.hostname, server)
            self.assertTrue(url.path.startswith(f"{self.script_name}/api/"))
