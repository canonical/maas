# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
import json
from unittest.mock import AsyncMock, Mock

import aiofiles
import pytest

from maasservicelayer.builders.image_manifests import ImageManifestBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.image_manifests import (
    ImageManifestsRepository,
)
from maasservicelayer.db.tables import ImageManifestTable
from maasservicelayer.models.bootsources import BootSource
from maasservicelayer.models.configurations import EnableHttpProxyConfig
from maasservicelayer.models.image_manifests import ImageManifest
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.image_manifests import ImageManifestsService
from maasservicelayer.services.msm import MSMService
from maasservicelayer.simplestreams.client import (
    SIGNED_INDEX_PATH,
    SimpleStreamsClient,
    SimpleStreamsClientException,
)
from maasservicelayer.simplestreams.models import (
    SimpleStreamsProductListFactory,
)
from tests.fixtures import get_test_data_file
from tests.fixtures.factories.boot_sources import create_test_bootsource_entry
from tests.fixtures.factories.configuration import create_test_configuration
from tests.maasapiserver.fixtures.db import Fixture

MANIFEST = SimpleStreamsProductListFactory.produce(
    json.loads(get_test_data_file("simplestreams_ubuntu.json"))
)
LAST_UPDATE = MANIFEST.updated

TEST_BOOT_SOURCE = BootSource(
    id=1,
    url="http://source-1.com",
    keyring_filename="/foo/bar",
    keyring_data=b"data",
    priority=1,
    skip_keyring_verification=True,
)

TEST_IMAGE_MANIFEST = ImageManifest(
    boot_source_id=1,
    manifest=[MANIFEST],
    last_update=LAST_UPDATE,
)


