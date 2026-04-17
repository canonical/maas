#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""
This module contains the response definitions for the Vault response objects.
The actual responses contain much more data, but here we just define the ones we are interested in.
"""

from datetime import datetime
from typing import Dict

from pydantic import BaseModel


class BaseVaultResponse(BaseModel):
    request_id: str | None = None
    warnings: str | None = None


class AppRoleLoginDetailResponse(BaseModel):
    client_token: str


class AppRoleLoginResponse(BaseVaultResponse):
    auth: AppRoleLoginDetailResponse


class TokenLookupSelfDetailResponse(BaseModel):
    issue_time: datetime
    expire_time: datetime


class TokenLookupSelfResponse(BaseVaultResponse):
    auth: str | None = None
    data: TokenLookupSelfDetailResponse


class KvV2ReadDetailResponse(BaseModel):
    data: Dict[str, str]


class KvV2ReadResponse(BaseVaultResponse):
    auth: str | None = None
    data: KvV2ReadDetailResponse


class KvV2WriteDetailResponse(BaseModel):
    created_time: datetime | None = None
    deletion_time: str | None = None
    version: int | None = None


class KvV2WriteResponse(BaseVaultResponse):
    auth: str | None = None
    data: KvV2WriteDetailResponse
