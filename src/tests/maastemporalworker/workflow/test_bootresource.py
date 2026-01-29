#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import shutil
from typing import Any
from unittest.mock import AsyncMock, Mock

from aiofiles.threadpool.binary import AsyncBufferedIOBase
import httpx
import pytest
from temporalio import activity
from temporalio.client import (
    Client,
    WorkflowExecutionStatus,
    WorkflowFailureError,
)
from temporalio.exceptions import ApplicationError, CancelledError
from temporalio.testing import ActivityEnvironment, WorkflowEnvironment
from temporalio.worker import Worker

from maascommon.enums.boot_resources import (
    BootResourceFileType,
    BootResourceType,
)
from maascommon.enums.msm import MSMStatusEnum
from maascommon.enums.notifications import (
    NotificationCategoryEnum,
    NotificationComponent,
)
from maascommon.workflows.bootresource import (
    CleanupBootResourceSetsParam,
    DeleteNotificationParam,
    DeletePendingFilesParam,
    DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME,
    GetFilesToDownloadForSelectionParam,
    GetFilesToDownloadReturnValue,
    GetLocalBootResourcesParamReturnValue,
    RegisterNotificationParam,
    ResourceDeleteParam,
    ResourceDownloadParam,
    ResourceIdentifier,
    SYNC_ALL_LOCAL_BOOTRESOURCES_WORKFLOW_NAME,
    SYNC_BOOTRESOURCES_WORKFLOW_NAME,
    SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME,
    SYNC_SELECTION_WORKFLOW_NAME,
    SyncRequestParam,
    SyncSelectionParam,
)
from maasservicelayer.builders.notifications import NotificationBuilder
from maasservicelayer.db import Database
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
)
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionClauseFactory,
)
from maasservicelayer.db.repositories.notifications import (
    NotificationsClauseFactory,
)
from maasservicelayer.models.bootresourcefiles import BootResourceFile
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.models.bootresourcesets import BootResourceSet
from maasservicelayer.models.bootsources import BootSource
from maasservicelayer.models.bootsourceselections import BootSourceSelection
from maasservicelayer.models.image_manifests import ImageManifest
from maasservicelayer.services import CacheForServices, ServiceCollectionV3
from maasservicelayer.services.boot_sources import BootSourcesService
from maasservicelayer.services.bootresourcefiles import (
    BootResourceFilesService,
)
from maasservicelayer.services.bootresourcefilesync import (
    BootResourceFileSyncService,
)
from maasservicelayer.services.bootresources import BootResourceService
from maasservicelayer.services.bootresourcesets import BootResourceSetsService
from maasservicelayer.services.bootsourcecache import BootSourceCacheService
from maasservicelayer.services.bootsourceselections import (
    BootSourceSelectionsService,
)
from maasservicelayer.services.image_manifests import ImageManifestsService
from maasservicelayer.services.image_sync import ImageSyncService
from maasservicelayer.services.msm import MSMService, MSMStatus
from maasservicelayer.services.notifications import NotificationsService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.simplestreams.client import SimpleStreamsClientException
from maasservicelayer.simplestreams.models import (
    BootloaderProduct,
    SimpleStreamsProductListType,
)
from maasservicelayer.utils.image_local_files import (
    AsyncLocalBootResourceFile,
    LocalStoreAllocationFail,
    LocalStoreFileSizeMismatch,
    LocalStoreInvalidHash,
)
from maastemporalworker.worker import (
    custom_sandbox_runner,
    pydantic_data_converter,
)
from maastemporalworker.workflow.api_client import MAASAPIClient
from maastemporalworker.workflow.bootresource import (
    BootResourcesActivity,
    CLEANUP_BOOT_RESOURCE_SETS_FOR_SELECTION_ACTIVITY_NAME,
    DELETE_BOOTRESOURCEFILE_ACTIVITY_NAME,
    DELETE_NOTIFICATION_ACTIVITY_NAME,
    DELETE_PENDING_FILES_FOR_SELECTION_ACTIVITY_NAME,
    DeleteBootResourceWorkflow,
    DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME,
    DownloadBootResourceWorkflow,
    FETCH_MANIFEST_AND_UPDATE_CACHE_ACTIVITY_NAME,
    FetchManifestWorkflow,
    GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME,
    GET_FILES_TO_DOWNLOAD_FOR_SELECTION_ACTIVITY_NAME,
    GET_HIGHEST_PRIORITY_SELECTIONS_ACTIVITY_NAME,
    GET_LOCAL_BOOT_RESOURCES_PARAMS_ACTIVITY_NAME,
    GET_SYNCED_REGIONS_ACTIVITY_NAME,
    MasterImageSyncWorkflow,
    REGION_TASK_QUEUE,
    REGISTER_NOTIFICATION_ACTIVITY_NAME,
    SyncAllLocalBootResourcesWorkflow,
    SyncBootResourcesWorkflow,
    SyncRemoteBootResourcesWorkflow,
    SyncSelectionWorkflow,
)
from tests.fixtures import AsyncContextManagerMock, AsyncIteratorMock
from tests.maastemporalworker.workflow import (
    cancel_workflow_immediately,
    get_workflow_status,
    TemporalCalls,
    WorkerTestInterceptor,
)

FILE_SIZE = 50


@pytest.fixture
def controller(factory, mocker):
    mocker.patch("maasserver.utils.orm.post_commit_hooks")
    mocker.patch("maasserver.utils.orm.post_commit_do")
    controller = factory.make_RegionRackController()
    yield controller


@pytest.fixture
def maas_data_dir(mocker, tmpdir):
    mocker.patch.dict(os.environ, {"MAAS_DATA": str(tmpdir)})
    yield tmpdir


@pytest.fixture
def image_store_dir(maas_data_dir, mocker):
    store = Path(maas_data_dir) / "image-storage"
    store.mkdir()
    mock_disk_usage = mocker.patch("shutil.disk_usage")
    mock_disk_usage.return_value = (0, 0, 101)  # only care about 'free'
    yield store
    shutil.rmtree(store)


@pytest.fixture
def mock_apiclient():
    m = Mock(MAASAPIClient)
    m.url = "http://test:5240"
    m._mocked_client = Mock(httpx.AsyncClient)
    m.make_client = Mock(return_value=m._mocked_client)
    yield m


@pytest.fixture
def mock_temporal_client():
    yield Mock(Client)


@pytest.fixture
def boot_activities(
    mocker,
    controller,
    mock_apiclient: Mock,
    mock_temporal_client: Mock,
    services_mock: ServiceCollectionV3,
):
    act = BootResourcesActivity(
        Mock(Database), CacheForServices(), mock_temporal_client
    )
    act.apiclient = mock_apiclient
    act.region_id = controller.system_id
    act.report_progress = AsyncMock(return_value=None)
    services_mock.msm = Mock(MSMService)
    mocker.patch.object(
        act, "start_transaction"
    ).return_value = AsyncContextManagerMock(services_mock)
    yield act


@pytest.fixture
def a_file(image_store_dir):
    content = b"\x01" * FILE_SIZE
    sha256 = hashlib.sha256()
    sha256.update(content)
    file = image_store_dir / f"{str(sha256.hexdigest())}"
    with file.open("wb") as f:
        f.write(content)
    yield file


@pytest.fixture
def mock_local_file(mocker):
    m = Mock(AsyncLocalBootResourceFile)
    mocker.patch(
        "maastemporalworker.workflow.bootresource.AsyncLocalBootResourceFile"
    ).return_value = m
    m.total_size = FILE_SIZE
    yield m


@pytest.fixture
def activity_env():
    env = ActivityEnvironment()
    env.payload_converter = pydantic_data_converter
    yield env


class TestGetSyncedRegionsForFilesActivity:
    async def test_calls_file_sync_service(
        self,
        boot_activities: BootResourcesActivity,
        services_mock: ServiceCollectionV3,
    ) -> None:
        services_mock.boot_resource_file_sync = Mock(
            BootResourceFileSyncService
        )
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        await env.run(boot_activities.get_synced_regions_for_file, 1)
        services_mock.boot_resource_file_sync.get_synced_regions_for_file.assert_awaited_once_with(
            1
        )


