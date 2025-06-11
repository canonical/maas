#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from asyncio import gather
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
import shutil
from typing import Coroutine, Sequence

from aiohttp.client_exceptions import ClientError
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio import activity, workflow
from temporalio.common import RetryPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import ApplicationError
from temporalio.workflow import ActivityCancellationType, random

from maasserver.utils.bootresource import (
    get_bootresource_store_path,
    LocalBootResourceFile,
    LocalStoreInvalidHash,
    LocalStoreWriteBeyondEOF,
)
from maasserver.utils.converters import human_readable_bytes
from maasservicelayer.db import Database
from maasservicelayer.models.configurations import MAASUrlConfig
from maasservicelayer.services import CacheForServices
from maastemporalworker.worker import REGION_TASK_QUEUE
from maastemporalworker.workflow.activity import ActivityBase
from maastemporalworker.workflow.api_client import MAASAPIClient
from maastemporalworker.workflow.utils import (
    activity_defn_with_context,
    workflow_run_with_context,
)
from provisioningserver.utils.url import compose_URL

REPORT_INTERVAL = timedelta(seconds=10)
HEARTBEAT_TIMEOUT = timedelta(seconds=10)
DISK_TIMEOUT = timedelta(minutes=15)
DOWNLOAD_TIMEOUT = timedelta(hours=2)
MAX_SOURCES = 5

DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME = "download-bootresource"
CHECK_BOOTRESOURCES_STORAGE_WORKFLOW_NAME = "check-bootresources-storage"
SYNC_BOOTRESOURCES_WORKFLOW_NAME = "sync-bootresources"
DELETE_BOOTRESOURCE_WORKFLOW_NAME = "delete-bootresource"

CHECK_DISK_SPACE_ACTIVITY_NAME = "check-disk-space"
GET_BOOTRESOURCEFILE_SYNC_STATUS_ACTIVITY_NAME = (
    "get-bootresourcefile-sync-status"
)
GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME = "get-bootresourcefile-endpoints"
DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME = "download-bootresourcefile"
DELETE_BOOTRESOURCEFILE_ACTIVITY_NAME = "delete-bootresourcefile"


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


class BootResourceImportCancelled(Exception):
    """Operation was cancelled"""


