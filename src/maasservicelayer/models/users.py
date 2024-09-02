# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Optional

from django.contrib.auth.hashers import PBKDF2PasswordHasher

from maasservicelayer.models.base import MaasBaseModel


class User(MaasBaseModel):
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
