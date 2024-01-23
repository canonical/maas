from re import compile

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
