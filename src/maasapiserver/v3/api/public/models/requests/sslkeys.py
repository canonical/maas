# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel, Field, validator

from maascommon.sslkey import is_valid_ssl_key
from maasservicelayer.builders.sslkeys import SSLKeyBuilder


class SSLKeyRequest(BaseModel):
    key: str = Field(description="A valid SSL key.")

    @validator("key")
    def validate_ssl_key(cls, key: str):
        """Validate that the given key value contains a valid SSL key."""
        if not is_valid_ssl_key(key):
            raise ValueError("Invalid SSL key.")

        return key

    def to_builder(self) -> SSLKeyBuilder:
        return SSLKeyBuilder(key=self.key)
