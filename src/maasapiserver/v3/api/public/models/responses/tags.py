# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.tags import Tag


class TagResponse(HalResponse[BaseHal]):
    kind = "Tag"
    id: int
    name: str
    comment: str
    definition: str
    kernel_opts: str

    @classmethod
    def from_model(cls, tag: Tag, self_base_hyperlink: str) -> Self:
        return cls(
            id=tag.id,
            name=tag.name,
            comment=tag.comment,
            definition=tag.definition,
            kernel_opts=tag.kernel_opts,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{tag.id}"
                )
            ),
        )


class TagsListResponse(PaginatedResponse[TagResponse]):
    kind = "TagsList"
