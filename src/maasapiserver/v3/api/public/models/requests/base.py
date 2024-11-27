# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from re import compile
from typing import Optional

from pydantic import BaseModel, Field, validator

# from src/maasserver/fields.py:31
MODEL_NAME_VALIDATOR = compile(r"^\w[ \w-]*$")


class NamedBaseModel(BaseModel):
    name: str = Field(description="The unique name of the entity.")

    # TODO: move to @field_validator when we migrate to pydantic 2.x
    @validator("name")
    def check_regex_name(cls, v: str) -> str:
        if not MODEL_NAME_VALIDATOR.match(v):
            raise ValueError("Invalid entity name.")
        return v


class OptionalNamedBaseModel(BaseModel):
    name: Optional[str] = Field(
        description="The unique name of the entity.", default=None
    )

    # TODO: move to @field_validator when we migrate to pydantic 2.x
    @validator("name")
    def check_regex_name(cls, v: str) -> str:
        # If the name is set, it must not be None and it must match the regex
        if v is not None and not MODEL_NAME_VALIDATOR.match(v):
            raise ValueError("Invalid entity name.")
        return v
