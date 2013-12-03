# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver API documentation functionality."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from inspect import getdoc
import new

from django.conf import settings
from django.conf.urls import (
    include,
    patterns,
    url,
    )
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from maasserver.api_support import (
    operation,
    OperationsHandler,
    OperationsResource,
    )
from maasserver.apidoc import (
    describe_handler,
    describe_resource,
    find_api_resources,
    generate_api_docs,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from mock import sentinel
from piston.doc import HandlerDocumentation
from piston.handler import BaseHandler
from piston.resource import Resource


class TestFindingResources(MAASServerTestCase):
    """Tests for API inspection support: finding resources."""

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/doc/', reverse('api-doc'))

    @staticmethod
    def make_module():
        """Return a new module with a fabricated name."""
        name = factory.make_name("module").encode("ascii")
        return new.module(name)

    def test_urlpatterns_empty(self):
        # No resources are found in empty modules.
        module = self.make_module()
        module.urlpatterns = patterns("")
        self.assertSetEqual(set(), find_api_resources(module))

    def test_urlpatterns_not_present(self):
        # The absence of urlpatterns is an error.
        module = self.make_module()
        self.assertRaises(ImproperlyConfigured, find_api_resources, module)

    def test_urlpatterns_with_resource_for_incomplete_handler(self):
        # Resources for handlers that don't specify resource_uri are ignored.
        module = self.make_module()
        module.urlpatterns = patterns("", url("^foo", BaseHandler))
        self.assertSetEqual(set(), find_api_resources(module))

    def test_urlpatterns_with_resource(self):
        # Resources for handlers with resource_uri attributes are discovered
        # in a urlconf module and returned. The type of resource_uri is not
        # checked; it must only be present and not None.
        handler = type(b"\m/", (BaseHandler,), {"resource_uri": True})
        resource = Resource(handler)
        module = self.make_module()
        module.urlpatterns = patterns("", url("^metal", resource))
        self.assertSetEqual({resource}, find_api_resources(module))

    def test_nested_urlpatterns_with_handler(self):
        # Resources are found in nested urlconfs.
        handler = type(b"\m/", (BaseHandler,), {"resource_uri": True})
        resource = Resource(handler)
        module = self.make_module()
        submodule = self.make_module()
        submodule.urlpatterns = patterns("", url("^metal", resource))
        module.urlpatterns = patterns("", ("^genre/", include(submodule)))
        self.assertSetEqual({resource}, find_api_resources(module))

    def test_smoke(self):
        # Resources are found for the MAAS API.
        from maasserver import urls_api as urlconf
        self.assertNotEqual(set(), find_api_resources(urlconf))


class TestGeneratingDocs(MAASServerTestCase):
    """Tests for API inspection support: generating docs."""

    @staticmethod
    def make_resource():
        """
        Return a new `OperationsResource` with a `BaseHandler` subclass
        handler, with a fabricated name and a `resource_uri` class-method.
        """
        name = factory.make_name("handler").encode("ascii")
        resource_uri = lambda cls: factory.make_name("resource-uri")
        namespace = {"resource_uri": classmethod(resource_uri)}
        handler = type(name, (BaseHandler,), namespace)
        return OperationsResource(handler)

    def test_generates_doc_for_handler(self):
        # generate_api_docs() yields HandlerDocumentation objects for the
        # handlers passed in.
        resource = self.make_resource()
        docs = list(generate_api_docs([resource]))
        self.assertEqual(1, len(docs))
        [doc] = docs
        self.assertIsInstance(doc, HandlerDocumentation)
        self.assertIs(type(resource.handler), doc.handler)

    def test_generates_doc_for_multiple_handlers(self):
        # generate_api_docs() yields HandlerDocumentation objects for the
        # handlers passed in.
        resources = [self.make_resource() for _ in range(5)]
        docs = list(generate_api_docs(resources))
        self.assertEqual(
            [type(resource.handler) for resource in resources],
            [doc.handler for doc in docs])

    def test_handler_without_resource_uri(self):
        # generate_api_docs() raises an exception if a handler does not have a
        # resource_uri attribute.
        resource = OperationsResource(BaseHandler)
        docs = generate_api_docs([resource])
        error = self.assertRaises(AssertionError, list, docs)
        self.assertEqual(
            "Missing resource_uri in %s" % type(resource.handler).__name__,
            unicode(error))


class ExampleHandler(OperationsHandler):
    """An example handler."""

    create = read = delete = None

    @operation(idempotent=False)
    def non_idempotent_operation(self, request, p_foo, p_bar):
        """A non-idempotent operation.

        Will piggyback on POST requests.
        """

    @operation(idempotent=True)
    def idempotent_operation(self, request, p_foo, p_bar):
        """An idempotent operation.

        Will piggyback on GET requests.
        """

    @classmethod
    def resource_uri(cls):
        # Note that the arguments, after request, to each of the ops
        # above matches the parameters (index 1) in the tuple below.
        return ("example_view", ["p_foo", "p_bar"])


class ExampleFallbackHandler(OperationsHandler):
    """An example fall-back handler."""

    create = read = delete = update = None


class TestDescribingAPI(MAASServerTestCase):
    """Tests for functions that describe a Piston API."""

    def setUp(self):
        super(TestDescribingAPI, self).setUp()
        # Override DEFAULT_MAAS_URL so that it's stable for testing.
        self.patch(settings, "DEFAULT_MAAS_URL", "http://example.com/")

    def test_describe_handler(self):
        # describe_handler() returns a description of a handler that can be
        # readily serialised into JSON, for example.
        expected_actions = [
            {"doc": getdoc(ExampleHandler.idempotent_operation),
             "method": "GET",
             "name": "idempotent_operation",
             "op": "idempotent_operation",
             "restful": False},
            {"doc": getdoc(ExampleHandler.non_idempotent_operation),
             "method": "POST",
             "name": "non_idempotent_operation",
             "op": "non_idempotent_operation",
             "restful": False},
            {"doc": None,
             "method": "PUT",
             "name": "update",
             "op": None,
             "restful": True},
            ]
        observed = describe_handler(ExampleHandler)
        # The description contains several entries.
        self.assertSetEqual(
            {"actions", "doc", "name", "params", "path"},
            set(observed))
        self.assertEqual(ExampleHandler.__doc__, observed["doc"])
        self.assertEqual(ExampleHandler.__name__, observed["name"])
        self.assertEqual(["p_foo", "p_bar"], observed["params"])
        self.assertItemsEqual(expected_actions, observed["actions"])

    def test_describe_handler_with_maas_handler(self):
        # Ensure that describe_handler() yields something sensible with a
        # "real" MAAS API handler.
        from maasserver.api import NodeHandler as handler
        description = describe_handler(handler)
        # The RUD of CRUD actions are still available, but the C(reate) action
        # has been overridden with custom non-ReSTful operations.
        expected_actions = {
            "DELETE delete op=None restful=True",
            "GET read op=None restful=True",
            "GET details op=details restful=False",
            "POST start op=start restful=False",
            "POST stop op=stop restful=False",
            "POST release op=release restful=False",
            "POST commission op=commission restful=False",
            "PUT update op=None restful=True",
            }
        observed_actions = {
            "%(method)s %(name)s op=%(op)s restful=%(restful)s" % action
            for action in description["actions"]
            }
        self.assertSetEqual(expected_actions, observed_actions)
        self.assertSetEqual({"system_id"}, set(description["params"]))
        # The path is a URI Template <http://tools.ietf.org/html/rfc6570>, the
        # components of which correspond to the parameters declared.
        self.assertEqual(
            "/api/1.0/nodes/{system_id}/",
            description["path"])

    def test_describe_resource_anonymous_resource(self):
        # When the resource does not require authentication, any configured
        # fallback is ignored, and only the resource's handler is described.
        # The resource name comes from this handler.
        self.patch(ExampleHandler, "anonymous", ExampleFallbackHandler)
        resource = OperationsResource(ExampleHandler)
        expected = {
            "anon": describe_handler(ExampleHandler),
            "auth": None,
            "name": "ExampleHandler",
            }
        self.assertEqual(expected, describe_resource(resource))

    def test_describe_resource_authenticated_resource(self):
        # When the resource requires authentication, but has no fallback
        # anonymous handler, the first is described. The resource name comes
        # from this handler.
        resource = OperationsResource(ExampleHandler, sentinel.auth)
        expected = {
            "anon": None,
            "auth": describe_handler(ExampleHandler),
            "name": "ExampleHandler",
            }
        self.assertEqual(expected, describe_resource(resource))

    def test_describe_resource_authenticated_resource_with_fallback(self):
        # When the resource requires authentication, but has a fallback
        # anonymous handler, both are described. The resource name is taken
        # from the authenticated handler.
        self.patch(ExampleHandler, "anonymous", ExampleFallbackHandler)
        resource = OperationsResource(ExampleHandler, sentinel.auth)
        expected = {
            "anon": describe_handler(ExampleFallbackHandler),
            "auth": describe_handler(ExampleHandler),
            "name": "ExampleHandler",
            }
        self.assertEqual(expected, describe_resource(resource))