class BootResourcesActivity(ActivityBase):
    def __init__(
        self,
        db: Database,
        services_cache: CacheForServices,
        connection: AsyncConnection | None = None,
    ):
        super().__init__(db, services_cache, connection)

    async def init(self, region_id: str):
        self.region_id = region_id
        async with self.start_transaction() as services:
            maas_url = await services.configurations.get(MAASUrlConfig.name)
            token = await services.users.get_MAAS_user_apikey()
            user_agent = await services.configurations.get_maas_user_agent()
            self.apiclient = MAASAPIClient(
                url=maas_url, token=token, user_agent=user_agent
            )

    async def report_progress(self, rfiles: list[int], size: int):
        """Report progress back to MAAS

        Args:
            rfiles (list[int]): BootResourceFile ids
            size (int): current size, in bytes

        Returns:
           requests.Response: Response object
        """
        url = f"{self.apiclient.url}/api/2.0/images-sync-progress/"
        return await self.apiclient.request_async(
            "POST",
            url,
            data={
                "system_id": self.region_id,
                "ids": rfiles,
                "size": size,
            },
        )

    @activity_defn_with_context(name=CHECK_DISK_SPACE_ACTIVITY_NAME)
    async def check_disk_space(self, param: SpaceRequirementParam) -> bool:
        target_dir = get_bootresource_store_path()
        _, _, free = shutil.disk_usage(target_dir)
        if param.total_resources_size:
            free += sum(file.stat().st_size for file in target_dir.rglob("*"))
            required = param.total_resources_size
        else:
            required = param.min_free_space
        if free > required:
            return True
        else:
            activity.logger.error(
                f"Not enough disk space at controller '{self.region_id}', needs "
                f"{human_readable_bytes(required)} to store all resources."
            )
            return False

    @activity_defn_with_context(
        name=GET_BOOTRESOURCEFILE_SYNC_STATUS_ACTIVITY_NAME
    )
    async def get_bootresourcefile_sync_status(
        self, with_sources: bool = True
    ) -> dict:
        url = f"{self.apiclient.url}/api/2.0/images-sync-progress/"
        return await self.apiclient.request_async(
            "GET", url, params={"sources": str(with_sources)}
        )

    @activity_defn_with_context(
        name=GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME
    )
    async def get_bootresourcefile_endpoints(self) -> dict[str, list]:
        url = f"{self.apiclient.url}/api/2.0/regioncontrollers/"
        regions = await self.apiclient.request_async("GET", url)
        regions_endpoints = {}
        for region in regions:
            # https://bugs.launchpad.net/maas/+bug/2058037
            if region["ip_addresses"]:
                regions_endpoints[region["system_id"]] = [
                    compose_URL("http://:5240/MAAS/boot-resources/", src)
                    for src in region["ip_addresses"]
                ]
            else:
                raise ApplicationError(
                    f"Could not retrieve the IP addresses of the region controller '{region['system_id']}' from the API. This "
                    f"activity will be retried until we have the IP for all the region controllers.",
                    non_retryable=False,
                )
        return regions_endpoints

    @activity_defn_with_context(name=DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME)
    async def download_bootresourcefile(
        self, param: ResourceDownloadParam
    ) -> bool:
        """downloads boot resource file

        Returns:
            bool: True if the file was successfully downloaded
        """

        lfile = LocalBootResourceFile(
            param.sha256, param.filename_on_disk, param.total_size, param.size
        )

        url = param.source_list[
            activity.info().attempt % len(param.source_list)
        ]
        activity.logger.debug(f"Downloading from {url}")

        try:
            while not lfile.acquire_lock(try_lock=True):
                activity.heartbeat()
                await asyncio.sleep(5)

            if await lfile.avalid():
                activity.logger.info("file already downloaded, skipping")
                lfile.commit()
                for target in param.extract_paths:
                    lfile.extract_file(target)
                    activity.heartbeat()
                await self.report_progress(param.rfile_ids, lfile.size)
                return True

            async with (
                self.apiclient.session.get(
                    url,
                    verify_ssl=False,
                    chunked=True,
                    proxy=param.http_proxy,
                ) as response,
                lfile.astore(autocommit=False) as store,
            ):
                response.raise_for_status()
                last_update = datetime.now(timezone.utc)
                async for data, _ in response.content.iter_chunks():
                    activity.heartbeat()
                    dt_now = datetime.now(timezone.utc)
                    if dt_now > (last_update + REPORT_INTERVAL):
                        await self.report_progress(param.rfile_ids, lfile.size)
                        last_update = dt_now
                    store.write(data)

            activity.logger.debug("Download done, doing checksum")
            activity.heartbeat()
            if await lfile.avalid():
                lfile.commit()
                activity.logger.debug(f"file commited {lfile.size}")

                for target in param.extract_paths:
                    lfile.extract_file(target)
                    activity.heartbeat()

                await self.report_progress(param.rfile_ids, lfile.size)
                return True
            else:
                await self.report_progress(param.rfile_ids, 0)
                lfile.unlink()
                raise ApplicationError("Invalid checksum")
        except IOError as ex:
            # if we run out of disk space, stop this download.
            # let the user fix the issue and restart it manually later
            if ex.errno == 28:
                lfile.unlink()
                await self.report_progress(param.rfile_ids, 0)
                activity.logger.error(ex.strerror)
                return False

            raise ApplicationError(
                ex.strerror, type=ex.__class__.__name__
            ) from None
        except (
            ClientError,
            LocalStoreInvalidHash,
            LocalStoreWriteBeyondEOF,
        ) as ex:
            raise ApplicationError(
                str(ex), type=ex.__class__.__name__
            ) from None
        finally:
            lfile.release_lock()

    @activity_defn_with_context(name=DELETE_BOOTRESOURCEFILE_ACTIVITY_NAME)
    async def delete_bootresourcefile(
        self, param: ResourceDeleteParam
    ) -> bool:
        """Delete files from disk"""
        for file in param.files:
            activity.logger.debug(f"attempt to delete {file}")
            lfile = LocalBootResourceFile(
                file.sha256, file.filename_on_disk, 0
            )
            try:
                while not lfile.acquire_lock(try_lock=True):
                    activity.heartbeat()
                    await asyncio.sleep(5)
                lfile.unlink()
            finally:
                lfile.release_lock()
            activity.logger.info(f"file {file} deleted")
        return True


@workflow.defn(name=DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME, sandboxed=False)
class DownloadBootResourceWorkflow:
    """Downloads a BootResourceFile to this controller"""

    @workflow_run_with_context
    async def run(self, input: ResourceDownloadParam) -> None:
        return await workflow.execute_activity(
            DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME,
            input,
            start_to_close_timeout=DOWNLOAD_TIMEOUT,
            heartbeat_timeout=HEARTBEAT_TIMEOUT,
            cancellation_type=ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
            retry_policy=RetryPolicy(
                maximum_attempts=0,  # No maximum attempts
                maximum_interval=timedelta(seconds=60),
            ),
        )


@workflow.defn(name=CHECK_BOOTRESOURCES_STORAGE_WORKFLOW_NAME, sandboxed=False)
class CheckBootResourcesStorageWorkflow:
    """Check the BootResource Storage on this controller"""

    @workflow_run_with_context
    async def run(self, input: SpaceRequirementParam) -> None:
        return await workflow.execute_activity(
            CHECK_DISK_SPACE_ACTIVITY_NAME,
            input,
            start_to_close_timeout=DISK_TIMEOUT,
            heartbeat_timeout=HEARTBEAT_TIMEOUT,
            cancellation_type=ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
        )