class TestImageManifestsService:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.configurations_service = Mock(ConfigurationsService)
        self.repository = Mock(ImageManifestsRepository)
        self.msm = Mock(MSMService)

        self.service = ImageManifestsService(
            context=Context(),
            repository=self.repository,
            configurations_service=self.configurations_service,
            msm_service=self.msm,
        )

    @pytest.mark.parametrize(
        "config_values, expected",
        # 3 calls to the configurations service:
        # 1) EnableHttpProxyConfig
        # 2) BootImagesNoProxyConfig
        # 3) HttpProxyConfig
        [
            ([True, False, "http://myproxy.com"], "http://myproxy.com"),
            ([False, False, "http://myproxy.com"], None),
            ([True, True, "http://myproxy.com"], None),
        ],
    )
    async def test_get_http_proxy__enabled(
        self, config_values: list, expected: str | None
    ):
        self.configurations_service.get.side_effect = config_values
        proxy = await self.service._get_http_proxy()
        assert proxy == expected

    async def test_get_keyring_file_writes_data(self, mocker) -> None:
        async with self.service._get_keyring_file(
            keyring_path=None, keyring_data=b"abc123"
        ) as keyring_path:
            async with aiofiles.open(
                keyring_path, "rb"
            ) as written_keyring_file:
                written_contents = await written_keyring_file.read()
                assert written_contents == b"abc123"

    async def test_get_keyring_file_yields_keyring_path(self, mocker) -> None:
        mock_file = AsyncMock()
        mocker.patch(
            "aiofiles.tempfile._temporary_file"
        ).return_value = mock_file
        async with self.service._get_keyring_file(
            keyring_path="path/to/file", keyring_data=None
        ) as path:
            assert path == "path/to/file"
        mock_file.write.assert_not_called()

    async def test_fetch_image_metadata(self, mocker) -> None:
        # don't use a proxy
        self.configurations_service.get.return_value = False
        # patch the file check on simplestreams client
        mocker.patch("os.path.exists").return_value = True
        # patch the get_all_products method
        ss_client_mock = Mock(SimpleStreamsClient)
        ss_client_mock.get_all_products = AsyncMock(return_value=[])
        mocker.patch(
            "maasservicelayer.simplestreams.client.SimpleStreamsClient.__aenter__"
        ).return_value = ss_client_mock

        await self.service.fetch_image_metadata(
            "http://source.com", "/path/to/file"
        )
        ss_client_mock.get_all_products.assert_awaited_once()

    async def test_fetch_image_metadata_for_boot_source(self, mocker) -> None:
        # don't use a proxy
        self.configurations_service.get.return_value = False
        # patch the file check on simplestreams client
        mocker.patch("os.path.exists").return_value = True
        # patch the get_all_products method
        ss_client_mock = Mock(SimpleStreamsClient)
        ss_client_mock.get_all_products = AsyncMock(return_value=[MANIFEST])
        mocker.patch(
            "maasservicelayer.simplestreams.client.SimpleStreamsClient.__aenter__"
        ).return_value = ss_client_mock

        # return a mocked file to assert that data has been written
        mock_file = AsyncMock()
        mocker.patch(
            "aiofiles.tempfile._temporary_file"
        ).return_value = mock_file
        mocker.patch("aiofiles.os.unlink").return_value = None

        await self.service.fetch_image_metadata_for_boot_source(
            TEST_BOOT_SOURCE
        )

        mock_file.write.assert_called_once_with(TEST_BOOT_SOURCE.keyring_data)
        ss_client_mock.get_all_products.assert_awaited_once()

    async def test_fetch_images_metadata_for_boot_source_raise_exception_empty_product_list(
        self, mocker
    ) -> None:
        # don't use a proxy
        self.configurations_service.get.return_value = False
        # patch the file check on simplestreams client
        mocker.patch("os.path.exists").return_value = True
        # patch the get_all_products method
        ss_client_mock = Mock(SimpleStreamsClient)
        ss_client_mock.get_all_products = AsyncMock(return_value=[])
        mocker.patch(
            "maasservicelayer.simplestreams.client.SimpleStreamsClient.__aenter__"
        ).return_value = ss_client_mock

        # return a mocked file to assert that data has been written
        mock_file = AsyncMock()
        mocker.patch(
            "aiofiles.tempfile._temporary_file"
        ).return_value = mock_file
        mocker.patch("aiofiles.os.unlink").return_value = None

        with pytest.raises(SimpleStreamsClientException):
            await self.service.fetch_image_metadata_for_boot_source(
                TEST_BOOT_SOURCE
            )

        mock_file.write.assert_called_once_with(TEST_BOOT_SOURCE.keyring_data)
        ss_client_mock.get_all_products.assert_awaited_once()

    async def test_get_or_fetch__from_db(self) -> None:
        self.repository.get.return_value = TEST_IMAGE_MANIFEST
        self.service.fetch_image_metadata_for_boot_source = AsyncMock()

        image_manifest, created = await self.service.get_or_fetch(
            TEST_BOOT_SOURCE
        )

        assert image_manifest is not None
        assert not created
        self.service.fetch_image_metadata_for_boot_source.assert_not_awaited()
        self.repository.get.assert_awaited_once_with(TEST_BOOT_SOURCE.id)

    async def test_get_or_fetch__from_http(self) -> None:
        self.repository.get.return_value = None
        self.repository.create.return_value = TEST_IMAGE_MANIFEST
        self.service.fetch_image_metadata_for_boot_source = AsyncMock(
            return_value=[MANIFEST]
        )

        image_manifest, created = await self.service.get_or_fetch(
            TEST_BOOT_SOURCE
        )

        assert image_manifest is not None
        assert created
        self.service.fetch_image_metadata_for_boot_source.assert_awaited_once_with(
            TEST_BOOT_SOURCE
        )
        self.repository.create.assert_awaited_once_with(
            ImageManifestBuilder(
                boot_source_id=TEST_BOOT_SOURCE.id,
                manifest=[MANIFEST],
                last_update=LAST_UPDATE,
            )
        )

    async def test_fetch_and_update__object_not_in_db(self) -> None:
        # the object gets created by `get_or_fetch`
        self.repository.get.return_value = None
        self.repository.create.return_value = TEST_IMAGE_MANIFEST
        self.service.fetch_image_metadata_for_boot_source = AsyncMock(
            return_value=[MANIFEST]
        )

        image_manifest = await self.service.fetch_and_update(TEST_BOOT_SOURCE)

        assert image_manifest is not None
        self.service.fetch_image_metadata_for_boot_source.assert_awaited_once_with(
            TEST_BOOT_SOURCE
        )
        self.repository.create.assert_awaited_once_with(
            ImageManifestBuilder(
                boot_source_id=TEST_BOOT_SOURCE.id,
                manifest=[MANIFEST],
                last_update=LAST_UPDATE,
            )
        )
        self.repository.update.assert_not_awaited()

    async def test_fetch_and_update__object_needs_update(self) -> None:
        # the object already exists
        self.repository.get.return_value = TEST_IMAGE_MANIFEST
        self.repository.update.return_value = TEST_IMAGE_MANIFEST
        # return an updated manifest from the simplestream server
        updated_manifest = MANIFEST.copy()
        updated_manifest.updated = LAST_UPDATE + timedelta(minutes=1)
        self.service.fetch_image_metadata_for_boot_source = AsyncMock(
            return_value=[updated_manifest]
        )

        image_manifest = await self.service.fetch_and_update(TEST_BOOT_SOURCE)

        assert image_manifest is not None
        self.service.fetch_image_metadata_for_boot_source.assert_awaited_once_with(
            TEST_BOOT_SOURCE
        )
        self.repository.update.assert_awaited_once_with(
            ImageManifestBuilder(
                boot_source_id=TEST_BOOT_SOURCE.id,
                manifest=[updated_manifest],
                last_update=updated_manifest.updated,
            )
        )

    async def test_fetch_and_update__object_already_up_to_date(self) -> None:
        # the object already exists
        self.repository.get.return_value = TEST_IMAGE_MANIFEST
        # manifest last_updated time is the same, no need to update
        self.service.fetch_image_metadata_for_boot_source = AsyncMock(
            return_value=[MANIFEST]
        )

        image_manifest = await self.service.fetch_and_update(TEST_BOOT_SOURCE)

        assert image_manifest is not None
        self.service.fetch_image_metadata_for_boot_source.assert_awaited_once_with(
            TEST_BOOT_SOURCE
        )
        self.repository.update.assert_not_awaited()

    # Passthrough methods
    async def test_get(self) -> None:
        await self.service.get(1)
        self.repository.get.assert_awaited_once_with(1)

    async def test_create(self) -> None:
        builder = ImageManifestBuilder(
            boot_source_id=TEST_BOOT_SOURCE.id,
            manifest=[MANIFEST],
            last_update=LAST_UPDATE,
        )
        await self.service.create(builder)
        self.repository.create.assert_awaited_once_with(builder)

    async def test_update(self) -> None:
        builder = ImageManifestBuilder(
            boot_source_id=TEST_BOOT_SOURCE.id,
            manifest=[MANIFEST],
            last_update=LAST_UPDATE,
        )
        await self.service.update(builder)
        self.repository.update.assert_awaited_once_with(builder)

    async def test_delete(self) -> None:
        await self.service.delete(1)
        self.repository.delete.assert_awaited_once_with(1)

    async def test_delete_many(self) -> None:
        await self.service.delete_many([1, 2])
        self.repository.delete_many_by_boot_source_ids.assert_awaited_once_with(
            [1, 2]
        )


