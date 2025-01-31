# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import re
from typing import Optional

from django.contrib.auth.hashers import PBKDF2PasswordHasher
from pydantic import BaseModel, Field, validator

from maasservicelayer.builders.users import UserBuilder


class UserRequest(BaseModel):
    username: str
    password: str = Field(..., min_length=1)
    is_superuser: bool
    is_staff: bool
    is_active: bool
    first_name: str
    last_name: str
    email: Optional[str]

    @validator("email")
    def check_email(cls, v: str) -> str:
        match = re.fullmatch(r"^(?!\.)[\w\.\+\-]+@([\w-]+\.)+[\w-]{2,4}$", v)
        if not match:
            raise ValueError("A valid email address must be provided.")
        return v.lower()

    def to_builder(self) -> UserBuilder:
        hasher = PBKDF2PasswordHasher()
        salt = hasher.salt()
        hashed_password = hasher.encode(self.password, salt)
        self.password = hashed_password

        return UserBuilder(
            username=self.username,
            password=self.password,
            is_superuser=self.is_superuser,
            is_staff=self.is_staff,
            is_active=self.is_active,
            first_name=self.first_name,
            last_name=self.last_name,
            email=self.email,
        )
