# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from pydantic import Field

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maascommon.enums.sshkeys import SshKeysProtocolType
from maasservicelayer.models.sshkeys import SshKey


class SshKeyResponse(HalResponse[BaseHal]):
    kind: str = Field(default="SshKey")
    id: int
    key: str
    protocol: SshKeysProtocolType | None = None
    auth_id: str | None = None

    @classmethod
    def from_model(cls, sshkey: SshKey, self_base_hyperlink: str) -> Self:
        return cls(
            id=sshkey.id,
            key=sshkey.key,
            protocol=sshkey.protocol,
            auth_id=sshkey.auth_id,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{sshkey.id}"
                )
            ),
        )


class SshKeysListResponse(PaginatedResponse[SshKeyResponse]):
    kind: str = Field(default="SshKeysList")
