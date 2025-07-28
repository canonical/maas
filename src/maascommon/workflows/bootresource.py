# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Sequence

REPORT_INTERVAL = timedelta(seconds=10)
HEARTBEAT_TIMEOUT = timedelta(seconds=10)
DISK_TIMEOUT = timedelta(minutes=15)
DOWNLOAD_TIMEOUT = timedelta(hours=2)
MAX_SOURCES = 5

DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME = "download-bootresource"
CHECK_BOOTRESOURCES_STORAGE_WORKFLOW_NAME = "check-bootresources-storage"
SYNC_BOOTRESOURCES_WORKFLOW_NAME = "sync-bootresources"
DELETE_BOOTRESOURCE_WORKFLOW_NAME = "delete-bootresource"


@dataclass
class ResourceDownloadParam:
    rfile_ids: list[int]
    source_list: list[str]
    sha256: str
    filename_on_disk: str
    total_size: int
    size: int = 0
    force: bool = False
    extract_paths: list[str] = field(default_factory=list)
    http_proxy: str | None = None


@dataclass
class SpaceRequirementParam:
    # If not None, the minimum free space (bytes) required for new resources
    min_free_space: int | None = None

    # If not None, represents the total space (bytes) required for synchronizing
    # all images, including those that might have been already synchronized
    # previously. Hence each region has to subtract the size of the images they
    # already have when they perform the check.
    total_resources_size: int | None = None

    def __post_init__(self):
        if all([self.min_free_space, self.total_resources_size]):
            raise ValueError(
                "Only one of 'min_free_space' and 'total_resources_size' can be specified."
            )


@dataclass
class SyncRequestParam:
    resources: Sequence[ResourceDownloadParam]
    requirement: SpaceRequirementParam
    http_proxy: str | None = None


@dataclass
class ResourceIdentifier:
    sha256: str
    filename_on_disk: str


@dataclass
class ResourceDeleteParam:
    files: Sequence[ResourceIdentifier]


@dataclass
class ResourceCleanupParam:
    expected_files: Sequence[str]


def merge_resource_delete_param(
    old: ResourceDeleteParam, new: ResourceDeleteParam
) -> ResourceDeleteParam:
    return ResourceDeleteParam(files=list(old.files) + list(new.files))
