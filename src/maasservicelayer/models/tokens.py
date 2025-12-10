# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Optional

from maasservicelayer.models.base import generate_builder, MaasBaseModel


@generate_builder()
class Token(MaasBaseModel):
    key: str
    secret: str
    verifier: str
    token_type: int
    timestamp: int
    is_approved: bool
    callback: Optional[str]
    callback_confirmed: bool
    consumer_id: int
    user_id: Optional[int]


@generate_builder()
class OIDCRevokedToken(MaasBaseModel):
    token_hash: str
    revoked_at: datetime
    user_email: str
    provider_id: int
