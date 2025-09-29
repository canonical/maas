#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from collections.abc import AsyncGenerator
import hashlib
from itertools import islice, repeat
import os
from pathlib import Path
import shutil
from unittest.mock import AsyncMock, call, Mock, patch

import httpx
import pytest
from temporalio import activity
from temporalio.client import (
    Client,
    WorkflowExecution,
    WorkflowFailureError,
    WorkflowHandle,
)
from temporalio.exceptions import (
    ApplicationError,
    CancelledError,
    WorkflowAlreadyStartedError,
)
from temporalio.testing import ActivityEnvironment, WorkflowEnvironment
from temporalio.worker import Worker

from maascommon.enums.events import EventTypeEnum
from maascommon.enums.notifications import (
    NotificationCategoryEnum,
    NotificationComponent,
)
from maascommon.workflows.bootresource import (
    CancelObsoleteDownloadWorkflowsParam,
    CleanupOldBootResourceParam,
    GetFilesToDownloadReturnValue,
    LocalSyncRequestParam,
    MASTER_IMAGE_SYNC_WORKFLOW_NAME,
    ResourceDeleteParam,
    ResourceDownloadParam,
    ResourceIdentifier,
    SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME,
    SyncRequestParam,
)
from maasservicelayer.builders.notifications import NotificationBuilder
from maasservicelayer.db import Database
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.notifications import (
    NotificationsClauseFactory,
)
from maasservicelayer.models.bootsources import BootSource
from maasservicelayer.services import (
    CacheForServices,
    ConfigurationsService,
    ServiceCollectionV3,
)
from maasservicelayer.services.boot_sources import BootSourcesService
from maasservicelayer.services.bootresourcefilesync import (
    BootResourceFileSyncService,
)
from maasservicelayer.services.events import EventsService
from maasservicelayer.services.image_sync import ImageSyncService
from maasservicelayer.services.notifications import NotificationsService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.simplestreams.models import (
    BootloaderProduct,
    SimpleStreamsProductList,
)
from maasservicelayer.utils.image_local_files import (
    LocalBootResourceFile,
    LocalStoreInvalidHash,
    LocalStoreWriteBeyondEOF,
    MMapedLocalFile,
)
from maastemporalworker.worker import (
    custom_sandbox_runner,
    pydantic_data_converter,
)
from maastemporalworker.workflow.api_client import MAASAPIClient
from maastemporalworker.workflow.bootresource import (
    BootResourcesActivity,
    BootSourceProductsMapping,
    CANCEL_OBSOLETE_DOWNLOAD_WORKFLOWS_ACTIVITY_NAME,
    CHECK_DISK_SPACE_ACTIVITY_NAME,
    CLEANUP_OLD_BOOT_RESOURCES_ACTIVITY_NAME,
    DISCARD_ERROR_NOTIFICATION_ACTIVITY_NAME,
    DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME,
    DownloadBootResourceWorkflow,
    FETCH_MANIFEST_AND_UPDATE_CACHE_ACTIVITY_NAME,
    GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME,
    GET_FILES_TO_DOWNLOAD_ACTIVITY_NAME,
    GET_SYNCED_REGIONS_ACTIVITY_NAME,
    MasterImageSyncWorkflow,
    REGISTER_ERROR_NOTIFICATION_ACTIVITY_NAME,
    SET_GLOBAL_DEFAULT_RELEASES_ACTIVITY_NAME,
    SpaceRequirementParam,
    SyncBootResourcesWorkflow,
    SyncLocalBootResourcesWorkflow,
    SyncRemoteBootResourcesWorkflow,
)
from tests.fixtures import AsyncContextManagerMock, AsyncIteratorMock

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
    mocker.patch.object(
        act, "start_transaction"
    ).return_value = AsyncContextManagerMock(services_mock)
    yield act


@pytest.fixture
def a_file(image_store_dir):
    content = bytes(b"".join(islice(repeat(b"\x01"), FILE_SIZE)))
    sha256 = hashlib.sha256()
    sha256.update(content)
    file = image_store_dir / f"{str(sha256.hexdigest())}"
    with file.open("wb") as f:
        f.write(content)
    yield file


@pytest.fixture
def mock_local_file(mocker):
    m = Mock(LocalBootResourceFile)
    mocker.patch(
        "maastemporalworker.workflow.bootresource.LocalBootResourceFile"
    ).return_value = m
    yield m


