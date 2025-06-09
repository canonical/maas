# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional, Self

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maascommon.enums.sshkeys import SshKeysProtocolType
from maasservicelayer.models.sshkeys import SshKey


class SshKeyResponse(HalResponse[BaseHal]):
    kind = "SshKey"
    id: int
    key: str
    protocol: Optional[SshKeysProtocolType] = None
    auth_id: Optional[str] = None

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
    kind = "SshKeysList"
