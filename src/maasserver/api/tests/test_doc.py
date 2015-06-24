# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
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

from django.conf.urls import (
    include,
    patterns,
    url,
)
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from maasserver.api import doc as doc_module
from maasserver.api.doc import (
    describe_api,
    describe_canonical,
    describe_handler,
    describe_resource,
    find_api_resources,
    generate_api_docs,
    generate_power_types_doc,
    get_api_description_hash,
    hash_canonical,
)
from maasserver.api.doc_handler import render_api_docs
from maasserver.api.support import (
    operation,
    OperationsHandler,
    OperationsResource,
)
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import (
    IsCallable,
    MockCalledOnceWith,
)
from maastesting.testcase import MAASTestCase
from mock import sentinel
from piston.doc import HandlerDocumentation
from piston.handler import BaseHandler
from piston.resource import Resource
from provisioningserver.power_schema import make_json_field
from testtools.matchers import (
    AfterPreprocessing,
    AllMatch,
    ContainsAll,
    Equals,
    HasLength,
    Is,
    IsInstance,
    MatchesAll,
    MatchesAny,
    MatchesDict,
    MatchesStructure,
    Not,
)


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

    def test_urlpatterns_with_resource_hidden(self):
        # Resources for handlers with resource_uri attributes are discovered
        # in a urlconf module and returned, unless hidden = True.
        handler = type(b"\m/", (BaseHandler,), {
            "resource_uri": True,
            "hidden": True,
            })
        resource = Resource(handler)
        module = self.make_module()
        module.urlpatterns = patterns("", url("^metal", resource))
        self.assertSetEqual(set(), find_api_resources(module))

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
        sorted_handlers = sorted(
            [type(resource.handler) for resource in resources],
            key=lambda handler_class: handler_class.__name__)
        self.assertEqual(
            sorted_handlers,
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


class TestHandlers(MAASServerTestCase):
    """Test that the handlers have all the details needed to generate the
    API documentation.
    """

    def test_handlers_have_section_title(self):
        from maasserver import urls_api as urlconf
        resources = find_api_resources(urlconf)
        handlers = []
        for doc in generate_api_docs(resources):
            handlers.append(doc.handler)
        handlers_missing_section_name = [
            handler.__name__
            for handler in handlers
            if not hasattr(handler, 'api_doc_section_name')
        ]
        self.assertEqual(
            [], handlers_missing_section_name,
            "%d handlers are missing an api_doc_section_name field." % len(
                handlers_missing_section_name))

    def test_contains_documentation_from_handlers(self):
        # The documentation contains some of the text used in the docstrings
        # of the API's methods.
        # This test is meant to catch bugs like bug 1411363.
        doc = render_api_docs()
        doc_snippets = [
            # Doc for a method.
            "Manage custom commissioning scripts.",
            # Doc for a method parameter.
            "GET a FileStorage object as a json object.",
            # Doc for a method parameter (:param: doc).
            "Optional prefix used to filter out the returned files.",
        ]
        self.assertThat(doc, ContainsAll(doc_snippets))


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
        # Override config maas url so that it's stable for testing.
        self.useFixture(
            RegionConfigurationFixture(maas_url="http://example.com/"))

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
        self.assertEqual(("p_foo", "p_bar"), observed["params"])
        self.assertItemsEqual(expected_actions, observed["actions"])

    def test_describe_handler_with_maas_handler(self):
        # Ensure that describe_handler() yields something sensible with a
        # "real" MAAS API handler.
        from maasserver.api.nodes import NodeHandler as handler
        description = describe_handler(handler)
        # The RUD of CRUD actions are still available, but the C(reate) action
        # has been overridden with custom non-ReSTful operations.
        expected_actions = {
            "DELETE delete op=None restful=True",
            "GET read op=None restful=True",
            "GET details op=details restful=False",
            "GET power_parameters op=power_parameters restful=False",
            "GET query_power_state op=query_power_state restful=False",
            "POST start op=start restful=False",
            "POST stop op=stop restful=False",
            "POST release op=release restful=False",
            "POST commission op=commission restful=False",
            "PUT update op=None restful=True",
            "POST claim_sticky_ip_address op=claim_sticky_ip_address "
            "restful=False",
            "POST release_sticky_ip_address op=release_sticky_ip_address "
            "restful=False",
            'POST mark_fixed op=mark_fixed restful=False',
            'POST mark_broken op=mark_broken restful=False',
            'POST abort_operation op=abort_operation restful=False',
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

    def test_describe_api_returns_description_document(self):
        is_list = IsInstance(list)
        is_tuple = IsInstance(tuple)
        is_text = MatchesAll(IsInstance((unicode, bytes)), Not(HasLength(0)))
        is_bool = IsInstance(bool)

        is_operation = MatchesAny(Is(None), is_text)

        is_http_method = MatchesAny(
            Equals("GET"), Equals("POST"),
            Equals("PUT"), Equals("DELETE"),
        )

        is_action = MatchesDict({
            "doc": is_text,
            "method": is_http_method,
            "name": is_text,
            "op": is_operation,
            "restful": is_bool,
        })

        is_handler = MatchesDict({
            "actions": MatchesAll(is_list, AllMatch(is_action)),
            "doc": is_text,
            "name": is_text,
            "params": is_tuple,
            "path": is_text,
        })

        is_resource = MatchesDict({
            "anon": MatchesAny(Is(None), is_handler),
            "auth": MatchesAny(Is(None), is_handler),
            "name": is_text,
        })

        is_resource_list = MatchesAll(is_list, AllMatch(is_resource))
        is_legacy_handler_list = MatchesAll(is_list, AllMatch(is_handler))

        self.assertThat(
            describe_api(), MatchesDict({
                "doc": Equals("MAAS API"),
                "resources": is_resource_list,
                "handlers": is_legacy_handler_list,
            }))


class TestGeneratePowerTypesDoc(MAASServerTestCase):
    """Tests for `generate_power_types_doc`."""

    def test__generate_power_types_doc_generates_doc(self):
        doc = generate_power_types_doc()
        self.assertThat(doc, ContainsAll(["Power types", "IPMI"]))

    def test__generate_power_types_doc_generates_describes_power_type(self):
        name = factory.make_name('name')
        description = factory.make_name('description')
        param_name = factory.make_name('param_name')
        param_description = factory.make_name('param_description')
        json_fields = [{
            'name': name,
            'description': description,
            'fields': [
                make_json_field(param_name, param_description),
            ],
        }]
        self.patch(doc_module, "JSON_POWER_TYPE_PARAMETERS", json_fields)
        doc = generate_power_types_doc()
        self.assertThat(
            doc,
            ContainsAll([name, description, param_name, param_description]))


class TestDescribeCanonical(MAASTestCase):

    def test__passes_True_False_and_None_through(self):
        self.expectThat(describe_canonical(True), Is(True))
        self.expectThat(describe_canonical(False), Is(False))
        self.expectThat(describe_canonical(None), Is(None))

    def test__passes_numbers_through(self):
        self.expectThat(
            describe_canonical(1), MatchesAll(
                IsInstance(int), Equals(1)))
        self.expectThat(
            describe_canonical(1L), MatchesAll(
                IsInstance(long), Equals(1L)))
        self.expectThat(
            describe_canonical(1.0), MatchesAll(
                IsInstance(float), Equals(1.0)))

    def test__passes_unicode_strings_through(self):
        string = factory.make_string()
        self.assertThat(string, IsInstance(unicode))
        self.expectThat(describe_canonical(string), Is(string))

    def test__decodes_byte_strings(self):
        string = factory.make_string().encode("utf-8")
        self.expectThat(
            describe_canonical(string), MatchesAll(
                IsInstance(unicode), Not(Is(string)),
                Equals(string.decode("utf-8"))))

    def test__returns_sequences_as_tuples(self):
        self.expectThat(describe_canonical([1, 2, 3]), Equals((1, 2, 3)))

    def test__recursively_calls_sequence_elements(self):
        self.expectThat(
            describe_canonical([1, [2, 3]]),
            Equals((1, (2, 3))))

    def test__sorts_sequences(self):
        self.expectThat(
            describe_canonical([3, 1, 2]),
            Equals((1, 2, 3)))
        self.expectThat(
            describe_canonical([[1, 2], [1, 1]]),
            Equals(((1, 1), (1, 2))))

    def test__returns_mappings_as_tuples(self):
        self.expectThat(describe_canonical({1: 2}), Equals(((1, 2),)))

    def test__recursively_calls_mapping_keys_and_values(self):
        mapping = {"key\u1234".encode("utf-8"): ["b", "a", "r"]}
        expected = (
            ("key\u1234", ("a", "b", "r")),
        )
        self.expectThat(
            describe_canonical(mapping),
            Equals(expected))

    def test__sorts_mappings(self):
        self.expectThat(
            describe_canonical({2: 1, 1: 1}),
            Equals(((1, 1), (2, 1))))

    def test__sorts_mappings_by_key_and_value(self):

        class inth(int):
            """An `int` that hashes independently from its value.

            This lets us use the same numeric key twice in a dict. Strictly
            this is an abuse, but it helps to demonstrate a point here, that
            values are considered when sorting.
            """
            __hash__ = object.__hash__

        mapping = {
            (1, inth(2)): "foo",
            (1, inth(2)): "bar",
            (1, inth(1)): "foo",
            (1, inth(1)): "bar",
        }
        expected = (
            ((1, 1), "bar"),
            ((1, 1), "foo"),
            ((1, 2), "bar"),
            ((1, 2), "foo"),
        )
        self.expectThat(
            describe_canonical(mapping),
            Equals(expected))

    def test__rejects_other_types(self):
        self.assertRaises(TypeError, describe_canonical, lambda: None)


class TestHashCanonical(MAASTestCase):
    """Tests for `hash_canonical`."""

    def test__canonicalizes_argument(self):
        describe_canonical = self.patch(doc_module, "describe_canonical")
        describe_canonical.return_value = b""
        hash_canonical(sentinel.desc)
        self.assertThat(describe_canonical, MockCalledOnceWith(sentinel.desc))

    def test__returns_hash_object(self):
        hasher = hash_canonical(factory.make_string())
        self.assertThat(hasher, MatchesStructure(
            block_size=Equals(64),
            digest=IsCallable(),
            digestsize=Equals(20),
            hexdigest=IsCallable(),
            name=Equals("sha1"),
            update=IsCallable(),
        ))

    def test__misc_digests(self):

        def hexdigest(data):
            return hash_canonical(data).hexdigest()

        def has_digest(digest):
            return AfterPreprocessing(hexdigest, Equals(digest))

        self.expectThat(
            None, has_digest("2be88ca4242c76e8253ac62474851065032d6833"))
        self.expectThat(
            False, has_digest("7cb6efb98ba5972a9b5090dc2e517fe14d12cb04"))
        self.expectThat(
            True, has_digest("5ffe533b830f08a0326348a9160afafc8ada44db"))

        self.expectThat(
            (1, 2, 3), has_digest(
                "a01eda32e4e0b1393274e91d1b3e9ecfc5eaba85"))
        self.expectThat(
            [1, 2, 3], has_digest(
                "a01eda32e4e0b1393274e91d1b3e9ecfc5eaba85"))

        self.expectThat(
            ((1, 2), (3, 4)), has_digest(
                "3bd746ab7fe760d0926546318cbf2b6f0a7a56f8"))
        self.expectThat(
            {1: 2, 3: 4}, has_digest(
                "3bd746ab7fe760d0926546318cbf2b6f0a7a56f8"))


class TestGetAPIDescriptionHash(MAASTestCase):
    """Tests for `get_api_description_hash`."""

    def setUp(self):
        super(TestGetAPIDescriptionHash, self).setUp()
        self.addCleanup(self.clear_hash_cache)
        self.clear_hash_cache()

    def clear_hash_cache(self):
        # Clear the API description hash cache.
        with doc_module.api_description_hash_lock:
            doc_module.api_description_hash = None

    def test__calculates_hash_from_api_description(self):
        # Fake the API description.
        api_description = factory.make_string()
        api_description_hasher = hash_canonical(api_description)
        self.patch(doc_module, "describe_api").return_value = api_description
        # The hash is generated from the faked API description.
        self.assertThat(
            get_api_description_hash(),
            Equals(api_description_hasher.hexdigest()))

    def test__caches_hash(self):
        # Fake the API description.
        api_description = factory.make_string()
        api_description_hasher = hash_canonical(api_description)
        # The description can only be fetched once before crashing.
        self.patch(doc_module, "describe_api").side_effect = [
            api_description, factory.make_exception_type(),
        ]
        # The hash is generated and cached.
        self.assertThat(
            get_api_description_hash(),
            Equals(api_description_hasher.hexdigest()))
        self.assertThat(
            get_api_description_hash(),
            Equals(api_description_hasher.hexdigest()))
        # Calling `describe_api` a second time would have failed.
        self.assertRaises(Exception, doc_module.describe_api)
