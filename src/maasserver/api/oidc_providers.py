# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `OIDCProvider`."""

import http.client
import json
from urllib.parse import urlparse

from django.http import HttpResponse

from maasserver.api.support import (
    check_permission,
    operation,
    OperationsHandler,
)
from maasserver.exceptions import (
    MAASAPIBadRequest,
    OIDCProviderBadGateway,
    OIDCProviderConflict,
    OIDCProviderNotFound,
)
from maasserver.sqlalchemy import service_layer
from maasservicelayer.builders.external_auth import OAuthProviderBuilder
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BadGatewayException,
    ConflictException,
    NotFoundException,
    PreconditionFailedException,
)
from maasservicelayer.models.external_auth import (
    AccessTokenType,
    OAuthProvider,
)

UPDATABLE_FIELDS = (
    "name",
    "issuer_url",
    "client_id",
    "client_secret",
    "enabled",
    "token_type",
    "redirect_uri",
    "scopes",
)


def provider_to_dict(provider: OAuthProvider) -> dict:
    return {
        "id": provider.id,
        "name": provider.name,
        "issuer_url": provider.issuer_url,
        "client_id": provider.client_id,
        "client_secret": provider.client_secret,
        "enabled": provider.enabled,
        "token_type": "JWT" if provider.token_type == 0 else "Opaque",
        "redirect_uri": provider.redirect_uri,
        "scopes": provider.scopes,
    }


def parse_token_type(token_type: str) -> AccessTokenType:
    token_type = token_type.upper()
    if token_type == "JWT":
        return AccessTokenType.JWT
    elif token_type == "OPAQUE":
        return AccessTokenType.OPAQUE
    else:
        raise MAASAPIBadRequest(
            f"Invalid token type: {token_type}. Must be 'JWT' or 'Opaque'."
        )


