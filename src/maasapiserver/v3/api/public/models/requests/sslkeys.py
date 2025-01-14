# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel, Field, validator

from maascommon.sslkey import is_valid_ssl_key
from maasservicelayer.db.repositories.sslkeys import SSLKeyResourceBuilder
from maasservicelayer.utils.date import utcnow


class SSLKeyRequest(BaseModel):
    key: str = Field(description="A valid SSL key.")

    @validator("key")
    def validate_ssl_key(cls, key: str):
        """Validate that the given key value contains a valid SSL key."""
        if not is_valid_ssl_key(key):
            raise ValueError("Invalid SSL key.")

        return key

    def to_builder(self) -> SSLKeyResourceBuilder:
        now = utcnow()
        resource_builder = (
            SSLKeyResourceBuilder()
            .with_key(self.key)
            .with_created(now)
            .with_updated(now)
        )
        return resource_builder
