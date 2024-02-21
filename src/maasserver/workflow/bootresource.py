import asyncio
from asyncio import gather
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
import random
from typing import Coroutine, Sequence

from temporalio import activity, workflow
from temporalio.common import RetryPolicy, WorkflowIDReusePolicy
from temporalio.workflow import ActivityCancellationType

from maasserver.utils.bootresource import (
    get_bootresource_store_path,
    LocalBootResourceFile,
    LocalStoreInvalidHash,
    LocalStoreWriteBeyondEOF,
)
from maasserver.workflow.api_client import MAASAPIClient
from maasserver.workflow.worker.worker import REGION_TASK_QUEUE
from provisioningserver.utils.url import compose_URL

REPORT_INTERVAL = timedelta(seconds=10)
HEARTBEAT_TIMEOUT = timedelta(seconds=10)
DISK_TIMEOUT = timedelta(minutes=15)
DOWNLOAD_TIMEOUT = timedelta(hours=2)
MAX_SOURCES = 5
CHUNK_SIZE = 5 * (2**20)  # 5 MB


@dataclass
class ResourceDownloadParam:
    rfile_ids: list[int]
    source_list: list[str]
    sha256: str
    total_size: int
    size: int = 0
    force: bool = False
    extract_paths: list[str] = field(default_factory=list)


@dataclass
class SyncRequestParam:
    resources: Sequence[ResourceDownloadParam]


@dataclass
class ResourceDeleteParam:
    files: Sequence[str]


@dataclass
class ResourceCleanupParam:
    expected_files: Sequence[str]


class BootResourceImportCancelled(Exception):
    """Operation was cancelled"""


class BootResourcesActivity(MAASAPIClient):
    def __init__(self, url: str, token: str, user_agent: str, region_id: str):
        super().__init__(url, token, user_agent=user_agent)
        self.region_id = region_id

    async def report_progress(self, rfiles: list[int], size: int):
        """Report progress back to MAAS

        Args:
            rfiles (list[int]): BootResourceFile ids
            size (int): current size, in bytes

        Returns:
           requests.Response: Response object
        """
        url = f"{self.url}/api/2.0/images-sync-progress/"
        return await self.request_async(
            "POST",
            url,
            data={
                "system_id": self.region_id,
                "ids": rfiles,
                "size": size,
            },
        )

    @activity.defn(name="get-bootresourcefile-sync-status")
    async def get_bootresourcefile_sync_status(
        self, with_sources: bool = True
    ) -> dict:
        url = f"{self.url}/api/2.0/images-sync-progress/"
        return await self.request_async(
            "GET", url, params={"sources": str(with_sources)}
        )

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
                for target in param.extract_paths:
                    lfile.extract_file(target)
                    activity.heartbeat()
                await self.report_progress(param.rfile_ids, lfile.size)
                return True

            async with self.session.get(
                url, verify_ssl=False, chunked=True
            ) as response, lfile.astore(autocommit=False) as store:
                response.raise_for_status()
                last_update = datetime.now()
                async for data in response.content.iter_chunked(CHUNK_SIZE):
                    activity.heartbeat()
                    dt_now = datetime.now()
                    if dt_now > (last_update + REPORT_INTERVAL):
                        await self.report_progress(param.rfile_ids, lfile.size)
                        last_update = dt_now
                    try:
                        store.write(data)
                    except (
                        IOError,
                        LocalStoreInvalidHash,
                        LocalStoreWriteBeyondEOF,
                    ) as ex:
                        activity.logger.warn(f"Download failed {str(ex)}")
                        raise

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
                activity.logger.warn("Download failed, invalid checksum")
                await self.report_progress(param.rfile_ids, 0)
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

    @activity.defn(name="cleanup-bootresources")
    async def cleanup_bootresources(self, param: ResourceCleanupParam) -> None:
        """Remove unknown files from disk"""
        store = get_bootresource_store_path()
        bootloaders_dir = store / "bootloaders"
        bootloaders_dir.mkdir(exist_ok=True)
        expected = {store / f for f in param.expected_files}
        expected |= {bootloaders_dir}

        existing = set(store.iterdir())
        for file in existing - expected:
            activity.logger.info(f"removing unexpected file: {file}")
            activity.heartbeat()
            file.unlink()


@workflow.defn(name="download-bootresource", sandboxed=False)
class DownloadBootResourceWorkflow:
    """Downloads a BootResourceFile to this controller"""

    @workflow.run
    async def run(self, input: ResourceDownloadParam) -> None:
        return await workflow.execute_activity(
            "download-bootresourcefile",
            input,
            start_to_close_timeout=DOWNLOAD_TIMEOUT,
            heartbeat_timeout=HEARTBEAT_TIMEOUT,
            cancellation_type=ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
            retry_policy=RetryPolicy(
                maximum_attempts=max(2, len(input.source_list)),
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
                id=f"bootresource-download:{res.sha256[:12]}",
                execution_timeout=DOWNLOAD_TIMEOUT,
                run_timeout=DOWNLOAD_TIMEOUT,
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
        endpoints: dict[str, list] = await workflow.execute_activity(
            "get-bootresourcefile-endpoints",
            start_to_close_timeout=timedelta(seconds=30),
        )
        regions: frozenset[str] = frozenset(endpoints.keys())

        sync_status: dict[str, dict] = await workflow.execute_activity(
            "get-bootresourcefile-sync-status",
            start_to_close_timeout=timedelta(seconds=30),
        )
        if len(regions) < 2:
            workflow.logger.info("Sync complete")
            return

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
                f"{ep}{res.sha256}/"
                for reg in sources
                for ep in endpoints[reg]
            ]
            new_res = replace(
                res,
                source_list=random.sample(eps, min(len(eps), MAX_SOURCES)),
            )
            for region in missing:
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
                start_to_close_timeout=DISK_TIMEOUT,
                schedule_to_close_timeout=DISK_TIMEOUT,
                retry_policy=RetryPolicy(maximum_attempts=3),
            )


@workflow.defn(name="cleanup-bootresource", sandboxed=False)
class CleanupBootResourceWorkflow:
    """Clean orphan BootResourceFiles from this cluster"""

    @workflow.run
    async def run(self) -> None:
        # remove orphan files from cluster
        sync_status = await workflow.execute_activity(
            "get-bootresourcefile-sync-status",
            False,
            start_to_close_timeout=timedelta(seconds=30),
        )
        expected_files = list(set(f["sha256"] for _, f in sync_status))

        endpoints = await workflow.execute_activity(
            "get-bootresourcefile-endpoints",
            start_to_close_timeout=timedelta(seconds=30),
        )
        regions = frozenset(endpoints.keys())
        for r in regions:
            await workflow.execute_activity(
                "cleanup-bootresourcefile",
                ResourceCleanupParam(expected_files),
                task_queue=f"{r}:region",
                start_to_close_timeout=DISK_TIMEOUT,
                schedule_to_close_timeout=DISK_TIMEOUT,
            )