def validate_http_urls(value: str, field: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise MAASAPIBadRequest(
            f"{field} must be a valid HTTP or HTTPS address."
        )


def generate_response(content: str | dict, status: int) -> HttpResponse:
    return HttpResponse(
        json.dumps(content, indent=4),
        content_type="application/json; charset=utf-8",
        status=status,
    )


class OidcProviderHandler(OperationsHandler):
    """Manage an OIDC provider."""

    api_doc_section_name = "OIDC provider"
    create = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("oidc_provider_handler", ["id"])

    @check_permission("can_edit_identities")
    def delete(self, request, id):
        """@description-title Delete OIDC provider
        @description Delete an OIDC provider by ID.

        @param (string) "{id}" [required=true] ID of the OIDC provider to delete.

        @success (http-status-code) "server-success" 204
        @error (http-status-code) "not-found" 404 If no OIDC provider with the specified ID exists.
        @error (http-status-code) "conflict" 409 If the provider is currently enabled.
        """

        try:
            service_layer.services.external_oauth.delete_by_id(id=int(id))
            return HttpResponse(status=http.client.NO_CONTENT)
        except PreconditionFailedException as e:
            raise OIDCProviderConflict(
                "Provider is currently enabled and cannot be deleted."
            ) from e
        except NotFoundException as e:
            raise OIDCProviderNotFound(
                f"No OIDC provider found with ID: {id}"
            ) from e

    @check_permission("can_view_identities")
    def read(self, request, id):
        """@description-title Get OIDC provider
        @description Retrieve an OIDC provider by ID.

        @param (string) "{id}" [required=true] ID of the OIDC provider to retrieve.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object representing the OIDC provider.
        @success-example "success-json" [exkey=oidc-provider-read-by-id] placeholder text
        @error (http-status-code) "not-found" 404 If no OIDC provider with the specified ID exists.
        """

        provider = service_layer.services.external_oauth.get_by_id(id=int(id))
        if not provider:
            print("No provider found with ID:", id)
            raise OIDCProviderNotFound(f"No OIDC provider found with ID: {id}")

        return generate_response(provider_to_dict(provider), http.client.OK)

    @check_permission("can_edit_identities")
    def update(self, request, id):
        """@description-title Update OIDC provider
        @description Update an existing OIDC provider by ID.

        @param (string) "{id}" [required=true] ID of the OIDC provider to update.
        @param (string) "name" [required=false] New name for the OIDC provider.
        @param (string) "issuer_url" [required=false] New issuer URL for the OIDC provider.
        @param (string) "client_id" [required=false] New client ID for the OIDC provider.
        @param (string) "client_secret" [required=false] New client secret for the OIDC provider.
        @param (boolean) "enabled" [required=false] Whether the OIDC provider should be enabled.
        @param (string) "token_type" [required=false] New token type for the OIDC provider (JWT or Opaque).
        @param (string) "redirect_uri" [required=false] New redirect URI for the OIDC provider.
        @param (string) "scopes" [required=false] Space-separated list of scopes for the OIDC provider.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object representing the updated OIDC provider.
        @error (http-status-code) "not-found" 404 If no OIDC provider with the specified ID exists.
        @error (http-status-code) "conflict" 409 If an enabled provider already exists or if a provider with the same name already exists.
        @error (http-status-code) "bad-gateway" 502 If there was an error communicating with the provider.
        """

        fields = {}
        for field in UPDATABLE_FIELDS:
            if field in request.POST:
                fields[field] = request.POST[field]

        if "issuer_url" in fields:
            validate_http_urls(fields["issuer_url"], "Issuer URL")
        if "redirect_uri" in fields:
            validate_http_urls(fields["redirect_uri"], "Redirect URI")
        if "token_type" in fields:
            fields["token_type"] = parse_token_type(fields["token_type"])

        builder = OAuthProviderBuilder(**fields)
        try:
            updated = service_layer.services.external_oauth.update_provider(
                id=id, builder=builder
            )
            return generate_response(provider_to_dict(updated), http.client.OK)
        except BadGatewayException as e:
            raise OIDCProviderBadGateway(
                f"Failed to update OIDC provider: {str(e)}"
            ) from e
        except AlreadyExistsException as e:
            raise OIDCProviderConflict(
                "An OIDC provider with the same name already exists."
            ) from e
        except ConflictException as e:
            raise OIDCProviderConflict(
                "An enabled provider already exists. Disable the existing provider before enabling this one."
            ) from e
        except NotFoundException as e:
            raise OIDCProviderNotFound(
                f"No OIDC provider found with ID: {id}"
            ) from e


class OidcProvidersHandler(OperationsHandler):
    """Manage OIDC providers."""

    api_doc_section_name = "OIDC providers"
    update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("oidc_providers_handler", [])

    @check_permission("can_view_identities")
    def read(self, request):
        """@description-title List OIDC providers
        @description List all configured OIDC providers.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of OIDC
        provider objects.
        @success-example "success-json" [exkey=oidc-provider-read] placeholder text
        """

        providers = service_layer.services.external_oauth.list(
            page=1, size=100
        )

        if providers.total == 0:
            return generate_response(
                "No OIDC providers found.", http.client.OK
            )

        return generate_response(
            [provider_to_dict(provider) for provider in providers.items],
            http.client.OK,
        )

    @check_permission("can_view_identities")
    @operation(idempotent=True)
    def get_active(self, request):
        """@description-title Get active OIDC provider
        @description Get the currently enabled OIDC provider.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object representing the active OIDC provider.
        @success-example "success-json" [exkey=oidc-provider-read-by-active] placeholder text
        @error (http-status-code) "not-found" 404 If no enabled OIDC provider is found.
        """

        provider = service_layer.services.external_oauth.get_provider()
        if not provider:
            raise OIDCProviderNotFound("No enabled OIDC provider found.")
        return generate_response(provider_to_dict(provider), http.client.OK)

    @check_permission("can_edit_identities")
    def create(self, request):
        """@description-title Create OIDC provider
        @description Create a new OIDC provider.

        @param (string) "name" [required=true] Name for the new OIDC provider.
        @param (string) "issuer_url" [required=true] Issuer URL for the new OIDC provider.
        @param (string) "client_id" [required=true] Client ID for the new OIDC provider.
        @param (string) "client_secret" [required=true] Client secret for the new OIDC provider.
        @param (boolean) "enabled" [required=false] Whether the OIDC provider is enabled. Defaults to false.
        @param (string) "token_type" [required=false] Token type for the OIDC provider (JWT or Opaque). Defaults to JWT.
        @param (string) "redirect_uri" [required=false] Redirect URI for the OIDC provider.
        @param (string) "scopes" [required=false] Space-separated list of scopes for the OIDC provider.

        @success (http-status-code) "server-success" 201
        @success (json) "success-json" A JSON object representing the newly created OIDC provider.
        @success-example "success-json" [exkey=oidc-provider-create] placeholder text
        @error (http-status-code) "bad-request" 400 If any required parameters are missing or invalid.
        @error (http-status-code) "conflict" 409 If an enabled provider already exists or if a provider with the same name already exists.
        @error (http-status-code) "bad-gateway" 502 If there was an error communicating with the provider.
        """

        name = request.POST.get("name", None)
        issuer_url = request.POST.get("issuer_url", None)
        client_id = request.POST.get("client_id", None)
        client_secret = request.POST.get("client_secret", None)
        enabled = request.POST.get("enabled", "false").lower() == "true"
        token_type = request.POST.get("token_type", "JWT")
        redirect_uri = request.POST.get("redirect_uri", None)
        scopes = request.POST.get("scopes", "")

        validate_http_urls(issuer_url, "Issuer URL")
        validate_http_urls(redirect_uri, "Redirect URI")
        token_type = parse_token_type(token_type)

        builder = OAuthProviderBuilder(
            name=name,
            issuer_url=issuer_url,
            client_id=client_id,
            client_secret=client_secret,
            enabled=enabled,
            token_type=token_type,
            redirect_uri=redirect_uri,
            scopes=scopes,
        )
        try:
            provider = service_layer.services.external_oauth.create(
                builder=builder
            )
            return generate_response(
                provider_to_dict(provider), http.client.CREATED
            )
        except BadGatewayException as e:
            raise OIDCProviderBadGateway(
                f"Failed to create OIDC provider: {str(e)}"
            ) from e
        except AlreadyExistsException as e:
            raise OIDCProviderConflict(
                "An OIDC provider with the same name already exists."
            ) from e
        except ConflictException as e:
            raise OIDCProviderConflict(
                "An enabled provider already exists. Disable the existing provider before creating a new one."
            ) from e
