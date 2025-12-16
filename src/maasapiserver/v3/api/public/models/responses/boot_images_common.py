# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Common responses for boot resources and selections."""

from datetime import datetime

from pydantic import BaseModel

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maascommon.enums.boot_resources import ImageStatus, ImageUpdateStatus
from maascommon.utils.converters import human_readable_bytes
from maascommon.utils.images import format_ubuntu_distro_series
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.models.bootsourceselections import (
    BootSourceSelection,
    BootSourceSelectionStatistic,
    BootSourceSelectionStatus,
)


class ImageResponse(HalResponse[BaseHal]):
    kind = "Image"
    id: int
    os: str
    release: str
    title: str
    architecture: str
    boot_source_id: int | None

    @classmethod
    def from_selection(
        cls, selection: BootSourceSelection, self_base_hyperlink: str
    ):
        return cls(
            id=selection.id,
            os=selection.os,
            release=selection.release,
            title=format_ubuntu_distro_series(selection.release),
            architecture=selection.arch,
            boot_source_id=selection.boot_source_id,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{selection.id}"
                )
            ),
        )

    @classmethod
    def from_boot_resource(
        cls, boot_resource: BootResource, self_base_hyperlink: str
    ):
        arch, _ = boot_resource.split_arch()
        osystem, release = boot_resource.name.split("/")
        return cls(
            id=boot_resource.id,
            os=osystem,
            release=release,
            title=format_ubuntu_distro_series(release),
            architecture=arch,
            boot_source_id=None,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{boot_resource.id}"
                )
            ),
        )


class ImageListResponse(PaginatedResponse[ImageResponse]):
    kind = "ImageList"


class ImageStatusResponse(BaseModel):
    kind = "ImageStatus"
    id: int
    status: ImageStatus
    update_status: ImageUpdateStatus
    sync_percentage: float
    selected: bool

    @classmethod
    def from_model(cls, status: BootSourceSelectionStatus):
        return cls(
            id=status.id,
            status=status.status,
            update_status=status.update_status,
            sync_percentage=status.sync_percentage,
            selected=status.selected,
        )


class ImageStatusListResponse(PaginatedResponse[ImageStatusResponse]):
    kind = "ImageStatusList"


class ImageStatisticResponse(BaseModel):
    kind = "ImageStatistic"
    id: int
    last_updated: datetime
    last_deployed: datetime | None
    size: str
    node_count: int
    deploy_to_memory: bool

    @classmethod
    def from_model(cls, statistic: BootSourceSelectionStatistic):
        return cls(
            id=statistic.id,
            last_updated=statistic.last_updated,
            last_deployed=statistic.last_deployed,
            size=human_readable_bytes(statistic.size),
            node_count=statistic.node_count,
            deploy_to_memory=statistic.deploy_to_memory,
        )


class ImageStatisticListResponse(PaginatedResponse[ImageStatisticResponse]):
    kind = "ImageStatisticList"
