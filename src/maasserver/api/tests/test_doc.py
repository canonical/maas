# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from inspect import getdoc
import random
import types
from unittest.mock import sentinel

from django.core.exceptions import ImproperlyConfigured
from django.urls import include, path, re_path
from piston3.doc import HandlerDocumentation
from piston3.handler import BaseHandler
from piston3.resource import Resource
from testtools.matchers import (
    AfterPreprocessing,
    AllMatch,
    ContainsAll,
    Equals,
    Is,
    IsInstance,
    MatchesAll,
    MatchesAny,
    MatchesDict,
    MatchesStructure,
    Not,
)

from maasserver.api import doc as doc_module
from maasserver.api.doc import (
    _describe_api,
    _describe_canonical,
    _describe_handler,
    _describe_resource,
    _get_api_description_hash,
    _hash_canonical,
    find_api_resources,
    generate_api_docs,
    generate_pod_types_doc,
    generate_power_types_doc,
    get_api_description,
)
from maasserver.api.doc_handler import render_api_docs
from maasserver.api.support import (
    operation,
    OperationsHandler,
    OperationsResource,
)
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.factory import factory
from maastesting.matchers import IsCallable
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.pod.registry import PodDriverRegistry
from provisioningserver.drivers.power.registry import PowerDriverRegistry


class TestGetAPIDescription(MAASTestCase):
    def setUp(self):
        super().setUp()
        get_api_description.cache_clear()

    def test_adds_hash(self):
        self.patch(doc_module, "_describe_api").return_value = {}
        self.patch(
            doc_module, "_get_api_description_hash"
        ).return_value = "abcd"
        self.assertEqual(get_api_description(), {"hash": "abcd"})

    def test_cached(self):
        mock_describe_api = self.patch(doc_module, "_describe_api")
        mock_describe_api.return_value = {}
        mock_get_api_description_hash = self.patch(
            doc_module, "_get_api_description_hash"
        )
        mock_get_api_description_hash.return_value = "abcd"
        description = get_api_description()
        self.assertEqual(get_api_description(), description)
        mock_describe_api.assert_called_once()
        mock_get_api_description_hash.assert_called_once()


class TestFindingResources(MAASTestCase):
    """Tests for API inspection support: finding resources."""

    @staticmethod
    def make_module():
        """Return a new module with a fabricated name."""
        name = factory.make_name("module")
        return types.ModuleType(name)

    def test_urlpatterns_empty(self):
        # No resources are found in empty modules.
        module = self.make_module()
        module.urlpatterns = []
        self.assertSetEqual(set(), find_api_resources(module))

    def test_urlpatterns_not_present(self):
        # The absence of urlpatterns is an error.
        module = self.make_module()
        self.assertRaises(ImproperlyConfigured, find_api_resources, module)

    def test_urlpatterns_with_resource_for_incomplete_handler(self):
        # Resources for handlers that don't specify resource_uri are ignored.
        module = self.make_module()
        module.urlpatterns = [re_path("^foo", BaseHandler)]
        self.assertSetEqual(set(), find_api_resources(module))

    def test_urlpatterns_with_resource(self):
        # Resources for handlers with resource_uri attributes are discovered
        # in a urlconf module and returned. The type of resource_uri is not
        # checked; it must only be present and not None.
        handler = type("\\m/", (BaseHandler,), {"resource_uri": True})
        resource = Resource(handler)
        module = self.make_module()
        module.urlpatterns = [re_path("^metal", resource)]
        self.assertSetEqual({resource}, find_api_resources(module))

    def test_urlpatterns_with_resource_hidden(self):
        # Resources for handlers with resource_uri attributes are discovered
        # in a urlconf module and returned, unless hidden = True.
        handler = type(
            "\\m/", (BaseHandler,), {"resource_uri": True, "hidden": True}
        )
        resource = Resource(handler)
        module = self.make_module()
        module.urlpatterns = [re_path("^metal", resource)]
        self.assertSetEqual(set(), find_api_resources(module))

    def test_nested_urlpatterns_with_handler(self):
        # Resources are found in nested urlconfs.
        handler = type("\\m/", (BaseHandler,), {"resource_uri": True})
        resource = Resource(handler)
        module = self.make_module()
        submodule = self.make_module()
        submodule.urlpatterns = [re_path("^metal", resource)]
        module.urlpatterns = [path("genre/", include(submodule))]
        self.assertSetEqual({resource}, find_api_resources(module))

    def test_smoke(self):
        # Resources are found for the MAAS API.
        from maasserver import urls_api as urlconf

        self.assertNotEqual(set(), find_api_resources(urlconf))


