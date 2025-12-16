# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Common responses for boot resources and selections."""

from pydantic import BaseModel

from maasapiserver.v3.api.public.models.responses.base import PaginatedResponse
from maascommon.enums.boot_resources import ImageStatus, ImageUpdateStatus
from maasservicelayer.models.bootsourceselections import (
    BootSourceSelectionStatus,
)


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