@workflow.defn(name=SYNC_BOOTRESOURCES_WORKFLOW_NAME, sandboxed=False)
class SyncBootResourcesWorkflow:
    """Execute Boot Resource synchronization from external sources"""

    @workflow_run_with_context
    async def run(self, input: SyncRequestParam) -> None:
        def _schedule_disk_check(
            res: SpaceRequirementParam,
            region: str,
        ):
            return workflow.execute_child_workflow(
                CHECK_BOOTRESOURCES_STORAGE_WORKFLOW_NAME,
                res,
                id=f"check-bootresources-storage:{region}",
                execution_timeout=DISK_TIMEOUT,
                run_timeout=DISK_TIMEOUT,
                id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
                task_queue=f"region:{region}",
            )

        def _schedule_download(
            res: ResourceDownloadParam,
            region: str | None = None,
        ):
            return workflow.execute_child_workflow(
                DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME,
                res,
                id=f"download-bootresource:{region or 'upstream'}:{res.sha256[:12]}",
                execution_timeout=DOWNLOAD_TIMEOUT,
                run_timeout=DOWNLOAD_TIMEOUT,
                id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
                task_queue=f"region:{region}" if region else REGION_TASK_QUEUE,
            )

        # get regions and endpoints
        endpoints: dict[str, list] = await workflow.execute_activity(
            GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME,
            start_to_close_timeout=timedelta(seconds=30),
        )
        regions: frozenset[str] = frozenset(endpoints.keys())

        # check disk space
        check_space_jobs = [
            _schedule_disk_check(input.requirement, region)
            for region in regions
        ]
        has_space: list[bool] = await gather(*check_space_jobs)
        if not all(has_space):
            raise ApplicationError(
                "some region controllers don't have enough disk space",
                non_retryable=True,
            )

        # download resources that must be fetched from upstream
        upstream_jobs = [
            _schedule_download(replace(res, http_proxy=input.http_proxy))
            for res in input.resources
            if res.source_list
        ]
        if upstream_jobs:
            workflow.logger.info(
                f"Syncing {len(upstream_jobs)} resources from upstream"
            )
            downloaded: list[bool] = await gather(*upstream_jobs)
            if not all(downloaded):
                raise ApplicationError(
                    "some files could not be downloaded, aborting",
                    non_retryable=True,
                )

        if len(regions) < 2:
            workflow.logger.info("Sync complete")
            return

        # distribute files inside cluster
        sync_status: dict[str, dict] = await workflow.execute_activity(
            GET_BOOTRESOURCEFILE_SYNC_STATUS_ACTIVITY_NAME,
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Use a random generator from the temporal sdk in order to keep the workflow deterministic.
        random_generator = random()

        sync_jobs: list[Coroutine] = []
        for res in input.resources:
            missing: set[str] = set()
            for id in res.rfile_ids:
                missing.update(regions - set(sync_status[str(id)]["sources"]))
            if missing == regions:
                workflow.logger.error(
                    f"File {res.sha256} has no complete copy available, skipping"
                )
                continue
            sources = regions - missing
            eps = [
                f"{ep}{res.filename_on_disk}/"
                for reg in sources
                for ep in endpoints[reg]
            ]
            # In order to balance the workload on the regions we randomize the order of the source_list.
            new_res = replace(
                res,
                source_list=random_generator.sample(
                    eps, min(len(eps), MAX_SOURCES)
                ),
            )
            for region in missing:
                sync_jobs.append(_schedule_download(new_res, region))
        if sync_jobs:
            synced: list[bool] = await gather(*sync_jobs)
            if not all(synced):
                raise ApplicationError(
                    "some files could not be synced, aborting",
                    non_retryable=True,
                )

        workflow.logger.info("Sync complete")


@workflow.defn(name=DELETE_BOOTRESOURCE_WORKFLOW_NAME, sandboxed=False)
class DeleteBootResourceWorkflow:
    """Delete a BootResourceFile from this cluster"""

    @workflow_run_with_context
    async def run(self, input: ResourceDeleteParam) -> None:
        # remove file from cluster
        endpoints = await workflow.execute_activity(
            GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME,
            start_to_close_timeout=timedelta(seconds=30),
        )
        regions = frozenset(endpoints.keys())
        for r in regions:
            await workflow.execute_activity(
                DELETE_BOOTRESOURCEFILE_ACTIVITY_NAME,
                input,
                task_queue=f"region:{r}",
                start_to_close_timeout=DISK_TIMEOUT,
                schedule_to_close_timeout=DISK_TIMEOUT,
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