class TestGeneratingDocs(MAASTestCase):
    """Tests for API inspection support: generating docs."""

    @staticmethod
    def make_resource():
        """
        Return a new `OperationsResource` with a `BaseHandler` subclass
        handler, with a fabricated name and a `resource_uri` class-method.
        """
        name = factory.make_name("handler")
        namespace = {
            "resource_uri": classmethod(
                lambda cls: factory.make_name("resource-uri")
            )
        }
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
            (type(resource.handler) for resource in resources),
            key=lambda handler_class: handler_class.__name__,
        )
        self.assertEqual(sorted_handlers, [doc.handler for doc in docs])

    def test_handler_without_resource_uri(self):
        # generate_api_docs() raises an exception if a handler does not have a
        # resource_uri attribute.
        resource = OperationsResource(BaseHandler)
        docs = generate_api_docs([resource])
        error = self.assertRaises(AssertionError, list, docs)
        self.assertEqual(
            "Missing resource_uri in %s" % type(resource.handler).__name__,
            str(error),
        )


class TestHandlers(MAASTestCase):
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
            if not hasattr(handler, "api_doc_section_name")
        ]
        self.assertEqual(
            [],
            handlers_missing_section_name,
            "%d handlers are missing an api_doc_section_name field."
            % len(handlers_missing_section_name),
        )

    def test_contains_documentation_from_handlers(self):
        # The documentation contains some of the text used in the docstrings
        # of the API's methods.
        # This test is meant to catch bugs like bug 1411363.
        doc = render_api_docs()
        doc_snippets = [
            # Doc for a method.
            "Manage custom commissioning scripts.",
            # Doc for a method parameter.
            "Reads a stored file",
            # Doc for a method parameter (:param: doc).
            "Prefix used to filter returned files.",
            # Doc for a rendered docstring containing annotations
            '"resource_uri": "/MAAS/api',
            # Doc for a rendered docstring containing annotations
            "Optional. A brief description of the new zone.",
        ]
        self.assertThat(doc, ContainsAll(doc_snippets))

    def test_does_not_contain_documentation_warnings_syntax_errors(self):
        # We don't want any of these strings in the rendered docs ever.
        doc = render_api_docs()
        self.assertNotIn(
            "API_WARNING",
            doc,
            """
            The rendered API doc contains an API_WARNING flag. To fix this,
            render the doc using `bin/maas-region generate_api_doc`, and
            search for the API_WARNING flag to find the inline warning.
        """,
        )
        self.assertNotIn(
            "API_SYNTAX_ERROR",
            doc,
            """
            The rendered API doc contains an API_SYNTAX_ERROR flag. To fix
            this, render the doc using `bin/maas-region generate_api_doc`,
            and search for the API_SYNTAX_ERROR flag to find the inline
            warning.
        """,
        )


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