@pytest.mark.usefixtures("maasdb")
class TestCheckDiskSpace:
    async def test_check_disk_space_total(
        self, boot_activities, image_store_dir
    ):
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        param = SpaceRequirementParam(total_resources_size=100)
        ok = await env.run(boot_activities.check_disk_space, param)
        assert ok

    async def test_check_disk_space_total_has_space(
        self, boot_activities, image_store_dir, a_file
    ):
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        param = SpaceRequirementParam(total_resources_size=70)
        ok = await env.run(boot_activities.check_disk_space, param)
        assert ok

    async def test_check_disk_space_total_full(
        self, boot_activities, image_store_dir
    ):
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        param = SpaceRequirementParam(total_resources_size=120)
        ok = await env.run(boot_activities.check_disk_space, param)
        assert not ok

    async def test_check_disk_space_min_free_space(
        self, boot_activities, image_store_dir
    ):
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        param = SpaceRequirementParam(min_free_space=50)
        ok = await env.run(boot_activities.check_disk_space, param)
        assert ok

    async def test_check_disk_space_min_free_space_full(
        self, boot_activities, image_store_dir
    ):
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        param = SpaceRequirementParam(min_free_space=500)
        ok = await env.run(boot_activities.check_disk_space, param)
        assert not ok


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
    async def test_failed_acquiring_lock_emits_heartbeat(
        self,
        mocker,
        mock_local_file: Mock,
        boot_activities: BootResourcesActivity,
    ) -> None:
        mock_local_file.acquire_lock.side_effect = [False, True]
        mock_local_file.avalid.return_value = True
        mocker.patch("asyncio.sleep")

        heartbeats = []
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        env.on_heartbeat = lambda *args: heartbeats.append(args[0])
        param = ResourceDownloadParam(
            rfile_ids=[1],
            source_list=["http://maas-image-stream.io"],
            sha256="0" * 64,
            filename_on_disk="0" * 7,
            total_size=100,
        )
        res = await env.run(boot_activities.download_bootresourcefile, param)
        assert res is True

        assert heartbeats == ["Waiting for file lock"]
        mock_local_file.release_lock.assert_called_once()

    async def test_valid_file_dont_get_downloaded_again(
        self,
        mock_local_file: Mock,
        boot_activities: BootResourcesActivity,
        mock_apiclient: Mock,
    ) -> None:
        mock_local_file.acquire_lock.return_value = True
        mock_local_file.avalid.return_value = True

        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        param = ResourceDownloadParam(
            rfile_ids=[1],
            source_list=["http://maas-image-stream.io"],
            sha256="0" * 64,
            filename_on_disk="0" * 7,
            total_size=100,
        )
        res = await env.run(boot_activities.download_bootresourcefile, param)
        assert res is True

        mock_local_file.commit.assert_called_once()
        boot_activities.report_progress.assert_awaited_once_with(
            param.rfile_ids, mock_local_file.size
        )
        mock_apiclient.make_client.assert_not_called()
        mock_local_file.release_lock.assert_called_once()

    async def test_extract_file_emits_heartbeat(
        self,
        mock_local_file: Mock,
        boot_activities: BootResourcesActivity,
        mock_apiclient: Mock,
    ) -> None:
        mock_local_file.acquire_lock.return_value = True
        mock_local_file.avalid.return_value = True
        mock_local_file.extract_file.return_value = None

        heartbeats = []
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        env.on_heartbeat = lambda *args: heartbeats.append(args[0])
        param = ResourceDownloadParam(
            rfile_ids=[1],
            source_list=["http://maas-image-stream.io"],
            sha256="0" * 64,
            filename_on_disk="0" * 7,
            total_size=100,
            extract_paths=["path1", "path2"],
        )
        res = await env.run(boot_activities.download_bootresourcefile, param)
        assert res is True

        assert heartbeats == [
            "Extracted file in path1",
            "Extracted file in path2",
        ]

        mock_local_file.commit.assert_called_once()
        boot_activities.report_progress.assert_awaited_once_with(
            param.rfile_ids, mock_local_file.size
        )
        mock_apiclient.make_client.assert_not_called()
        mock_local_file.release_lock.assert_called_once()

    async def test_download_file_if_not_valid(
        self,
        mock_local_file: Mock,
        boot_activities: BootResourcesActivity,
        mock_apiclient: Mock,
    ) -> None:
        mock_local_file.acquire_lock.return_value = True
        mock_local_file.avalid.side_effect = [False, True]
        chunked_data = [b"foo", b"bar", b""]

        mock_http_response = Mock(httpx.Response)
        mock_http_response.aiter_bytes.return_value = AsyncIteratorMock(
            chunked_data
        )
        mock_apiclient._mocked_client.stream.return_value = (
            AsyncContextManagerMock(mock_http_response)
        )
        mock_store = Mock(MMapedLocalFile)
        mock_local_file.astore.return_value = AsyncContextManagerMock(
            mock_store
        )

        heartbeats = []
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        env.on_heartbeat = lambda *args: heartbeats.append(args[0])
        param = ResourceDownloadParam(
            rfile_ids=[1],
            source_list=["http://maas-image-stream.io"],
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
            "Finished download, doing checksum",
        ]

        mock_store.write.assert_has_calls(
            [
                call(b"foo"),
                call(b"bar"),
                call(b""),
            ]
        )
        mock_local_file.commit.assert_called_once()
        boot_activities.report_progress.assert_awaited_once_with(
            param.rfile_ids, mock_local_file.size
        )
        mock_apiclient.make_client.assert_called_once_with(None)
        mock_apiclient._mocked_client.stream.assert_called_once_with(
            "GET",
            "http://maas-image-stream.io",
        )
        mock_local_file.release_lock.assert_called_once()

    async def test_download_file_fails_checksum_check(
        self,
        mock_local_file: Mock,
        boot_activities: BootResourcesActivity,
        mock_apiclient: Mock,
    ) -> None:
        mock_local_file.acquire_lock.return_value = True
        mock_local_file.avalid.side_effect = [False, False]
        chunked_data = [b"foo", b"bar", b""]

        mock_http_response = Mock(httpx.Response)
        mock_http_response.aiter_bytes.return_value = AsyncIteratorMock(
            chunked_data
        )
        mock_apiclient._mocked_client.stream.return_value = (
            AsyncContextManagerMock(mock_http_response)
        )
        mock_local_file.astore.return_value = AsyncContextManagerMock(
            Mock(MMapedLocalFile)
        )

        heartbeats = []
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        env.on_heartbeat = lambda *args: heartbeats.append(args[0])
        param = ResourceDownloadParam(
            rfile_ids=[1],
            source_list=["http://maas-image-stream.io"],
            sha256="0" * 64,
            filename_on_disk="0" * 7,
            total_size=100,
        )
        with pytest.raises(ApplicationError) as err:
            await env.run(boot_activities.download_bootresourcefile, param)

        assert str(err.value) == "Invalid checksum"

        assert heartbeats == [
            "Downloaded chunk",
            "Downloaded chunk",
            "Downloaded chunk",
            "Finished download, doing checksum",
        ]

        mock_local_file.unlink.assert_called_once()
        boot_activities.report_progress.assert_awaited_once_with(
            param.rfile_ids, 0
        )
        mock_apiclient._mocked_client.stream.assert_called_once_with(
            "GET",
            "http://maas-image-stream.io",
        )
        mock_local_file.release_lock.assert_called_once()

    async def test_download_file_raise_out_of_disk_exception(
        self,
        mock_local_file: Mock,
        boot_activities: BootResourcesActivity,
    ) -> None:
        # Acquire lock is not the responsible of raising all these exceptions,
        # but we use it to avoid patching the rest of the function
        exception = IOError()
        exception.errno = 28
        mock_local_file.acquire_lock.side_effect = exception
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        param = ResourceDownloadParam(
            rfile_ids=[1],
            source_list=["http://maas-image-stream.io"],
            sha256="0" * 64,
            filename_on_disk="0" * 7,
            total_size=100,
        )
        res = await env.run(boot_activities.download_bootresourcefile, param)
        assert res is False
        mock_local_file.unlink.assert_called_once()
        boot_activities.report_progress.assert_awaited_once_with(
            param.rfile_ids, 0
        )
        mock_local_file.release_lock.assert_called_once()

    @pytest.mark.parametrize(
        "exception",
        [CancelledError(), asyncio.CancelledError()],
    )
    async def test_local_file_gets_unlinked_when_activity_is_cancelled(
        self,
        mock_local_file: Mock,
        boot_activities: BootResourcesActivity,
        exception,
    ) -> None:
        # Acquire lock is not the responsible of raising all these exceptions,
        # but we use it to avoid patching the rest of the function
        mock_local_file.acquire_lock.side_effect = exception
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        param = ResourceDownloadParam(
            rfile_ids=[1],
            source_list=["http://maas-image-stream.io"],
            sha256="0" * 64,
            filename_on_disk="0" * 7,
            total_size=100,
        )
        with pytest.raises(type(exception)):
            await env.run(boot_activities.download_bootresourcefile, param)
        mock_local_file.unlink.assert_called_once()
        boot_activities.report_progress.assert_awaited_once_with(
            param.rfile_ids, 0
        )
        mock_local_file.release_lock.assert_called_once()

    @pytest.mark.parametrize(
        "exception",
        [
            IOError(),
            httpx.HTTPError("Error"),
            LocalStoreInvalidHash(),
            LocalStoreWriteBeyondEOF(),
        ],
    )
    async def test_download_file_raise_other_exception(
        self,
        mock_local_file: Mock,
        boot_activities: BootResourcesActivity,
        exception,
    ) -> None:
        # Acquire lock is not the responsible of raising all these exceptions,
        # but we use it to avoid patching the rest of the function
        mock_local_file.acquire_lock.side_effect = exception
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        param = ResourceDownloadParam(
            rfile_ids=[1],
            source_list=["http://maas-image-stream.io"],
            sha256="0" * 64,
            filename_on_disk="0" * 7,
            total_size=100,
        )
        with pytest.raises(ApplicationError):
            await env.run(boot_activities.download_bootresourcefile, param)
        mock_local_file.release_lock.assert_called_once()


