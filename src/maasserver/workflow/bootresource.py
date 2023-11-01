import asyncio
from asyncio import gather
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from io import BytesIO
from typing import Coroutine

from aiohttp import ClientSession
from temporalio import activity, workflow
from temporalio.common import RetryPolicy, WorkflowIDReusePolicy
from temporalio.workflow import ActivityCancellationType

from maasserver.utils.bootresource import (
    LocalBootResourceFile,
    LocalStoreInvalidHash,
)
from maasserver.workflow.api_client import MAASAPIClient
from maasserver.workflow.worker.worker import REGION_TASK_QUEUE
from provisioningserver.utils.url import compose_URL

READ_BUF = 4 * (1 << 20)  # 4 MB
HEARTBEAT_TIMEOUT = 30
DISK_TIMEOUT = 15 * 60  # 15 minutes
LOCK_TIMEOUT = 15 * 60  # 15 minutes
DOWNLOAD_TIMEOUT = 2 * 60 * 60  # 2 hours


@dataclass
class ResourceDownloadParam:
    rfile_id: int
    source_list: list[str]
    sha256: str
    total_size: int
    size: int = 0
    force: bool = False


@dataclass
class SyncRequestParam:
    resources: list[ResourceDownloadParam]


@dataclass
class ResourceDeleteParam:
    files: list[str]


class BootResourceImportCancelled(Exception):
    """Operation was cancelled"""


class BootResourcesActivity(MAASAPIClient):
    def __init__(self, url: str, token: str, region_id: str):
        super().__init__(url, token)
        self.region_id = region_id

    async def report_progress(self, rfile: int, size: int):
        """Report progress back to MAAS

        Args:
            rfile (int): BootResourceFile id
            size (int): current size, in bytes

        Returns:
           requests.Response: Response object
        """
        url = f"{self.url}/api/2.0/images-sync-progress/{rfile}/{self.region_id}/"
        return await self.request_async(
            "PUT",
            url,
            data={
                "size": size,
            },
        )

    @activity.defn(name="get-bootresourcefile-sync-status")
    async def get_bootresourcefile_sync_status(self) -> dict:
        url = f"{self.url}/api/2.0/images-sync-progress/"
        return await self.request_async("GET", url)

    @activity.defn(name="get-bootresourcefile-endpoints")
    async def get_bootresourcefile_endpoints(self) -> dict[str, list]:
        url = f"{self.url}/api/2.0/regioncontrollers/"
        regions = await self.request_async("GET", url)
        return {
            r["system_id"]: [
                compose_URL("http://:5240/MAAS/boot-resources/", src)
                for src in r["ip_addresses"]
            ]
            for r in regions
        }

    @activity.defn(name="download-bootresourcefile")
    async def download_bootresourcefile(
        self, param: ResourceDownloadParam
    ) -> bool:
        """downloads boot resource file

        Returns:
            bool: True if the file was successfully downloaded
        """

        lfile = LocalBootResourceFile(
            param.sha256, param.total_size, param.size
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
                await self.report_progress(param.rfile_id, lfile.size)
                return True

            async with ClientSession() as session, session.get(
                url,
                verify_ssl=False,
                chunked=True,
                read_bufsize=READ_BUF,
            ) as response:
                response.raise_for_status()
                last_update = datetime.now()
                chunk_cnt = 0
                async for data, _ in response.content.iter_chunks():
                    activity.heartbeat()
                    chunk_cnt += 1
                    dt_now = datetime.now()
                    if dt_now > (last_update + timedelta(seconds=10)) or (
                        chunk_cnt % 10 == 0
                    ):
                        await self.report_progress(param.rfile_id, lfile.size)
                        last_update = dt_now
                    try:
                        await lfile.astore(BytesIO(data), autocommit=False)
                    except (IOError, LocalStoreInvalidHash) as ex:
                        activity.logger.warn(f"Download failed {str(ex)}")
                        raise

            activity.logger.debug("Download done, doing checksum")
            activity.heartbeat()
            if await lfile.avalid():
                lfile.commit()
                activity.logger.debug(f"file commited {lfile.size}")
                await self.report_progress(param.rfile_id, lfile.size)
                return True
            else:
                activity.logger.warn("Download failed, invalid checksum")
                await self.report_progress(param.rfile_id, 0)
                lfile.unlink()
                return False
        finally:
            lfile.release_lock()

    @activity.defn(name="delete-bootresourcefile")
    async def delete_bootresourcefile(
        self, param: ResourceDeleteParam
    ) -> bool:
        """Delete files from disk"""
        for file in param.files:
            activity.logger.debug(f"attempt to delete {file}")
            lfile = LocalBootResourceFile(file, 0)
            try:
                while not lfile.acquire_lock(try_lock=True):
                    activity.heartbeat()
                    await asyncio.sleep(5)
                lfile.unlink()
            finally:
                lfile.release_lock()
            activity.logger.info(f"file {file} deleted")
        return True


@workflow.defn(name="download-bootresource", sandboxed=False)
class DownloadBootResourceWorkflow:
    """Downloads a BootResourceFile to this controller"""

    @workflow.run
    async def run(self, input: ResourceDownloadParam) -> None:
        return await workflow.execute_activity(
            "download-bootresourcefile",
            input,
            activity_id=f"download_{input.rfile_id}",
            start_to_close_timeout=timedelta(seconds=DOWNLOAD_TIMEOUT),
            heartbeat_timeout=timedelta(seconds=HEARTBEAT_TIMEOUT),
            cancellation_type=ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
            retry_policy=RetryPolicy(
                backoff_coefficient=2.0,
                maximum_attempts=5,
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=60),
            ),
        )


