#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import shutil
from typing import Any, Coroutine

import httpx
import structlog
from temporalio import activity, workflow
from temporalio.client import WorkflowFailureError
from temporalio.common import RetryPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import (
    ActivityError,
    ApplicationError,
    CancelledError,
    WorkflowAlreadyStartedError,
)
from temporalio.service import RPCError
from temporalio.workflow import (
    ActivityCancellationType,
    ParentClosePolicy,
    random,
)

from maascommon.enums.events import EventTypeEnum
from maascommon.enums.notifications import (
    NotificationCategoryEnum,
    NotificationComponent,
)
from maascommon.workflows.bootresource import (
    CancelObsoleteDownloadWorkflowsParam,
    CHECK_BOOTRESOURCES_STORAGE_WORKFLOW_NAME,
    CLEANUP_TIMEOUT,
    CleanupOldBootResourceParam,
    DELETE_BOOTRESOURCE_WORKFLOW_NAME,
    DISK_TIMEOUT,
    DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME,
    DOWNLOAD_TIMEOUT,
    FETCH_IMAGE_METADATA_TIMEOUT,
    FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME,
    GetFilesToDownloadReturnValue,
    HEARTBEAT_TIMEOUT,
    LocalSyncRequestParam,
    MASTER_IMAGE_SYNC_WORKFLOW_NAME,
    MAX_SOURCES,
    REPORT_INTERVAL,
    ResourceDeleteParam,
    ResourceDownloadParam,
    SpaceRequirementParam,
    SYNC_BOOTRESOURCES_WORKFLOW_NAME,
    SYNC_LOCAL_BOOTRESOURCES_WORKFLOW_NAME,
    SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME,
    SyncRequestParam,
)
from maasserver.utils.converters import human_readable_bytes
from maasservicelayer.builders.notifications import NotificationBuilder
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootsources import (
    BootSourcesClauseFactory,
)
from maasservicelayer.db.repositories.notifications import (
    NotificationsClauseFactory,
)
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.configurations import (
    HttpProxyConfig,
    MAASUrlConfig,
)
from maasservicelayer.simplestreams.models import (
    SimpleStreamsBootloaderProductList,
    SimpleStreamsMultiFileProductList,
    SimpleStreamsSingleFileProductList,
)
from maasservicelayer.utils.image_local_files import (
    get_bootresource_store_path,
    LocalBootResourceFile,
    LocalStoreInvalidHash,
    LocalStoreWriteBeyondEOF,
)
from maastemporalworker.worker import REGION_TASK_QUEUE
from maastemporalworker.workflow.activity import ActivityBase
from maastemporalworker.workflow.api_client import MAASAPIClient
from maastemporalworker.workflow.utils import (
    activity_defn_with_context,
    workflow_run_with_context,
)
from provisioningserver.utils.url import compose_URL

CHECK_DISK_SPACE_ACTIVITY_NAME = "check-disk-space"
GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME = "get-bootresourcefile-endpoints"
DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME = "download-bootresourcefile"
DELETE_BOOTRESOURCEFILE_ACTIVITY_NAME = "delete-bootresourcefile"
FETCH_MANIFEST_AND_UPDATE_CACHE_ACTIVITY_NAME = (
    "fetch-manifest-and-update-cache"
)
GET_FILES_TO_DOWNLOAD_ACTIVITY_NAME = "get-files-to-download"
CLEANUP_OLD_BOOT_RESOURCES_ACTIVITY_NAME = "cleanup-old-boot-resources"
CANCEL_OBSOLETE_DOWNLOAD_WORKFLOWS_ACTIVITY_NAME = (
    "cancel-obsolete-download-workflows"
)
GET_SYNCED_REGIONS_ACTIVITY_NAME = "get-synced-regions"
SET_GLOBAL_DEFAULT_RELEASES_ACTIVITY_NAME = "set-global-default-releases"
REGISTER_ERROR_NOTIFICATION_ACTIVITY_NAME = "register-error-notification"
DISCARD_ERROR_NOTIFICATION_ACTIVITY_NAME = "discard-error-notification"


# can't be defined in maascommon due to service layer imports
@dataclass
class BootSourceProductsMapping:
    boot_source_id: int
    # Ugly, but temporal needs concrete classes to convert json to python
    products_list: list[
        SimpleStreamsSingleFileProductList
        | SimpleStreamsMultiFileProductList
        | SimpleStreamsBootloaderProductList
    ]