class TestDeleteBootresourcefileActivity:
    async def test_delete_emits_heartbeat(
        self,
        mocker,
        mock_local_file: Mock,
        boot_activities: BootResourcesActivity,
    ) -> None:
        mock_local_file.acquire_lock.side_effect = [False, True]
        mocker.patch("asyncio.sleep")

        heartbeats = []
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        env.on_heartbeat = lambda *args: heartbeats.append(args[0])
        param = ResourceDeleteParam(
            files=[ResourceIdentifier("0" * 64, "0" * 7)]
        )
        res = await env.run(boot_activities.delete_bootresourcefile, param)
        assert res is True

        assert heartbeats == ["Waiting for file lock"]

    async def test_delete(
        self,
        mock_local_file: Mock,
        boot_activities: BootResourcesActivity,
    ) -> None:
        mock_local_file.acquire_lock.return_value = True

        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        param = ResourceDeleteParam(
            files=[ResourceIdentifier("0" * 64, "0" * 7)]
        )
        res = await env.run(boot_activities.delete_bootresourcefile, param)
        assert res is True
        mock_local_file.acquire_lock.assert_called_once()
        mock_local_file.unlink.assert_called_once()
        mock_local_file.release_lock.assert_called_once()


class TestFetchManifestAndUpdateCacheActivity:
    async def test_calls_image_sync_service(
        self,
        boot_activities: BootResourcesActivity,
        services_mock: ServiceCollectionV3,
    ) -> None:
        mock_boot_source = Mock(BootSource)
        mock_boot_source.id = 1
        mock_ss_products_list = Mock(SimpleStreamsProductList)
        mock_ss_products_list.products = [Mock(BootloaderProduct)]
        services_mock.image_sync = Mock(ImageSyncService)
        services_mock.image_sync.fetch_images_metadata.return_value = {
            mock_boot_source: [mock_ss_products_list]
        }
        services_mock.image_sync.check_commissioning_series_selected.return_value = True
        services_mock.image_sync.filter_products.return_value = {
            mock_boot_source: mock_ss_products_list
        }

        heartbeats = []
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        env.on_heartbeat = lambda *args: heartbeats.append(args[0])
        await env.run(boot_activities.fetch_manifest_and_update_cache)

        assert heartbeats == ["Downloaded images descriptions"]
        services_mock.image_sync.ensure_boot_source_definition.assert_awaited_once()
        services_mock.image_sync.fetch_images_metadata.assert_awaited_once()
        services_mock.image_sync.cache_boot_source_from_simplestreams_products.assert_awaited_once()
        services_mock.image_sync.sync_boot_source_selections_from_msm.assert_awaited_once()
        services_mock.image_sync.check_commissioning_series_selected.assert_awaited_once()


