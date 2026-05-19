# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime

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
    last_name: str | None = None
    is_staff: bool
    is_active: bool
    date_joined: datetime = Field(default_factory=utcnow)
    email: str | None = None
    last_login: datetime | None = None

    def check_password(self, password) -> bool:
        return PBKDF2PasswordHasher().verify(password, self.password)


@generate_builder()
class UserProfile(MaasBaseModel):
    completed_intro: bool
    auth_last_check: datetime | None = None
    is_local: bool
    user_id: int
    provider_id: int | None = None


class UserStatistics(BaseModel):
    id: int
    completed_intro: bool
    is_local: bool
    machines_count: int
    sshkeys_count: int