class TestGetBootresourcefileEndpointsActivity:
    async def test_calls_apiclient(
        self, boot_activities: BootResourcesActivity, mock_apiclient: Mock
    ) -> None:
        mock_apiclient.request_async = AsyncMock(
            return_value=[
                {
                    "system_id": "abcdef",
                    "ip_addresses": ["10.0.0.1"],
                },
                {
                    "system_id": "ghijkl",
                    "ip_addresses": ["10.0.0.2"],
                },
                {
                    "system_id": "mnopqr",
                    "ip_addresses": ["10.0.0.3"],
                },
            ]
        )
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        endpoints = await env.run(
            boot_activities.get_bootresourcefile_endpoints
        )
        assert endpoints == {
            "abcdef": ["http://10.0.0.1:5240/MAAS/boot-resources/"],
            "ghijkl": ["http://10.0.0.2:5240/MAAS/boot-resources/"],
            "mnopqr": ["http://10.0.0.3:5240/MAAS/boot-resources/"],
        }
        mock_apiclient.request_async.assert_awaited_once_with(
            "GET", f"{mock_apiclient.url}/api/2.0/regioncontrollers/"
        )

    async def test_bug_2058037(
        self, boot_activities: BootResourcesActivity, mock_apiclient: Mock
    ) -> None:
        mock_apiclient.request_async = AsyncMock(
            return_value=[
                {
                    "system_id": "abcdef",
                    "ip_addresses": [],
                },
                {
                    "system_id": "ghijkl",
                    "ip_addresses": ["10.0.0.2"],
                },
                {
                    "system_id": "mnopqr",
                    "ip_addresses": ["10.0.0.3"],
                },
            ]
        )
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        with pytest.raises(ApplicationError) as err:
            await env.run(boot_activities.get_bootresourcefile_endpoints)

        assert (
            str(err.value)
            == "Could not retrieve the IP addresses of the region controller 'abcdef' from the API. This activity will be retried until we have the IP for all the region controllers."
        )


class TestDownloadBootresourcefileActivity:
    async def test_valid_file_dont_get_downloaded_again(
        self,
        mock_local_file: Mock,
        boot_activities: BootResourcesActivity,
        mock_apiclient: Mock,
        activity_env: ActivityEnvironment,
    ) -> None:
        mock_local_file.valid.return_value = True

        param = ResourceDownloadParam(
            rfile_ids=[1],
            source_list=["http://maas-image-stream.io"],
            sha256="0" * 64,
            filename_on_disk="0" * 7,
            total_size=100,
        )
        res = await activity_env.run(
            boot_activities.download_bootresourcefile, param
        )
        assert res is True

        boot_activities.report_progress.assert_awaited_once_with(
            param.rfile_ids, mock_local_file.total_size
        )
        mock_apiclient.make_client.assert_not_called()
        mock_local_file.store.assert_not_called()

    async def test_extract_file_emits_heartbeat(
        self,
        mock_local_file: Mock,
        boot_activities: BootResourcesActivity,
        mock_apiclient: Mock,
        activity_env: ActivityEnvironment,
    ) -> None:
        mock_local_file.valid.return_value = True
        mock_local_file.extract_file.return_value = None

        heartbeats = []
        activity_env.on_heartbeat = lambda *args: heartbeats.append(args[0])
        param = ResourceDownloadParam(
            rfile_ids=[1],
            source_list=["http://maas-image-stream.io"],
            sha256="0" * 64,
            filename_on_disk="0" * 7,
            total_size=100,
            extract_paths=["path1", "path2"],
        )
        res = await activity_env.run(
            boot_activities.download_bootresourcefile, param
        )
        assert res is True

        assert heartbeats == [
            "Extracted file in path1",
            "Extracted file in path2",
        ]

        boot_activities.report_progress.assert_awaited_once_with(
            param.rfile_ids, mock_local_file.total_size
        )
        mock_apiclient.make_client.assert_not_called()

    async def test_download_file_if_not_valid(
        self,
        mock_local_file: Mock,
        boot_activities: BootResourcesActivity,
        mock_apiclient: Mock,
        activity_env: ActivityEnvironment,
    ) -> None:
        mock_local_file.valid.side_effect = [False, True]
        chunked_data = [b"foo", b"bar", b""]

        mock_http_response = Mock(httpx.Response)
        mock_http_response.aiter_bytes.return_value = AsyncIteratorMock(
            chunked_data
        )
        mock_apiclient._mocked_client.stream.return_value = (
            AsyncContextManagerMock(mock_http_response)
        )
        mock_store = Mock(AsyncBufferedIOBase)
        mock_local_file.store.return_value = AsyncContextManagerMock(
            mock_store
        )

        heartbeats = []
        activity_env.on_heartbeat = lambda *args: heartbeats.append(args[0])
        param = ResourceDownloadParam(
            rfile_ids=[1],
            source_list=["http://maas-image-stream.io"],
            sha256="0" * 64,
            filename_on_disk="0" * 7,
            total_size=100,
        )
        res = await activity_env.run(
            boot_activities.download_bootresourcefile, param
        )
        assert res is True

        assert heartbeats == [
            "Downloaded chunk",
            "Downloaded chunk",
            "Downloaded chunk",
            "Download finished",
        ]

        mock_store.write.assert_awaited_once_with(bytearray(b"foobar"))
        boot_activities.report_progress.assert_awaited_once_with(
            param.rfile_ids, mock_local_file.total_size
        )
        mock_apiclient.make_client.assert_called_once_with(None, {})
        mock_apiclient._mocked_client.stream.assert_called_once_with(
            "GET",
            "http://maas-image-stream.io",
        )

    async def test_download_file_from_msm(
        self,
        mock_local_file: Mock,
        boot_activities: BootResourcesActivity,
        mock_apiclient: Mock,
        services_mock: ServiceCollectionV3,
    ) -> None:
        mock_local_file.valid.side_effect = [False, True]
        chunked_data = [b"foo", b"bar", b""]

        mock_http_response = Mock(httpx.Response)
        mock_http_response.aiter_bytes.return_value = AsyncIteratorMock(
            chunked_data
        )
        mock_apiclient._mocked_client.stream.return_value = (
            AsyncContextManagerMock(mock_http_response)
        )
        mock_store = Mock(AsyncBufferedIOBase)
        mock_local_file.store.return_value = AsyncContextManagerMock(
            mock_store
        )
        services_mock.msm.get_status.return_value = MSMStatus(
            sm_url="http://site-manager.io",
            sm_jwt="jwt_token",
            running=MSMStatusEnum.CONNECTED,
            start_time=None,
        )

        heartbeats = []
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        env.on_heartbeat = lambda *args: heartbeats.append(args[0])
        param = ResourceDownloadParam(
            rfile_ids=[1],
            source_list=["http://site-manager.io/site/images/squashfs"],
            sha256="0" * 64,
            filename_on_disk="0" * 7,
            total_size=100,
        )
        res = await env.run(boot_activities.download_bootresourcefile, param)
        assert res is True

        assert heartbeats == [
            "Downloaded chunk",
            "Downloaded chunk",
            "Downloaded chunk",
            "Download finished",
        ]

        mock_apiclient.make_client.assert_called_once_with(
            None, {"Authorization": "bearer jwt_token"}
        )
        mock_apiclient._mocked_client.stream.assert_called_once_with(
            "GET",
            "http://site-manager.io/site/images/squashfs",
        )

    async def test_download_file_fails_checksum_check(
        self,
        mock_local_file: Mock,
        boot_activities: BootResourcesActivity,
        mock_apiclient: Mock,
        activity_env: ActivityEnvironment,
    ) -> None:
        mock_local_file.valid.return_value = False
        mock_local_file.store.side_effect = LocalStoreInvalidHash()

        mock_http_response = Mock(httpx.Response)
        mock_apiclient._mocked_client.stream.return_value = (
            AsyncContextManagerMock(mock_http_response)
        )

        heartbeats = []
        activity_env.on_heartbeat = lambda *args: heartbeats.append(args[0])
        param = ResourceDownloadParam(
            rfile_ids=[1],
            source_list=["http://maas-image-stream.io"],
            sha256="0" * 64,
            filename_on_disk="0" * 7,
            total_size=100,
        )
        with pytest.raises(ApplicationError) as err:
            await activity_env.run(
                boot_activities.download_bootresourcefile, param
            )

        assert str(err.value) == "Invalid SHA256 checksum"

        boot_activities.report_progress.assert_awaited_once_with(
            param.rfile_ids, 0
        )
        mock_apiclient._mocked_client.stream.assert_called_once_with(
            "GET",
            "http://maas-image-stream.io",
        )

    async def test_download_file_raise_out_of_disk_exception(
        self,
        mock_local_file: Mock,
        boot_activities: BootResourcesActivity,
        mock_apiclient: Mock,
        activity_env: ActivityEnvironment,
    ) -> None:
        mock_local_file.valid.return_value = False
        exception = IOError()
        exception.errno = 28
        mock_local_file.store.side_effect = exception
        mock_http_response = Mock(httpx.Response)
        mock_apiclient._mocked_client.stream.return_value = (
            AsyncContextManagerMock(mock_http_response)
        )

        param = ResourceDownloadParam(
            rfile_ids=[1],
            source_list=["http://maas-image-stream.io"],
            sha256="0" * 64,
            filename_on_disk="0" * 7,
            total_size=100,
        )
        with pytest.raises(ApplicationError):
            await activity_env.run(
                boot_activities.download_bootresourcefile, param
            )

        mock_local_file.unlink.assert_awaited_once()
        boot_activities.report_progress.assert_awaited_once_with(
            param.rfile_ids, 0
        )

    @pytest.mark.parametrize(
        "exception",
        [CancelledError(), asyncio.CancelledError()],
    )
    async def test_local_file_gets_unlinked_when_activity_is_cancelled(
        self,
        mock_local_file: Mock,
        boot_activities: BootResourcesActivity,
        mock_apiclient: Mock,
        activity_env: ActivityEnvironment,
        exception,
    ) -> None:
        mock_local_file.valid.return_value = False
        # `store` is not the responsible of raising all these exceptions,
        # but we use it to avoid patching the rest of the function
        mock_local_file.store.side_effect = exception
        mock_http_response = Mock(httpx.Response)
        mock_apiclient._mocked_client.stream.return_value = (
            AsyncContextManagerMock(mock_http_response)
        )

        param = ResourceDownloadParam(
            rfile_ids=[1],
            source_list=["http://maas-image-stream.io"],
            sha256="0" * 64,
            filename_on_disk="0" * 7,
            total_size=100,
        )
        with pytest.raises(type(exception)):
            await activity_env.run(
                boot_activities.download_bootresourcefile, param
            )
        mock_local_file.unlink.assert_called_once()
        boot_activities.report_progress.assert_awaited_once_with(
            param.rfile_ids, 0
        )

    @pytest.mark.parametrize(
        "exception",
        [
            IOError(),
            httpx.HTTPError("Error"),
            LocalStoreInvalidHash(),
            LocalStoreAllocationFail(),
            LocalStoreFileSizeMismatch(),
        ],
    )
    async def test_download_file_raise_other_exception(
        self,
        mock_local_file: Mock,
        boot_activities: BootResourcesActivity,
        mock_apiclient: Mock,
        activity_env: ActivityEnvironment,
        exception,
    ) -> None:
        mock_local_file.valid.return_value = False
        # `store` is not the responsible of raising all these exceptions,
        # but we use it to avoid patching the rest of the function
        mock_local_file.store.side_effect = exception
        mock_http_response = Mock(httpx.Response)
        mock_apiclient._mocked_client.stream.return_value = (
            AsyncContextManagerMock(mock_http_response)
        )

        param = ResourceDownloadParam(
            rfile_ids=[1],
            source_list=["http://maas-image-stream.io"],
            sha256="0" * 64,
            filename_on_disk="0" * 7,
            total_size=100,
        )
        with pytest.raises(ApplicationError):
            await activity_env.run(
                boot_activities.download_bootresourcefile, param
            )