class TestGetFilesToDownloadActivity:
    async def test_calls_image_sync_service(
        self,
        boot_activities: BootResourcesActivity,
        services_mock: ServiceCollectionV3,
    ) -> None:
        mock_boot_source = Mock(BootSource)
        mock_boot_source.id = 1
        mock_ss_products_list = Mock(SimpleStreamsProductList)
        mock_ss_products_list.products = [Mock(BootloaderProduct)]
        services_mock.events = Mock(EventsService)
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.get_many.return_value = [mock_boot_source]
        services_mock.image_sync = Mock(ImageSyncService)
        services_mock.image_sync.filter_products.return_value = {
            mock_boot_source: mock_ss_products_list
        }
        services_mock.image_sync.get_files_to_download_from_product_list.return_value = (
            {},
            {1},
        )
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get.return_value = [
            "http://internal-proxy/"
        ]

        heartbeats = []
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        env.on_heartbeat = lambda *args: heartbeats.append(args[0])
        await env.run(
            boot_activities.get_files_to_download,
            [
                BootSourceProductsMapping(
                    boot_source_id=mock_boot_source.id,
                    products_list=mock_ss_products_list,
                )
            ],
        )

        services_mock.events.record_event.assert_awaited_once_with(
            event_type=EventTypeEnum.REGION_IMPORT_INFO,
            event_description="Started importing boot images from 1 source(s).",
        )
        services_mock.image_sync.filter_products.assert_awaited_once()
        services_mock.image_sync.get_files_to_download_from_product_list.assert_awaited_once()
        services_mock.configurations.get.assert_awaited_once()


class TestGetGlobalDefaultReleaseActivity:
    async def test_calls_image_sync_service(
        self,
        boot_activities: BootResourcesActivity,
        services_mock: ServiceCollectionV3,
    ) -> None:
        services_mock.image_sync = Mock(ImageSyncService)

        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        await env.run(boot_activities.set_global_default_releases)
        services_mock.image_sync.set_global_default_releases.assert_awaited_once()


class TestCleanupOldBootResourcesActivity:
    async def test_calls_image_sync_service(
        self,
        boot_activities: BootResourcesActivity,
        services_mock: ServiceCollectionV3,
    ) -> None:
        services_mock.image_sync = Mock(ImageSyncService)
        services_mock.temporal = Mock(TemporalService)

        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        param = CleanupOldBootResourceParam(
            boot_resource_ids_to_keep={1, 2, 3}
        )
        await env.run(boot_activities.cleanup_old_boot_resources, param)
        services_mock.image_sync.delete_old_boot_resources.assert_awaited_once_with(
            {1, 2, 3}
        )
        services_mock.image_sync.delete_old_boot_resource_sets.assert_awaited_once()
        services_mock.temporal.post_commit.assert_awaited_once()


class TestCancelObsoleteDownloadWorkflowsActivity:
    async def test_cancel(
        self,
        boot_activities: BootResourcesActivity,
        mock_temporal_client: Mock,
    ) -> None:
        shas = {"a" * 64, "b" * 64, "c" * 64}
        wf1 = Mock(WorkflowExecution)
        wf1.id = f"{SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME}:{'0' * 12}"
        wf2 = Mock(WorkflowExecution)
        wf2.id = f"{SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME}:{'1' * 12}"
        wf3 = Mock(WorkflowExecution)
        wf3.id = f"{SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME}:{'a' * 12}"

        workflows = [wf1, wf2, wf3]
        handle_wf1 = AsyncMock(WorkflowHandle)
        handle_wf2 = AsyncMock(WorkflowHandle)

        mock_temporal_client.list_workflows.return_value = AsyncIteratorMock(
            workflows
        )
        mock_temporal_client.get_workflow_handle.side_effect = [
            handle_wf1,
            handle_wf2,
        ]
        param = CancelObsoleteDownloadWorkflowsParam(sha_to_keep=shas)

        heartbeats = []
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter
        env.on_heartbeat = lambda *args: heartbeats.append(args[0])
        await env.run(
            boot_activities.cancel_obsolete_download_workflows, param
        )

        assert heartbeats == ["Obsolete workflow cancelled"] * 2
        mock_temporal_client.list_workflows.assert_called_once_with(
            query=f"WorkflowType='{SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME}' AND ExecutionStatus='Running'"
        )

        mock_temporal_client.get_workflow_handle.assert_has_calls(
            [
                call(wf1.id),
                call(wf2.id),
            ]
        )

        handle_wf1.cancel.assert_awaited_once()
        handle_wf2.cancel.assert_awaited_once()


