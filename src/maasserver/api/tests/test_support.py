# Copyright 2013-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections import namedtuple
import http.client
from unittest.mock import call, Mock, sentinel

from django.core.exceptions import PermissionDenied
from django.urls import reverse
from piston3.authentication import NoAuthentication
from piston3.emitters import JSONEmitter
from piston3.handler import typemapper

from maasserver.api.doc import get_api_description
from maasserver.api.emitters import ModelCachingJSONEmitter
from maasserver.api.machines import MachinesHandler
from maasserver.api.support import (
    AdminRestrictedResource,
    check_permission,
    deprecated,
    Emitter,
    OperationsHandlerMixin,
    OperationsResource,
    RestrictedResource,
)
from maasserver.auth.tests.test_auth import OpenFGAMockMixin
from maasserver.models.config import Config, ConfigManager
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.testcase import MAASTestCase


class TestEmitterOnlyJSON(MAASTestCase):
    def test_emitters(self):
        self.assertEqual(Emitter.EMITTERS.keys(), {"json"})


class TestModelCachingJSONEmitter(MAASServerTestCase):
    def test_allows_finite_related_back_references(self):
        machine = factory.make_Node().as_machine()
        reverse("machines_handler")
        fields = (
            "system_id",
            ("numanode_set", ("index", ("node", ("system_id",)))),
        )
        expected = JSONEmitter(
            [machine], typemapper, MachinesHandler(), fields, anonymous=False
        ).construct()
        actual = ModelCachingJSONEmitter(
            [machine], typemapper, MachinesHandler(), fields, anonymous=False
        ).construct()
        self.assertEqual(expected, actual)
        self.assertEqual(
            machine.system_id,
            actual[0]["numanode_set"][0]["node"]["system_id"],
        )

    def test_keeps_distinct_fieldsets_for_shared_models(self):
        machine = factory.make_Node().as_machine()
        machine.brief_zone = machine.zone
        zone_uri = reverse("zone_handler", args=[machine.zone.name])
        fields = ("zone", ("brief_zone", ("name",)))
        handler = MachinesHandler()
        expected = JSONEmitter(
            [machine], typemapper, handler, fields, anonymous=False
        ).construct()
        actual = ModelCachingJSONEmitter(
            [machine], typemapper, handler, fields, anonymous=False
        ).construct()

        self.assertEqual(expected, actual)
        self.assertEqual(
            {"name": machine.zone.name, "resource_uri": zone_uri},
            actual[0]["brief_zone"],
        )
        self.assertEqual(
            machine.zone.description, actual[0]["zone"]["description"]
        )

    def test_keeps_equal_instances_with_different_values_separate(self):
        first = factory.make_Node().as_machine()
        second = type(first).objects.get(id=first.id)
        first.hostname = "first-view"
        second.hostname = "second-view"
        emitter = ModelCachingJSONEmitter(
            [first, second],
            typemapper,
            MachinesHandler(),
            ("hostname",),
            anonymous=False,
        )
        self.assertEqual(
            ["first-view", "second-view"],
            [result["hostname"] for result in emitter.construct()],
        )

    def test_construct_does_not_retain_previous_model_values(self):
        machine = factory.make_Node().as_machine()
        machine.hostname = "before"
        emitter = ModelCachingJSONEmitter(
            [machine],
            typemapper,
            MachinesHandler(),
            ("hostname",),
            anonymous=False,
        )
        first = emitter.construct()
        machine.hostname = "after"
        second = emitter.construct()
        self.assertEqual("before", first[0]["hostname"])
        self.assertEqual("after", second[0]["hostname"])

    def test_rejects_recursive_model_fields(self):
        machine = factory.make_Node().as_machine()
        machine.recursive = machine
        reverse("machines_handler")
        for emitter_class in (JSONEmitter, ModelCachingJSONEmitter):
            emitter = emitter_class(
                [machine],
                typemapper,
                MachinesHandler(),
                ("recursive",),
                anonymous=False,
            )
            self.assertRaises(RuntimeError, emitter.construct)


class StubHandler:
    """A stub handler class that breaks when called."""

    def __call__(self, request):
        raise AssertionError("Do not call the stub handler.")


class TestOperationsResource(APITestCase.ForUser):
    def test_type_error_is_not_hidden(self):
        # This tests that bug #1228205 is fixed (i.e. that a
        # TypeError is properly reported and not swallowed by
        # piston).

        # Create a valid configuration item.
        name = "maas_name"
        value = factory.make_string()
        Config.objects.set_config(name, value)

        # Patch ConfigManager.get_config so that it will raise a
        # TypeError exception.
        def mock_get_config(config):
            if config == name:
                raise TypeError()

        self.patch(
            ConfigManager, "get_config", Mock(side_effect=mock_get_config)
        )
        self.become_admin()
        response = self.client.get(
            reverse("maas_handler"), {"op": "get_config", "name": name}
        )
        self.assertEqual(
            http.client.INTERNAL_SERVER_ERROR,
            response.status_code,
            response.content,
        )

    def test_api_hash_is_set_in_headers(self):
        Config.objects.set_config("maas_name", factory.make_name("name"))
        self.become_admin()
        response = self.client.get(
            reverse("maas_handler"), {"op": "get_config", "name": "maas_name"}
        )
        self.assertEqual(
            response["X-MAAS-API-Hash"], get_api_description()["hash"]
        )

    def test_call_op_in_path(self):
        Config.objects.set_config("maas_name", factory.make_name("name"))
        self.become_admin()
        response = self.client.get(
            reverse("maas_handler-op-get_config"), {"name": "maas_name"}
        )
        self.assertEqual(http.client.OK, response.status_code)

    def test_authenticated_is_False_when_no_authentication_provided(self):
        resource = OperationsResource(StubHandler)
        self.assertFalse(resource.is_authentication_attempted)

    def test_authenticated_is_False_when_authentication_is_empty(self):
        resource = OperationsResource(StubHandler, authentication=[])
        self.assertFalse(resource.is_authentication_attempted)

    def test_authenticated_is_False_when_authentication_is_NoAuthn(self):
        resource = OperationsResource(
            StubHandler, authentication=NoAuthentication()
        )
        self.assertFalse(resource.is_authentication_attempted)

    def test_authenticated_is_True_when_authentication_is_provided(self):
        resource = OperationsResource(
            StubHandler, authentication=sentinel.authentication
        )
        self.assertTrue(resource.is_authentication_attempted)