class TestDeleteBootresourcefileActivity:
    async def test_delete_emits_heartbeat(
        self,
        mocker,
        boot_activities: BootResourcesActivity,
        activity_env: ActivityEnvironment,
    ) -> None:
        mocker.patch("asyncio.sleep")

        heartbeats = []
        activity_env.on_heartbeat = lambda *args: heartbeats.append(args[0])
        param = ResourceDeleteParam(
            files=[ResourceIdentifier("0" * 64, "0" * 7)]
        )
        res = await activity_env.run(
            boot_activities.delete_bootresourcefile, param
        )
        assert res is True

        assert heartbeats == ["File deleted"]

    async def test_delete(
        self,
        mock_local_file: Mock,
        boot_activities: BootResourcesActivity,
        activity_env: ActivityEnvironment,
    ) -> None:
        param = ResourceDeleteParam(
            files=[ResourceIdentifier("0" * 64, "0" * 7)]
        )
        res = await activity_env.run(
            boot_activities.delete_bootresourcefile, param
        )
        assert res is True
        mock_local_file.unlink.assert_called_once()


class TestFetchManifestAndUpdateCacheActivity:
    async def test_calls_service_layer(
        self,
        boot_activities: BootResourcesActivity,
        services_mock: ServiceCollectionV3,
        activity_env: ActivityEnvironment,
    ) -> None:
        mock_boot_source = Mock(BootSource)
        mock_ss_products_list = Mock(SimpleStreamsProductListType)
        mock_ss_products_list.products = [Mock(BootloaderProduct)]
        services_mock.image_sync = Mock(ImageSyncService)
        services_mock.image_sync.check_commissioning_series_selected.return_value = True
        services_mock.image_sync.filter_products_for_selection.return_value = [
            mock_ss_products_list
        ]
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.get_many.return_value = [mock_boot_source]
        services_mock.image_manifests = Mock(ImageManifestsService)
        services_mock.boot_source_cache = Mock(BootSourceCacheService)
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.notifications = Mock(NotificationsService)
        services_mock.notifications.delete_one.return_value = None

        heartbeats = []
        activity_env.on_heartbeat = lambda *args: heartbeats.append(args[0])
        await activity_env.run(boot_activities.fetch_manifest_and_update_cache)

        assert heartbeats == ["Downloaded images descriptions"]
        services_mock.image_sync.ensure_boot_source_definition.assert_awaited_once()
        services_mock.boot_sources.get_many.assert_awaited_once()
        services_mock.image_manifests.fetch_and_update.assert_awaited_once()
        services_mock.boot_source_cache.update_from_image_manifest.assert_awaited_once()
        services_mock.image_sync.sync_boot_source_selections_from_msm.assert_awaited_once()
        services_mock.image_sync.check_commissioning_series_selected.assert_awaited_once()
        services_mock.boot_source_selections.ensure_selections_from_legacy.assert_awaited_once()
        services_mock.notifications.delete_one.assert_awaited_once_with(
            query=QuerySpec(
                where=NotificationsClauseFactory.with_ident(
                    NotificationComponent.FETCH_IMAGE_MANIFEST
                )
            ),
        )

    async def test_creates_notification_if_exception_is_raised(
        self,
        boot_activities: BootResourcesActivity,
        services_mock: ServiceCollectionV3,
        activity_env: ActivityEnvironment,
    ) -> None:
        services_mock.image_sync = Mock(ImageSyncService)
        services_mock.image_sync.check_commissioning_series_selected.return_value = True
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.get_many.return_value = [
            BootSource(
                id=1,
                url="http://foo.com",
                keyring_filename="/tmp/foo",
                keyring_data=None,
                priority=1,
                skip_keyring_verification=True,
            )
        ]
        services_mock.image_manifests = Mock(ImageManifestsService)
        services_mock.image_manifests.fetch_and_update.side_effect = (
            SimpleStreamsClientException()
        )
        services_mock.notifications = Mock(NotificationsService)
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )

        await activity_env.run(boot_activities.fetch_manifest_and_update_cache)

        services_mock.notifications.create_or_update.assert_awaited_once_with(
            query=QuerySpec(
                where=NotificationsClauseFactory.with_ident(
                    NotificationComponent.FETCH_IMAGE_MANIFEST
                )
            ),
            builder=NotificationBuilder(
                ident=NotificationComponent.FETCH_IMAGE_MANIFEST,
                users=True,
                admins=True,
                message="Failed to fetch image manifest for boot source with url http://foo.com. Check the logs for more details.",
                context={},
                user_id=None,
                category=NotificationCategoryEnum.ERROR,
                dismissable=True,
            ),
        )


