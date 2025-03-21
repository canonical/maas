# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Optional

from django.contrib.auth.hashers import PBKDF2PasswordHasher
from pydantic import BaseModel, Field

from maasservicelayer.models.base import generate_builder, MaasBaseModel
from maasservicelayer.utils.date import utcnow


@generate_builder()
class User(MaasBaseModel):
    username: str
    password: str
    is_superuser: bool
    first_name: str
    last_name: Optional[str] = None
    is_staff: bool
    is_active: bool
    date_joined: datetime = Field(default_factory=utcnow)
    email: Optional[str] = None
    last_login: Optional[datetime] = None

    def check_password(self, password) -> bool:
        return PBKDF2PasswordHasher().verify(password, self.password)


@generate_builder()
class UserProfile(MaasBaseModel):
    completed_intro: bool
    auth_last_check: Optional[datetime]
    is_local: bool
    user_id: int


class Consumer(MaasBaseModel):
    name: str
    description: str
    key: str
    secret: str
    status: str
    user_id: Optional[int]


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


class UserWithSummary(BaseModel):
    id: int
    completed_intro: bool
    email: Optional[str] = None  # it's a string in the UI
    is_local: bool
    is_superuser: bool
    last_name: Optional[str] = None  # it's a string in the UI
    last_login: Optional[datetime] = None
    machines_count: int
    sshkeys_count: int
    username: str