class TestRestrictedResources(MAASTestCase):
    """Tests for `RestrictedResource` and `AdminRestrictedResource`."""

    scenarios = (
        ("user", dict(resource_type=RestrictedResource)),
        ("admin", dict(resource_type=AdminRestrictedResource)),
    )

    def test_authentication_must_not_be_None(self):
        error = self.assertRaises(
            AssertionError,
            self.resource_type,
            StubHandler,
            authentication=None,
        )
        self.assertEqual("Authentication must be attempted.", str(error))

    def test_authentication_must_be_non_empty(self):
        error = self.assertRaises(
            AssertionError, self.resource_type, StubHandler, authentication=[]
        )
        self.assertEqual("Authentication must be attempted.", str(error))

    def test_authentication_must_be_meaningful(self):
        error = self.assertRaises(
            AssertionError,
            self.resource_type,
            StubHandler,
            authentication=NoAuthentication(),
        )
        self.assertEqual("Authentication must be attempted.", str(error))

    def test_authentication_is_okay(self):
        resource = self.resource_type(
            StubHandler, authentication=sentinel.authentication
        )
        self.assertTrue(resource.is_authentication_attempted)


class TestAdminMethodDecorator(OpenFGAMockMixin, MAASServerTestCase):
    def test_permission_denied(self):
        self.openfga_client.can_edit_global_entities.return_value = False

        FakeRequest = namedtuple("FakeRequest", ["user"])
        user = factory.make_User()
        request = FakeRequest(user=user)
        mock = Mock()

        @check_permission("can_edit_global_entities")
        def api_method(self, request):
            return mock()

        self.assertRaises(PermissionDenied, api_method, "self", request)
        self.assertEqual([], mock.mock_calls)
        self.openfga_client.can_edit_global_entities.assert_called_once_with(
            user
        )

    def test_permission_success(self):
        self.openfga_client.can_edit_global_entities.return_value = True

        FakeRequest = namedtuple("FakeRequest", ["user"])
        user = factory.make_User()
        request = FakeRequest(user=user)
        return_value = factory.make_name("return")
        mock = Mock(return_value=return_value)

        @check_permission("can_edit_global_entities")
        def api_method(self, request):
            return mock()

        response = api_method("self", request)
        self.assertEqual((return_value, [call()]), (response, mock.mock_calls))
        self.openfga_client.can_edit_global_entities.assert_called_once_with(
            user
        )


class TestDeprecatedMethodDecorator(MAASServerTestCase):
    def test_function_marked_as_deprecated(self):
        def api_replacement_method(self, request):
            pass

        @deprecated(use=api_replacement_method)
        def api_method(self, request):
            pass

        self.assertEqual(api_method.deprecated, api_replacement_method)

    def test_class_marked_as_deprecated(self):
        class api_replacement_endpoint:
            api_doc_section_name = "Replacement"

        @deprecated(use=api_replacement_endpoint)
        class api_endpoint:
            api_doc_section_name = "Deprecated"

        self.assertEqual(api_endpoint.deprecated, api_replacement_endpoint)

    def test_deprecated_class_inheritance_only_affects_own_methods(self):
        class BaseHandler:
            api_doc_section_name = "Base"

            def inherited_method(self):
                pass

        class ReplacementHandler:
            api_doc_section_name = "Replacement"

            def own_method(self):
                pass

        @deprecated(use=ReplacementHandler)
        class DeprecatedHandler(BaseHandler):
            api_doc_section_name = "Deprecated"

            def own_method(self):
                pass

        self.assertTrue(hasattr(DeprecatedHandler.own_method, "deprecated"))
        self.assertFalse(
            hasattr(DeprecatedHandler.inherited_method, "deprecated")
        )


class TestOperationsHandlerMixin(MAASTestCase):
    """Tests for :py:class:`maasserver.api.support.OperationsHandlerMixin`."""

    def make_handler(self, **namespace):
        return type("TestHandler", (OperationsHandlerMixin,), namespace)

    def test_decorate_decorates_exports(self):
        handler = self.make_handler(
            exports={"foo": sentinel.foo, "bar": sentinel.bar}
        )
        handler.decorate(lambda thing: str(thing).upper())
        self.assertEqual(
            {"foo": "SENTINEL.FOO", "bar": "SENTINEL.BAR"}, handler.exports
        )

    def test_decorate_decorates_anonymous_exports(self):
        handler = self.make_handler(exports={"foo": sentinel.foo})
        handler.anonymous = self.make_handler(exports={"bar": sentinel.bar})
        handler.decorate(lambda thing: str(thing).upper())
        self.assertEqual({"foo": "SENTINEL.FOO"}, handler.exports)
        self.assertEqual({"bar": "SENTINEL.BAR"}, handler.anonymous.exports)
