# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import re
from typing import Optional

from pydantic import BaseModel, validator

from maasservicelayer.db.repositories.users import UserResourceBuilder


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

    def to_builder(self) -> UserResourceBuilder:
        resource_builder = (
            UserResourceBuilder()
            .with_username(self.username)
            .with_password(self.password)
            .with_is_superuser(self.is_superuser)
            .with_first_name(self.first_name)
            .with_last_name(self.last_name)
            .with_email(self.email)
        )
        return resource_builder
