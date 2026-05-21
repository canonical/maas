#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import Field

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maascommon.enums.boot_resources import BootResourceFileType
from maasservicelayer.models.bootresourcefiles import BootResourceFile
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


def _file_info_from_model(f: BootResourceFile) -> BootAssetFileInfo:
    return BootAssetFileInfo(
        filename=f.filename,
        filetype=f.filetype,
        sha256=f.sha256,
        size=f.size,
        _links=BaseHal(self=BaseHref(href="")),
    )


class BootloaderResponse(HalResponse[BaseHal]):
    kind: str = Field(default="Bootloader")
    type: Literal["bootloader"] = "bootloader"
    id: int
    name: str
    architecture: str
    bootloader_type: str
    versions: list[str] = Field(default_factory=list)
    latest_version: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    primary_file: str = ""
    files: list[BootAssetFileInfo] = Field(default_factory=list)

    @classmethod
    def from_model(
        cls,
        boot_resource: BootResource,
        self_base_hyperlink: str,
        versions: list[str] | None = None,
        resource_files: list[BootResourceFile] | None = None,
    ) -> Self:
        name, _ = boot_resource.split_name()
        arch, _ = boot_resource.split_arch()
        versions = versions or []
        files = resource_files or []
        primary_file = ""
        for f in files:
            if f.filetype == BootResourceFileType.BOOTLOADER_TARBALL:
                primary_file = (f.extra or {}).get("primary_file", "")
                break
        return cls(
            id=boot_resource.id,
            name=name,
            architecture=arch,
            bootloader_type=boot_resource.bootloader_type or "",
            versions=versions,
            latest_version=versions[0] if versions else "",
            created_at=boot_resource.created,
            updated_at=boot_resource.updated,
            primary_file=primary_file,
            files=[_file_info_from_model(f) for f in files],
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
    type: Literal["kernel"] = "kernel"
    id: int
    name: str
    architecture: str
    kflavor: str
    versions: list[str] = Field(default_factory=list)
    latest_version: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    complete: bool = False

    @classmethod
    def from_model(
        cls,
        boot_resource: BootResource,
        self_base_hyperlink: str,
        versions: list[str] | None = None,
        resource_files: list[BootResourceFile] | None = None,
    ) -> Self:
        name, _ = boot_resource.split_name()
        arch, _ = boot_resource.split_arch()
        versions = versions or []
        files = resource_files or []
        filetypes = {f.filetype for f in files}
        complete = (
            BootResourceFileType.BOOT_KERNEL in filetypes
            and BootResourceFileType.BOOT_INITRD in filetypes
        )
        return cls(
            id=boot_resource.id,
            name=name,
            architecture=arch,
            kflavor=boot_resource.kflavor or "",
            versions=versions,
            latest_version=versions[0] if versions else "",
            created_at=boot_resource.created,
            updated_at=boot_resource.updated,
            complete=complete,
            _links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{boot_resource.id}"
                )
            ),
        )


class KernelListResponse(PaginatedResponse[KernelResponse]):
    kind: str = Field(default="KernelList")


# Discriminated union for all custom boot asset types.
BootAssetResponse = Annotated[
    BootloaderResponse | KernelResponse,
    Field(discriminator="type"),
]