class TestDescribingAPI(MAASTestCase):
    """Tests for functions that describe a Piston API."""

    def setUp(self):
        super().setUp()
        # Override config maas url so that it's stable for testing.
        self.useFixture(
            RegionConfigurationFixture(maas_url="http://example.com/")
        )

    def test_describe_handler(self):
        # _describe_handler() returns a description of a handler that can be
        # readily serialised into JSON, for example.
        expected_actions = [
            {
                "doc": getdoc(ExampleHandler.idempotent_operation),
                "method": "GET",
                "name": "idempotent_operation",
                "op": "idempotent_operation",
                "restful": False,
            },
            {
                "doc": getdoc(ExampleHandler.non_idempotent_operation),
                "method": "POST",
                "name": "non_idempotent_operation",
                "op": "non_idempotent_operation",
                "restful": False,
            },
            {
                "doc": None,
                "method": "PUT",
                "name": "update",
                "op": None,
                "restful": True,
            },
        ]
        observed = _describe_handler(ExampleHandler)
        # The description contains several entries.
        self.assertSetEqual(
            {"actions", "doc", "name", "params", "path"}, set(observed)
        )
        self.assertEqual(ExampleHandler.__doc__, observed["doc"])
        self.assertEqual(ExampleHandler.__name__, observed["name"])
        self.assertEqual(("p_foo", "p_bar"), observed["params"])
        self.assertCountEqual(expected_actions, observed["actions"])

    def test_describe_handler_with_maas_handler(self):
        # Ensure that _describe_handler() yields something sensible with a
        # "real" MAAS API handler.
        from maasserver.api.zones import ZoneHandler as handler

        description = _describe_handler(handler)
        # The RUD of CRUD actions are still available, but the C(reate) action
        # has been overridden with custom non-ReSTful operations.
        expected_actions = {
            "DELETE delete op=None restful=True",
            "GET read op=None restful=True",
            "PUT update op=None restful=True",
        }
        observed_actions = {
            "%(method)s %(name)s op=%(op)s restful=%(restful)s" % action
            for action in description["actions"]
        }
        self.assertSetEqual(expected_actions, observed_actions)
        self.assertSetEqual({"name"}, set(description["params"]))
        # The path is a URI Template <http://tools.ietf.org/html/rfc6570>, the
        # components of which correspond to the parameters declared.
        self.assertEqual("/MAAS/api/2.0/zones/{name}/", description["path"])

    def test_describe_resource_anonymous_resource(self):
        # When the resource does not require authentication, any configured
        # fallback is ignored, and only the resource's handler is described.
        # The resource name comes from this handler.
        self.patch(ExampleHandler, "anonymous", ExampleFallbackHandler)
        resource = OperationsResource(ExampleHandler)
        expected = {
            "anon": _describe_handler(ExampleHandler),
            "auth": None,
            "name": "ExampleHandler",
        }
        self.assertEqual(expected, _describe_resource(resource))

    def test_describe_resource_authenticated_resource(self):
        # When the resource requires authentication, but has no fallback
        # anonymous handler, the first is described. The resource name comes
        # from this handler.
        resource = OperationsResource(ExampleHandler, sentinel.auth)
        expected = {
            "anon": None,
            "auth": _describe_handler(ExampleHandler),
            "name": "ExampleHandler",
        }
        self.assertEqual(expected, _describe_resource(resource))

    def test_describe_resource_authenticated_resource_with_fallback(self):
        # When the resource requires authentication, but has a fallback
        # anonymous handler, both are described. The resource name is taken
        # from the authenticated handler.
        self.patch(ExampleHandler, "anonymous", ExampleFallbackHandler)
        resource = OperationsResource(ExampleHandler, sentinel.auth)
        expected = {
            "anon": _describe_handler(ExampleFallbackHandler),
            "auth": _describe_handler(ExampleHandler),
            "name": "ExampleHandler",
        }
        self.assertEqual(expected, _describe_resource(resource))

    def test_describe_api_returns_description_document(self):
        is_list = IsInstance(list)
        is_tuple = IsInstance(tuple)
        is_text = MatchesAny(IsInstance((str, bytes)), Is(None))
        is_bool = IsInstance(bool)

        is_operation = MatchesAny(Is(None), is_text)

        is_http_method = MatchesAny(
            Equals("GET"), Equals("POST"), Equals("PUT"), Equals("DELETE")
        )

        is_action = MatchesDict(
            {
                "doc": is_text,
                "method": is_http_method,
                "name": is_text,
                "op": is_operation,
                "restful": is_bool,
            }
        )

        is_handler = MatchesDict(
            {
                "actions": MatchesAll(is_list, AllMatch(is_action)),
                "doc": is_text,
                "name": is_text,
                "params": is_tuple,
                "path": is_text,
            }
        )

        is_resource = MatchesDict(
            {
                "anon": MatchesAny(Is(None), is_handler),
                "auth": MatchesAny(Is(None), is_handler),
                "name": is_text,
            }
        )

        is_resource_list = MatchesAll(is_list, AllMatch(is_resource))
        is_legacy_handler_list = MatchesAll(is_list, AllMatch(is_handler))

        self.assertThat(
            _describe_api(),
            MatchesDict(
                {
                    "doc": Equals("MAAS API"),
                    "resources": is_resource_list,
                    "handlers": is_legacy_handler_list,
                }
            ),
        )


class TestGeneratePowerTypesDoc(MAASTestCase):
    """Tests for `generate_power_types_doc`."""

    def test_generate_power_types_doc_generates_doc(self):
        doc = generate_power_types_doc()
        self.assertThat(doc, ContainsAll(["Power types", "IPMI", "virsh"]))

    def test_generate_power_types_doc_generates_describes_power_type(self):
        power_driver = random.choice(
            [
                driver
                for _, driver in PowerDriverRegistry
                if len(driver.settings) > 0
            ]
        )
        doc = generate_power_types_doc()
        self.assertThat(
            doc,
            ContainsAll(
                [
                    power_driver.name,
                    power_driver.description,
                    power_driver.settings[0]["name"],
                    power_driver.settings[0]["label"],
                ]
            ),
        )


class TestGeneratePodTypesDoc(MAASTestCase):
    """Tests for `generate_pod_types_doc`."""

    def test_generate_pod_types_doc_generates_doc(self):
        doc = generate_pod_types_doc()
        self.assertThat(doc, ContainsAll(["Pod types", "virsh"]))

    def test_generate_pod_types_doc_generates_describes_types(self):
        pod_driver = random.choice([driver for _, driver in PodDriverRegistry])
        doc = generate_pod_types_doc()
        self.assertThat(
            doc, ContainsAll([pod_driver.name, pod_driver.description])
        )


