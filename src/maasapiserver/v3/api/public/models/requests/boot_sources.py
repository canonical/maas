# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import b64decode
from urllib.parse import urlparse

from pydantic import BaseModel, Extra, Field, root_validator, validator

from maasservicelayer.builders.bootsources import BootSourceBuilder
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootsources import (
    BootSourcesClauseFactory,
)
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.services import ServiceCollectionV3


def validate_url_format(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationException.build_for_field(
            field="url",
            message="URL must be a valid HTTP or HTTPS address.",
        )
    return value


async def validate_priority(value: int, services: ServiceCollectionV3) -> int:
    if value < 0:
        raise ValidationException.build_for_field(
            field="priority",
            message="Priority must be a non-negative integer.",
        )

    if await services.boot_sources.exists(
        query=QuerySpec(where=BootSourcesClauseFactory.with_priority(value))
    ):
        raise ValidationException.build_for_field(
            field="priority",
            message="A boot source with the same priority already exists.",
        )
    return value


class BootSourceRequest(BaseModel):
    keyring_filename: str | None = Field(
        description="File path to keyring to use for verifying signatures of "
        "the boot sources.",
        default="",
    )
    keyring_data: str | None = Field(
        description="Base64-encoded keyring data used for signature "
        "verification. Optional alternative to providing a keyring "
        "file path.",
        default="",
    )
    skip_keyring_verification: bool = Field(
        description="If true, keyring signature verification will be skipped.",
        default=False,
    )

    @root_validator
    def validate_keyring_fields(cls, values):
        skip_verification = values.get("skip_keyring_verification")
        keyring_filename = values.get("keyring_filename")
        keyring_data = values.get("keyring_data")

        has_filename = bool(keyring_filename)
        has_data = bool(keyring_data)

        if has_filename and has_data:
            raise ValidationException.build_for_field(
                field="keyring_data",
                message="Only one of keyring_filename or keyring_data can be specified.",
            )

        if not skip_verification and (not has_filename and not has_data):
            raise ValidationException.build_for_field(
                field="keyring_data",
                message="One of keyring_filename or keyring_data must be specified.",
            )

        return values

    @validator("keyring_filename")
    def validate_b64_keyring_filename(cls, value: str | None) -> str:
        return "" if value is None else value

    @validator("keyring_data")
    def validate_b64_keyring_data(cls, value: str) -> str:
        value = "" if value is None else value
        try:
            b64decode(value)
        except Exception as e:
            raise ValidationException.build_for_field(
                field="keyring_data",
                message="keyring_data must be valid Base64 encoded binary data.",
            ) from e
        return value


# Extra.forbid will raise a validation error if the user passes fields not defined.
# Used mainly because of the 'url' being immutable.
class BootSourceUpdateRequest(BootSourceRequest, extra=Extra.forbid):
    priority: int = Field(
        description="Priority value. Higher values mean higher priority. Must "
        "be non-negative.",
    )

    async def to_builder(
        self, services: ServiceCollectionV3
    ) -> BootSourceBuilder:
        priority = await validate_priority(self.priority, services)
        self.keyring_filename = self.keyring_filename or ""
        self.keyring_data = self.keyring_data or ""
        keyring_data = self.keyring_data.encode("utf-8")
        return BootSourceBuilder(
            keyring_filename=self.keyring_filename,
            keyring_data=keyring_data,
            priority=priority,
            skip_keyring_verification=self.skip_keyring_verification,
        )


class BootSourceCreateRequest(BootSourceRequest):
    priority: int = Field(
        description="Priority value. Higher values mean higher priority. Must "
        "be non-negative.",
    )
    url: str = Field(
        description="URL of SimpleStreams server providing boot source information."
    )
    # TODO: switch to field_validator when we migrate to pydantic 2.x
    _validate_url = validator("url", pre=True, allow_reuse=True)(
        validate_url_format
    )

    async def to_builder(
        self, services: ServiceCollectionV3
    ) -> BootSourceBuilder:
        priority = await validate_priority(self.priority, services)
        self.keyring_filename = self.keyring_filename or ""
        self.keyring_data = self.keyring_data or ""
        keyring_data = self.keyring_data.encode("utf-8")
        return BootSourceBuilder(
            url=self.url,
            keyring_filename=self.keyring_filename,
            keyring_data=keyring_data,
            priority=priority,
            skip_keyring_verification=self.skip_keyring_verification,
        )


class BootSourceFetchRequest(BootSourceRequest):
    url: str = Field(
        description="URL of SimpleStreams server providing boot source information."
    )
    # TODO: switch to field_validator when we migrate to pydantic 2.x
    _validate_url = validator("url", pre=True, allow_reuse=True)(
        validate_url_format
    )