logger = structlog.get_logger()


class BootResourcesActivity(ActivityBase):
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
            logger.error(
                f"Not enough disk space at controller '{self.region_id}', needs "
                f"{human_readable_bytes(required)} to store all resources."
            )
            return False

    @activity_defn_with_context(name=GET_SYNCED_REGIONS_ACTIVITY_NAME)
    async def get_synced_regions_for_file(self, file_id: int) -> list[str]:
        async with self.start_transaction() as services:
            return await services.boot_resource_file_sync.get_synced_regions_for_file(
                file_id
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
        logger.debug(f"Downloading from {url}")

        try:
            while not lfile.acquire_lock(try_lock=True):
                activity.heartbeat("Waiting for file lock")
                await asyncio.sleep(5)

            if await lfile.avalid():
                logger.info("file already downloaded, skipping")
                lfile.commit()
                for target in param.extract_paths:
                    lfile.extract_file(target)
                    activity.heartbeat(f"Extracted file in {target}")
                await self.report_progress(param.rfile_ids, lfile.size)
                return True

            async with (
                self.apiclient.make_client(param.http_proxy).stream(
                    "GET", url
                ) as response,
                lfile.astore(autocommit=False) as store,
            ):
                response.raise_for_status()
                last_update = datetime.now(timezone.utc)

                # Let's assume the network is fast, and we can get 5MB chunks within 10 seconds (the heartbeat timeout).
                # If we fail the activity, then we shrink the chunk size. The more we fail, the more we shrink so to deal with
                # slow networks.
                BASE_CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB
                MIN_CHUNK_SIZE = 256 * 1024  # 256 KB

                attempt = activity.info().attempt
                chunk_size = BASE_CHUNK_SIZE // (
                    2 ** (attempt - 1)
                )  # halves each attempt
                chunk_size = max(chunk_size, MIN_CHUNK_SIZE)

                async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                    activity.heartbeat("Downloaded chunk")
                    dt_now = datetime.now(timezone.utc)
                    if dt_now > (last_update + REPORT_INTERVAL):
                        await self.report_progress(param.rfile_ids, lfile.size)
                        last_update = dt_now
                    store.write(chunk)

            logger.debug("Download done, doing checksum")
            activity.heartbeat("Finished download, doing checksum")
            if await lfile.avalid():
                lfile.commit()
                logger.debug(f"file commited {lfile.size}")

                for target in param.extract_paths:
                    lfile.extract_file(target)
                    activity.heartbeat(f"Extracted file in {target}")

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
                logger.error(
                    ex.strerror
                    if ex.strerror is not None
                    else "No space left on device"
                )
                return False

            raise ApplicationError(
                ex.strerror, type=ex.__class__.__name__
            ) from None
        except (
            httpx.HTTPError,
            LocalStoreInvalidHash,
            LocalStoreWriteBeyondEOF,
        ) as ex:
            raise ApplicationError(
                str(ex), type=ex.__class__.__name__
            ) from None
        except (asyncio.CancelledError, CancelledError) as ex:
            lfile.unlink()
            await self.report_progress(param.rfile_ids, 0)
            # re-raise it as it is since temporal will propagate this to the parent wf
            raise ex
        finally:
            lfile.release_lock()

    @activity_defn_with_context(name=DELETE_BOOTRESOURCEFILE_ACTIVITY_NAME)
    async def delete_bootresourcefile(
        self, param: ResourceDeleteParam
    ) -> bool:
        """Delete files from disk"""
        for file in param.files:
            logger.debug(f"attempt to delete {file}")
            lfile = LocalBootResourceFile(
                file.sha256, file.filename_on_disk, 0
            )
            try:
                while not lfile.acquire_lock(try_lock=True):
                    activity.heartbeat("Waiting for file lock")
                    await asyncio.sleep(5)
                lfile.unlink()
            finally:
                lfile.release_lock()
            logger.info(f"file {file} deleted")
        return True

    @activity_defn_with_context(
        name=FETCH_MANIFEST_AND_UPDATE_CACHE_ACTIVITY_NAME
    )
    async def fetch_manifest_and_update_cache(
        self,
    ) -> list[BootSourceProductsMapping]:
        async with self.start_transaction() as services:
            await services.image_sync.ensure_boot_source_definition()
            boot_source_products_mapping = (
                await services.image_sync.fetch_images_metadata()
            )
            activity.heartbeat("Downloaded images descriptions")
            for (
                boot_source,
                products_list,
            ) in boot_source_products_mapping.items():
                await services.image_sync.cache_boot_source_from_simplestreams_products(
                    boot_source.id, products_list
                )

            await services.image_sync.sync_boot_source_selections_from_msm(
                list(boot_source_products_mapping.keys())
            )

            # don't raise an exception, just create the notification
            await services.image_sync.check_commissioning_series_selected()
            return [
                BootSourceProductsMapping(
                    boot_source_id=source.id, products_list=products_list
                )
                for source, products_list in boot_source_products_mapping.items()
            ]

    @activity_defn_with_context(name=GET_FILES_TO_DOWNLOAD_ACTIVITY_NAME)
    async def get_files_to_download(
        self, param: list[BootSourceProductsMapping]
    ) -> GetFilesToDownloadReturnValue:
        resources_to_download: dict[str, ResourceDownloadParam] = {}
        boot_resource_ids_to_keep: set[int] = set()
        async with self.start_transaction() as services:
            await services.events.record_event(
                event_type=EventTypeEnum.REGION_IMPORT_INFO,
                event_description=f"Started importing boot images from {len(param)} source(s).",
            )
            boot_sources = await services.boot_sources.get_many(
                query=QuerySpec(
                    where=BootSourcesClauseFactory.with_ids(
                        {m.boot_source_id for m in param}
                    )
                )
            )
            boot_source_products_mapping = {}
            for mapping in param:
                boot_source = next(
                    filter(
                        lambda x: x.id == mapping.boot_source_id, boot_sources
                    )
                )
                boot_source_products_mapping[boot_source] = (
                    mapping.products_list
                )

            boot_source_products_mapping = (
                await services.image_sync.filter_products(
                    boot_source_products_mapping
                )
            )
            for (
                boot_source,
                products_list,
            ) in boot_source_products_mapping.items():
                (
                    to_download,
                    boot_resource_ids,
                ) = await services.image_sync.get_files_to_download_from_product_list(
                    boot_source, products_list
                )
                resources_to_download.update(to_download)
                boot_resource_ids_to_keep |= boot_resource_ids

            # Do not include the http_proxy in every boot resource here so to keep the return value of the activity small.
            http_proxy = await services.configurations.get(
                HttpProxyConfig.name
            )

        return GetFilesToDownloadReturnValue(
            resources=list(resources_to_download.values()),
            boot_resource_ids=boot_resource_ids_to_keep,
            http_proxy=http_proxy,
        )

    @activity_defn_with_context(name=SET_GLOBAL_DEFAULT_RELEASES_ACTIVITY_NAME)
    async def set_global_default_releases(self) -> None:
        async with self.start_transaction() as services:
            await services.image_sync.set_global_default_releases()

    @activity_defn_with_context(name=CLEANUP_OLD_BOOT_RESOURCES_ACTIVITY_NAME)
    async def cleanup_old_boot_resources(
        self, param: CleanupOldBootResourceParam
    ) -> None:
        async with self.start_transaction() as services:
            if not await services.image_sync.delete_old_boot_resources(
                param.boot_resource_ids_to_keep
            ):
                raise ApplicationError(
                    message="Finalization of image synchronization aborted or all the synced images would be deleted.",
                    non_retryable=True,
                )
            await services.image_sync.delete_old_boot_resource_sets()
            # Deletion of files is handled by the temporal service, so we have to manually call post_commit
            await services.temporal.post_commit()

    @activity_defn_with_context(
        name=CANCEL_OBSOLETE_DOWNLOAD_WORKFLOWS_ACTIVITY_NAME
    )
    async def cancel_obsolete_download_workflows(
        self, param: CancelObsoleteDownloadWorkflowsParam
    ) -> None:
        shas_to_download = {sha[:12] for sha in param.sha_to_keep}
        async for wf in self.temporal_client.list_workflows(
            query=f"WorkflowType='{SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME}' AND ExecutionStatus='Running'"
        ):
            # Workflow ID is in the form: <wf-name>:<sha>
            sha = wf.id.rsplit(":", maxsplit=1)[1]
            if sha not in shas_to_download:
                handle = self.temporal_client.get_workflow_handle(wf.id)
                await handle.cancel()
                activity.heartbeat("Obsolete workflow cancelled")

    @activity_defn_with_context(name=REGISTER_ERROR_NOTIFICATION_ACTIVITY_NAME)
    async def register_error_notification(self, err_msg: str) -> None:
        async with self.start_transaction() as services:
            await services.notifications.get_or_create(
                query=QuerySpec(
                    where=NotificationsClauseFactory.with_ident(
                        NotificationComponent.REGION_IMAGE_SYNC
                    )
                ),
                builder=NotificationBuilder(
                    ident=NotificationComponent.REGION_IMAGE_SYNC,
                    users=True,
                    admins=True,
                    message=f"Failed to synchronize boot resources: {err_msg}",
                    context={},
                    user_id=None,
                    category=NotificationCategoryEnum.ERROR,
                    dismissable=False,
                ),
            )

    @activity_defn_with_context(name=DISCARD_ERROR_NOTIFICATION_ACTIVITY_NAME)
    async def discard_error_notification(self) -> None:
        async with self.start_transaction() as services:
            try:
                await services.notifications.delete_one(
                    query=QuerySpec(
                        where=NotificationsClauseFactory.with_ident(
                            NotificationComponent.REGION_IMAGE_SYNC
                        )
                    ),
                )
            except NotFoundException:
                pass


