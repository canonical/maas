# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import b64decode
from typing import Any

from pydantic import BaseModel, Field, root_validator


class BootSourceFetchRequest(BaseModel):
    url: str = Field(
        description="URL of SimpleStreams server providing boot source information."
    )

    keyring_path: str | None = Field(
        default=None,
        description="File path to keyring to use for verifying signatures of the boot sources.",
    )
    keyring_data: str | None = Field(
        default=None,
        description="Base64-encoded keyring data to use for verifying signatures of the boot sources.",
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