class TestDescribeCanonical(MAASTestCase):
    def test_passes_True_False_and_None_through(self):
        self.expectThat(_describe_canonical(True), Is(True))
        self.expectThat(_describe_canonical(False), Is(False))
        self.expectThat(_describe_canonical(None), Is(None))

    def test_passes_numbers_through(self):
        self.expectThat(
            _describe_canonical(1), MatchesAll(IsInstance(int), Equals(1))
        )
        self.expectThat(
            _describe_canonical(1), MatchesAll(IsInstance(int), Equals(1))
        )
        self.expectThat(
            _describe_canonical(1.0),
            MatchesAll(IsInstance(float), Equals(1.0)),
        )

    def test_passes_unicode_strings_through(self):
        string = factory.make_string()
        self.assertIsInstance(string, str)
        self.expectThat(_describe_canonical(string), Is(string))

    def test_decodes_byte_strings(self):
        string = factory.make_string().encode("utf-8")
        self.expectThat(
            _describe_canonical(string),
            MatchesAll(
                IsInstance(str),
                Not(Is(string)),
                Equals(string.decode("utf-8")),
            ),
        )

    def test_returns_sequences_as_tuples(self):
        self.expectThat(_describe_canonical([1, 2, 3]), Equals((1, 2, 3)))

    def test_recursively_calls_sequence_elements(self):
        self.expectThat(_describe_canonical([1, [2, 3]]), Equals((1, (2, 3))))

    def test_sorts_sequences(self):
        self.expectThat(_describe_canonical([3, 1, 2]), Equals((1, 2, 3)))
        self.expectThat(
            _describe_canonical([[1, 2], [1, 1]]), Equals(((1, 1), (1, 2)))
        )

    def test_returns_mappings_as_tuples(self):
        self.expectThat(_describe_canonical({1: 2}), Equals(((1, 2),)))

    def test_recursively_calls_mapping_keys_and_values(self):
        mapping = {"key\u1234".encode(): ["b", "a", "r"]}
        expected = (("key\u1234", ("a", "b", "r")),)
        self.expectThat(_describe_canonical(mapping), Equals(expected))

    def test_sorts_mappings(self):
        self.expectThat(
            _describe_canonical({2: 1, 1: 1}), Equals(((1, 1), (2, 1)))
        )

    def test_sorts_mappings_by_key_and_value(self):
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
        self.expectThat(_describe_canonical(mapping), Equals(expected))

    def test_rejects_other_types(self):
        self.assertRaises(TypeError, _describe_canonical, lambda: None)


class TestHashCanonical(MAASTestCase):
    def test_canonicalizes_argument(self):
        _describe_canonical = self.patch(doc_module, "_describe_canonical")
        _describe_canonical.return_value = ""
        _hash_canonical(sentinel.desc)
        _describe_canonical.assert_called_once_with(sentinel.desc)

    def test_returns_hash_object(self):
        hasher = _hash_canonical(factory.make_string())
        self.assertThat(
            hasher,
            MatchesStructure(
                block_size=Equals(64),
                digest=IsCallable(),
                digest_size=Equals(20),
                hexdigest=IsCallable(),
                name=Equals("sha1"),
                update=IsCallable(),
            ),
        )

    def test_misc_digests(self):
        def hexdigest(data):
            return _hash_canonical(data).hexdigest()

        def has_digest(digest):
            return AfterPreprocessing(hexdigest, Equals(digest))

        self.expectThat(
            None, has_digest("2be88ca4242c76e8253ac62474851065032d6833")
        )
        self.expectThat(
            False, has_digest("7cb6efb98ba5972a9b5090dc2e517fe14d12cb04")
        )
        self.expectThat(
            True, has_digest("5ffe533b830f08a0326348a9160afafc8ada44db")
        )

        self.expectThat(
            (1, 2, 3), has_digest("a01eda32e4e0b1393274e91d1b3e9ecfc5eaba85")
        )
        self.expectThat(
            [1, 2, 3], has_digest("a01eda32e4e0b1393274e91d1b3e9ecfc5eaba85")
        )

        self.expectThat(
            ((1, 2), (3, 4)),
            has_digest("3bd746ab7fe760d0926546318cbf2b6f0a7a56f8"),
        )
        self.expectThat(
            {1: 2, 3: 4},
            has_digest("3bd746ab7fe760d0926546318cbf2b6f0a7a56f8"),
        )


class TestGetAPIDescriptionHash(MAASTestCase):
    def test_calculates_hash_from_api_description(self):
        # Fake the API description.
        api_description = factory.make_string()
        api_description_hasher = _hash_canonical(api_description)
        self.patch(doc_module, "_describe_api").return_value = api_description
        # The hash is generated from the faked API description.
        self.assertEqual(
            _get_api_description_hash(api_description),
            api_description_hasher.hexdigest(),
        )