class TestRegisterNotificationErrorActivity:
    async def test_calls_service(
        self,
        boot_activities: BootResourcesActivity,
        services_mock: Mock,
    ) -> None:
        services_mock.notifications = Mock(NotificationsService)
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter

        await env.run(
            boot_activities.register_error_notification, "error message"
        )

        services_mock.notifications.get_or_create.assert_awaited_once_with(
            query=QuerySpec(
                where=NotificationsClauseFactory.with_ident(
                    NotificationComponent.REGION_IMAGE_SYNC
                )
            ),
            builder=NotificationBuilder(
                ident=NotificationComponent.REGION_IMAGE_SYNC,
                users=True,
                admins=True,
                message="Failed to synchronize boot resources: error message",
                context={},
                user_id=None,
                category=NotificationCategoryEnum.ERROR,
                dismissable=False,
            ),
        )


class TestDiscardNotificationErrorActivity:
    async def test_calls_service(
        self,
        boot_activities: BootResourcesActivity,
        services_mock: Mock,
    ) -> None:
        services_mock.notifications = Mock(NotificationsService)
        env = ActivityEnvironment()
        env.payload_converter = pydantic_data_converter

        await env.run(boot_activities.discard_error_notification)

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


class MockActivities:
    def __init__(self):
        self.disk_space_result = True
        self.endpoints_result = {
            "abcdef": ["http://10.0.0.1:5240/MAAS/boot-resources/"],
            "ghijkl": ["http://10.0.0.2:5240/MAAS/boot-resources/"],
            "mnopqr": ["http://10.0.0.3:5240/MAAS/boot-resources/"],
        }
        self.download_result = True
        self.synced_regions_result = ["abcdef"]
        self.files_to_download_result = GetFilesToDownloadReturnValue(
            resources=[
                ResourceDownloadParam(
                    rfile_ids=[1],
                    source_list=["http://maas-image-stream.io"],
                    sha256="0" * 64,
                    filename_on_disk="0" * 7,
                    total_size=100,
                )
            ],
            boot_resource_ids={1, 2, 3},
            http_proxy="http://proxy:8080",
        )
        self.fetch_manifest_and_update_cache_result = []

    @activity.defn(name=CHECK_DISK_SPACE_ACTIVITY_NAME)
    async def check_disk_space(self, param: SpaceRequirementParam) -> bool:
        return self.disk_space_result

    @activity.defn(name=GET_BOOTRESOURCEFILE_ENDPOINTS_ACTIVITY_NAME)
    async def get_bootresourcefile_endpoints(self) -> dict[str, list]:
        return self.endpoints_result

    @activity.defn(name=DOWNLOAD_BOOTRESOURCEFILE_ACTIVITY_NAME)
    async def download_bootresourcefile(
        self, param: ResourceDownloadParam
    ) -> bool:
        return self.download_result

    @activity.defn(name=GET_SYNCED_REGIONS_ACTIVITY_NAME)
    async def get_synced_regions_for_file(self, file_id: int) -> list[str]:
        return self.synced_regions_result

    @activity.defn(name=FETCH_MANIFEST_AND_UPDATE_CACHE_ACTIVITY_NAME)
    async def fetch_manifest_and_update_cache(
        self,
    ) -> list[BootSourceProductsMapping]:
        return self.fetch_manifest_and_update_cache_result

    @activity.defn(name=GET_FILES_TO_DOWNLOAD_ACTIVITY_NAME)
    async def get_files_to_download(
        self, param: list[BootSourceProductsMapping]
    ) -> GetFilesToDownloadReturnValue:
        return self.files_to_download_result

    @activity.defn(name=CLEANUP_OLD_BOOT_RESOURCES_ACTIVITY_NAME)
    async def cleanup_old_boot_resources(
        self, param: CleanupOldBootResourceParam
    ) -> None:
        pass

    @activity.defn(name=CANCEL_OBSOLETE_DOWNLOAD_WORKFLOWS_ACTIVITY_NAME)
    async def cancel_obsolete_download_workflows(
        self, param: CancelObsoleteDownloadWorkflowsParam
    ) -> None:
        pass

    @activity.defn(name=SET_GLOBAL_DEFAULT_RELEASES_ACTIVITY_NAME)
    async def set_global_default_releases(self) -> None:
        pass

    @activity.defn(name=REGISTER_ERROR_NOTIFICATION_ACTIVITY_NAME)
    async def register_error_notification(self, err_msg: str) -> None:
        pass

    @activity.defn(name=DISCARD_ERROR_NOTIFICATION_ACTIVITY_NAME)
    async def discard_error_notification(self) -> None:
        pass


@pytest.fixture
def sample_endpoints_single_region():
    """Single region endpoint configuration"""
    return {"abcdef": ["http://10.0.0.1:5240/MAAS/boot-resources/"]}


@pytest.fixture
def sample_endpoints_three_regions():
    """Three region endpoint configuration"""
    return {
        "abcdef": ["http://10.0.0.1:5240/MAAS/boot-resources/"],
        "ghijkl": ["http://10.0.0.2:5240/MAAS/boot-resources/"],
        "mnopqr": ["http://10.0.0.3:5240/MAAS/boot-resources/"],
    }


@pytest.fixture
def sample_resource():
    """Sample ResourceDownloadParam"""
    return ResourceDownloadParam(
        rfile_ids=[1],
        source_list=["http://maas-image-stream.io"],
        sha256="0" * 64,
        filename_on_disk="0" * 7,
        total_size=100,
    )


@pytest.fixture
def sample_sync_request_single(
    sample_resource, sample_endpoints_single_region
):
    """Sample SyncRequestParam for single region"""
    return SyncRequestParam(
        resource=sample_resource,
        region_endpoints=sample_endpoints_single_region,
    )


