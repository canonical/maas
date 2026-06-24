# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import BaseModel, Field, validator

from maasservicelayer.builders.ssh_host_keys import TrustedSshHostKeyBuilder

# Standard SSH public-key types accepted by MAAS.
_VALID_KEY_TYPES = frozenset(
    {
        "ssh-rsa",
        "ssh-dss",
        "ecdsa-sha2-nistp256",
        "ecdsa-sha2-nistp384",
        "ecdsa-sha2-nistp521",
        "ssh-ed25519",
        "sk-ecdsa-sha2-nistp256@openssh.com",
        "sk-ssh-ed25519@openssh.com",
    }
)


class SshHostKeyRequest(BaseModel):
    host: str = Field(description="The hostname or IP address.")
    key_type: str = Field(description="The SSH key type (e.g. ssh-rsa).")
    public_key: str = Field(description="The Base64-encoded public key.")
    label: Optional[str] = Field(
        default=None, description="An optional human-readable label."
    )

    @validator("key_type")
    @classmethod
    def validate_key_type(cls, v: str) -> str:
        if v not in _VALID_KEY_TYPES:
            raise ValueError(
                f"Invalid key_type {v!r}. "
                f"Must be one of: {', '.join(sorted(_VALID_KEY_TYPES))}."
            )
        return v

    def to_builder(self) -> TrustedSshHostKeyBuilder:
        return TrustedSshHostKeyBuilder(
            host=self.host,
            key_type=self.key_type,
            public_key=self.public_key,
            label=self.label,
        )
