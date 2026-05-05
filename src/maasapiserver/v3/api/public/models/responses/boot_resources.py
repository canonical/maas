#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from typing import Self

from pydantic import Field

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.bootresources import BootResource


class BootAssetFileInfo(HalResponse[BaseHal]):
    """Information about a boot asset file."""

    kind: str = Field(default="BootAssetFile")
    filename: str
    filetype: str
    sha256: str
    size: int


class BootAssetUploadResponse(HalResponse[BaseHal]):
    """Response from a boot asset upload operation."""

    kind: str = Field(default="BootAssetUpload")
    id: int
    name: str
    architecture: str
    version: str
    kflavor: str | None = None
    bootloader_type: str | None = None
    files: list[BootAssetFileInfo] = Field(default_factory=list)

    @classmethod
    def from_model(
        cls,
        boot_resource: BootResource,
        version: str,
        files: list[dict],
        self_base_hyperlink: str,
    ) -> Self:
        file_infos = [
            BootAssetFileInfo(
                filename=f["filename"],
                filetype=f["filetype"],
                sha256=f["sha256"],
                size=f["size"],
                _links=BaseHal(self=BaseHref(href="")),
            )
            for f in files
        ]
        return cls(
            id=boot_resource.id,
            name=boot_resource.name,
            architecture=boot_resource.architecture,
            version=version,
            kflavor=boot_resource.kflavor,
            bootloader_type=boot_resource.bootloader_type,
            files=file_infos,
            _links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{boot_resource.id}"
                )
            ),
        )


class BootResourceResponse(HalResponse[BaseHal]):
    kind: str = Field(default="BootResource")
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
    kind: str = Field(default="BootResourceList")


class BootloaderResponse(HalResponse[BaseHal]):
    kind: str = Field(default="Bootloader")
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
    kind: str = Field(default="BootloaderList")


class KernelResponse(HalResponse[BaseHal]):
    kind: str = Field(default="Kernel")
    id: int
    name: str
    architecture: str
    kflavor: str

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
            kflavor=boot_resource.kflavor or "",
            _links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{boot_resource.id}"
                )
            ),
        )


class KernelListResponse(PaginatedResponse[KernelResponse]):
    kind: str = Field(default="KernelList")
