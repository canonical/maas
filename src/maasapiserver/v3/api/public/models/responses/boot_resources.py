#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from typing import Self

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.bootresources import BootResource


class BootResourceResponse(HalResponse[BaseHal]):
    kind = "BootResource"
    id: int
    os: str
    release: str
    architecture: str
    sub_architecture: str

    @classmethod
    def from_model(
        cls, boot_resource: BootResource, self_base_hyperlink: str
    ) -> Self:
        os, release = boot_resource.split_name()
        arch, subarch = boot_resource.split_arch()
        return cls(
            id=boot_resource.id,
            os=os,
            release=release,
            architecture=arch,
            sub_architecture=subarch,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{boot_resource.id}"
                )
            ),
        )


class BootResourceListResponse(PaginatedResponse[BootResourceResponse]):
    kind = "BootResourceList"


class BootloaderResponse(HalResponse[BaseHal]):
    kind = "Bootloader"
    id: int
    name: str
    architecture: str
    bootloader_type: str

    @classmethod
    def from_model(
        cls, boot_resource: BootResource, self_base_hyperlink: str
    ) -> Self:
        name, _ = boot_resource.split_name()
        arch, _ = boot_resource.split_arch()
        return cls(
            id=boot_resource.id,
            name=name,
            architecture=arch,
            bootloader_type=boot_resource.bootloader_type,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{boot_resource.id}"
                )
            ),
        )


class BootloaderListResponse(PaginatedResponse[BootloaderResponse]):
    kind = "BootloaderList"