@pytest.mark.parametrize("http_proxy", ["http://proxy.com", None])
class TestGetFilesToDownloadForSelectionActivity:
    async def test_calls_service_layer(
        self,
        boot_activities: BootResourcesActivity,
        services_mock: ServiceCollectionV3,
        activity_env: ActivityEnvironment,
        resource_download_param: ResourceDownloadParam,
        http_proxy: str | None,
    ) -> None:
        boot_source = BootSource(
            id=1,
            url="http://foo.com",
            keyring_filename="/tmp/foo",
            keyring_data=None,
            priority=1,
            skip_keyring_verification=True,
        )
        boot_source_selection = BootSourceSelection(
            id=1,
            os="ubuntu",
            arch="amd64",
            release="noble",
            boot_source_id=boot_source.id,
            legacyselection_id=1,
        )

        mock_product = Mock(BootloaderProduct)
        mock_ss_products_list = Mock(SimpleStreamsProductListType)
        mock_ss_products_list.products = [mock_product]

        image_manifest = Mock(ImageManifest)
        image_manifest.manifest = [mock_ss_products_list]

        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.get_by_id.return_value = (
            boot_source_selection
        )
        services_mock.boot_source_selections.get_one.return_value = (
            BootSourceSelection(
                id=2,
                os="ubuntu",
                arch="amd64",
                release="noble",
                boot_source_id=2,
                legacyselection_id=1,
            )
        )

        services_mock.boot_resources = Mock(BootResourceService)

        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.get_by_id.return_value = boot_source
        services_mock.image_manifests = Mock(ImageManifestsService)
        services_mock.image_manifests.get_or_fetch.return_value = (
            image_manifest,
            False,
        )
        services_mock.image_manifests._get_http_proxy.return_value = http_proxy
        services_mock.image_sync = Mock(ImageSyncService)
        services_mock.image_sync.filter_products_for_selection.return_value = [
            mock_ss_products_list
        ]
        services_mock.image_sync.get_files_to_download_from_product_list.return_value = [
            resource_download_param
        ]

        result = await activity_env.run(
            boot_activities.get_files_to_download_for_selection,
            GetFilesToDownloadForSelectionParam(
                selection_id=1,
            ),
        )

        resources_to_download = result.resources
        assert len(resources_to_download) == 1
        assert resources_to_download[0].http_proxy == http_proxy

        services_mock.boot_source_selections.get_by_id.assert_awaited_once_with(
            1
        )
        services_mock.boot_source_selections.get_one.assert_awaited_once_with(
            query=QuerySpec(
                where=BootSourceSelectionClauseFactory.and_clauses(
                    [
                        BootSourceSelectionClauseFactory.with_os(
                            boot_source_selection.os
                        ),
                        BootSourceSelectionClauseFactory.with_arch(
                            boot_source_selection.arch
                        ),
                        BootSourceSelectionClauseFactory.with_release(
                            boot_source_selection.release
                        ),
                        BootSourceSelectionClauseFactory.not_clause(
                            BootSourceSelectionClauseFactory.with_id(
                                boot_source_selection.id
                            )
                        ),
                    ]
                )
            )
        )
        services_mock.boot_resources.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceClauseFactory.with_selection_id(2)
            )
        )
        services_mock.boot_sources.get_by_id.assert_awaited_once_with(1)
        services_mock.image_manifests.get_or_fetch.assert_awaited_once_with(
            boot_source
        )
        services_mock.image_sync.filter_products_for_selection.assert_called_once()
        services_mock.image_sync.get_files_to_download_from_product_list.assert_awaited_once()
        services_mock.image_manifests._get_http_proxy.assert_awaited_once()


class TestGetManuallyUploadedResourcesActivity:
    async def test_calls_service_layer(
        self,
        boot_activities: BootResourcesActivity,
        services_mock: ServiceCollectionV3,
        activity_env: ActivityEnvironment,
    ) -> None:
        boot_resource = BootResource(
            id=1,
            rtype=BootResourceType.UPLOADED,
            name="test",
            architecture="amd64/generic",
            extra={},
            rolling=False,
            base_image="",
        )
        boot_resource_set = BootResourceSet(
            id=1,
            version="20251028",
            label="uploaded",
            resource_id=boot_resource.id,
        )
        boot_resource_files = [
            BootResourceFile(
                id=i,
                filename=f"test-{i}",
                filetype=BootResourceFileType.SQUASHFS_IMAGE,
                sha256=str(i) * 64,
                size=100,
                extra={},
                filename_on_disk=str(i) * 7,
            )
            for i in range(3)
        ]
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_many = AsyncMock(
            return_value=[boot_resource]
        )

        services_mock.boot_resource_sets = Mock(BootResourceSetsService)
        services_mock.boot_resource_sets.get_latest_for_boot_resource = (
            AsyncMock(return_value=boot_resource_set)
        )
        services_mock.boot_resource_files = Mock(BootResourceFilesService)
        services_mock.boot_resource_files.get_files_in_resource_set = (
            AsyncMock(return_value=boot_resource_files)
        )

        resources_result = await activity_env.run(
            boot_activities.get_manually_uploaded_resources
        )

        assert resources_result.resources == [
            ResourceDownloadParam(
                rfile_ids=[file.id],
                source_list=[],  # this will get overridden with the region url
                sha256=file.sha256,
                filename_on_disk=file.filename_on_disk,
                total_size=file.size,
            )
            for file in boot_resource_files
        ]

        services_mock.boot_resources.get_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceClauseFactory.with_rtype(
                    BootResourceType.UPLOADED
                )
            )
        )

        services_mock.boot_resource_sets.get_latest_for_boot_resource.assert_awaited_once_with(
            boot_resource.id
        )
        services_mock.boot_resource_files.get_files_in_resource_set.assert_awaited_once_with(
            boot_resource_set.id
        )


class TestDeletePendingFilesForSelectionActivity:
    async def test_calls_image_sync_service(
        self,
        boot_activities: BootResourcesActivity,
        services_mock: ServiceCollectionV3,
        activity_env: ActivityEnvironment,
    ) -> None:
        services_mock.boot_resource_files = Mock(BootResourceFilesService)

        await activity_env.run(
            boot_activities.delete_pending_files,
            DeletePendingFilesParam(resources=[]),
        )
        services_mock.boot_resource_files.delete_many.assert_awaited_once()


class TestCleanupOldBootResourcesActivity:
    async def test_calls_image_sync_service(
        self,
        boot_activities: BootResourcesActivity,
        services_mock: ServiceCollectionV3,
        activity_env: ActivityEnvironment,
    ) -> None:
        services_mock.image_sync = Mock(ImageSyncService)
        services_mock.temporal = Mock(TemporalService)

        await activity_env.run(
            boot_activities.cleanup_boot_resource_sets_for_selection,
            CleanupBootResourceSetsParam(selection_id=1),
        )
        services_mock.image_sync.cleanup_boot_resource_sets_for_selection.assert_awaited_once()


class TestGetAllHighestPrioritySelectionsActivity:
    async def test_calls_service(
        self,
        boot_activities: BootResourcesActivity,
        services_mock: ServiceCollectionV3,
        activity_env: ActivityEnvironment,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )

        await activity_env.run(
            boot_activities.get_all_highest_priority_selections,
        )

        services_mock.boot_source_selections.get_all_highest_priority.assert_awaited_once()


