# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.fields import PackageRepoUrl
from maasservicelayer.models.package_repositories import PackageRepository


class PackageRepositoryResponse(HalResponse[BaseHal]):
    kind = "PackageRepository"
    id: int
    name: str
    key: str
    url: PackageRepoUrl
    distributions: list[str]
    components: set[str]
    arches: set[str]
    disabled_pockets: set[str]
    disabled_components: set[str]
    disable_sources: bool
    enabled: bool
    # the 'default' field is excluded from the response

    @classmethod
    def from_model(
        cls, package_repository: PackageRepository, self_base_hyperlink: str
    ) -> Self:
        return cls(
            id=package_repository.id,
            name=package_repository.name,
            key=package_repository.key,
            url=package_repository.url,
            distributions=package_repository.distributions,
            components=package_repository.components,
            arches=package_repository.arches,
            disabled_pockets=package_repository.disabled_pockets,
            disabled_components=package_repository.disabled_components,
            disable_sources=package_repository.disable_sources,
            enabled=package_repository.enabled,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{package_repository.id}"
                )
            ),
        )


class PackageRepositoryListResponse(
    PaginatedResponse[PackageRepositoryResponse]
):
    kind = "PackageRepositoryList"
