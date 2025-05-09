# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from pydantic import BaseModel, Field, root_validator

from maascommon.enums.package_repositories import (
    ComponentsToDisableEnum,
    KnownArchesEnum,
    KnownComponentsEnum,
    PACKAGE_REPO_MAIN_ARCHES,
    PACKAGE_REPO_PORTS_ARCHES,
    PocketsToDisableEnum,
)
from maasservicelayer.builders.package_repositories import (
    PackageRepositoryBuilder,
)
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.fields import PackageRepoUrl


class PackageRepositoryCreateRequest(BaseModel):
    name: str = Field(description="The name of the package repository.")
    key: str | None = Field(
        description="The authentication key to use with the repository.",
        default="",
    )
    url: PackageRepoUrl = Field(
        description="The url of the package repository."
    )
    distributions: list[str] = Field(
        description="Which package distribution to include.",
        default_factory=list,
    )
    components: set[KnownComponentsEnum] = Field(
        description="The list of components to enable."
        "Only applicable to custom repositories.",
        default_factory=set,
    )
    arches: set[KnownArchesEnum] = Field(
        description="The list of supported architectures.",
        default_factory=set,
    )
    disabled_pockets: set[PocketsToDisableEnum] = Field(
        description="The list of pockets to disable.",
        default_factory=set,
    )
    disabled_components: set[ComponentsToDisableEnum] = Field(
        description="The list of components to disable."
        "Only applicable to the default Ubuntu repositories.",
        default_factory=set,
    )
    disable_sources: bool = Field(description="Disable deb-src lines.")
    enabled: bool = Field(
        description="Whether or not the repository is enabled.", default=True
    )

    @root_validator
    def populate_arches_if_empty(cls, values: dict[str, Any]):
        if len(values["arches"]) == 0:
            if values["name"] == "ports_archive":
                values["arches"] = PACKAGE_REPO_PORTS_ARCHES
            else:
                values["arches"] = PACKAGE_REPO_MAIN_ARCHES
        return values

    def to_builder(self, is_default: bool = False) -> PackageRepositoryBuilder:
        return PackageRepositoryBuilder(
            name=self.name,
            key=self.key,  # pyright: ignore [reportArgumentType]
            url=self.url,
            distributions=self.distributions,
            components=self.components,
            arches=self.arches,
            disabled_pockets=self.disabled_pockets,
            disabled_components=self.disabled_components,
            disable_sources=self.disable_sources,
            enabled=self.enabled,
            default=is_default,
        )


class PackageRepositoryUpdateRequest(PackageRepositoryCreateRequest):
    def validate_components(self, is_default: bool) -> None:
        if is_default and len(self.components) > 0:
            raise ValidationException.build_for_field(
                "components",
                message="This is a default Ubuntu repository. Please update "
                "'disabled_components' instead.",
            )
        if not is_default and len(self.disabled_components) > 0:
            raise ValidationException.build_for_field(
                "disabled_components",
                message="This is a custom Ubuntu repository. Please update "
                "'components' instead.",
            )

    def validate_enabled(self, is_default: bool) -> None:
        if is_default and not self.enabled:
            raise ValidationException.build_for_field(
                field="enabled",
                message="Default repositories may not be disabled.",
            )

    def to_builder(self, is_default: bool = False) -> PackageRepositoryBuilder:
        self.validate_components(is_default)
        self.validate_enabled(is_default)
        return super().to_builder(is_default)