@workflow.defn(name="sync-bootresources", sandboxed=False)
class SyncBootResourcesWorkflow:
    """Execute Boot Resource synchronization from external sources"""

    @workflow.run
    async def run(self, input: SyncRequestParam) -> None:
        def _schedule(res: ResourceDownloadParam, region: str | None = None):
            return workflow.execute_child_workflow(
                "download-bootresource",
                res,
                id=f"bootresource_download_{res.rfile_id}@{region or REGION_TASK_QUEUE}",
                execution_timeout=timedelta(seconds=DOWNLOAD_TIMEOUT),
                run_timeout=timedelta(seconds=DOWNLOAD_TIMEOUT),
                task_timeout=timedelta(seconds=LOCK_TIMEOUT),
                id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
                task_queue=f"{region}:region" if region else REGION_TASK_QUEUE,
            )

        # fetch resources from upstream
        upstream_jobs = [
            _schedule(res) for res in input.resources if res.source_list
        ]
        if upstream_jobs:
            workflow.logger.info(
                f"Syncing {len(upstream_jobs)} resources from upstream"
            )
            await gather(*upstream_jobs)

        # distribute files inside cluster
        endpoints = await workflow.execute_activity(
            "get-bootresourcefile-endpoints",
            start_to_close_timeout=timedelta(seconds=30),
        )
        regions = frozenset(endpoints.keys())

        sync_status = await workflow.execute_activity(
            "get-bootresourcefile-sync-status",
            start_to_close_timeout=timedelta(seconds=30),
        )
        if len(regions) < 2:
            workflow.logger.info("Sync complete")
            return

        sync_jobs: list[Coroutine] = []
        for res in input.resources:
            if res.rfile_id not in sync_status:
                workflow.logger.warn(
                    f"File {res.rfile_id} has no complete copy available, skipping"
                )
                continue
            sources = set(sync_status[res.rfile_id]["sources"])
            missing = regions - sources
            for region in missing:
                new_res = replace(
                    res,
                    source_list=[
                        f"{ep}{res.sha256}/"
                        for reg in sources
                        for ep in endpoints[reg]
                    ],
                )
                sync_jobs.append(_schedule(new_res, region))
        if sync_jobs:
            await gather(*sync_jobs)
        workflow.logger.info("Sync complete")


@workflow.defn(name="delete-bootresource", sandboxed=False)
class DeleteBootResourceWorkflow:
    """Delete a BootResourceFile from this cluster"""

    @workflow.run
    async def run(self, input: ResourceDeleteParam) -> None:
        # remove file from cluster
        endpoints = await workflow.execute_activity(
            "get-bootresourcefile-endpoints",
            start_to_close_timeout=timedelta(seconds=30),
        )
        regions = frozenset(endpoints.keys())
        for r in regions:
            await workflow.execute_activity(
                "delete-bootresourcefile",
                input,
                task_queue=f"{r}:region",
                start_to_close_timeout=timedelta(seconds=DISK_TIMEOUT),
                schedule_to_close_timeout=timedelta(seconds=DISK_TIMEOUT),
            )
