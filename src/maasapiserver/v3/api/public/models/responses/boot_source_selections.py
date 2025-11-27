# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from pydantic import BaseModel

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maascommon.enums.boot_resources import ImageStatus, ImageUpdateStatus
from maasservicelayer.models.bootsourceselections import (
    BootSourceSelection,
    BootSourceSelectionStatus,
)


class BootSourceSelectionResponse(HalResponse[BaseHal]):
    kind = "BootSourceSelection"
    id: int
    os: str
    release: str
    arch: str
    boot_source_id: int

    @classmethod
    def from_model(
        cls,
        boot_source_selection: BootSourceSelection,
        self_base_hyperlink: str,
    ):
        return cls(
            id=boot_source_selection.id,
            os=boot_source_selection.os,
            release=boot_source_selection.release,
            arch=boot_source_selection.arch,
            boot_source_id=boot_source_selection.boot_source_id,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{boot_source_selection.id}"
                )
            ),
        )


class BootSourceSelectionListResponse(
    PaginatedResponse[BootSourceSelectionResponse]
):
    kind = "BootSourcesList"


class BootSourceSelectionSyncResponse(BaseModel):
    kind = "BootSourceSelectionSync"
    monitor_url: str


class BootSourceSelectionStatusResponse(BaseModel):
    kind = "BootSourceSelectionStatus"
    selection_id: int
    status: ImageStatus
    update_status: ImageUpdateStatus
    sync_percentage: float
    selected: bool

    @classmethod
    def from_model(cls, status: BootSourceSelectionStatus):
        return cls(
            selection_id=status.id,
            status=status.status,
            update_status=status.update_status,
            sync_percentage=status.sync_percentage,
            selected=status.selected,
        )


class BootSourceSelectionStatusListResponse(
    PaginatedResponse[BootSourceSelectionStatusResponse]
):
    kind = "BootSourceSelectionStatusList"
