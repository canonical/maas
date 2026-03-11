import http.client
from unittest.mock import patch

from django.urls import reverse

from maasserver.api.oidc_providers import provider_to_dict
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BadGatewayException,
    ConflictException,
    NotFoundException,
    PreconditionFailedException,
)
from maasservicelayer.models.base import ListResult


def get_oidc_provider_uri(provider):
    """Return an OIDC provider's URI on the API."""
    return reverse("oidc_provider_handler", args=[provider.id])


class TestOidcProvider(APITestCase.ForUser):
    def setUp(self):
        super().setUp()
        patcher = patch(
            "maasserver.api.oidc_providers.service_layer"
            ".services.external_oauth"
        )
        self.external_oauth = patcher.start()
        self.addCleanup(patcher.stop)

    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/oidc-providers/1/",
            reverse("oidc_provider_handler", args=["1"]),
        )

    def test_GET_returns_provider(self):
        self.become_admin()
        provider = factory.make_OidcProvider()
        self.external_oauth.get_by_id.return_value = provider

        response = self.client.get(get_oidc_provider_uri(provider))

        self.assertEqual(http.client.OK, response.status_code)
        self.external_oauth.get_by_id.assert_called_once_with(id=provider.id)
        self.assertEqual(
            json_load_bytes(response.content), provider_to_dict(provider)
        )

    def test_GET_nonexistent_provider(self):
        self.become_admin()
        self.external_oauth.get_by_id.return_value = None

        response = self.client.get(
            reverse("oidc_provider_handler", args=[999])
        )

        self.assertEqual(http.client.NOT_FOUND, response.status_code)
        self.external_oauth.get_by_id.assert_called_once_with(id=999)

    def test_GET_requires_admin(self):
        provider = factory.make_OidcProvider()

        response = self.client.get(get_oidc_provider_uri(provider))

        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_DELETE_nonexistent_provider(self):
        self.become_admin()
        self.external_oauth.delete_by_id.side_effect = NotFoundException()

        response = self.client.delete(
            reverse("oidc_provider_handler", args=[999])
        )

        self.assertEqual(http.client.NOT_FOUND, response.status_code)
        self.external_oauth.delete_by_id.assert_called_once_with(id=999)

    def test_DELETE_raises_conflict(self):
        self.become_admin()
        self.external_oauth.delete_by_id.side_effect = (
            PreconditionFailedException()
        )

        response = self.client.delete(
            get_oidc_provider_uri(factory.make_OidcProvider())
        )

        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.external_oauth.delete_by_id.assert_called_once_with(id=1)

    def test_DELETE_returns_no_content(self):
        self.become_admin()

        response = self.client.delete(
            get_oidc_provider_uri(factory.make_OidcProvider())
        )

        self.assertEqual(http.client.NO_CONTENT, response.status_code)
        self.external_oauth.delete_by_id.assert_called_once_with(id=1)

    def test_DELETE_requires_admin(self):
        provider = factory.make_OidcProvider()

        response = self.client.delete(get_oidc_provider_uri(provider))

        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_PUT_nonexistent_provider(self):
        self.become_admin()
        self.external_oauth.update_provider.side_effect = NotFoundException()

        response = self.client.put(
            reverse("oidc_provider_handler", args=[999]), data={}
        )

        self.assertEqual(http.client.NOT_FOUND, response.status_code)

    def test_PUT_conflict(self):
        self.become_admin()
        self.external_oauth.update_provider.side_effect = ConflictException()

        response = self.client.put(
            reverse("oidc_provider_handler", args=[999]), data={}
        )

        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.assertEqual(
            str(response.content, "utf-8"),
            "An enabled provider already exists. Disable the existing provider before enabling this one.",
        )

    def test_PUT_success(self):
        self.become_admin()
        provider = factory.make_OidcProvider()
        updated_provider = provider.copy()
        updated_provider.name = "New Name"
        self.external_oauth.get_by_id.return_value = provider
        self.external_oauth.update_provider.return_value = updated_provider

        response = self.client.put(
            get_oidc_provider_uri(provider),
            data={
                "name": "New Name",
            },
        )

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            json_load_bytes(response.content),
            provider_to_dict(updated_provider),
        )

    def test_PUT_requires_admin(self):
        provider = factory.make_OidcProvider()

        response = self.client.put(
            get_oidc_provider_uri(provider),
            data={
                "name": "New Name",
            },
        )

        self.assertEqual(http.client.FORBIDDEN, response.status_code)