class TestRegisterNotificationErrorActivity:
    async def test_calls_service(
        self,
        boot_activities: BootResourcesActivity,
        services_mock: Mock,
        activity_env: ActivityEnvironment,
    ) -> None:
        services_mock.notifications = Mock(NotificationsService)

        await activity_env.run(
            boot_activities.register_notification,
            RegisterNotificationParam(
                ident=NotificationComponent.REGION_IMAGE_SYNC,
                err_msg="Error",
                category=NotificationCategoryEnum.ERROR,
                dismissable=False,
            ),
        )

        services_mock.notifications.create_or_update.assert_awaited_once_with(
            query=QuerySpec(
                where=NotificationsClauseFactory.with_ident(
                    NotificationComponent.REGION_IMAGE_SYNC
                )
            ),
            builder=NotificationBuilder(
                ident=NotificationComponent.REGION_IMAGE_SYNC,
                users=True,
                admins=True,
                message="Error",
                context={},
                user_id=None,
                category=NotificationCategoryEnum.ERROR,
                dismissable=False,
            ),
        )


class TestDeleteNotificationErrorActivity:
    async def test_calls_service(
        self,
        boot_activities: BootResourcesActivity,
        services_mock: Mock,
        activity_env: ActivityEnvironment,
    ) -> None:
        services_mock.notifications = Mock(NotificationsService)

        await activity_env.run(
            boot_activities.delete_notification,
            DeleteNotificationParam(
                ident=NotificationComponent.REGION_IMAGE_SYNC
            ),
        )

        services_mock.notifications.delete_one.assert_awaited_once_with(
            query=QuerySpec(
                where=NotificationsClauseFactory.with_ident(
                    NotificationComponent.REGION_IMAGE_SYNC
                )
            ),
        )


@pytest.fixture
async def env() -> AsyncGenerator[WorkflowEnvironment, None]:
    env = await WorkflowEnvironment.start_time_skipping()
    yield env
    await env.shutdown()


@pytest.fixture
async def client(env: WorkflowEnvironment) -> Client:
    config = env.client.config()
    config["data_converter"] = pydantic_data_converter
    client = Client(**config)
    return client


@dataclass
class ActivityResult:
    result: Any = None
    side_effect: list = field(default_factory=list)
    sleep: int = 0

    async def get_result(self) -> Any:
        if self.sleep > 0:
            for _ in range(self.sleep):
                await asyncio.sleep(1)
                # In order for an activity to be cancelled, it must heartbeat (https://docs.temporal.io/activity-execution#cancellation)
                activity.heartbeat()
        if self.side_effect:
            value = self.side_effect.pop(0)
            if isinstance(value, BaseException):
                raise value
            else:
                return value
        return self.result


class MockActivities:
    """Class that mocks the activities and allows changing their return value.

    Use the `results` field to change the outcome of a specific activity.
    `results` is a dict with the key being the activity name and the value being an `ActivityResult`.

    """

    results: dict[str, ActivityResult]

    def __init__(self):
        self.results = {
            GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME: ActivityResult(
                result={}
            ),
            DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME: ActivityResult(
                result=True
            ),
            GET_SYNCED_REGIONS_ACTIVITY_NAME: ActivityResult(result=[]),
            FETCH_MANIFEST_AND_UPDATE_CACHE_ACTIVITY_NAME: ActivityResult(
                result=None
            ),
            GET_HIGHEST_PRIORITY_SELECTIONS_ACTIVITY_NAME: ActivityResult(
                result=[1, 2]
            ),
            GET_FILES_TO_DOWNLOAD_FOR_SELECTION_ACTIVITY_NAME: ActivityResult(
                side_effect=[
                    GetFilesToDownloadReturnValue(
                        resources=[
                            ResourceDownloadParam(
                                rfile_ids=[1],
                                source_list=["http://maas-image-stream.io"],
                                sha256="1" * 64,
                                filename_on_disk="1" * 7,
                                total_size=100,
                            )
                        ]
                    ),
                    GetFilesToDownloadReturnValue(
                        resources=[
                            ResourceDownloadParam(
                                rfile_ids=[2],
                                source_list=["http://maas-image-stream.io"],
                                sha256="2" * 64,
                                filename_on_disk="2" * 7,
                                total_size=100,
                            )
                        ]
                    ),
                ]
            ),
            GET_LOCAL_BOOT_RESOURCES_PARAMS_ACTIVITY_NAME: ActivityResult(
                result=GetLocalBootResourcesParamReturnValue(resources=[])
            ),
            DELETE_PENDING_FILES_FOR_SELECTION_ACTIVITY_NAME: ActivityResult(
                result=None
            ),
            CLEANUP_BOOT_RESOURCE_SETS_FOR_SELECTION_ACTIVITY_NAME: ActivityResult(
                result=None
            ),
            REGISTER_NOTIFICATION_ACTIVITY_NAME: ActivityResult(result=None),
            DELETE_NOTIFICATION_ACTIVITY_NAME: ActivityResult(result=None),
            DELETE_BOOTRESOURCEFILE_ACTIVITY_NAME: ActivityResult(result=True),
        }

    async def _execute_activity(
        self, activity_name: str, *args, **kwargs
    ) -> Any:
        return await self.results[activity_name].get_result()

    @staticmethod
    def _mock_activity_method(activity_name: str):
        """Utility to dynamically define activities and pick results from `MockActivities.results`"""

        async def method(self, *args, **kwargs):
            return await self._execute_activity(activity_name)

        return activity.defn(name=activity_name)(method)

    get_bootresourcefile_endpoints = _mock_activity_method(
        GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME
    )
    download_bootresourcefile = _mock_activity_method(
        DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME
    )
    get_synced_regions_for_file = _mock_activity_method(
        GET_SYNCED_REGIONS_ACTIVITY_NAME
    )
    fetch_manifest_and_update_cache = _mock_activity_method(
        FETCH_MANIFEST_AND_UPDATE_CACHE_ACTIVITY_NAME
    )
    get_all_highest_priority_selections = _mock_activity_method(
        GET_HIGHEST_PRIORITY_SELECTIONS_ACTIVITY_NAME
    )
    get_files_to_download_for_selection = _mock_activity_method(
        GET_FILES_TO_DOWNLOAD_FOR_SELECTION_ACTIVITY_NAME
    )
    get_manually_uploaded_resources = _mock_activity_method(
        GET_LOCAL_BOOT_RESOURCES_PARAMS_ACTIVITY_NAME
    )
    delete_pending_files = _mock_activity_method(
        DELETE_PENDING_FILES_FOR_SELECTION_ACTIVITY_NAME
    )
    cleanup_boot_resource_sets_for_selection = _mock_activity_method(
        CLEANUP_BOOT_RESOURCE_SETS_FOR_SELECTION_ACTIVITY_NAME
    )
    register_notification = _mock_activity_method(
        REGISTER_NOTIFICATION_ACTIVITY_NAME
    )
    delete_notification = _mock_activity_method(
        DELETE_NOTIFICATION_ACTIVITY_NAME
    )
    delete_bootresourcefile = _mock_activity_method(
        DELETE_BOOTRESOURCEFILE_ACTIVITY_NAME
    )


@pytest.fixture
def region1_system_id() -> str:
    return "abcdef"


@pytest.fixture
def region2_system_id() -> str:
    return "ghijkl"


@pytest.fixture
def region3_system_id() -> str:
    return "mnopqr"


@pytest.fixture
def endpoints_single_region(region1_system_id: str):
    return {region1_system_id: ["http://10.0.0.1:5240/MAAS/boot-resources/"]}


@pytest.fixture
def endpoints_three_regions(
    region1_system_id: str, region2_system_id: str, region3_system_id: str
):
    """Three region endpoint configuration"""
    return {
        region1_system_id: ["http://10.0.0.1:5240/MAAS/boot-resources/"],
        region2_system_id: ["http://10.0.0.2:5240/MAAS/boot-resources/"],
        region3_system_id: ["http://10.0.0.3:5240/MAAS/boot-resources/"],
    }


