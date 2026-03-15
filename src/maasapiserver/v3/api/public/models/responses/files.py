#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import b64encode
from typing import Self

from pydantic import BaseModel, Field

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
)
from maasservicelayer.models.filestorage import FileStorage


class FileResponse(HalResponse[BaseHal]):
    kind: str = Field(default="File")

    id: int
    filename: str
    content: str
    key: str
    owner_id: int | None = None

    @classmethod
    def from_model(cls, file: FileStorage, self_base_hyperlink: str) -> Self:
        return cls(
            id=file.id,
            filename=file.filename,
            content=b64encode(file.content).decode(),
            key=file.key,
            owner_id=file.owner_id,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{file.id}"
                )
            ),
        )


class FileListItemResponse(HalResponse[BaseHal]):
    # Files returned as part of a list query should not contain file content.
    # A separate, specific GET is required to retrieve content.
    kind: str = Field(default="FileListItem")

    id: int
    filename: str
    key: str
    owner_id: int | None = None

    @classmethod
    def from_model(cls, file: FileStorage, self_base_hyperlink: str) -> Self:
        return cls(
            id=file.id,
            filename=file.filename,
            key=file.key,
            owner_id=file.owner_id,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{file.id}"
                )
            ),
        )


class FileListResponse(BaseModel):
    kind: str = Field(default="FileList")

    items: list[FileListItemResponse]
