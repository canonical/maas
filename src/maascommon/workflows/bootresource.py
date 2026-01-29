# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Sequence

from maascommon.enums.notifications import NotificationCategoryEnum

REPORT_INTERVAL = timedelta(seconds=10)
HEARTBEAT_TIMEOUT = timedelta(seconds=10)
DISK_TIMEOUT = timedelta(minutes=15)
DOWNLOAD_TIMEOUT = timedelta(hours=2)
FETCH_IMAGE_METADATA_TIMEOUT = timedelta(minutes=10)
CLEANUP_TIMEOUT = timedelta(minutes=1)
MAX_SOURCES = 5

DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME = "download-bootresource"
SYNC_BOOTRESOURCES_WORKFLOW_NAME = "sync-bootresources"
SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME = "sync-remote-bootresources"
SYNC_ALL_LOCAL_BOOTRESOURCES_WORKFLOW_NAME = "sync-all-local-bootresources"
DELETE_BOOTRESOURCE_WORKFLOW_NAME = "delete-bootresource"
SYNC_SELECTION_WORKFLOW_NAME = "sync-selection"
MASTER_IMAGE_SYNC_WORKFLOW_NAME = "master-image-sync"
FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME = (
    "fetch-manifest-and-update-cache"
)


@dataclass
class ResourceDownloadParam:
    rfile_ids: list[int]
    source_list: list[str]
    sha256: str
    filename_on_disk: str
    total_size: int
    extract_paths: list[str] = field(default_factory=list)
    http_proxy: str | None = None


@dataclass
class SyncRequestParam:
    resource: ResourceDownloadParam


@dataclass
class ResourceIdentifier:
    sha256: str
    filename_on_disk: str


@dataclass
class ResourceDeleteParam:
    files: Sequence[ResourceIdentifier]


@dataclass
class GetFilesToDownloadForSelectionParam:
    selection_id: int


@dataclass
class GetFilesToDownloadReturnValue:
    resources: list[ResourceDownloadParam]


@dataclass
class GetLocalBootResourcesParamReturnValue:
    resources: list[ResourceDownloadParam]


@dataclass
class SyncSelectionParam:
    selection_id: int


@dataclass
class DeletePendingFilesParam:
    resources: list[ResourceDownloadParam]


@dataclass
class CleanupBootResourceSetsParam:
    selection_id: int


@dataclass
class RegisterNotificationParam:
    ident: str
    category: NotificationCategoryEnum
    err_msg: str
    dismissable: bool


@dataclass
class DeleteNotificationParam:
    ident: str


def merge_resource_delete_param(
    old: ResourceDeleteParam, new: ResourceDeleteParam
) -> ResourceDeleteParam:
    return ResourceDeleteParam(files=list(old.files) + list(new.files))


def short_sha(sha256: str) -> str:
    return sha256[:12]