@pytest.fixture
def sample_sync_request_three(sample_resource, sample_endpoints_three_regions):
    """Sample SyncRequestParam for three regions"""
    return SyncRequestParam(
        resource=sample_resource,
        region_endpoints=sample_endpoints_three_regions,
    )


@pytest.fixture
def sample_local_sync_request(sample_resource):
    return LocalSyncRequestParam(
        resource=sample_resource,
        space_requirement=SpaceRequirementParam(
            min_free_space=sample_resource.size
        ),
    )


@pytest.fixture
def mock_activities():
    return MockActivities()


class TestSyncBootResourcesWorkflow:
    @pytest.mark.asyncio
    async def test_single_region_sync(
        self,
        client: Client,
        sample_sync_request_single,
        mock_activities: MockActivities,
    ):
        async with Worker(
            client,
            task_queue="test-queue",
            workflows=[SyncBootResourcesWorkflow],
            activities=[
                mock_activities.get_synced_regions_for_file,
            ],
        ):
            with (
                patch(
                    "temporalio.workflow.execute_child_workflow",
                    return_value=True,
                ) as mock_child,
            ):
                await client.execute_workflow(
                    SyncBootResourcesWorkflow.run,
                    sample_sync_request_single,
                    id="test-sync-single",
                    task_queue="test-queue",
                )

                # Should return early
                assert mock_child.call_count == 0

    @pytest.mark.asyncio
    async def test_three_region_sync_with_missing_regions(
        self,
        client: Client,
        sample_sync_request_three,
        mock_activities: MockActivities,
    ):
        # Only one synced region
        mock_activities.synced_regions_result = ["abcdef"]
        async with Worker(
            client,
            task_queue="test-queue",
            workflows=[
                SyncBootResourcesWorkflow,
            ],
            activities=[
                mock_activities.get_synced_regions_for_file,
            ],
        ):
            with (
                patch(
                    "temporalio.workflow.execute_child_workflow",
                    return_value=True,
                ) as mock_child,
            ):
                await client.execute_workflow(
                    SyncBootResourcesWorkflow.run,
                    sample_sync_request_three,
                    id="test-sync-three",
                    task_queue="test-queue",
                )

                # one for each missing region
                assert mock_child.call_count == 2

    @pytest.mark.asyncio
    async def test_failed_sync_to_regions(
        self,
        client: Client,
        sample_sync_request_three,
        mock_activities: MockActivities,
    ):
        """Test workflow fails when sync to other regions fails"""
        mock_activities.synced_regions_result = ["abcdef"]
        mock_handle = AsyncMock()

        async with Worker(
            client,
            task_queue="test-queue",
            workflows=[
                SyncBootResourcesWorkflow,
            ],
            activities=[
                mock_activities.download_bootresourcefile,
                mock_activities.get_synced_regions_for_file,
            ],
        ):
            with (
                patch(
                    "temporalio.workflow.execute_child_workflow",
                    return_value=False,  # Sync fails
                ) as mock_child,
                patch(
                    "temporalio.workflow.get_external_workflow_handle_for",
                    return_value=mock_handle,
                ),
                pytest.raises(WorkflowFailureError) as exc_info,
            ):
                await client.execute_workflow(
                    SyncBootResourcesWorkflow.run,
                    sample_sync_request_three,
                    id="test-failed-sync",
                    task_queue="test-queue",
                )

                # one for each missing region
                assert mock_child.call_count == 2
                # The exception returned is WorkflowFailureError.
                # The ApplicationError we raise is available in the `cause` attribute.
                assert "could not be synced" in str(
                    exc_info.value.cause.message
                )
                assert exc_info.value.cause.non_retryable

    @pytest.mark.asyncio
    async def test_no_synced_regions_available(
        self,
        client: Client,
        sample_sync_request_three,
        mock_activities: MockActivities,
    ):
        """Test workflow fails when no regions have the complete file"""
        mock_activities.synced_regions_result = []  # No regions have the file

        async with Worker(
            client,
            task_queue="test-queue",
            workflows=[
                SyncRemoteBootResourcesWorkflow,
                SyncBootResourcesWorkflow,
                DownloadBootResourceWorkflow,
            ],
            activities=[
                mock_activities.download_bootresourcefile,
                mock_activities.get_synced_regions_for_file,
            ],
        ):
            with (
                patch(
                    "temporalio.workflow.execute_child_workflow",
                    return_value=True,
                ),
                pytest.raises(WorkflowFailureError) as exc_info,
            ):
                await client.execute_workflow(
                    SyncBootResourcesWorkflow.run,
                    sample_sync_request_three,
                    id="test-no-synced-regions",
                    task_queue="test-queue",
                )

                # The exception returned is WorkflowFailureError.
                # The ApplicationError we raise is available in the `cause` attribute.
                assert "has no complete copy available" in str(
                    exc_info.value.cause.message
                )
                assert not exc_info.value.cause.non_retryable