@workflow.defn(name=DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME, sandboxed=False)
class DownloadBootResourceWorkflow:
    """Downloads a BootResourceFile to this controller"""

    @workflow_run_with_context
    async def run(self, input: ResourceDownloadParam) -> bool:
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


@workflow.defn(name=SYNC_LOCAL_BOOTRESOURCES_WORKFLOW_NAME, sandboxed=False)
class SyncLocalBootResourcesWorkflow:
    @workflow_run_with_context
    async def run(self, input: LocalSyncRequestParam) -> None:
        # get regions and endpoints
        endpoints = await workflow.execute_activity(
            GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME,
            start_to_close_timeout=timedelta(seconds=30),
        )
        regions: frozenset[str] = frozenset(endpoints.keys())
        # check space
        check_space_jobs: list[Coroutine] = []
        for region in regions:
            check_space_jobs.append(
                workflow.execute_child_workflow(
                    CHECK_BOOTRESOURCES_STORAGE_WORKFLOW_NAME,
                    input.resource,
                    id=f"check-bootresources-storage:{region}",
                    execution_timeout=DISK_TIMEOUT,
                    run_timeout=DISK_TIMEOUT,
                    id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
                    task_queue=f"region:{region}",
                )
            )

        has_space: list[bool] = await asyncio.gather(*check_space_jobs)
        if not all(has_space):
            raise ApplicationError(
                "some region controllers don't have enough disk space",
                non_retryable=True,
            )

        await workflow.execute_child_workflow(
            SYNC_BOOTRESOURCES_WORKFLOW_NAME,
            arg=SyncRequestParam(
                resource=input.resource, region_endpoints=endpoints
            ),
            id=f"sync-bootresources:{input.resource.sha256[:12]}",
        )


