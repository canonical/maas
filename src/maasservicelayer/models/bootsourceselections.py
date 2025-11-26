# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from enum import StrEnum

from maasservicelayer.models.base import (
    generate_builder,
    MaasBaseModel,
    MaasTimestampedBaseModel,
)


class SelectionStatus(StrEnum):
    READY = "Ready"
    DOWNLOADING = "Downloading"
    WAITING_FOR_DOWNLOAD = "Waiting for download"


class SelectionUpdateStatus(StrEnum):
    DOWNLOADING = "Downloading"
    UPDATE_AVAILABLE = "Update available"
    NO_UPDATES_AVAILABLE = "No updates available"


class BootSourceSelectionStatus(MaasBaseModel):
    id: int
    status: SelectionStatus
    update_status: SelectionUpdateStatus
    sync_percentage: float
    selected: bool


@generate_builder()
class BootSourceSelection(MaasTimestampedBaseModel):
    os: str
    release: str
    arch: str
    boot_source_id: int
