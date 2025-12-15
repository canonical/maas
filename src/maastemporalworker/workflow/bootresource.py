#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
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
    ChildWorkflowError,
    WorkflowAlreadyStartedError,
)
from temporalio.workflow import (
    ActivityCancellationType,
    ParentClosePolicy,
    random,
)

from maascommon.enums.boot_resources import BootResourceType
from maascommon.enums.msm import MSMStatusEnum
from maascommon.enums.notifications import (
    NotificationCategoryEnum,
    NotificationComponent,
)
from maascommon.workflows.bootresource import (
    CLEANUP_TIMEOUT,
    CleanupBootResourceSetsParam,
    DELETE_BOOTRESOURCE_WORKFLOW_NAME,
    DeletePendingFilesParam,
    DISK_TIMEOUT,
    DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME,
    DOWNLOAD_TIMEOUT,
    FETCH_IMAGE_METADATA_TIMEOUT,
    FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME,
    GetFilesToDownloadForSelectionParam,
    GetFilesToDownloadReturnValue,
    GetLocalBootResourcesParamReturnValue,
    HEARTBEAT_TIMEOUT,
    MASTER_IMAGE_SYNC_WORKFLOW_NAME,
    MAX_SOURCES,
    REPORT_INTERVAL,
    ResourceDeleteParam,
    ResourceDownloadParam,
    short_sha,
    SYNC_ALL_LOCAL_BOOTRESOURCES_WORKFLOW_NAME,
    SYNC_BOOTRESOURCES_WORKFLOW_NAME,
    SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME,
    SYNC_SELECTION_WORKFLOW_NAME,
    SyncRequestParam,
    SyncSelectionParam,
)
from maasservicelayer.builders.notifications import NotificationBuilder
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresourcefiles import (
    BootResourceFileClauseFactory,
)
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
)
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionClauseFactory,
)
from maasservicelayer.db.repositories.notifications import (
    NotificationsClauseFactory,
)
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.configurations import MAASUrlConfig
from maasservicelayer.utils.buffer import ChunkBuffer
from maasservicelayer.utils.image_local_files import (
    AsyncLocalBootResourceFile,
    LocalStoreAllocationFail,
    LocalStoreFileSizeMismatch,
    LocalStoreInvalidHash,
)
from maastemporalworker.worker import REGION_TASK_QUEUE
from maastemporalworker.workflow.activity import ActivityBase
from maastemporalworker.workflow.api_client import MAASAPIClient
from maastemporalworker.workflow.utils import (
    activity_defn_with_context,
    get_error_message_from_temporal_exc,
    workflow_run_with_context,
)
from provisioningserver.utils.url import compose_URL

GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME = "get-bootresourcefile-endpoints"
DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME = "download-bootresourcefile"
DELETE_BOOTRESOURCEFILE_ACTIVITY_NAME = "delete-bootresourcefile"
FETCH_MANIFEST_AND_UPDATE_CACHE_ACTIVITY_NAME = (
    "fetch-manifest-and-update-cache"
)
GET_HIGHEST_PRIORITY_SELECTIONS_ACTIVITY_NAME = (
    "get-highest-priority-selections"
)
GET_FILES_TO_DOWNLOAD_FOR_SELECTION_ACTIVITY_NAME = (
    "get-files-to-download-for-selection"
)
GET_LOCAL_BOOT_RESOURCES_PARAMS_ACTIVITY_NAME = "get-local-boot-resources"
DELETE_PENDING_FILES_FOR_SELECTION_ACTIVITY_NAME = (
    "delete-pending-files-for-selection"
)
CLEANUP_BOOT_RESOURCE_SETS_FOR_SELECTION_ACTIVITY_NAME = (
    "cleanup-boot-resource-sets-for-selection"
)
GET_SYNCED_REGIONS_ACTIVITY_NAME = "get-synced-regions"
REGISTER_ERROR_NOTIFICATION_ACTIVITY_NAME = "register-error-notification"
DISCARD_ERROR_NOTIFICATION_ACTIVITY_NAME = "discard-error-notification"


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

    async def _get_extra_http_headers(self, url: str) -> dict[str, str]:
        headers: dict[str, str] = {}
        async with self.start_transaction() as services:
            msm_status = await services.msm.get_status()
            if (
                msm_status
                and msm_status.running == MSMStatusEnum.CONNECTED
                and url.startswith(msm_status.sm_url)
            ):
                headers["Authorization"] = f"bearer {msm_status.sm_jwt}"
        return headers

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
        lfile = AsyncLocalBootResourceFile(
            param.sha256, param.filename_on_disk, param.total_size
        )

        url = param.source_list[
            activity.info().attempt % len(param.source_list)
        ]
        logger.debug(f"Downloading from {url}")

        try:
            if await lfile.valid():
                logger.info("file already downloaded, skipping")
                for target in param.extract_paths:
                    await lfile.extract_file(target)
                    activity.heartbeat(f"Extracted file in {target}")
                await self.report_progress(param.rfile_ids, lfile.total_size)
                return True

            headers = await self._get_extra_http_headers(url)

            async with (
                self.apiclient.make_client(param.http_proxy, headers).stream(
                    "GET", url
                ) as response,
                lfile.store() as store,
            ):
                response.raise_for_status()
                last_update = datetime.now(timezone.utc)

                # Buffer the chunks coming from the requests up to 4MB and then
                # flush to the disk. This ensures that we keep sending the heartbeat
                # and we do not pay the overhead of writing very small chunks
                # to the disk every time.
                CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB
                chunk_buffer = ChunkBuffer(CHUNK_SIZE)

                async for chunk in response.aiter_bytes():
                    activity.heartbeat("Downloaded chunk")
                    dt_now = datetime.now(timezone.utc)
                    if dt_now > (last_update + REPORT_INTERVAL):
                        await self.report_progress(
                            param.rfile_ids, await store.tell()
                        )
                        last_update = dt_now
                    needs_flushing = chunk_buffer.append_and_check(chunk)
                    if needs_flushing:
                        await store.write(chunk_buffer.get_and_reset())
                if not chunk_buffer.is_empty():
                    await store.write(chunk_buffer.get_and_reset())

            activity.heartbeat("Download finished")

            for target in param.extract_paths:
                await lfile.extract_file(target)
                activity.heartbeat(f"Extracted file in {target}")

            await self.report_progress(param.rfile_ids, lfile.total_size)
            return True

        except LocalStoreInvalidHash as e:
            await self.report_progress(param.rfile_ids, 0)
            raise ApplicationError("Invalid SHA256 checksum") from e
        except LocalStoreAllocationFail as e:
            await self.report_progress(param.rfile_ids, 0)
            raise ApplicationError(
                "No space left on disk", non_retryable=True
            ) from e
        except LocalStoreFileSizeMismatch as e:
            await self.report_progress(param.rfile_ids, 0)
            raise ApplicationError(
                "Downloaded file size does not match expected size"
            ) from e
        except IOError as ex:
            # if we run out of disk space, stop this download.
            # let the user fix the issue and restart it manually later
            await lfile.unlink()
            await self.report_progress(param.rfile_ids, 0)
            if ex.errno == 28:
                logger.error(ex.strerror)
                raise ApplicationError(
                    "No space left on disk", non_retryable=True
                ) from ex

            raise ApplicationError(
                ex.strerror if ex.strerror else str(ex),
                type=ex.__class__.__name__,
            ) from ex
        except httpx.HTTPError as ex:
            await lfile.unlink()
            await self.report_progress(param.rfile_ids, 0)
            raise ApplicationError(str(ex), type=ex.__class__.__name__) from ex
        except (asyncio.CancelledError, CancelledError) as ex:
            await lfile.unlink()
            await self.report_progress(param.rfile_ids, 0)
            # re-raise it as it is since temporal will propagate this to the parent wf
            raise ex

    @activity_defn_with_context(name=DELETE_BOOTRESOURCEFILE_ACTIVITY_NAME)
    async def delete_bootresourcefile(
        self, param: ResourceDeleteParam
    ) -> bool:
        """Delete files from disk"""
        for file in param.files:
            logger.debug(f"attempt to delete {file}")
            lfile = AsyncLocalBootResourceFile(
                file.sha256, file.filename_on_disk, 0
            )
            await lfile.unlink()
            activity.heartbeat("File deleted")
            logger.info(f"file {file} deleted")
        return True

    @activity_defn_with_context(
        name=FETCH_MANIFEST_AND_UPDATE_CACHE_ACTIVITY_NAME
    )
    async def fetch_manifest_and_update_cache(
        self,
    ):
        """Fetch the latest manifest for all the boot sources and updates both
        the manifests and the boot source caches.
        """
        async with self.start_transaction() as services:
            await services.image_sync.ensure_boot_source_definition()
            boot_sources = await services.boot_sources.get_many(
                query=QuerySpec()
            )

            for boot_source in boot_sources:
                try:
                    image_manifest = (
                        await services.image_manifests.fetch_and_update(
                            boot_source
                        )
                    )
                    activity.heartbeat("Downloaded images descriptions")
                    await (
                        services.boot_source_cache.update_from_image_manifest(
                            image_manifest
                        )
                    )
                except Exception as ex:
                    logger.error(
                        f"Could not fetch manifest for boot source with url {boot_source.url}: {ex}"
                    )
                    await services.notifications.create(
                        NotificationBuilder(
                            ident=NotificationComponent.FETCH_IMAGE_MANIFEST,
                            users=True,
                            admins=True,
                            message=f"Failed to fetch image manifest for boot source with url {boot_source.url}. Check the logs for more details.",
                            context={},
                            user_id=None,
                            category=NotificationCategoryEnum.ERROR,
                            dismissable=True,
                        )
                    )
            await services.image_sync.sync_boot_source_selections_from_msm(
                boot_sources
            )

            # don't raise an exception, just create the notification
            await services.image_sync.check_commissioning_series_selected()

            # TODO: MAASENG-5738 remove this
            await (
                services.boot_source_selections.ensure_selections_from_legacy()
            )

    @activity_defn_with_context(
        name=GET_HIGHEST_PRIORITY_SELECTIONS_ACTIVITY_NAME
    )
    async def get_all_highest_priority_selections(self) -> list[int]:
        async with self.start_transaction() as services:
            selections = await services.boot_source_selections.get_all_highest_priority()
            return [s.id for s in selections]

    @activity_defn_with_context(
        name=GET_FILES_TO_DOWNLOAD_FOR_SELECTION_ACTIVITY_NAME
    )
    async def get_files_to_download_for_selection(
        self, param: GetFilesToDownloadForSelectionParam
    ) -> GetFilesToDownloadReturnValue:
        async with self.start_transaction() as services:
            selection = await services.boot_source_selections.get_by_id(
                param.selection_id
            )
            assert selection is not None

            # Remove any existing boot resources related to a selection with
            # the same os/arch/release. This can happen when there is a clash
            # between selections. (e.g. two selections for ubuntu/20.04/amd64
            # from different boot sources).
            # NOTE: We are assuming that the higher priority selection will be
            # the only one to be downloaded, i.e. we don't allow the user to
            # start a sync selection workflow for a lower priority selection.
            # This is enforced at the API level and in the master-image-sync wf.
            if (
                existing_selection
                := await services.boot_source_selections.get_one(
                    query=QuerySpec(
                        where=BootSourceSelectionClauseFactory.and_clauses(
                            [
                                BootSourceSelectionClauseFactory.with_os(
                                    selection.os
                                ),
                                BootSourceSelectionClauseFactory.with_arch(
                                    selection.arch
                                ),
                                BootSourceSelectionClauseFactory.with_release(
                                    selection.release
                                ),
                                BootSourceSelectionClauseFactory.not_clause(
                                    BootSourceSelectionClauseFactory.with_id(
                                        selection.id
                                    )
                                ),
                            ]
                        )
                    )
                )
            ):
                await services.boot_resources.delete_many(
                    query=QuerySpec(
                        where=BootResourceClauseFactory.with_selection_id(
                            existing_selection.id
                        )
                    )
                )

            boot_source = await services.boot_sources.get_by_id(
                selection.boot_source_id
            )
            assert boot_source is not None

            image_manifest, _ = await services.image_manifests.get_or_fetch(
                boot_source
            )

            filtered_products_list = (
                services.image_sync.filter_products_for_selection(
                    selection=selection,
                    manifest=image_manifest.manifest,
                )
            )
            resources_to_download = await services.image_sync.get_files_to_download_from_product_list(
                boot_source, filtered_products_list
            )

            # get the http proxy to use and update the resources
            if http_proxy := await services.image_manifests._get_http_proxy():
                resources_to_download = [
                    replace(r, http_proxy=http_proxy)
                    for r in resources_to_download
                ]

            return GetFilesToDownloadReturnValue(
                resources=resources_to_download,
            )

    @activity_defn_with_context(
        name=GET_LOCAL_BOOT_RESOURCES_PARAMS_ACTIVITY_NAME
    )
    async def get_manually_uploaded_resources(
        self,
    ) -> GetLocalBootResourcesParamReturnValue:
        async with self.start_transaction() as services:
            boot_resources = await services.boot_resources.get_many(
                query=QuerySpec(
                    where=BootResourceClauseFactory.with_rtype(
                        BootResourceType.UPLOADED
                    )
                )
            )

            resources: list[ResourceDownloadParam] = []
            for boot_resource in boot_resources:
                resource_set = await services.boot_resource_sets.get_latest_for_boot_resource(
                    boot_resource.id
                )
                assert resource_set is not None
                files = await services.boot_resource_files.get_files_in_resource_set(
                    resource_set.id
                )
                for file in files:
                    resources.append(
                        ResourceDownloadParam(
                            rfile_ids=[file.id],
                            source_list=[],  # this will get overridden with the region url
                            sha256=file.sha256,
                            filename_on_disk=file.filename_on_disk,
                            total_size=file.size,
                        )
                    )
            return GetLocalBootResourcesParamReturnValue(resources=resources)

    @activity_defn_with_context(
        name=DELETE_PENDING_FILES_FOR_SELECTION_ACTIVITY_NAME
    )
    async def delete_pending_files(
        self, param: DeletePendingFilesParam
    ) -> None:
        file_ids = []
        for res in param.resources:
            file_ids.extend(res.rfile_ids)

        async with self.start_transaction() as services:
            await services.boot_resource_files.delete_many(
                query=QuerySpec(
                    where=BootResourceFileClauseFactory.with_ids(file_ids)
                )
            )

    @activity_defn_with_context(
        name=CLEANUP_BOOT_RESOURCE_SETS_FOR_SELECTION_ACTIVITY_NAME
    )
    async def cleanup_boot_resource_sets_for_selection(
        self,
        param: CleanupBootResourceSetsParam,
    ) -> None:
        async with self.start_transaction() as services:
            await services.image_sync.cleanup_boot_resource_sets_for_selection(
                param.selection_id
            )

    @activity_defn_with_context(name=REGISTER_ERROR_NOTIFICATION_ACTIVITY_NAME)
    async def register_error_notification(self, err_msg: str) -> None:
        async with self.start_transaction() as services:
            await services.notifications.create_or_update(
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


@workflow.defn(name=SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME, sandboxed=False)
class SyncRemoteBootResourcesWorkflow:
    """Downloads the resource from upstream and synchronizes it among the regions."""

    @workflow_run_with_context
    async def run(self, input: SyncRequestParam) -> None:
        # download resource from upstream
        downloaded = await workflow.execute_child_workflow(
            DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME,
            arg=input.resource,
            id=f"download-bootresource:upstream:{short_sha(input.resource.sha256)}",
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
            id=f"sync-bootresources:{short_sha(input.resource.sha256)}",
        )

        logger.info(f"Sync complete for file {input.resource.sha256}")


@workflow.defn(
    name=SYNC_ALL_LOCAL_BOOTRESOURCES_WORKFLOW_NAME, sandboxed=False
)
class SyncAllLocalBootResourcesWorkflow:
    """Synchronize all the manually uploaded boot resources among regions.

    To be exclusively used in the `MasterImageSyncWorkflow`.

    If you have to sync a new uploaded boot resource from the API you have to
    use the `SyncBootResourcesWorkflow`.
    """

    @workflow_run_with_context
    async def run(self) -> None:
        resources_to_sync: GetLocalBootResourcesParamReturnValue = (
            await workflow.execute_activity(
                GET_LOCAL_BOOT_RESOURCES_PARAMS_ACTIVITY_NAME,
                start_to_close_timeout=timedelta(seconds=30),
                result_type=GetLocalBootResourcesParamReturnValue,
            )
        )

        if not resources_to_sync.resources:
            return

        sync_boot_resourcs_jobs = [
            workflow.execute_child_workflow(
                SYNC_BOOTRESOURCES_WORKFLOW_NAME,
                arg=SyncRequestParam(resource=resource),
                id=f"sync-bootresources:{short_sha(resource.sha256)}",
            )
            for resource in resources_to_sync.resources
        ]

        await asyncio.gather(*sync_boot_resourcs_jobs)


@workflow.defn(name=SYNC_BOOTRESOURCES_WORKFLOW_NAME, sandboxed=False)
class SyncBootResourcesWorkflow:
    """Synchronize boot resource among regions."""

    @workflow_run_with_context
    async def run(self, input: SyncRequestParam) -> None:
        # get regions and endpoints
        region_endpoints = await workflow.execute_activity(
            GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME,
            start_to_close_timeout=timedelta(seconds=30),
        )
        regions = frozenset(region_endpoints.keys())

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
            for endpoint in region_endpoints[region]
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
                    id=f"download-bootresource:{region}:{short_sha(new_res.sha256)}",
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
    async def run(self) -> None:
        return await workflow.execute_activity(
            FETCH_MANIFEST_AND_UPDATE_CACHE_ACTIVITY_NAME,
            start_to_close_timeout=FETCH_IMAGE_METADATA_TIMEOUT,
            heartbeat_timeout=timedelta(seconds=30),
        )


@workflow.defn(name=SYNC_SELECTION_WORKFLOW_NAME, sandboxed=False)
class SyncSelectionWorkflow:
    async def _download_and_sync_resource(self, input: SyncRequestParam):
        wf_id = f"sync-remote-bootresource:{short_sha(input.resource.sha256)}"
        try:
            return await workflow.execute_child_workflow(
                SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME,
                input,
                id=wf_id,
                execution_timeout=DOWNLOAD_TIMEOUT,
                run_timeout=DOWNLOAD_TIMEOUT,
                parent_close_policy=ParentClosePolicy.TERMINATE,
                task_queue=REGION_TASK_QUEUE,
            )
        except WorkflowAlreadyStartedError:
            logger.debug(
                f"Sync workflow with id {wf_id} already running. Skipping."
            )

    @workflow_run_with_context
    async def run(self, param: SyncSelectionParam) -> None:
        result: GetFilesToDownloadReturnValue = (
            await workflow.execute_activity(
                GET_FILES_TO_DOWNLOAD_FOR_SELECTION_ACTIVITY_NAME,
                arg=GetFilesToDownloadForSelectionParam(
                    selection_id=param.selection_id,
                ),
                start_to_close_timeout=FETCH_IMAGE_METADATA_TIMEOUT,
                heartbeat_timeout=timedelta(seconds=30),
                result_type=GetFilesToDownloadReturnValue,
            )
        )
        resources_to_download = result.resources

        # _download_and_sync_resource is a coroutine that will handle the `WorfklowAlreadyStartedError`
        download_and_sync_jobs = [
            self._download_and_sync_resource(SyncRequestParam(resource=res))
            for res in resources_to_download
        ]

        try:
            if download_and_sync_jobs:
                logger.info(
                    f"Syncing {len(download_and_sync_jobs)} resources from upstream"
                )
                await asyncio.gather(*download_and_sync_jobs)
        except (ActivityError, ChildWorkflowError, WorkflowFailureError) as ex:
            # In case of a failure we delete all the files that were downloading
            await workflow.execute_activity(
                DELETE_PENDING_FILES_FOR_SELECTION_ACTIVITY_NAME,
                arg=DeletePendingFilesParam(resources=resources_to_download),
                start_to_close_timeout=CLEANUP_TIMEOUT,
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            raise ex
        finally:
            # we do the cleanup even if some downloads failed. This will delete
            # the boot resource sets that aren't complete ensuring the db
            # status is consistent with the actual state of the files on disk.
            await workflow.execute_activity(
                CLEANUP_BOOT_RESOURCE_SETS_FOR_SELECTION_ACTIVITY_NAME,
                arg=CleanupBootResourceSetsParam(
                    selection_id=param.selection_id
                ),
                start_to_close_timeout=CLEANUP_TIMEOUT,
            )

        logger.info(
            f"Downloaded and synchronized all images for selection with id {param.selection_id}"
        )


@workflow.defn(name=MASTER_IMAGE_SYNC_WORKFLOW_NAME, sandboxed=False)
class MasterImageSyncWorkflow:
    async def _download_resources_for_selection(
        self, input: SyncSelectionParam
    ):
        wf_id = f"sync-selection:{input.selection_id}"
        try:
            return await workflow.execute_child_workflow(
                SYNC_SELECTION_WORKFLOW_NAME,
                input,
                id=wf_id,
                execution_timeout=DOWNLOAD_TIMEOUT,
                run_timeout=DOWNLOAD_TIMEOUT,
                id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
                # It follows the parent close policy. Now that we have granular
                # control over selections, we don't make things "smart" by not
                # canceling workflows when we cancel the master image sync wf.
                # We use the REQUEST_CANCEL policy to ensure that child workflows
                # are gracefully cancelled and can cleanup properly.
                parent_close_policy=ParentClosePolicy.REQUEST_CANCEL,
                task_queue=REGION_TASK_QUEUE,
            )
        except WorkflowAlreadyStartedError:
            logger.debug(
                f"Sync workflow with id {wf_id} already running. Skipping."
            )

    @workflow_run_with_context
    async def run(self) -> None:
        try:
            selection_ids: list[int] = await workflow.execute_activity(
                GET_HIGHEST_PRIORITY_SELECTIONS_ACTIVITY_NAME,
                start_to_close_timeout=timedelta(seconds=60),
            )

            # Start a `SyncSelectionWorkflow` for each selection
            sync_jobs = [
                self._download_resources_for_selection(
                    SyncSelectionParam(selection_id=selection_id)
                )
                for selection_id in selection_ids
            ]

            await asyncio.gather(*sync_jobs)
            # Sync the local boot resources. This covers the edge case when a
            # region is added after images have been synchronized.
            await workflow.execute_child_workflow(
                SYNC_ALL_LOCAL_BOOTRESOURCES_WORKFLOW_NAME,
                task_queue=REGION_TASK_QUEUE,
            )

        except (ActivityError, ChildWorkflowError, WorkflowFailureError) as ex:
            # catch any error from activities/child workflows and report that to the user
            message = get_error_message_from_temporal_exc(ex)
            await workflow.execute_activity(
                REGISTER_ERROR_NOTIFICATION_ACTIVITY_NAME,
                arg=message,
                start_to_close_timeout=timedelta(seconds=10),
            )
        else:
            await workflow.execute_activity(
                DISCARD_ERROR_NOTIFICATION_ACTIVITY_NAME,
                start_to_close_timeout=timedelta(seconds=10),
            )