@workflow.defn(name=SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME, sandboxed=False)
class SyncRemoteBootResourcesWorkflow:
    """Downloads the resource from upstream and synchronizes it among the regions."""

    @workflow_run_with_context
    async def run(self, input: SyncRequestParam) -> None:
        # download resource from upstream
        downloaded = await workflow.execute_child_workflow(
            DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME,
            arg=input.resource,
            id=f"download-bootresource:upstream:{input.resource.sha256[:12]}",
            execution_timeout=DOWNLOAD_TIMEOUT,
            run_timeout=DOWNLOAD_TIMEOUT,
            task_queue=REGION_TASK_QUEUE,
        )

        if not downloaded:
            raise ApplicationError(
                f"File {input.resource.sha256} could not be downloaded, aborting",
                non_retryable=True,
            )

        await workflow.execute_child_workflow(
            SYNC_BOOTRESOURCES_WORKFLOW_NAME,
            arg=input,
            id=f"sync-bootresources:{input.resource.sha256[:12]}",
        )

        handle = workflow.get_external_workflow_handle_for(
            MasterImageSyncWorkflow.run, "master-image-sync"
        )
        try:
            await handle.signal(
                MasterImageSyncWorkflow.file_completed_download,
                input.resource.sha256,
            )
        except RPCError:
            # The workflow could try to send a signal to the master workflow
            # when it's restarting.
            pass
        logger.info(f"Sync complete for file {input.resource.sha256}")


