#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from urllib.parse import urlencode

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


class RootKey(MaasTimestampedBaseModel):
    expiration: datetime


@generate_builder()
class OAuthProvider(MaasTimestampedBaseModel):
    issuer_url: str
    name: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: str
    enabled: bool

    def build_auth_url(self):
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scopes,
        }

        return f"{self.issuer_url.rstrip('/')}/authorize?{urlencode(params)}"
