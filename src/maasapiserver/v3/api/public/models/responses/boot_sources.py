# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional, Self

from pydantic import BaseModel

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.bootsources import (
    BootSource,
    SourceAvailableImage,
)


class BootSourceResponse(HalResponse[BaseHal]):
    kind = "BootSource"
    id: int
    url: str
    keyring_filename: Optional[str]
    keyring_data: Optional[str]
    priority: int
    skip_keyring_verification: bool

    @classmethod
    def from_model(
        cls, boot_source: BootSource, self_base_hyperlink: str
    ) -> Self:
        keyring_data = boot_source.keyring_data or b""
        keyring_data = keyring_data.decode("utf-8")
        return cls(
            id=boot_source.id,
            url=boot_source.url,
            keyring_filename=boot_source.keyring_filename,
            keyring_data=keyring_data,
            priority=boot_source.priority,
            skip_keyring_verification=boot_source.skip_keyring_verification,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{boot_source.id}"
                )
            ),
        )


class BootSourcesListResponse(PaginatedResponse[BootSourceResponse]):
    kind = "BootSourcesList"


class SourceAvailableImageResponse(BaseModel):
    kind = "SourceAvailableImage"
    os: str
    release: str
    release_title: str
    architecture: str

    @classmethod
    def from_model(
        cls,
        source_image: SourceAvailableImage,
    ) -> Self:
        return cls(
            os=source_image.os,
            release=source_image.release,
            release_title=source_image.release_title,
            architecture=source_image.architecture,
        )


class SourceAvailableImageListResponse(BaseModel):
    kind = "SourceAvailableImageList"
    items: list[SourceAvailableImageResponse]
