# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Optional

from django.contrib.auth.hashers import PBKDF2PasswordHasher
from pydantic import Field

from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.utils.date import utcnow


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

    def etag(self) -> str:
        pass

    def check_password(self, password) -> bool:
        return PBKDF2PasswordHasher().verify(password, self.password)


class UserProfile(MaasBaseModel):
    completed_intro: bool
    auth_last_check: Optional[datetime]
    is_local: bool
    user_id: int

    def etag(self) -> str:
        pass


class Consumer(MaasBaseModel):
    name: str
    description: str
    key: str
    secret: str
    status: str
    user_id: Optional[int]

    def etag(self) -> str:
        pass


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

    def etag(self) -> str:
        pass
