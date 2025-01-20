# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import re
from typing import Optional

from pydantic import BaseModel, validator

from maasservicelayer.models.users import UserBuilder


class UserRequest(BaseModel):
    username: str
    password: str
    is_superuser: bool
    first_name: str
    last_name: Optional[str]
    email: Optional[str]

    @validator("email")
    def check_email(cls, v: str) -> str:
        match = re.fullmatch(r"^[\w\.-]+@([\w-]+\.)+[\w-]{2,4}$", v)
        if not match:
            raise ValueError("A valid email address must be provided.")
        return v.lower()

    def to_builder(self) -> UserBuilder:
        return UserBuilder(
            username=self.username,
            password=self.password,
            is_superuser=self.is_superuser,
            first_name=self.first_name,
            last_name=self.last_name,
            email=self.email,
        )