@pytest.fixture
def resource_download_param():
    return ResourceDownloadParam(
        rfile_ids=[1],
        source_list=["http://maas-image-stream.io"],
        sha256="0" * 64,
        filename_on_disk="0" * 7,
        total_size=100,
    )


@pytest.fixture
def sync_request(resource_download_param: ResourceDownloadParam):
    return SyncRequestParam(resource=resource_download_param)


@pytest.fixture
def mock_activities():
    return MockActivities()


@pytest.fixture
async def _shared_queue_worker(
    client: Client,
    mock_activities: MockActivities,
    worker_test_interceptor: WorkerTestInterceptor,
):
    """Temporal worker that listens on the shared task queue."""
    async with Worker(
        client=client,
        task_queue=REGION_TASK_QUEUE,
        workflows=[
            DeleteBootResourceWorkflow,
            DownloadBootResourceWorkflow,
            SyncRemoteBootResourcesWorkflow,
            SyncBootResourcesWorkflow,
            SyncSelectionWorkflow,
            SyncAllLocalBootResourcesWorkflow,
            MasterImageSyncWorkflow,
            FetchManifestWorkflow,
        ],
        activities=[
            mock_activities.fetch_manifest_and_update_cache,
            mock_activities.download_bootresourcefile,
            mock_activities.get_bootresourcefile_endpoints,
            mock_activities.get_files_to_download_for_selection,
            mock_activities.get_synced_regions_for_file,
            mock_activities.get_all_highest_priority_selections,
            mock_activities.get_manually_uploaded_resources,
            mock_activities.delete_pending_files,
            mock_activities.cleanup_boot_resource_sets_for_selection,
            mock_activities.register_notification,
            mock_activities.delete_notification,
        ],
        workflow_runner=custom_sandbox_runner(),
        interceptors=[worker_test_interceptor],
    ):
        yield


def _make_region_worker(
    client: Client,
    system_id: str,
    mock_activities: MockActivities,
    worker_test_interceptor: WorkerTestInterceptor,
) -> Worker:
    return Worker(
        client=client,
        task_queue=f"region:{system_id}",
        workflows=[
            DownloadBootResourceWorkflow,
        ],
        activities=[
            mock_activities.delete_bootresourcefile,
            mock_activities.download_bootresourcefile,
        ],
        workflow_runner=custom_sandbox_runner(),
        interceptors=[worker_test_interceptor],
    )


@pytest.fixture
async def single_region_workers(
    client: Client,
    region1_system_id: str,
    endpoints_single_region: dict[str, list],
    mock_activities: MockActivities,
    worker_test_interceptor: WorkerTestInterceptor,
    _shared_queue_worker,
):
    """Setup the temporal workers for a single region scenario."""
    mock_activities.results[GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME] = (
        ActivityResult(result=endpoints_single_region)
    )
    async with _make_region_worker(
        client, region1_system_id, mock_activities, worker_test_interceptor
    ):
        yield


@pytest.fixture
async def three_regions_workers(
    client: Client,
    region1_system_id: str,
    region2_system_id: str,
    region3_system_id: str,
    endpoints_three_regions: dict[str, list],
    mock_activities: MockActivities,
    worker_test_interceptor: WorkerTestInterceptor,
    _shared_queue_worker,
):
    """Setup the temporal workers for an HA scenario."""
    mock_activities.results[GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME] = (
        ActivityResult(result=endpoints_three_regions)
    )
    async with (
        _make_region_worker(
            client, region1_system_id, mock_activities, worker_test_interceptor
        ),
        _make_region_worker(
            client, region2_system_id, mock_activities, worker_test_interceptor
        ),
        _make_region_worker(
            client, region3_system_id, mock_activities, worker_test_interceptor
        ),
    ):
        yield


class TestFetchManifestWorkflow:
    @pytest.mark.asyncio
    async def test_retry_activity_if_it_fails(
        self,
        client: Client,
        single_region_workers,
        mock_activities: MockActivities,
    ):
        mock_activities.results[
            FETCH_MANIFEST_AND_UPDATE_CACHE_ACTIVITY_NAME
        ] = ActivityResult(
            side_effect=[
                Exception(),
                Exception(),
                None,
            ]
        )
        await client.execute_workflow(
            FetchManifestWorkflow.run,
            id="test-fail-maximum-attempts",
            task_queue=REGION_TASK_QUEUE,
        )

    @pytest.mark.asyncio
    async def test_workflow_fails_after_three_activity_retries(
        self,
        client: Client,
        single_region_workers,
        mock_activities: MockActivities,
    ):
        mock_activities.results[
            FETCH_MANIFEST_AND_UPDATE_CACHE_ACTIVITY_NAME
        ] = ActivityResult(
            side_effect=[
                Exception(),
                Exception(),
                Exception(),
            ]
        )
        with pytest.raises(WorkflowFailureError):
            await client.execute_workflow(
                FetchManifestWorkflow.run,
                id="test-fail-maximum-attempts",
                task_queue=REGION_TASK_QUEUE,
            )


class TestSyncBootResourcesWorkflow:
    @pytest.mark.asyncio
    async def test_single_region_sync(
        self,
        client: Client,
        single_region_workers,
        temporal_calls: TemporalCalls,
        sync_request: SyncRequestParam,
    ):
        await client.execute_workflow(
            SyncBootResourcesWorkflow.run,
            sync_request,
            id="test-sync-single",
            task_queue=REGION_TASK_QUEUE,
        )

        # Only one region, nothing to sync
        temporal_calls.assert_activity_calls(
            [GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME]
        )
        temporal_calls.assert_child_workflow_calls([])

    @pytest.mark.asyncio
    async def test_three_region_sync_with_missing_regions(
        self,
        client: Client,
        three_regions_workers,
        sync_request: SyncRequestParam,
        region1_system_id: str,
        temporal_calls: TemporalCalls,
        mock_activities: MockActivities,
    ):
        # Only one synced region
        mock_activities.results[GET_SYNCED_REGIONS_ACTIVITY_NAME] = (
            ActivityResult(result=[region1_system_id])
        )
        await client.execute_workflow(
            SyncBootResourcesWorkflow.run,
            sync_request,
            id="test-sync-three",
            task_queue=REGION_TASK_QUEUE,
        )

        temporal_calls.assert_activity_calls(
            [
                GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME,
                GET_SYNCED_REGIONS_ACTIVITY_NAME,
                DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME,
                DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME,
            ]
        )
        temporal_calls.assert_child_workflow_called_times(
            DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME, times=2
        )

    @pytest.mark.asyncio
    async def test_failed_sync_to_regions(
        self,
        client: Client,
        three_regions_workers,
        sync_request: SyncRequestParam,
        region1_system_id: str,
        mock_activities: MockActivities,
    ):
        """Test workflow fails when sync to other regions fails"""
        mock_activities.results[GET_SYNCED_REGIONS_ACTIVITY_NAME] = (
            ActivityResult(result=[region1_system_id])
        )
        # Make the download wf fail
        mock_activities.results[DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME] = (
            ActivityResult(result=False)
        )

        with (
            pytest.raises(WorkflowFailureError) as exc_info,
        ):
            await client.execute_workflow(
                SyncBootResourcesWorkflow.run,
                sync_request,
                id="test-failed-sync",
                task_queue=REGION_TASK_QUEUE,
            )

            # The exception returned is WorkflowFailureError.
            # The ApplicationError we raise is available in the `cause` attribute.
            assert "could not be synced" in str(exc_info.value.cause.message)
            assert exc_info.value.cause.non_retryable

    @pytest.mark.asyncio
    async def test_no_synced_regions_available(
        self,
        client: Client,
        sync_request: SyncRequestParam,
        three_regions_workers,
        mock_activities: MockActivities,
    ):
        """Test workflow fails when no regions have the complete file"""
        # No region have the file
        mock_activities.results[GET_SYNCED_REGIONS_ACTIVITY_NAME] = (
            ActivityResult(result=[])
        )

        with (
            pytest.raises(WorkflowFailureError) as exc_info,
        ):
            await client.execute_workflow(
                SyncBootResourcesWorkflow.run,
                sync_request,
                id="test-no-synced-regions",
                task_queue=REGION_TASK_QUEUE,
            )

            # The exception returned is WorkflowFailureError.
            # The ApplicationError we raise is available in the `cause` attribute.
            assert "has no complete copy available" in str(
                exc_info.value.cause.message
            )
            assert not exc_info.value.cause.non_retryable


