#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""
This module contains the response definitions for the Vault response objects.
The actual responses contain much more data, but here we just define the ones we are interested in.
"""

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel


class BaseVaultResponse(BaseModel):
    request_id: Optional[str]
    warnings: Optional[str] = None
    auth: Optional[str] = None


class AppRoleLoginDetailResponse(BaseModel):
    client_token: str


class AppRoleLoginResponse(BaseVaultResponse):
    auth: AppRoleLoginDetailResponse


class TokenLookupSelfDetailResponse(BaseModel):
    issue_time: datetime
    expire_time: datetime


class TokenLookupSelfResponse(BaseVaultResponse):
    data: TokenLookupSelfDetailResponse


class KvV2ReadDetailResponse(BaseModel):
    data: Dict[str, str]


class KvV2ReadResponse(BaseVaultResponse):
    data: KvV2ReadDetailResponse


class KvV2WriteDetailResponse(BaseModel):
    created_time: Optional[datetime] = None
    deletion_time: Optional[str] = None
    version: Optional[int] = None


class KvV2WriteResponse(BaseVaultResponse):
    data: KvV2WriteDetailResponse
