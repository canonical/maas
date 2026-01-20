# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime

from maascommon.enums.boot_resources import BootResourceType, ImageUpdateStatus
from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)
from maasservicelayer.models.bootsourceselections import (
    BootSourceSelectionStatistic,
    BootSourceSelectionStatus,
)


class CustomBootResourceStatus(BootSourceSelectionStatus):
    update_status: ImageUpdateStatus = ImageUpdateStatus.NO_UPDATES_AVAILABLE
    selected: bool = True


class CustomBootResourceStatistic(BootSourceSelectionStatistic): ...


@generate_builder()
class BootResource(MaasTimestampedBaseModel):
    rtype: BootResourceType
    name: str
    architecture: str
    extra: dict
    kflavor: str | None = None
    bootloader_type: str | None = None
    rolling: bool
    base_image: str
    alias: str | None = None
    last_deployed: datetime | None = None
    selection_id: int | None = None

    def split_arch(self) -> tuple[str, str]:
        arch, subarch = self.architecture.split("/", 1)
        return arch, subarch

    def split_name(self) -> tuple[str, str]:
        if "/" in self.name:
            osystem, release = self.name.split("/", 1)
        else:
            osystem = "custom"
            release = self.name
        return osystem, release

    def get_title(self) -> str | None:
        return self.extra.get("title")
