# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.package_repositories import (
    ComponentsToDisableEnum,
    KnownArchesEnum,
    KnownComponentsEnum,
    PocketsToDisableEnum,
)
from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)
from maasservicelayer.models.fields import PackageRepoUrl


@generate_builder()
class PackageRepository(MaasTimestampedBaseModel):
    name: str
    key: str
    url: PackageRepoUrl
    distributions: list[str]
    components: set[KnownComponentsEnum]
    arches: set[KnownArchesEnum]
    disabled_pockets: set[PocketsToDisableEnum]
    disabled_components: set[ComponentsToDisableEnum]
    disable_sources: bool
    default: bool
    enabled: bool