class TestSyncRemoteBootResourcesWorkflow:
    @pytest.mark.asyncio
    async def test_remote_sync_signals_master(
        self,
        client: Client,
        single_region_workers,
        temporal_calls: TemporalCalls,
        sync_request: SyncRequestParam,
    ):
        await client.execute_workflow(
            SyncRemoteBootResourcesWorkflow.run,
            sync_request,
            id="test-sync-single",
            task_queue=REGION_TASK_QUEUE,
        )

        temporal_calls.assert_child_workflow_calls(
            [
                DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME,
                SYNC_BOOTRESOURCES_WORKFLOW_NAME,
            ]
        )

    @pytest.mark.asyncio
    async def test_failed_upstream_download(
        self,
        client: Client,
        single_region_workers,
        sync_request: SyncRequestParam,
        mock_activities: MockActivities,
    ):
        """Test workflow fails when upstream download fails"""
        mock_activities.results[DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME] = (
            ActivityResult(result=False)
        )
        with (
            pytest.raises(WorkflowFailureError) as exc_info,
        ):
            await client.execute_workflow(
                SyncRemoteBootResourcesWorkflow.run,
                sync_request,
                id="test-failed-download",
                task_queue=REGION_TASK_QUEUE,
            )

            # The exception returned is WorkflowFailureError.
            # The ApplicationError we raise is available in the `cause` attribute.
            assert "could not be downloaded" in exc_info.value.cause.message
            assert exc_info.value.cause.non_retryable


class TestSyncSelectionWorkflow:
    """Tests for selection-based image sync"""

    async def test_nothing_to_download(
        self,
        client: Client,
        single_region_workers,
        temporal_calls: TemporalCalls,
        mock_activities: MockActivities,
    ):
        mock_activities.results[
            GET_HIGHEST_PRIORITY_SELECTIONS_ACTIVITY_NAME
        ] = ActivityResult(result=[1])
        mock_activities.results[
            GET_FILES_TO_DOWNLOAD_FOR_SELECTION_ACTIVITY_NAME
        ] = ActivityResult(result=GetFilesToDownloadReturnValue(resources=[]))

        await client.execute_workflow(
            SyncSelectionWorkflow.run,
            SyncSelectionParam(selection_id=1),
            id="test-nothing-to-download",
            task_queue=REGION_TASK_QUEUE,
        )

        temporal_calls.assert_child_workflow_not_called(
            SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME
        )

    async def test_single_region(
        self,
        client: Client,
        single_region_workers,
        temporal_calls: TemporalCalls,
    ):
        await client.execute_workflow(
            SyncSelectionWorkflow.run,
            SyncSelectionParam(selection_id=1),
            id="test-nothing-to-download",
            task_queue=REGION_TASK_QUEUE,
        )

        temporal_calls.assert_activity_calls(
            [
                GET_FILES_TO_DOWNLOAD_FOR_SELECTION_ACTIVITY_NAME,
                DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME,  # SyncBootResources wf
                GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME,  # SyncBootResources wf
                DELETE_NOTIFICATION_ACTIVITY_NAME,
                CLEANUP_BOOT_RESOURCE_SETS_FOR_SELECTION_ACTIVITY_NAME,
            ]
        )

        temporal_calls.assert_child_workflow_calls(
            [
                SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME,
                DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME,
                SYNC_BOOTRESOURCES_WORKFLOW_NAME,
            ]
        )

    async def test_three_regions(
        self,
        client: Client,
        three_regions_workers,
        temporal_calls: TemporalCalls,
        region1_system_id: str,
        mock_activities: MockActivities,
    ):
        # One synced region after the download
        mock_activities.results[GET_SYNCED_REGIONS_ACTIVITY_NAME] = (
            ActivityResult(result=[region1_system_id])
        )
        await client.execute_workflow(
            SyncSelectionWorkflow.run,
            SyncSelectionParam(selection_id=1),
            id="test-nothing-to-download",
            task_queue=REGION_TASK_QUEUE,
        )

        temporal_calls.assert_activity_calls(
            [
                GET_FILES_TO_DOWNLOAD_FOR_SELECTION_ACTIVITY_NAME,
                DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME,  # SyncRemoteBootResources wf
                GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME,  # SyncBootResources wf
                GET_SYNCED_REGIONS_ACTIVITY_NAME,  # SyncBootResources wf
                DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME,  # SyncBootResources wf
                DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME,  # SyncBootResources wf
                DELETE_NOTIFICATION_ACTIVITY_NAME,
                CLEANUP_BOOT_RESOURCE_SETS_FOR_SELECTION_ACTIVITY_NAME,
            ]
        )

        temporal_calls.assert_child_workflow_calls(
            [
                SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME,
                DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME,
                SYNC_BOOTRESOURCES_WORKFLOW_NAME,
                DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME,
                DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME,
            ]
        )

    async def test_files_are_deleted_if_wf_cancelled(
        self,
        client: Client,
        single_region_workers,
        temporal_calls: TemporalCalls,
        mock_activities: MockActivities,
    ) -> None:
        mock_activities.results[DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME] = (
            ActivityResult(result=True, sleep=5)
        )
        workflow_handle = await client.start_workflow(
            SyncSelectionWorkflow.run,
            SyncSelectionParam(selection_id=1),
            id="test-cancelled-cleanup",
            task_queue=REGION_TASK_QUEUE,
        )
        await asyncio.sleep(1)
        # We expect the workflow to be in a completed status, as we handle the exceptions
        await asyncio.wait_for(
            cancel_workflow_immediately(
                workflow_handle,
                expected_status=WorkflowExecutionStatus.COMPLETED,
            ),
            timeout=5,
        )

        await workflow_handle.result()

        temporal_calls.assert_activity_called_once(
            DELETE_PENDING_FILES_FOR_SELECTION_ACTIVITY_NAME
        )
        temporal_calls.assert_activity_called_once(
            CLEANUP_BOOT_RESOURCE_SETS_FOR_SELECTION_ACTIVITY_NAME
        )
        # No notification for cancellation
        temporal_calls.assert_activity_not_called(
            REGISTER_NOTIFICATION_ACTIVITY_NAME
        )

    @pytest.mark.asyncio
    async def test_creates_notification_on_error(
        self,
        client: Client,
        single_region_workers,
        temporal_calls: TemporalCalls,
        mock_activities: MockActivities,
    ):
        mock_activities.results[DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME] = (
            ActivityResult(result=False)
        )
        await client.execute_workflow(
            SyncSelectionWorkflow.run,
            SyncSelectionParam(selection_id=1),
            id="test-error-notification",
            task_queue=REGION_TASK_QUEUE,
        )

        temporal_calls.assert_activity_called_once(
            REGISTER_NOTIFICATION_ACTIVITY_NAME,
        )

    @pytest.mark.asyncio
    async def test_doesnt_create_notification_on_cancellation(
        self,
        client: Client,
        single_region_workers,
        temporal_calls: TemporalCalls,
        mock_activities: MockActivities,
    ):
        mock_activities.results[DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME] = (
            ActivityResult(result=True, sleep=5)
        )
        sync_selection_handle = await client.start_workflow(
            SyncSelectionWorkflow.run,
            SyncSelectionParam(selection_id=1),
            id="test-error-notification",
            task_queue=REGION_TASK_QUEUE,
        )

        await asyncio.sleep(1)
        await asyncio.wait_for(
            cancel_workflow_immediately(
                sync_selection_handle,
                expected_status=WorkflowExecutionStatus.COMPLETED,
            ),
            timeout=5,
        )

        await sync_selection_handle.result()

        temporal_calls.assert_activity_called_once(
            DELETE_PENDING_FILES_FOR_SELECTION_ACTIVITY_NAME
        )
        temporal_calls.assert_activity_not_called(
            REGISTER_NOTIFICATION_ACTIVITY_NAME,
        )