class TestSyncLocalBootResourcesWorkflow:
    @pytest.mark.asyncio
    async def test_single_region(
        self,
        client: Client,
        sample_local_sync_request,
        mock_activities: MockActivities,
        sample_endpoints_single_region,
    ):
        mock_activities.endpoints_result = sample_endpoints_single_region
        async with Worker(
            client,
            task_queue="test-queue",
            workflows=[
                SyncLocalBootResourcesWorkflow,
                SyncBootResourcesWorkflow,
            ],
            activities=[
                mock_activities.get_bootresourcefile_endpoints,
            ],
        ):
            with (
                patch(
                    "temporalio.workflow.execute_child_workflow",
                    return_value=True,
                ) as mock_child,
            ):
                await client.execute_workflow(
                    SyncLocalBootResourcesWorkflow.run,
                    sample_local_sync_request,
                    id="test-sync-single",
                    task_queue="test-queue",
                )

                # one call for the check space, another one for the sync
                assert mock_child.call_count == 2

    @pytest.mark.asyncio
    async def test_three_region(
        self,
        client: Client,
        sample_local_sync_request,
        mock_activities: MockActivities,
        sample_endpoints_three_regions,
    ):
        mock_activities.endpoints_result = sample_endpoints_three_regions
        async with Worker(
            client,
            task_queue="test-queue",
            workflows=[
                SyncLocalBootResourcesWorkflow,
                SyncBootResourcesWorkflow,
            ],
            activities=[
                mock_activities.get_bootresourcefile_endpoints,
            ],
        ):
            with (
                patch(
                    "temporalio.workflow.execute_child_workflow",
                    return_value=True,
                ) as mock_child,
            ):
                await client.execute_workflow(
                    SyncLocalBootResourcesWorkflow.run,
                    sample_local_sync_request,
                    id="test-sync-three",
                    task_queue="test-queue",
                )

                # three calls for the check space, another one for the sync
                assert mock_child.call_count == 4


class TestSyncRemoteBootResourcesWorkflow:
    @pytest.mark.asyncio
    async def test_remote_sync_signals_master(
        self,
        client: Client,
        sample_sync_request_single,
        mock_activities: MockActivities,
    ):
        mock_handle = AsyncMock()
        mock_handle.signal = AsyncMock()

        async with Worker(
            client,
            task_queue="test-queue",
            workflows=[
                SyncRemoteBootResourcesWorkflow,
            ],
            activities=[
                mock_activities.download_bootresourcefile,
                mock_activities.get_synced_regions_for_file,
            ],
        ):
            with (
                patch(
                    "temporalio.workflow.execute_child_workflow",
                    return_value=True,
                ) as mock_child,
                patch(
                    "temporalio.workflow.get_external_workflow_handle_for",
                    return_value=mock_handle,
                ),
            ):
                await client.execute_workflow(
                    SyncRemoteBootResourcesWorkflow.run,
                    sample_sync_request_single,
                    id="test-sync-single",
                    task_queue="test-queue",
                )

                # one call for the download, another one for the sync
                assert mock_child.call_count == 2

                mock_handle.signal.assert_called_once_with(
                    MasterImageSyncWorkflow.file_completed_download,
                    sample_sync_request_single.resource.sha256,
                )

    @pytest.mark.asyncio
    async def test_failed_upstream_download(
        self,
        client: Client,
        sample_sync_request_single,
        mock_activities: MockActivities,
    ):
        """Test workflow fails when upstream download fails"""
        async with Worker(
            client,
            task_queue="test-queue",
            workflows=[
                SyncRemoteBootResourcesWorkflow,
            ],
            activities=[mock_activities.download_bootresourcefile],
        ):
            with (
                patch(
                    "temporalio.workflow.execute_child_workflow",
                    return_value=False,
                ) as mock_child,
                pytest.raises(WorkflowFailureError) as exc_info,
            ):
                await client.execute_workflow(
                    SyncRemoteBootResourcesWorkflow.run,
                    sample_sync_request_single,
                    id="test-failed-download",
                    task_queue="test-queue",
                )

                mock_child.assert_called_once()
                # The exception returned is WorkflowFailureError.
                # The ApplicationError we raise is available in the `cause` attribute.
                assert (
                    "could not be downloaded" in exc_info.value.cause.message
                )
                assert exc_info.value.cause.non_retryable