class TestOidcProviders(APITestCase.ForUser):
    SAMPLE_PROVIDER_DATA = {
        "name": "Test Provider",
        "issuer_url": "https://example.com",
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "redirect_uri": "https://example.com/callback",
        "scopes": "openid profile email",
        "enabled": True,
        "token_type": "JWT",
    }

    def setUp(self):
        super().setUp()
        patcher = patch(
            "maasserver.api.oidc_providers.service_layer"
            ".services.external_oauth"
        )
        self.external_oauth = patcher.start()
        self.addCleanup(patcher.stop)

    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/oidc-providers/",
            reverse("oidc_providers_handler"),
        )

    def test_GET_empty_list(self):
        self.become_admin()
        self.external_oauth.list.return_value = ListResult(items=[], total=0)

        response = self.client.get(reverse("oidc_providers_handler"))

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            json_load_bytes(response.content), "No OIDC providers found."
        )
        self.external_oauth.list.assert_called_once()

    def test_GET_returns_providers(self):
        self.become_admin()
        providers = [factory.make_OidcProvider() for _ in range(3)]
        self.external_oauth.list.return_value = ListResult(
            items=providers, total=3
        )

        response = self.client.get(reverse("oidc_providers_handler"))

        self.assertEqual(http.client.OK, response.status_code)
        self.external_oauth.list.assert_called_once()
        self.assertEqual(
            json_load_bytes(response.content),
            [provider_to_dict(provider) for provider in providers],
        )

    def test_GET_requires_admin(self):
        response = self.client.get(reverse("oidc_providers_handler"))

        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_GET_get_active_not_found(self):
        self.become_admin()
        self.external_oauth.get_provider.return_value = None

        response = self.client.get(
            reverse("oidc_providers_handler"), {"op": "get_active"}
        )

        self.assertEqual(http.client.NOT_FOUND, response.status_code)
        self.assertEqual(
            str(response.content, "utf-8"), "No enabled OIDC provider found."
        )
        self.external_oauth.get_provider.assert_called_once()

    def test_GET_get_active_success(self):
        self.become_admin()
        provider = factory.make_OidcProvider()
        self.external_oauth.get_provider.return_value = provider

        response = self.client.get(
            reverse("oidc_providers_handler"), {"op": "get_active"}
        )

        self.assertEqual(http.client.OK, response.status_code)
        self.external_oauth.get_provider.assert_called_once()
        self.assertEqual(
            json_load_bytes(response.content), provider_to_dict(provider)
        )

    def test_CREATE_invalid_url(self):
        self.become_admin()
        data = self.SAMPLE_PROVIDER_DATA.copy()
        data["issuer_url"] = "not-a-valid-url"

        response = self.client.post(
            reverse("oidc_providers_handler"),
            data=data,
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            str(response.content, "utf-8"),
            "Issuer URL must be a valid HTTP or HTTPS address.",
        )

    def test_CREATE_invalid_token_type(self):
        self.become_admin()
        data = self.SAMPLE_PROVIDER_DATA.copy()
        data["token_type"] = "INVALID"

        response = self.client.post(
            reverse("oidc_providers_handler"),
            data=data,
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            str(response.content, "utf-8"),
            "Invalid token type: INVALID. Must be 'JWT' or 'Opaque'.",
        )

    def test_CREATE_bad_gateway(self):
        self.become_admin()
        self.external_oauth.create.side_effect = BadGatewayException()

        response = self.client.post(
            reverse("oidc_providers_handler"),
            data=self.SAMPLE_PROVIDER_DATA,
        )
        self.assertEqual(http.client.BAD_GATEWAY, response.status_code)
        self.assertEqual(
            str(response.content, "utf-8"),
            "Failed to create OIDC provider: Bad gateway.",
        )

    def test_CREATE_already_exists(self):
        self.become_admin()
        self.external_oauth.create.side_effect = AlreadyExistsException()

        response = self.client.post(
            reverse("oidc_providers_handler"),
            data=self.SAMPLE_PROVIDER_DATA,
        )
        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.assertEqual(
            str(response.content, "utf-8"),
            "An OIDC provider with the same name already exists.",
        )

    def test_CREATE_conflict_with_enabled_provider(self):
        self.become_admin()
        self.external_oauth.create.side_effect = ConflictException()

        response = self.client.post(
            reverse("oidc_providers_handler"),
            data=self.SAMPLE_PROVIDER_DATA,
        )
        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.assertEqual(
            str(response.content, "utf-8"),
            "An enabled provider already exists. Disable the existing provider before creating a new one.",
        )

    def test_CREATE_success(self):
        self.become_admin()
        provider = factory.make_OidcProvider()
        self.external_oauth.create.return_value = provider

        response = self.client.post(
            reverse("oidc_providers_handler"),
            data=self.SAMPLE_PROVIDER_DATA,
        )
        self.assertEqual(http.client.CREATED, response.status_code)
        self.assertEqual(
            json_load_bytes(response.content), provider_to_dict(provider)
        )

    def test_CREATE_requires_admin(self):
        response = self.client.post(
            reverse("oidc_providers_handler"),
            data=self.SAMPLE_PROVIDER_DATA,
        )

        self.assertEqual(http.client.FORBIDDEN, response.status_code)