class TestSyncAllBootResourcesWorkflow:
    async def test_no_local_resources(
        self,
        client: Client,
        single_region_workers,
        temporal_calls: TemporalCalls,
    ) -> None:
        await client.execute_workflow(
            SyncAllLocalBootResourcesWorkflow.run,
            id="test-sync-all-local",
            task_queue=REGION_TASK_QUEUE,
        )

        temporal_calls.assert_activity_called_once(
            GET_LOCAL_BOOT_RESOURCES_PARAMS_ACTIVITY_NAME
        )
        temporal_calls.assert_child_workflow_not_called(
            SYNC_BOOTRESOURCES_WORKFLOW_NAME
        )

    async def test_single_region(
        self,
        client: Client,
        single_region_workers,
        temporal_calls: TemporalCalls,
        mock_activities: MockActivities,
        resource_download_param: ResourceDownloadParam,
    ) -> None:
        mock_activities.results[
            GET_LOCAL_BOOT_RESOURCES_PARAMS_ACTIVITY_NAME
        ] = ActivityResult(
            result=GetLocalBootResourcesParamReturnValue(
                resources=[resource_download_param]
            )
        )
        await client.execute_workflow(
            SyncAllLocalBootResourcesWorkflow.run,
            id="test-sync-all-local",
            task_queue=REGION_TASK_QUEUE,
        )

        temporal_calls.assert_activity_called_once(
            GET_LOCAL_BOOT_RESOURCES_PARAMS_ACTIVITY_NAME
        )
        temporal_calls.assert_child_workflow_called_once(
            SYNC_BOOTRESOURCES_WORKFLOW_NAME
        )
        # Single region, nothing to sync
        temporal_calls.assert_child_workflow_not_called(
            DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME
        )

    async def test_three_region(
        self,
        client: Client,
        three_regions_workers,
        temporal_calls: TemporalCalls,
        region1_system_id: str,
        mock_activities: MockActivities,
        resource_download_param: ResourceDownloadParam,
    ) -> None:
        mock_activities.results[
            GET_LOCAL_BOOT_RESOURCES_PARAMS_ACTIVITY_NAME
        ] = ActivityResult(
            result=GetLocalBootResourcesParamReturnValue(
                resources=[resource_download_param]
            )
        )
        mock_activities.results[GET_SYNCED_REGIONS_ACTIVITY_NAME] = (
            ActivityResult(result=[region1_system_id])
        )
        await client.execute_workflow(
            SyncAllLocalBootResourcesWorkflow.run,
            id="test-sync-all-local",
            task_queue=REGION_TASK_QUEUE,
        )

        temporal_calls.assert_activity_called_once(
            GET_LOCAL_BOOT_RESOURCES_PARAMS_ACTIVITY_NAME
        )
        temporal_calls.assert_child_workflow_called_once(
            SYNC_BOOTRESOURCES_WORKFLOW_NAME
        )
        # two regions need the file
        temporal_calls.assert_child_workflow_called_times(
            DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME, times=2
        )


class TestMasterImageSyncWorkflow:
    """Tests for MasterImageSyncWorkflow"""

    @pytest.mark.asyncio
    async def test_single_region_master_workflow(
        self,
        client: Client,
        single_region_workers,
        temporal_calls: TemporalCalls,
    ):
        """Test master workflow with single region"""
        await client.execute_workflow(
            MasterImageSyncWorkflow.run,
            id="test-master-single",
            task_queue=REGION_TASK_QUEUE,
        )

        temporal_calls.assert_child_workflow_called_times(
            SYNC_SELECTION_WORKFLOW_NAME, times=2
        )
        # One download per selection and per region
        temporal_calls.assert_child_workflow_called_times(
            DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME, times=2
        )
        temporal_calls.assert_activity_called_times(
            DELETE_NOTIFICATION_ACTIVITY_NAME, times=2
        )
        temporal_calls.assert_child_workflow_called_once(
            SYNC_ALL_LOCAL_BOOTRESOURCES_WORKFLOW_NAME
        )

    @pytest.mark.asyncio
    async def test_three_region_master_workflow(
        self,
        client: Client,
        three_regions_workers,
        temporal_calls: TemporalCalls,
        region1_system_id: str,
        mock_activities: MockActivities,
    ):
        """Test master workflow schedules sync for all regions"""
        mock_activities.results[GET_SYNCED_REGIONS_ACTIVITY_NAME] = (
            ActivityResult(result=[region1_system_id])
        )
        await client.execute_workflow(
            MasterImageSyncWorkflow.run,
            id="test-master-three",
            task_queue=REGION_TASK_QUEUE,
        )

        temporal_calls.assert_child_workflow_called_times(
            SYNC_SELECTION_WORKFLOW_NAME, times=2
        )
        # One download per selection and per region
        temporal_calls.assert_child_workflow_called_times(
            DOWNLOAD_BOOTRESOURCE_WORKFLOW_NAME, times=6
        )
        temporal_calls.assert_activity_called_times(
            DELETE_NOTIFICATION_ACTIVITY_NAME, times=2
        )
        temporal_calls.assert_child_workflow_called_once(
            SYNC_ALL_LOCAL_BOOTRESOURCES_WORKFLOW_NAME
        )

    @pytest.mark.asyncio
    async def test_cancelling_a_wf_doesnt_cancel_others(
        self,
        client: Client,
        single_region_workers,
        temporal_calls: TemporalCalls,
        mock_activities: MockActivities,
    ):
        mock_activities.results[DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME] = (
            ActivityResult(result=True, sleep=3)
        )
        master_handle = await client.start_workflow(
            MasterImageSyncWorkflow.run,
            id="test-wf-cancelation",
            task_queue=REGION_TASK_QUEUE,
        )

        # the selection ids returned by mock_activities are the ones with id 1 and 2
        h1 = client.get_workflow_handle("sync-selection:1")
        h2 = client.get_workflow_handle("sync-selection:2")

        await asyncio.sleep(1)
        # We expect the workflow to be in a completed state because exceptions
        # are handled and not re-raised
        await asyncio.wait_for(
            cancel_workflow_immediately(
                h1, expected_status=WorkflowExecutionStatus.COMPLETED
            ),
            timeout=5,
        )

        await master_handle.result()

        h2_status = await get_workflow_status(h2)
        assert h2_status == WorkflowExecutionStatus.COMPLETED

        # The succesful sync selection wf calls this
        temporal_calls.assert_activity_called_once(
            DELETE_NOTIFICATION_ACTIVITY_NAME
        )
        # The cancelled sync selection wf calls this
        temporal_calls.assert_activity_called_once(
            DELETE_PENDING_FILES_FOR_SELECTION_ACTIVITY_NAME
        )

    @pytest.mark.asyncio
    async def test_already_started_workflow_handling(
        self,
        client: Client,
        single_region_workers,
        temporal_calls: TemporalCalls,
        mock_activities: MockActivities,
    ):
        """Test workflow handles already started child workflows gracefully"""

        # SyncSelectionWorflow for selection with id 1 already running
        await client.start_workflow(
            SYNC_SELECTION_WORKFLOW_NAME,
            SyncSelectionParam(selection_id=1),
            id="sync-selection:1",
            task_queue=REGION_TASK_QUEUE,
        )
        # Should not raise error
        await client.execute_workflow(
            MasterImageSyncWorkflow.run,
            id="test-already-started",
            task_queue=REGION_TASK_QUEUE,
        )

        temporal_calls.assert_child_workflow_called_times(
            SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME, times=2
        )