class TestMasterImageSyncWorkflow:
    """Tests for MasterImageSyncWorkflow"""

    @pytest.mark.asyncio
    async def test_single_region_master_workflow(
        self,
        client: Client,
        sample_endpoints_single_region,
        mock_activities: MockActivities,
    ):
        """Test master workflow with single region"""
        mock_activities.endpoints_result = sample_endpoints_single_region

        async with Worker(
            client,
            task_queue="test-queue",
            workflows=[MasterImageSyncWorkflow],
            activities=[
                mock_activities.get_files_to_download,
                mock_activities.get_bootresourcefile_endpoints,
                mock_activities.cancel_obsolete_download_workflows,
                mock_activities.set_global_default_releases,
                mock_activities.cleanup_old_boot_resources,
                mock_activities.register_error_notification,
                mock_activities.discard_error_notification,
            ],
            workflow_runner=custom_sandbox_runner(),
        ):
            with (
                patch(
                    "temporalio.workflow.execute_child_workflow",
                    side_effect=[
                        mock_activities.fetch_manifest_and_update_cache_result,
                        True,
                    ],
                ) as mock_execute_child,
                patch(
                    "temporalio.workflow.start_child_workflow"
                ) as mock_start_child,
                patch("temporalio.workflow.wait_condition") as mock_wait,
            ):
                await client.execute_workflow(
                    MasterImageSyncWorkflow.run,
                    id="test-master-single",
                    task_queue="test-queue",
                )

                # Fetch manifest + Check disk space for single region
                assert mock_execute_child.call_count == 2
                mock_wait.assert_awaited_once()
                # Start remote sync workflow for one resource
                mock_start_child.assert_called_once()

    @pytest.mark.asyncio
    async def test_three_region_master_workflow(
        self,
        client: Client,
        sample_endpoints_three_regions,
        mock_activities: MockActivities,
    ):
        """Test master workflow schedules sync for all regions"""
        mock_activities.endpoints_result = sample_endpoints_three_regions

        async with Worker(
            client,
            task_queue="test-queue",
            workflows=[MasterImageSyncWorkflow],
            activities=[
                mock_activities.get_files_to_download,
                mock_activities.get_bootresourcefile_endpoints,
                mock_activities.cancel_obsolete_download_workflows,
                mock_activities.set_global_default_releases,
                mock_activities.cleanup_old_boot_resources,
                mock_activities.register_error_notification,
                mock_activities.discard_error_notification,
            ],
            workflow_runner=custom_sandbox_runner(),
        ):
            with (
                patch(
                    "temporalio.workflow.execute_child_workflow",
                    side_effect=[
                        mock_activities.fetch_manifest_and_update_cache_result,
                        True,
                        True,
                        True,
                    ],
                ) as mock_execute_child,
                patch(
                    "temporalio.workflow.start_child_workflow"
                ) as mock_start_child,
                patch("temporalio.workflow.wait_condition") as mock_wait,
            ):
                await client.execute_workflow(
                    MasterImageSyncWorkflow.run,
                    id="test-master-three",
                    task_queue="test-queue",
                )

                # Fetch manifest + Check disk space for all 3 regions
                assert mock_execute_child.call_count == 4
                mock_wait.assert_awaited_once()

                # Start remote sync workflow for one resource
                mock_start_child.assert_called_once()

    @pytest.mark.asyncio
    async def test_insufficient_disk_space(
        self,
        client: Client,
        sample_endpoints_three_regions,
        mock_activities: MockActivities,
    ):
        mock_activities.endpoints_result = sample_endpoints_three_regions
        # One region has insufficient space
        mock_activities.disk_space_result = False

        async with Worker(
            client,
            task_queue="test-queue",
            workflows=[MasterImageSyncWorkflow],
            activities=[
                mock_activities.fetch_manifest_and_update_cache,
                mock_activities.get_files_to_download,
                mock_activities.get_bootresourcefile_endpoints,
                mock_activities.cancel_obsolete_download_workflows,
                mock_activities.register_error_notification,
                mock_activities.discard_error_notification,
            ],
            workflow_runner=custom_sandbox_runner(),
        ):
            with (
                patch(
                    "temporalio.workflow.execute_child_workflow",
                    side_effect=[
                        mock_activities.fetch_manifest_and_update_cache_result,
                        mock_activities.disk_space_result,
                        mock_activities.disk_space_result,
                        mock_activities.disk_space_result,
                    ],
                ) as mock_execute_child,
                pytest.raises(WorkflowFailureError) as exc_info,
            ):
                await client.execute_workflow(
                    MasterImageSyncWorkflow.run,
                    id="test-insufficient-space",
                    task_queue="test-queue",
                )

                assert mock_execute_child.call_count == 4
                assert "don't have enough disk space" in str(
                    exc_info.value.cause.message
                )
                assert exc_info.value.cause.non_retryable

    @pytest.mark.asyncio
    async def test_already_started_workflow_handling(
        self,
        client: Client,
        sample_endpoints_single_region,
        mock_activities: MockActivities,
    ):
        """Test workflow handles already started child workflows gracefully"""
        mock_activities.endpoints_result = sample_endpoints_single_region

        async with Worker(
            client,
            task_queue="test-queue",
            workflows=[MasterImageSyncWorkflow],
            activities=[
                mock_activities.get_files_to_download,
                mock_activities.get_bootresourcefile_endpoints,
                mock_activities.cancel_obsolete_download_workflows,
                mock_activities.set_global_default_releases,
                mock_activities.cleanup_old_boot_resources,
                mock_activities.register_error_notification,
                mock_activities.discard_error_notification,
            ],
            workflow_runner=custom_sandbox_runner(),
        ):
            with (
                patch(
                    "temporalio.workflow.execute_child_workflow",
                    side_effect=[
                        mock_activities.fetch_manifest_and_update_cache_result,
                        True,
                    ],
                ),
                patch(
                    "temporalio.workflow.start_child_workflow",
                    side_effect=WorkflowAlreadyStartedError(
                        workflow_id="test-already-started",
                        workflow_type=MASTER_IMAGE_SYNC_WORKFLOW_NAME,
                    ),
                ) as mock_start,
                patch("temporalio.workflow.wait_condition"),
            ):
                # Should not raise error
                await client.execute_workflow(
                    MasterImageSyncWorkflow.run,
                    id="test-already-started",
                    task_queue="test-queue",
                )

                # Verify start_child_workflow was called
                mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_signal_handling_removes_files(self):
        """Test that file_completed_download signal correctly removes files from tracking"""
        workflow_instance = MasterImageSyncWorkflow()
        workflow_instance._files_to_download = {"file1", "file2", "file3"}

        # Signal completion of file1
        await workflow_instance.file_completed_download("file1")
        assert "file1" not in workflow_instance._files_to_download
        assert workflow_instance._files_to_download == {"file2", "file3"}

        # Signal completion of non-existent file
        await workflow_instance.file_completed_download("nonexistent")
        assert workflow_instance._files_to_download == {"file2", "file3"}

        # Signal completion of remaining files
        await workflow_instance.file_completed_download("file2")
        await workflow_instance.file_completed_download("file3")
        assert workflow_instance._files_to_download == set()
