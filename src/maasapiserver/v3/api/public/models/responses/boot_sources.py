# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Optional, Self, Tuple

from pydantic import BaseModel

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.bootsources import BootSource
from maasservicelayer.utils.images.helpers import ImageSpec


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


class BootSourceFetchResponse(BaseModel):
    os: str
    arch: str
    subarch: str
    kflavor: str
    release: str
    label: Optional[str]

    content_id: str
    product_name: str
    version_name: str
    path: str

    subarches: Optional[str]
    bootloader_type: Optional[str]
    release_title: Optional[str]
    release_codename: Optional[str]
    support_eol: Optional[datetime]

    @classmethod
    def from_model(
        cls,
        boot_source: Tuple[ImageSpec, dict[str, str]],
    ) -> Self:
        image_spec, metadata = boot_source
        parsed_support_eol = None
        if "support_eol" in metadata:
            parsed_support_eol = datetime.strptime(
                metadata["support_eol"], "%Y-%m-%d"
            )

        return cls(
            os=image_spec.os,
            arch=image_spec.arch,
            subarch=image_spec.subarch,
            kflavor=image_spec.kflavor,
            release=image_spec.release,
            label=metadata.get("label"),
            content_id=metadata.get("content_id"),  # pyright: ignore [reportArgumentType]
            product_name=metadata.get("product_name"),  # pyright: ignore [reportArgumentType]
            version_name=metadata.get("version_name"),  # pyright: ignore [reportArgumentType]
            path=metadata.get("path"),  # pyright: ignore [reportArgumentType]
            subarches=metadata.get("subarches"),
            bootloader_type=metadata.get("bootloader_type"),
            release_title=metadata.get("release_title"),
            release_codename=metadata.get("release_codename"),
            support_eol=parsed_support_eol,
        )


class BootSourceFetchListResponse(BaseModel):
    items: list[BootSourceFetchResponse]