@workflow.defn(name=SYNC_BOOTRESOURCES_WORKFLOW_NAME, sandboxed=False)
class SyncBootResourcesWorkflow:
    """Synchronize boot resource among regions."""

    @workflow_run_with_context
    async def run(self, input: SyncRequestParam) -> None:
        regions = frozenset(input.region_endpoints.keys())

        if len(regions) < 2:
            return

        # sync the resource with the other regions
        synced_regions: list[str] = await workflow.execute_activity(
            GET_SYNCED_REGIONS_ACTIVITY_NAME,
            # rfile_ids is the list of the ids of bootresourcefile that reference
            # the same SHA. The sync status for these files is updated at the same time
            # so we can use the first one.
            arg=input.resource.rfile_ids[0],
            start_to_close_timeout=timedelta(seconds=30),
        )

        if not synced_regions:
            raise ApplicationError(
                f"File {input.resource.sha256} has no complete copy available"
            )

        missing_regions = regions - set(synced_regions)

        # Use a random generator from the temporal sdk in order to keep the workflow deterministic.
        random_generator = random()

        endpoints = [
            f"{endpoint}{input.resource.filename_on_disk}/"
            for region in synced_regions
            for endpoint in input.region_endpoints[region]
        ]
        # In order to balance the workload on the regions we randomize the order of the source_list.
        new_res = replace(
            input.resource,
            source_list=random_generator.sample(
                endpoints, min(len(endpoints), MAX_SOURCES)
            ),
        )
        sync_jobs: list[Coroutine[Any, Any, bool]] = []
        for region in missing_regions:
            sync_jobs.append(
                workflow.execute_child_workflow(
                    DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME,
                    new_res,
                    id=f"download-bootresource:{region}:{new_res.sha256[:12]}",
                    execution_timeout=DOWNLOAD_TIMEOUT,
                    run_timeout=DOWNLOAD_TIMEOUT,
                    task_queue=f"region:{region}",
                )
            )

        if sync_jobs:
            synced = await asyncio.gather(*sync_jobs)
            if not all(synced):
                raise ApplicationError(
                    f"File {input.resource.sha256} could not be synced, aborting",
                    non_retryable=True,
                )


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


@workflow.defn(
    name=FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME, sandboxed=False
)
class FetchManifestWorkflow:
    @workflow_run_with_context
    async def run(self) -> list[BootSourceProductsMapping]:
        return await workflow.execute_activity(
            FETCH_MANIFEST_AND_UPDATE_CACHE_ACTIVITY_NAME,
            start_to_close_timeout=FETCH_IMAGE_METADATA_TIMEOUT,
            heartbeat_timeout=timedelta(seconds=30),
        )


