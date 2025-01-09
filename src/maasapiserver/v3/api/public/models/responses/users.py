# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Optional, Self

from pydantic import BaseModel

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    TokenPaginatedResponse,
)
from maascommon.enums.sshkeys import SshKeysProtocolType
from maasservicelayer.models.sshkeys import SshKey
from maasservicelayer.models.users import User


class UserInfoResponse(BaseModel):
    id: int
    username: str
    is_superuser: bool


class UserResponse(HalResponse[BaseHal]):
    kind = "User"
    id: int
    username: str
    password: str
    is_superuser: bool
    first_name: str
    last_name: Optional[str]
    is_staff: bool
    is_active: bool
    date_joined: datetime
    email: Optional[str]
    last_login: Optional[datetime]

    @classmethod
    def from_model(cls, user: User, self_base_hyperlink: str) -> Self:
        return cls(
            id=user.id,
            username=user.username,
            password=user.password,
            is_superuser=user.is_superuser,
            first_name=user.first_name,
            last_name=user.last_name,
            is_staff=user.is_staff,
            is_active=user.is_active,
            date_joined=user.date_joined,
            email=user.email,
            last_login=user.last_login,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{user.id}"
                )
            ),
        )


class UsersListResponse(TokenPaginatedResponse[UserResponse]):
    kind = "UsersList"


class SshKeyResponse(HalResponse[BaseHal]):
    kind = "SshKey"
    id: int
    key: str
    protocol: Optional[SshKeysProtocolType] = None
    auth_id: Optional[str] = None
    user_id: int

    @classmethod
    def from_model(cls, sshkey: SshKey, self_base_hyperlink: str) -> Self:
        return cls(
            id=sshkey.id,
            key=sshkey.key,
            protocol=sshkey.protocol,
            auth_id=sshkey.auth_id,
            user_id=sshkey.user_id,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{sshkey.id}"
                )
            ),
        )


class SshKeysListResponse(TokenPaginatedResponse[SshKeyResponse]):
    kind = "SshKeysList"
