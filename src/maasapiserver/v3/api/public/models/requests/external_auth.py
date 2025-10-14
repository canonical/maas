from urllib.parse import urlparse

from pydantic import BaseModel, Field, validator

from maasservicelayer.builders.external_auth import OAuthProviderBuilder
from maasservicelayer.exceptions.catalog import ValidationException


class OAuthProviderRequest(BaseModel):
    name: str = Field(
        description="A unique, human-readable name identifying the OIDC provider.",
    )
    client_id: str = Field(
        description="The client ID issued by the OIDC provider to identify your application.",
    )
    client_secret: str = Field(
        description="The client secret issued by the OIDC provider, used to authenticate your application securely.",
    )
    issuer_url: str = Field(
        description="The base URL of the OIDC provider’s authorization server.",
    )
    redirect_uri: str = Field(
        description="The callback URL in your application where the OIDC provider will redirect users after successful authentication.",
    )
    scopes: str = Field(
        description="A space-separated list of OIDC scopes defining the information requested from the provider.",
    )
    enabled: bool = Field(
        description="Specifies whether this provider should be enabled for user authentication.",
    )

    @validator("issuer_url", "redirect_uri")
    def validate_http_urls(cls, value: str, field):
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValidationException.build_for_field(
                field=field.name,
                message=f"{field.name.replace('_', ' ').capitalize()} must be a valid HTTP or HTTPS address.",
            )
        return value

    def to_builder(self) -> OAuthProviderBuilder:
        return OAuthProviderBuilder(
            name=self.name,
            client_id=self.client_id,
            client_secret=self.client_secret,
            issuer_url=self.issuer_url,
            redirect_uri=self.redirect_uri,
            scopes=self.scopes,
            enabled=self.enabled,
        )
