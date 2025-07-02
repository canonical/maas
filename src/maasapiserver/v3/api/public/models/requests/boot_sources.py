# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import b64decode
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, root_validator, validator

from maasservicelayer.builders.bootsources import BootSourceBuilder
from maasservicelayer.exceptions.catalog import ValidationException


class BootSourceRequest(BaseModel):
    url: str = Field(
        description="URL of SimpleStreams server providing boot source "
        "information."
    )
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
    priority: int = Field(
        description="Priority value. Higher values mean higher priority. Must "
        "be non-negative.",
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

    @validator("url")
    def validate_url_format(cls, value: str):
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValidationException.build_for_field(
                field="url",
                message="URL must be a valid HTTP or HTTPS address.",
            )
        return value

    @validator("priority")
    def validate_priority(cls, value: int) -> int:
        if value < 0:
            raise ValidationException.build_for_field(
                field="priority",
                message="Priority must be a non-negative integer.",
            )
        return value

    def to_builder(self) -> BootSourceBuilder:
        self.keyring_filename = self.keyring_filename or ""
        self.keyring_data = self.keyring_data or ""
        keyring_data = self.keyring_data.encode("utf-8")
        return BootSourceBuilder(
            url=self.url,
            keyring_filename=self.keyring_filename,
            keyring_data=keyring_data,
            priority=self.priority,
            skip_keyring_verification=self.skip_keyring_verification,
        )


class BootSourceFetchRequest(BaseModel):
    url: str = Field(
        description="URL of SimpleStreams server providing boot source "
        "information."
    )

    keyring_path: str | None = Field(
        default=None,
        description="File path to keyring to use for verifying signatures of "
        "the boot sources.",
    )
    keyring_data: str | None = Field(
        default=None,
        description="Base64-encoded keyring data to use for verifying "
        "signatures of the boot sources.",
    )
    validate_products: bool = Field(
        default=True,
        description="Whether to validate products in the boot sources.",
    )

    # TODO: Switch to model_validator when we migrate to pydantic 2.x
    @root_validator
    def ensure_either_keyring_path_or_data_not_both(
        cls, values: dict[str, Any]
    ) -> dict[str, Any]:
        if (
            values.get("keyring_path", None) is not None
            and values.get("keyring_data", None) is not None
        ):
            raise ValueError(
                "At most one of 'keyring_path' and 'keyring_data' may be specified"
            )
        return values

    # TODO: Switch to model_validator when we migrate to pydantic 2.x
    @root_validator
    def ensure_valid_base64_keyring_data_provided(
        cls, values: dict[str, Any]
    ) -> dict[str, Any]:
        keyring_data: str | None = values.get("keyring_data", None)
        if keyring_data is None:
            return values

        try:
            b64decode(keyring_data)
            return values
        except Exception as err:
            raise ValueError(
                "Invalid base64 encoding of `keyring-data` provided"
            ) from err