class TestIntegrationImageManifestsService:
    @pytest.fixture
    async def test_boot_source(self, fixture: Fixture) -> BootSource:
        return await create_test_bootsource_entry(
            fixture,
            url="http://source-1.com",
            priority=1,
            skip_keyring_verification=True,
        )

    @pytest.fixture(autouse=True)
    async def _setup(
        self,
        fixture: Fixture,
        test_boot_source: BootSource,
        mocker,
        mock_aioresponse,
    ) -> None:
        # no proxy
        await create_test_configuration(
            fixture, name=EnableHttpProxyConfig.name, value=False
        )
        # skip keyring file checks
        mocker.patch("os.path.exists").return_value = True

        ss_index = json.loads(get_test_data_file("simplestreams_index.json"))
        bootloader_products = json.loads(
            get_test_data_file("simplestreams_bootloaders.json")
        )

        ubuntu_products = json.loads(
            get_test_data_file("simplestreams_ubuntu.json")
        )

        centos_products = json.loads(
            get_test_data_file("simplestreams_centos.json")
        )
        mock_aioresponse.get(
            f"{test_boot_source.url}/{SIGNED_INDEX_PATH}", payload=ss_index
        )
        product_paths = [v["path"] for v in ss_index["index"].values()]
        for path, product in zip(
            product_paths,
            [bootloader_products, ubuntu_products, centos_products],
        ):
            mock_aioresponse.get(
                f"{test_boot_source.url}/{path}", payload=product
            )

    async def test_get_or_fetch(
        self,
        fixture: Fixture,
        services: ServiceCollectionV3,
        test_boot_source: BootSource,
        mock_aioresponse,
    ) -> None:
        image_manifests_db = await fixture.get(ImageManifestTable.name)
        assert len(image_manifests_db) == 0

        # should fetch from http
        await services.image_manifests.get_or_fetch(test_boot_source)
        mock_aioresponse.assert_called()
        assert len(mock_aioresponse.requests) == 4
        image_manifests_db = await fixture.get_typed(
            ImageManifestTable.name, type_result=ImageManifest
        )
        assert len(image_manifests_db) == 1
        # 3 list of products (botoloaders, ubuntu, centos)
        assert len(image_manifests_db[0].manifest) == 3

        # Reset the mock
        mock_aioresponse.clear()
        mock_aioresponse.requests = {}
        # should fetch from the db
        image_manifest, _ = await services.image_manifests.get_or_fetch(
            test_boot_source
        )
        mock_aioresponse.assert_not_called()

        assert image_manifest == image_manifests_db[0]