@workflow.defn(name=MASTER_IMAGE_SYNC_WORKFLOW_NAME, sandboxed=False)
class MasterImageSyncWorkflow:
    def __init__(self) -> None:
        # list of sha256 that must be downloaded
        self._files_to_download: set[str] = set()

    def _schedule_disk_check(self, res: SpaceRequirementParam, region: str):
        return workflow.execute_child_workflow(
            CHECK_BOOTRESOURCES_STORAGE_WORKFLOW_NAME,
            res,
            id=f"check-bootresources-storage:{region}",
            execution_timeout=DISK_TIMEOUT,
            run_timeout=DISK_TIMEOUT,
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
            task_queue=f"region:{region}",
        )

    async def _download_and_sync_resource(self, input: SyncRequestParam):
        wf_id = f"sync-remote-bootresource:{input.resource.sha256[:12]}"
        try:
            return await workflow.start_child_workflow(
                SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME,
                input,
                id=wf_id,
                execution_timeout=DOWNLOAD_TIMEOUT,
                run_timeout=DOWNLOAD_TIMEOUT,
                parent_close_policy=ParentClosePolicy.ABANDON,
                task_queue=REGION_TASK_QUEUE,
            )
        except WorkflowAlreadyStartedError:
            logger.debug(
                f"Sync workflow with id {wf_id} already running. Skipping."
            )

    @workflow_run_with_context
    async def run(self) -> None:
        # XXX: the same workflow is triggered by a django signal defined in
        # maasserver/models/signals/bootsources.py that is always triggered by
        # the websocket handler in maasserver/websockets/handler/bootresource.py:get_bootsource
        # So we'll always see two `fetch-manifest` workflows starting when
        # triggering the image sync through the UI.
        try:
            mapping: list[
                BootSourceProductsMapping
            ] = await workflow.execute_child_workflow(
                FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME,
                id="fetch-manifest",
                run_timeout=FETCH_IMAGE_METADATA_TIMEOUT,
                task_queue=REGION_TASK_QUEUE,
                id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
            )

            result: GetFilesToDownloadReturnValue = (
                await workflow.execute_activity(
                    GET_FILES_TO_DOWNLOAD_ACTIVITY_NAME,
                    arg=mapping,
                    start_to_close_timeout=FETCH_IMAGE_METADATA_TIMEOUT,
                    heartbeat_timeout=timedelta(seconds=30),
                    result_type=GetFilesToDownloadReturnValue,
                )
            )

            resources_to_download = result.resources
            boot_resource_ids_to_keep = result.boot_resource_ids
            http_proxy = result.http_proxy

            required_disk_space_for_files = sum(
                [r.total_size for r in resources_to_download],
                start=100 * 2**20,  # space to uncompress the bootloaders
            )
            # get regions and endpoints
            endpoints = await workflow.execute_activity(
                GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME,
                start_to_close_timeout=timedelta(seconds=30),
            )
            regions: frozenset[str] = frozenset(endpoints.keys())

            self._files_to_download = set(
                res.sha256 for res in resources_to_download
            )

            # check disk space
            check_space_jobs = [
                self._schedule_disk_check(
                    SpaceRequirementParam(
                        total_resources_size=required_disk_space_for_files
                    ),
                    region,
                )
                for region in regions
            ]
            has_space: list[bool] = await asyncio.gather(*check_space_jobs)
            if not all(has_space):
                raise ApplicationError(
                    "some region controllers don't have enough disk space",
                    non_retryable=True,
                )

            # cancel obsolete download workflows that are running
            await workflow.execute_activity(
                CANCEL_OBSOLETE_DOWNLOAD_WORKFLOWS_ACTIVITY_NAME,
                arg=CancelObsoleteDownloadWorkflowsParam(
                    self._files_to_download
                ),
                start_to_close_timeout=timedelta(seconds=60),
                heartbeat_timeout=timedelta(seconds=15),
            )

            # _download_and_sync_resource is a coroutine that will handle the `WorfklowAlreadyStartedError`
            download_and_sync_jobs = []
            for res in resources_to_download:
                res.http_proxy = http_proxy
                download_and_sync_jobs.append(
                    self._download_and_sync_resource(
                        SyncRequestParam(
                            resource=res, region_endpoints=endpoints
                        )
                    )
                )

            if download_and_sync_jobs:
                logger.info(
                    f"Syncing {len(download_and_sync_jobs)} resources from upstream"
                )
                await asyncio.gather(*download_and_sync_jobs)

            await workflow.wait_condition(
                lambda: self._files_to_download == set()
            )

            await workflow.execute_activity(
                SET_GLOBAL_DEFAULT_RELEASES_ACTIVITY_NAME,
                start_to_close_timeout=timedelta(seconds=30),
            )
            await workflow.execute_activity(
                CLEANUP_OLD_BOOT_RESOURCES_ACTIVITY_NAME,
                arg=CleanupOldBootResourceParam(boot_resource_ids_to_keep),
                start_to_close_timeout=CLEANUP_TIMEOUT,
            )
        except (ActivityError, WorkflowFailureError) as ex:
            # catch any error from activities/child workflows and report that to the user
            await workflow.execute_activity(
                REGISTER_ERROR_NOTIFICATION_ACTIVITY_NAME,
                arg=str(ex.cause),
                start_to_close_timeout=timedelta(seconds=10),
            )
        else:
            await workflow.execute_activity(
                DISCARD_ERROR_NOTIFICATION_ACTIVITY_NAME,
                start_to_close_timeout=timedelta(seconds=10),
            )

    @workflow.signal
    async def file_completed_download(self, sha256: str) -> None:
        """Signal handler for when a sync workflow has been completed."""
        try:
            self._files_to_download.remove(sha256)
        except KeyError:
            # KeyError can happen if the signal is sent when the MasterWorkflow has
            # been restarted but it hasn't populated the files yet.
            pass
