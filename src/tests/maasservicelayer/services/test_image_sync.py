# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import json
from unittest.mock import ANY, AsyncMock, call, Mock

import pytest

from maascommon.constants import BOOTLOADERS_DIR
from maascommon.enums.boot_resources import (
    BootResourceFileType,
    BootResourceType,
)
from maascommon.enums.events import EventTypeEnum
from maascommon.enums.notifications import NotificationCategoryEnum
from maascommon.workflows.bootresource import (
    DELETE_BOOTRESOURCE_WORKFLOW_NAME,
    ResourceDeleteParam,
    ResourceDownloadParam,
    ResourceIdentifier,
)
from maasservicelayer.builders.notifications import NotificationBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import OrderByClauseFactory, QuerySpec
from maasservicelayer.db.repositories.bootresourcefiles import (
    BootResourceFileClauseFactory,
)
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
)
from maasservicelayer.db.repositories.bootresourcesets import (
    BootResourceSetClauseFactory,
    BootResourceSetsOrderByClauses,
)
from maasservicelayer.db.repositories.bootsourcecache import (
    BootSourceCacheClauseFactory,
)
from maasservicelayer.db.tables import (
    BootResourceFileTable,
    BootResourceSetTable,
    BootResourceTable,
    BootSourceCacheTable,
    EventTable,
    NotificationTable,
)
from maasservicelayer.models.bootresourcefiles import BootResourceFile
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.models.bootresourcesets import BootResourceSet
from maasservicelayer.models.bootsourcecache import BootSourceCache
from maasservicelayer.models.bootsources import BootSource
from maasservicelayer.models.bootsourceselections import BootSourceSelection
from maasservicelayer.models.configurations import (
    CommissioningDistroSeriesConfig,
    CommissioningOSystemConfig,
    EnableHttpProxyConfig,
)
from maasservicelayer.services import ServiceCollectionV3
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
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.events import EventsService
from maasservicelayer.services.image_sync import ImageSyncService
from maasservicelayer.services.notifications import NotificationsService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.simplestreams.client import (
    SIGNED_INDEX_PATH,
    SimpleStreamsClient,
)
from maasservicelayer.simplestreams.models import (
    BootloaderProduct,
    BootloaderVersion,
    Datatype,
    MultiFileImageVersion,
    MultiFileProduct,
    SimpleStreamsBootloaderProductList,
    SimpleStreamsMultiFileProductList,
    SimpleStreamsSingleFileProductList,
    SingleFileProduct,
)
from tests.fixtures import get_test_data_file
from tests.fixtures.factories.boot_sources import create_test_bootsource_entry
from tests.fixtures.factories.bootresourcefiles import (
    create_test_bootresourcefile_entry,
)
from tests.fixtures.factories.bootresourcefilesync import (
    create_test_bootresourcefilesync_entry,
)
from tests.fixtures.factories.bootresources import (
    create_test_bootresource_entry,
)
from tests.fixtures.factories.bootresourcesets import (
    create_test_bootresourceset_entry,
)
from tests.fixtures.factories.bootsourceselections import (
    create_test_bootsourceselection_entry,
)
from tests.fixtures.factories.configuration import create_test_configuration
from tests.fixtures.factories.node import create_test_region_controller_entry
from tests.maasapiserver.fixtures.db import Fixture

BOOT_SOURCE_1 = BootSource(
    id=1,
    url="http://source-1.com",
    keyring_filename="/foo/bar",
    keyring_data=None,
    priority=1,
    skip_keyring_verification=True,
)
BOOT_SOURCE_2 = BootSource(
    id=2,
    url="http://source-2.com",
    keyring_filename=None,
    keyring_data=b"some bytes",
    priority=2,
    skip_keyring_verification=True,
)

BOOT_SELECTION_NOBLE_SOURCE_1 = BootSourceSelection(
    id=1,
    os="ubuntu",
    release="noble",
    arches=["*"],
    subarches=["*"],
    labels=["*"],
    boot_source_id=BOOT_SOURCE_1.id,
)

BOOT_SELECTION_NOBLE_SOURCE_2 = BootSourceSelection(
    id=1,
    os="ubuntu",
    release="noble",
    arches=["*"],
    subarches=["*"],
    labels=["*"],
    boot_source_id=BOOT_SOURCE_2.id,
)
BOOT_SELECTION_ORACULAR_SOURCE_1 = BootSourceSelection(
    id=2,
    os="ubuntu",
    release="oracular",
    arches=["*"],
    subarches=["*"],
    labels=["*"],
    boot_source_id=BOOT_SOURCE_1.id,
)

BOOT_RESOURCE_ORACULAR = BootResource(
    id=1,
    rtype=BootResourceType.SYNCED,
    name="ubuntu/oracular",
    architecture="amd64/ga-24.10",
    extra={},
    rolling=False,
    base_image="",
)

BOOT_RESOURCE_SET_ORACULAR = BootResourceSet(
    id=1,
    version="20250718",
    label="stable",
    resource_id=BOOT_RESOURCE_ORACULAR.id,
)

BOOT_RESOURCE_BOOTLOADER = BootResource(
    id=2,
    rtype=BootResourceType.SYNCED,
    name="grub-efi-signed/uefi",
    architecture="amd64/generic",
    bootloader_type="uefi",
    extra={},
    rolling=False,
    base_image="",
)

BOOT_RESOURCE_SET_BOOTLOADER = BootResourceSet(
    id=1,
    version="20250715.0",
    label="stable",
    resource_id=BOOT_RESOURCE_BOOTLOADER.id,
)

BOOTLOADER_VERSION = BootloaderVersion(
    **{
        "version_name": "20210819.0",
        "grub2-signed": {
            "ftype": "archive.tar.xz",
            "path": "bootloaders/uefi/amd64/20210819.0/grub2-signed.tar.xz",
            "sha256": "9d4a3a826ed55c46412613d2f7caf3185da4d6b18f35225f4f6a5b86b2bccfe3",
            "size": 375316,
            "src_package": "grub2-signed",
            "src_release": "focal",
            "src_version": "1.167.2+2.04-1ubuntu44.2",
        },
        "shim-signed": {
            "ftype": "archive.tar.xz",
            "path": "bootloaders/uefi/amd64/20210819.0/shim-signed.tar.xz",
            "sha256": "07b42d0aa2540b6999c726eacf383e2c8f172378c964bdefab6d71410e2b72db",
            "size": 322336,
            "src_package": "shim-signed",
            "src_release": "focal",
            "src_version": "1.40.7+15.4-0ubuntu9",
        },
    }
)

BOOTLOADER_PRODUCT = BootloaderProduct(
    **{
        "product_name": "com.ubuntu.maas.stable:1:grub-efi-signed:uefi:amd64",
        "arch": "amd64",
        "arches": "amd64",
        "bootloader-type": "uefi",
        "label": "stable",
        "os": "grub-efi-signed",
        "versions": [BOOTLOADER_VERSION],
    }
)

MULTIFILE_IMAGE_VERSION = MultiFileImageVersion(
    **{
        "version_name": "20250718",
        "support_eol": "2025-07-10",
        "support_esm_eol": "2025-07-10",
        "boot-initrd": {
            "ftype": "boot-initrd",
            "kpackage": "linux-generic",
            "path": "oracular/amd64/20250404/ga-24.10/generic/boot-initrd",
            "sha256": "e42de3a72d142498c2945e8b0e1b9bad2fc031a2224b7497ccaca66199b51f93",
            "size": 75990212,
        },
        "boot-kernel": {
            "ftype": "boot-kernel",
            "kpackage": "linux-generic",
            "path": "oracular/amd64/20250404/ga-24.10/generic/boot-kernel",
            "sha256": "b2a29c2d269742933c15ed0ad48340ff4691261bdf0e6ba3c721dd15b835766d",
            "size": 15440264,
        },
        "manifest": {
            "ftype": "manifest",
            "path": "oracular/amd64/20250404/squashfs.manifest",
            "sha256": "5a5c81aebfc41adafb7db34d6f8022ab0084b1dddcfb8b2ff55f735ffd7a64fd",
            "size": 17898,
        },
        "squashfs": {
            "ftype": "squashfs",
            "path": "oracular/amd64/20250404/squashfs",
            "sha256": "201b7972f0f3b3bc5a345b85ed3a63688981c74b3fe52805edb2853fdbd70bbf",
            "size": 272650240,
        },
    }
)

MULTIFILE_PRODUCT_ORACULAR = MultiFileProduct(
    product_name="com.ubuntu.maas.stable:v3:boot:24.10:amd64:ga-24.10",
    arch="amd64",
    kflavor="generic",
    krel="oracular",
    label="stable",
    os="ubuntu",
    release="oracular",
    release_codename="Oracular Oriole",
    release_title="24.10",
    subarch="ga-24.10",
    subarches="generic",
    support_eol=None,
    version="24.10",
    versions=[MULTIFILE_IMAGE_VERSION],
)
MULTIFILE_PRODUCT_NOBLE = MultiFileProduct(
    product_name="com.ubuntu.maas.stable:v3:boot:24.10:amd64:ga-24.10",
    arch="amd64",
    kflavor="generic",
    krel="noble",
    label="stable",
    os="ubuntu",
    release="noble",
    release_codename="Noble Numbat",
    release_title="24.04",
    subarch="ga-24.04",
    subarches="generic",
    support_eol=None,
    version="24.04",
    versions=[],
)


@pytest.mark.asyncio
class TestImageSyncService:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.boot_sources_service = Mock(BootSourcesService)
        self.boot_source_cache_service = Mock(BootSourceCacheService)
        self.boot_source_selections_service = Mock(BootSourceSelectionsService)
        self.boot_resources_service = Mock(BootResourceService)
        self.boot_resource_sets_service = Mock(BootResourceSetsService)
        self.boot_resource_files_service = Mock(BootResourceFilesService)
        self.boot_resource_file_sync_service = Mock(
            BootResourceFileSyncService
        )
        self.events_service = Mock(EventsService)
        self.configurations_service = Mock(ConfigurationsService)
        self.notifications_service = Mock(NotificationsService)

        self.service = ImageSyncService(
            context=Context(),
            boot_sources_service=self.boot_sources_service,
            boot_source_cache_service=self.boot_source_cache_service,
            boot_source_selections_service=self.boot_source_selections_service,
            boot_resources_service=self.boot_resources_service,
            boot_resource_sets_service=self.boot_resource_sets_service,
            boot_resource_files_service=self.boot_resource_files_service,
            boot_resource_file_sync_service=self.boot_resource_file_sync_service,
            events_service=self.events_service,
            configurations_service=self.configurations_service,
            notifications_service=self.notifications_service,
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
        # return a mocked file to assert that data has been written
        mock_file = AsyncMock()
        mocker.patch(
            "aiofiles.tempfile._temporary_file"
        ).return_value = mock_file
        async with self.service._get_keyring_file(
            keyring_path=None, keyring_data=b"abc123"
        ):
            mock_file.write.assert_called_once_with(b"abc123")

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

    async def test_fetch_images_metadata(self, mocker) -> None:
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

        self.boot_sources_service.get_many.return_value = [
            BOOT_SOURCE_1,
            BOOT_SOURCE_2,
        ]

        # return a mocked file to assert that data has been written
        mock_file = AsyncMock()
        mocker.patch(
            "aiofiles.tempfile._temporary_file"
        ).return_value = mock_file
        mocker.patch("aiofiles.os.unlink").return_value = None

        mapping = await self.service.fetch_images_metadata()

        assert mapping == {BOOT_SOURCE_1: [], BOOT_SOURCE_2: []}
        # BOOT_SOURCE_2 has keyring_data while BOOT_SOURCE_1 has a keyring_filename
        mock_file.write.assert_called_once_with(BOOT_SOURCE_2.keyring_data)
        ss_client_mock.get_all_products.assert_has_awaits([call(), call()])

    async def test_cache_boot_sources_from_simplestreams_product(self) -> None:
        self.boot_source_cache_service.create_or_update.return_value = (
            BootSourceCache(
                id=1,
                os="grub-efi-signed",
                arch="amd64",
                subarch="generic",
                release="grub-efi-signed",
                label="stable",
                bootloader_type="uefi",
                boot_source_id=1,
                extra={},
            )
        )

        ss_product_list = [
            SimpleStreamsBootloaderProductList(
                content_id="com.ubuntu.maas:stable:1:bootloader-download",
                datatype=Datatype.image_ids,
                format="products:1.0",
                updated=None,
                products=[BOOTLOADER_PRODUCT],
            )
        ]

        await self.service.cache_boot_source_from_simplestreams_products(
            1, ss_product_list
        )
        self.boot_source_cache_service.create_or_update.assert_awaited_once()
        self.boot_source_cache_service.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootSourceCacheClauseFactory.and_clauses(
                    [
                        BootSourceCacheClauseFactory.with_boot_source_id(1),
                        BootSourceCacheClauseFactory.not_clause(
                            BootSourceCacheClauseFactory.with_ids({1})
                        ),
                    ]
                )
            )
        )

    async def test_cache_boot_sources_from_simplestreams_product__no_products(
        self,
    ) -> None:
        await self.service.cache_boot_source_from_simplestreams_products(1, [])

        self.boot_source_cache_service.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootSourceCacheClauseFactory.with_boot_source_id(1)
            )
        )
        self.boot_source_cache_service.create_or_update.assert_not_awaited()

    async def test_check_commissioning_series_selected__no_selection(
        self,
    ) -> None:
        self.configurations_service.get.side_effect = ["ubuntu", "noble"]
        self.boot_source_selections_service.exists.return_value = False
        self.boot_source_cache_service.exists.return_value = True

        await self.service.check_commissioning_series_selected()

        self.notifications_service.create.assert_awaited_once_with(
            NotificationBuilder(
                ident="commissioning_series_unselected",
                users=True,
                admins=True,
                message="ubuntu noble is configured "
                "as the commissioning release but it is not selected for download!",
                context={},
                user_id=None,
                category=NotificationCategoryEnum.ERROR,
                dismissable=True,
            )
        )

    async def test_check_commissioning_series_selected__no_cache(self) -> None:
        self.configurations_service.get.side_effect = ["ubuntu", "noble"]
        self.boot_source_selections_service.exists.return_value = True
        self.boot_source_cache_service.exists.return_value = False

        await self.service.check_commissioning_series_selected()

        self.notifications_service.create.assert_awaited_once_with(
            NotificationBuilder(
                ident="commissioning_series_unavailable",
                users=True,
                admins=True,
                message="ubuntu noble is configured "
                "as the commissioning release but it is unavailable in the "
                "configured streams!",
                context={},
                user_id=None,
                category=NotificationCategoryEnum.ERROR,
                dismissable=True,
            )
        )

    async def test_check_commissioning_series_selected__no_notifications(
        self,
    ) -> None:
        self.configurations_service.get.side_effect = ["ubuntu", "noble"]
        self.boot_source_selections_service.exists.return_value = True
        self.boot_source_cache_service.exists.return_value = True

        await self.service.check_commissioning_series_selected()

        self.notifications_service.create.assert_not_awaited()

    def test_bootloader_matches_selections(self):
        good = BOOTLOADER_PRODUCT
        bad_arch = BOOTLOADER_PRODUCT.copy()
        bad_arch.arch = "ppc64el"
        bad_name = BOOTLOADER_PRODUCT.copy()
        bad_name.product_name = (
            "com.ubuntu.maas.stable:9:grub-efi-signed:uefi:amd64"
        )

        assert self.service._bootloader_matches_selections(good) is True
        assert self.service._bootloader_matches_selections(bad_arch) is False
        assert self.service._bootloader_matches_selections(bad_name) is False

    def test_single_file_image_matches_selections(self) -> None:
        selections = [
            BootSourceSelection(
                id=1,
                os="centos",
                release="centos70",
                arches=["*"],
                subarches=["*"],
                labels=["*"],
                boot_source_id=1,
            )
        ]
        good = SingleFileProduct(
            product_name="com.ubuntu.maas.stable:centos-bases:7.0:amd64",
            arch="amd64",
            label="stable",
            os="centos",
            release="centos70",
            release_title="CentOS 7",
            subarch="generic",
            subarches="generic",
            support_eol=None,
            version="7.0",
            versions=[],
        )
        bad_release = good.copy()
        bad_release.release = "wrong-release"
        assert (
            self.service._single_file_image_matches_selections(
                good, selections
            )
            is True
        )
        assert (
            self.service._single_file_image_matches_selections(
                bad_release, selections
            )
            is False
        )

    def test_multi_file_image_matches_selections(self) -> None:
        selections = [BOOT_SELECTION_ORACULAR_SOURCE_1]

        good = MULTIFILE_PRODUCT_ORACULAR
        bad_name = MULTIFILE_PRODUCT_ORACULAR.copy()
        bad_name.product_name = (
            "com.ubuntu.maas.stable:v4:boot:24.10:amd64:ga-24.10"
        )
        bad_release = MULTIFILE_PRODUCT_ORACULAR.copy()
        bad_release.release = "noble"

        assert (
            self.service._multi_file_image_matches_selections(good, selections)
            is True
        )
        assert (
            self.service._multi_file_image_matches_selections(
                bad_name, selections
            )
            is False
        )
        assert (
            self.service._multi_file_image_matches_selections(
                bad_release, selections
            )
            is False
        )

    async def test_product_matches_selections_calls_right_function(
        self,
    ) -> None:
        self.service._single_file_image_matches_selections = Mock(
            return_value=True
        )
        self.service._multi_file_image_matches_selections = Mock(
            return_value=True
        )
        self.service._bootloader_matches_selections = Mock(return_value=True)

        match = self.service.product_matches_selections(
            Mock(BootloaderProduct), []
        )
        assert match is True
        self.service._bootloader_matches_selections.assert_called_once()

        match = self.service.product_matches_selections(
            Mock(SingleFileProduct), []
        )
        assert match is True
        self.service._single_file_image_matches_selections.assert_called_once()

        match = self.service.product_matches_selections(
            Mock(MultiFileProduct), []
        )
        assert match is True
        self.service._multi_file_image_matches_selections.assert_called_once()

        match = self.service.product_matches_selections(Mock(), [])
        assert match is False

    async def test_filter_products(self) -> None:
        bs1 = BOOT_SOURCE_1
        bs2 = BOOT_SOURCE_2
        bs1_product_list = [
            SimpleStreamsMultiFileProductList(
                content_id="com.ubuntu.maas:stable:v3:download",
                datatype=Datatype.image_ids,
                format="products:1.0",
                updated=None,
                products=[MULTIFILE_PRODUCT_NOBLE, MULTIFILE_PRODUCT_ORACULAR],
            )
        ]
        bs2_product_list = [
            SimpleStreamsMultiFileProductList(
                content_id="com.ubuntu.maas:stable:v3:download",
                datatype=Datatype.image_ids,
                format="products:1.0",
                updated=None,
                products=[MULTIFILE_PRODUCT_NOBLE],
            )
        ]

        selections = [
            BOOT_SELECTION_NOBLE_SOURCE_1,
            BOOT_SELECTION_NOBLE_SOURCE_2,
            BOOT_SELECTION_ORACULAR_SOURCE_1,
        ]

        self.boot_source_selections_service.get_many.return_value = selections

        mapping = {bs1: bs1_product_list}
        result = await self.service.filter_products(mapping)

        assert result == mapping

        mapping = {bs1: bs1_product_list, bs2: bs2_product_list}
        result = await self.service.filter_products(mapping)

        # we have noble and oracular in bs1 and only noble in bs2.
        # since bs2 has higher priority we expect to see noble only in bs2.
        bs1_product_list[0].products.pop(0)
        expected = {bs1: bs1_product_list, bs2: bs2_product_list}
        assert result == expected

    async def test_get_files_to_download_from_product__image_product(
        self,
    ):
        boot_resource = BOOT_RESOURCE_ORACULAR
        boot_resource_set = BOOT_RESOURCE_SET_ORACULAR
        product = MULTIFILE_PRODUCT_ORACULAR
        file_boot_initrd = BootResourceFile(
            id=1,
            filename="boot-initrd",
            filetype=BootResourceFileType.BOOT_INITRD,
            sha256="e42de3a72d142498c2945e8b0e1b9bad2fc031a2224b7497ccaca66199b51f93",
            size=75990212,
            filename_on_disk="e42de3a",
            extra={},
            resource_set_id=boot_resource_set.id,
        )
        file_boot_kernel = BootResourceFile(
            id=2,
            filename="boot-kernel",
            filetype=BootResourceFileType.BOOT_KERNEL,
            sha256="b2a29c2d269742933c15ed0ad48340ff4691261bdf0e6ba3c721dd15b835766d",
            size=15440264,
            filename_on_disk="b2a29c2",
            extra={},
            resource_set_id=boot_resource_set.id,
        )
        file_squashfs = BootResourceFile(
            id=3,
            filename="squashfs",
            filetype=BootResourceFileType.SQUASHFS_IMAGE,
            sha256="201b7972f0f3b3bc5a345b85ed3a63688981c74b3fe52805edb2853fdbd70bbf",
            size=272650240,
            filename_on_disk="201b797",
            extra={},
            resource_set_id=boot_resource_set.id,
        )
        # the manifest won't be downloaded, see `get_downloadable_files`

        resource_files = [
            file_boot_initrd,
            file_boot_kernel,
            file_squashfs,
        ]

        self.boot_resources_service.create_or_update_from_simplestreams_product.return_value = boot_resource
        self.boot_resource_sets_service.get_or_create_from_simplestreams_product.return_value = (
            boot_resource_set,
            True,
        )
        self.boot_resource_files_service.get_or_create_from_simplestreams_file.side_effect = resource_files
        # mark all the files as not complete
        self.boot_resource_file_sync_service.file_sync_complete.return_value = False
        (
            res_to_download,
            boot_res_id,
        ) = await self.service.get_files_to_download_from_product(
            "http://source-1.com", product
        )

        assert res_to_download == [
            ResourceDownloadParam(
                rfile_ids=[file.id],
                source_list=[f"http://source-1.com/{path}"],
                sha256=file.sha256,
                filename_on_disk=file.filename_on_disk,
                total_size=file.size,
                extract_paths=[],
            )
            for file, path in zip(
                resource_files,
                [
                    "oracular/amd64/20250404/ga-24.10/generic/boot-initrd",
                    "oracular/amd64/20250404/ga-24.10/generic/boot-kernel",
                    "oracular/amd64/20250404/squashfs",
                ],
            )
        ]
        assert boot_res_id == boot_resource.id

        self.boot_resources_service.create_or_update_from_simplestreams_product.assert_awaited_once_with(
            product
        )
        self.boot_resource_sets_service.get_or_create_from_simplestreams_product.assert_awaited_once_with(
            product, boot_resource.id
        )
        self.boot_resource_files_service.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceFileClauseFactory.and_clauses(
                    [
                        BootResourceFileClauseFactory.with_resource_set_id(
                            boot_resource_set.id
                        ),
                        BootResourceFileClauseFactory.with_filetype(
                            BootResourceFileType.ROOT_IMAGE
                        ),
                    ]
                )
            )
        )

    async def test_get_files_to_download_from_product__bootloader_product(
        self,
    ):
        boot_resource = BOOT_RESOURCE_BOOTLOADER
        boot_resource_set = BOOT_RESOURCE_SET_BOOTLOADER
        product = BOOTLOADER_PRODUCT
        file_grub2_signed = BootResourceFile(
            id=1,
            filename="grub2-signed.tar.xz",
            filetype=BootResourceFileType.ARCHIVE_TAR_XZ,
            sha256="9d4a3a826ed55c46412613d2f7caf3185da4d6b18f35225f4f6a5b86b2bccfe3",
            size=375316,
            filename_on_disk="9d4a3a8",
            extra={
                "src_package": "grub2-signed",
                "src_release": "focal",
                "src_version": "1.167.2+2.04-1ubuntu44.2",
            },
            resource_set_id=boot_resource_set.id,
        )
        file_shim_signed = BootResourceFile(
            id=2,
            filename="shim-signed.tar.xz",
            filetype=BootResourceFileType.ARCHIVE_TAR_XZ,
            sha256="07b42d0aa2540b6999c726eacf383e2c8f172378c964bdefab6d71410e2b72db",
            size=322336,
            filename_on_disk="07b42d0",
            extra={
                "src_package": "shim-signed",
                "src_release": "focal",
                "src_version": "1.40.7+15.4-0ubuntu9",
            },
            resource_set_id=boot_resource_set.id,
        )

        resource_files = [file_grub2_signed, file_shim_signed]

        self.boot_resources_service.create_or_update_from_simplestreams_product.return_value = boot_resource
        self.boot_resource_sets_service.get_or_create_from_simplestreams_product.return_value = (
            boot_resource_set,
            True,
        )
        self.boot_resource_files_service.get_or_create_from_simplestreams_file.side_effect = resource_files
        # mark all the files as not complete
        self.boot_resource_file_sync_service.file_sync_complete.return_value = False
        (
            res_to_download,
            boot_res_id,
        ) = await self.service.get_files_to_download_from_product(
            "http://source-1.com", product
        )

        assert res_to_download == [
            ResourceDownloadParam(
                rfile_ids=[file.id],
                source_list=[f"http://source-1.com/{path}"],
                sha256=file.sha256,
                filename_on_disk=file.filename_on_disk,
                total_size=file.size,
                extract_paths=[
                    f"{BOOTLOADERS_DIR}/{BOOT_RESOURCE_BOOTLOADER.bootloader_type}/{BOOT_RESOURCE_BOOTLOADER.architecture.split('/')[0]}"
                ],
            )
            for file, path in zip(
                resource_files,
                [
                    "bootloaders/uefi/amd64/20210819.0/grub2-signed.tar.xz",
                    "bootloaders/uefi/amd64/20210819.0/shim-signed.tar.xz",
                ],
            )
        ]
        assert boot_res_id == boot_resource.id

        self.boot_resources_service.create_or_update_from_simplestreams_product.assert_awaited_once_with(
            product
        )
        self.boot_resource_sets_service.get_or_create_from_simplestreams_product.assert_awaited_once_with(
            product, boot_resource.id
        )
        self.boot_resource_files_service.delete_many.assert_not_awaited()

    async def test_get_files_to_download_from_product_list(self) -> None:
        r1 = ResourceDownloadParam(
            rfile_ids=[1],
            source_list=["http://source-1.com/file-1"],
            sha256="0" * 64,
            filename_on_disk="0" * 7,
            total_size=1024,
            extract_paths=["path/to/file-1"],
        )
        r2 = ResourceDownloadParam(
            rfile_ids=[2],
            source_list=["http://source-2.com/file-2"],
            sha256="0" * 64,
            filename_on_disk="0" * 7,
            total_size=1024,
            extract_paths=["path/to/file-2"],
        )
        # Already tested above, mock for this test
        self.service.get_files_to_download_from_product = AsyncMock(
            side_effect=[([r1], 1), ([r2], 2)]
        )

        product_list = SimpleStreamsBootloaderProductList(
            content_id="com.ubuntu.maas:stable:1:bootloader-download",
            datatype=Datatype.image_ids,
            format="products:1.0",
            updated=None,
            products=[BOOTLOADER_PRODUCT, BOOTLOADER_PRODUCT],
        )

        (
            resources_to_download,
            used_boot_resource_ids,
        ) = await self.service.get_files_to_download_from_product_list(
            BOOT_SOURCE_1, [product_list]
        )

        assert len(resources_to_download) == 1
        assert resources_to_download["0" * 64] == ResourceDownloadParam(
            rfile_ids=[1, 2],
            source_list=[
                "http://source-1.com/file-1",
                "http://source-2.com/file-2",
            ],
            sha256="0" * 64,
            filename_on_disk="0" * 7,
            total_size=1024,
            extract_paths=["path/to/file-1", "path/to/file-2"],
        )

        assert used_boot_resource_ids == {1, 2}

    async def test_boot_resource_is_duplicated(self) -> None:
        await self.service._boot_resource_is_duplicated(
            BOOT_RESOURCE_BOOTLOADER, set()
        )

        self.boot_resources_service.exists.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.not_clause(
                            BootResourceClauseFactory.with_ids(set())
                        ),
                        BootResourceClauseFactory.with_name(
                            BOOT_RESOURCE_BOOTLOADER.name
                        ),
                        BootResourceClauseFactory.with_architecture_starting_with(
                            BOOT_RESOURCE_BOOTLOADER.architecture.split("/")[0]
                        ),
                    ]
                )
            )
        )

    async def test_boot_resource_is_selected(self) -> None:
        selections = [BOOT_SELECTION_ORACULAR_SOURCE_1]
        resource_set_label = "stable"
        is_selected = await self.service._boot_resource_is_selected(
            BOOT_RESOURCE_ORACULAR, resource_set_label, selections
        )
        assert is_selected is True
        is_selected = await self.service._boot_resource_is_selected(
            BOOT_RESOURCE_BOOTLOADER, resource_set_label, selections
        )
        assert is_selected is False

    async def test_delete_old_boot_resources__no_resources_to_delete(
        self,
    ) -> None:
        self.boot_resources_service.get_many.return_value = []
        await self.service.delete_old_boot_resources({1, 2})

    async def test_delete_old_boot_resources__keep_image(self) -> None:
        self.boot_resources_service.get_many.return_value = [
            BOOT_RESOURCE_ORACULAR
        ]
        self.boot_resource_sets_service.get_latest_for_boot_resource.return_value = BOOT_RESOURCE_SET_ORACULAR
        self.service._boot_resource_is_selected = AsyncMock(return_value=True)
        self.service._boot_resource_is_duplicated = AsyncMock(
            return_value=False
        )

        await self.service.delete_old_boot_resources({100})

        self.boot_resources_service.get_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.not_clause(
                            BootResourceClauseFactory.with_ids({100})
                        ),
                        BootResourceClauseFactory.with_rtype(
                            BootResourceType.SYNCED
                        ),
                    ]
                )
            )
        )
        self.boot_resource_sets_service.get_latest_for_boot_resource.assert_awaited_once_with(
            BOOT_RESOURCE_ORACULAR.id
        )
        self.events_service.record_event.assert_awaited_once_with(
            event_type=EventTypeEnum.REGION_IMPORT_WARNING,
            event_description=f"Boot image {BOOT_RESOURCE_ORACULAR.name}/"
            f"{BOOT_RESOURCE_ORACULAR.architecture} no longer exists in stream, "
            "but remains in selections. To delete this image remove its selection.",
        )
        self.boot_resources_service.delete_many.assert_awaited_once_with(
            query=QuerySpec(where=BootResourceClauseFactory.with_ids(set()))
        )

    async def test_delete_old_boot_resources__deletes_image(self) -> None:
        self.boot_resources_service.get_many.return_value = [
            BOOT_RESOURCE_ORACULAR
        ]
        self.boot_resource_sets_service.get_latest_for_boot_resource.return_value = BOOT_RESOURCE_SET_ORACULAR
        self.service._boot_resource_is_selected = AsyncMock(return_value=False)
        self.service._boot_resource_is_duplicated = AsyncMock(
            return_value=False
        )

        await self.service.delete_old_boot_resources({100})

        self.boot_resources_service.get_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.not_clause(
                            BootResourceClauseFactory.with_ids({100})
                        ),
                        BootResourceClauseFactory.with_rtype(
                            BootResourceType.SYNCED
                        ),
                    ]
                )
            )
        )
        self.boot_resource_sets_service.get_latest_for_boot_resource.assert_awaited_once_with(
            BOOT_RESOURCE_ORACULAR.id
        )
        self.events_service.record_event.assert_not_awaited()
        self.boot_resources_service.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceClauseFactory.with_ids(
                    {BOOT_RESOURCE_ORACULAR.id}
                )
            )
        )

    async def test_delete_old_boot_resource_sets(self) -> None:
        self.boot_resources_service.get_many.return_value = [
            BOOT_RESOURCE_ORACULAR
        ]
        set1 = BOOT_RESOURCE_ORACULAR.copy()
        set2 = BOOT_RESOURCE_ORACULAR.copy()
        set2.id = 2
        self.boot_resource_sets_service.get_many.return_value = [set2, set1]
        self.boot_resource_file_sync_service.resource_set_sync_complete.side_effect = [
            True,
            False,
        ]

        await self.service.delete_old_boot_resource_sets()

        self.boot_resources_service.get_many.assert_awaited_once()
        self.boot_resource_sets_service.get_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.with_resource_id(
                    BOOT_RESOURCE_ORACULAR.id
                ),
                order_by=[
                    OrderByClauseFactory.desc_clause(
                        BootResourceSetsOrderByClauses.by_id()
                    )
                ],
            )
        )
        self.boot_resource_sets_service.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.with_ids({set1.id})
            )
        )
        self.boot_resources_service.delete_all_without_sets.assert_awaited_once()


@pytest.mark.asyncio
class TestIntegrationImageSyncService:
    @pytest.fixture
    async def test_boot_source_1(self, fixture: Fixture) -> BootSource:
        return await create_test_bootsource_entry(
            fixture,
            url="http://source-1.com",
            priority=1,
            skip_keyring_verification=True,
        )

    @pytest.fixture
    async def test_boot_source_2(self, fixture: Fixture) -> BootSource:
        return await create_test_bootsource_entry(
            fixture,
            url="http://source-2.com",
            priority=2,
            skip_keyring_verification=True,
        )

    async def _setup_mocked_simplestreams_client(
        self,
        fixture: Fixture,
        boot_sources: list[BootSource],
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
        for boot_source in boot_sources:
            mock_aioresponse.get(
                f"{boot_source.url}/{SIGNED_INDEX_PATH}", payload=ss_index
            )
            product_paths = [v["path"] for v in ss_index["index"].values()]
            for path, product in zip(
                product_paths,
                [bootloader_products, ubuntu_products, centos_products],
            ):
                mock_aioresponse.get(
                    f"{boot_source.url}/{path}", payload=product
                )

    async def test_get_resources_to_download_single_boot_source(
        self,
        fixture: Fixture,
        services: ServiceCollectionV3,
        test_boot_source_1: BootSource,
        mocker,
        mock_aioresponse,
    ) -> None:
        """Tests the following flow:

        1. Fetch data from simplestreams
        2. Cache boot sources
        3. Check the commissioning series
        4. Filter products
        5. Get files to be downloaded
        """
        await self._setup_mocked_simplestreams_client(
            fixture, [test_boot_source_1], mocker, mock_aioresponse
        )
        # 1.
        mapping = await services.image_sync.fetch_images_metadata()
        assert mapping[test_boot_source_1] != []

        # 2.
        boot_source_caches = await fixture.get(BootSourceCacheTable.name)
        assert boot_source_caches == []
        created_boot_sources = []
        for bs, products_list in mapping.items():
            created_boot_sources.extend(
                await services.image_sync.cache_boot_source_from_simplestreams_products(
                    bs.id, products_list
                )
            )
        boot_source_caches = await fixture.get_typed(
            BootSourceCacheTable.name, BootSourceCache
        )
        assert boot_source_caches == created_boot_sources

        await create_test_configuration(
            fixture, name=CommissioningOSystemConfig.name, value="ubuntu"
        )
        await create_test_configuration(
            fixture, name=CommissioningDistroSeriesConfig.name, value="noble"
        )
        await create_test_bootsourceselection_entry(
            fixture,
            os="ubuntu",
            release="noble",
            boot_source_id=test_boot_source_1.id,
            arches=["amd64", "arm64"],
        )
        await create_test_bootsourceselection_entry(
            fixture,
            os="ubuntu",
            release="jammy",
            boot_source_id=test_boot_source_1.id,
            arches=["amd64"],
            subarches=["hwe-22.04"],
        )

        # 3.
        await services.image_sync.check_commissioning_series_selected()
        notifications = await fixture.get(NotificationTable.name)
        assert notifications == []

        # 4.
        mapping = await services.image_sync.filter_products(mapping)
        for product_list in mapping[test_boot_source_1]:
            if isinstance(product_list, SimpleStreamsBootloaderProductList):
                assert len(product_list.products) == 4
                os_arch = [(p.os, p.arch) for p in product_list.products]
                assert os_arch == [
                    ("grub-efi-signed", "amd64"),
                    ("grub-efi", "arm64"),
                    ("grub-ieee1275", "ppc64el"),
                    ("pxelinux", "i386"),
                ]
            elif isinstance(product_list, SimpleStreamsMultiFileProductList):
                assert len(product_list.products) == 3
                os_release_arch_subarch = [
                    (p.os, p.release, p.arch, p.subarch)
                    for p in product_list.products
                ]
                # The test data contains two entries for jammy amd64. Make sure
                # that we only selected the "hwe-22.04" subarch for jammy
                # and both amd64 and arm64 for noble.
                assert os_release_arch_subarch == [
                    ("ubuntu", "jammy", "amd64", "hwe-22.04"),
                    ("ubuntu", "noble", "amd64", "ga-24.04"),
                    ("ubuntu", "noble", "arm64", "ga-24.04"),
                ]
            elif isinstance(product_list, SimpleStreamsSingleFileProductList):
                assert len(product_list.products) == 0

        # 5.
        existing_boot_resources = await fixture.get(BootResourceTable.name)
        assert existing_boot_resources == []
        (
            resources_to_download,
            boot_resource_ids,
        ) = await services.image_sync.get_files_to_download_from_product_list(
            test_boot_source_1, mapping[test_boot_source_1]
        )

        created_boot_resources = await fixture.get_typed(
            BootResourceTable.name, BootResource
        )
        assert {br.id for br in created_boot_resources} == boot_resource_ids

        sha256s = {
            file.sha256
            for products_list in mapping[test_boot_source_1]
            for product in products_list.products
            for file in product.get_latest_version().get_downloadable_files()
        }
        assert set(resources_to_download.keys()) == sha256s

    async def test_get_resources_to_download_multiple_boot_sources(
        self,
        fixture: Fixture,
        services: ServiceCollectionV3,
        test_boot_source_1: BootSource,
        test_boot_source_2: BootSource,
        mocker,
        mock_aioresponse,
    ) -> None:
        """Tests the following flow:

        1. Fetch data from simplestreams
        2. Cache boot sources
        3. Check the commissioning series
        4. Filter products
        5. Get files to be downloaded
        """
        boot_sources = [test_boot_source_1, test_boot_source_2]

        await self._setup_mocked_simplestreams_client(
            fixture, boot_sources, mocker, mock_aioresponse
        )
        # 1.
        mapping = await services.image_sync.fetch_images_metadata()
        for boot_source in boot_sources:
            assert mapping[boot_source] != []

        # 2.
        boot_source_caches = await fixture.get(BootSourceCacheTable.name)
        assert boot_source_caches == []
        created_boot_sources = []
        for boot_source, products_list in mapping.items():
            created_boot_sources.extend(
                await services.image_sync.cache_boot_source_from_simplestreams_products(
                    boot_source.id, products_list
                )
            )
        boot_source_caches = await fixture.get_typed(
            BootSourceCacheTable.name, BootSourceCache
        )
        assert boot_source_caches == created_boot_sources

        await create_test_configuration(
            fixture, name=CommissioningOSystemConfig.name, value="ubuntu"
        )
        await create_test_configuration(
            fixture, name=CommissioningDistroSeriesConfig.name, value="noble"
        )
        # remember: test_boot_source_2 has higher priority
        await create_test_bootsourceselection_entry(
            fixture,
            os="ubuntu",
            release="noble",
            boot_source_id=test_boot_source_2.id,
            arches=["arm64"],
        )
        await create_test_bootsourceselection_entry(
            fixture,
            os="ubuntu",
            release="noble",
            boot_source_id=test_boot_source_1.id,
            arches=["amd64", "arm64"],
        )
        await create_test_bootsourceselection_entry(
            fixture,
            os="ubuntu",
            release="jammy",
            boot_source_id=test_boot_source_1.id,
            arches=["amd64"],
            subarches=["hwe-22.04"],
        )

        # 3.
        await services.image_sync.check_commissioning_series_selected()
        notifications = await fixture.get(NotificationTable.name)
        assert notifications == []

        # 4.
        mapping = await services.image_sync.filter_products(mapping)

        for product_list in mapping[test_boot_source_2]:
            if isinstance(product_list, SimpleStreamsBootloaderProductList):
                assert len(product_list.products) == 4
                os_arch = [(p.os, p.arch) for p in product_list.products]
                assert os_arch == [
                    ("grub-efi-signed", "amd64"),
                    ("grub-efi", "arm64"),
                    ("grub-ieee1275", "ppc64el"),
                    ("pxelinux", "i386"),
                ]
            elif isinstance(product_list, SimpleStreamsMultiFileProductList):
                assert len(product_list.products) == 1
                os_release_arch_subarch = [
                    (p.os, p.release, p.arch, p.subarch)
                    for p in product_list.products
                ]
                # test_boot_source_2 has higher priority, so noble arm64 will
                # be downloaded only from this source
                assert os_release_arch_subarch == [
                    ("ubuntu", "noble", "arm64", "ga-24.04"),
                ]
            elif isinstance(product_list, SimpleStreamsSingleFileProductList):
                assert len(product_list.products) == 0

        for product_list in mapping[test_boot_source_1]:
            if isinstance(product_list, SimpleStreamsBootloaderProductList):
                # these already being downloaded by the other boot source
                # since they are the same
                assert len(product_list.products) == 0

            elif isinstance(product_list, SimpleStreamsMultiFileProductList):
                assert len(product_list.products) == 2
                os_release_arch_subarch = [
                    (p.os, p.release, p.arch, p.subarch)
                    for p in product_list.products
                ]
                assert os_release_arch_subarch == [
                    ("ubuntu", "jammy", "amd64", "hwe-22.04"),
                    ("ubuntu", "noble", "amd64", "ga-24.04"),
                ]
            elif isinstance(product_list, SimpleStreamsSingleFileProductList):
                assert len(product_list.products) == 0
        # 5.
        existing_boot_resources = await fixture.get(BootResourceTable.name)
        assert existing_boot_resources == []
        (
            resources_to_download_1,
            boot_resource_ids_1,
        ) = await services.image_sync.get_files_to_download_from_product_list(
            test_boot_source_1, mapping[test_boot_source_1]
        )
        (
            resources_to_download_2,
            boot_resource_ids_2,
        ) = await services.image_sync.get_files_to_download_from_product_list(
            test_boot_source_2, mapping[test_boot_source_2]
        )

        created_boot_resources_1 = await fixture.get_typed(
            BootResourceTable.name, BootResource
        )
        assert {
            br.id for br in created_boot_resources_1
        } == boot_resource_ids_1.union(boot_resource_ids_2)

        sha256_source_1 = {
            file.sha256
            for products_list in mapping[test_boot_source_1]
            for product in products_list.products
            for file in product.get_latest_version().get_downloadable_files()
        }
        assert set(resources_to_download_1.keys()) == sha256_source_1
        sha256_source_2 = {
            file.sha256
            for products_list in mapping[test_boot_source_2]
            for product in products_list.products
            for file in product.get_latest_version().get_downloadable_files()
        }

        assert set(resources_to_download_2.keys()) == sha256_source_2

    async def test_delete_old_boot_resources(
        self,
        fixture: Fixture,
        services: ServiceCollectionV3,
        test_boot_source_1: BootSource,
    ) -> None:
        # must be deleted - no resource set associated
        await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.SYNCED,
            name="ubuntu/noble",
            architecture="amd64/ga24.04",
        )
        # must be deleted - no selection applies to this
        to_delete_1 = await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.SYNCED,
            name="ubuntu/focal",
            architecture="amd64/ga20.04",
        )
        await create_test_bootresourceset_entry(
            fixture,
            version="20250618",
            label="stable",
            resource_id=to_delete_1.id,
        )

        # must be kept - matches a selection
        to_keep = await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.SYNCED,
            name="ubuntu/noble",
            architecture="amd64/hwe24.04",
        )
        await create_test_bootresourceset_entry(
            fixture, version="20250618", label="stable", resource_id=to_keep.id
        )

        await create_test_bootsourceselection_entry(
            fixture,
            os="ubuntu",
            release="noble",
            boot_source_id=test_boot_source_1.id,
        )

        await services.image_sync.delete_old_boot_resources(set())

        boot_resources = await fixture.get_typed(
            BootResourceTable.name, BootResource
        )

        assert boot_resources == [to_keep]

        events = await fixture.get(EventTable.name)
        assert len(events) == 1
        assert events[0]["description"] == (
            "Boot image ubuntu/noble/amd64/hwe24.04 no longer exists in stream, "
            "but remains in selections. To delete this image remove its selection."
        )

    async def test_delete_old_boot_resource_sets(
        self,
        fixture: Fixture,
        services: ServiceCollectionV3,
    ) -> None:
        """
        Setup and expected behavior:
            - br_1: boot resource with an associated empty boot resource set. Both
            of them will be deleted (first we remove the set because is not complete
            and then the boot resources since it doesn't have any associated set)
            - br_2: boot resource with a completely synced resource set. Nothing
            will be deleted
            - br_3: boot resource with two completely synced resource sets. The
            older one will be deleted.

        """
        region = await create_test_region_controller_entry(fixture)
        br_1 = await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.SYNCED,
            name="ubuntu/focal",
            architecture="amd64/ga20.04",
        )
        await create_test_bootresourceset_entry(
            fixture, version="20250618", label="stable", resource_id=br_1.id
        )

        br_2 = await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.SYNCED,
            name="ubuntu/noble",
            architecture="amd64/hwe24.04",
        )
        set_2 = await create_test_bootresourceset_entry(
            fixture, version="20250618", label="stable", resource_id=br_2.id
        )
        file_2 = await create_test_bootresourcefile_entry(
            fixture,
            filename="filename1",
            filetype=BootResourceFileType.SQUASHFS_IMAGE,
            sha256="0" * 7,
            filename_on_disk="0" * 7,
            size=100,
            resource_set_id=set_2.id,
        )
        await create_test_bootresourcefilesync_entry(
            fixture,
            size=100,
            file_id=file_2.id,
            region_id=region["id"],
        )

        br_3 = await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.SYNCED,
            name="ubuntu/noble",
            architecture="arm64/hwe24.04",
        )
        set_3a = await create_test_bootresourceset_entry(
            fixture, version="20250617", label="stable", resource_id=br_3.id
        )
        file_3a = await create_test_bootresourcefile_entry(
            fixture,
            filename="filename2",
            filetype=BootResourceFileType.SQUASHFS_IMAGE,
            sha256="1" * 7,
            filename_on_disk="1" * 7,
            size=100,
            resource_set_id=set_3a.id,
        )
        await create_test_bootresourcefilesync_entry(
            fixture,
            size=100,
            file_id=file_3a.id,
            region_id=region["id"],
        )
        set_3b = await create_test_bootresourceset_entry(
            fixture, version="20250618", label="stable", resource_id=br_3.id
        )
        file_3b = await create_test_bootresourcefile_entry(
            fixture,
            filename="filename3",
            filetype=BootResourceFileType.SQUASHFS_IMAGE,
            sha256="2" * 7,
            filename_on_disk="2" * 7,
            size=100,
            resource_set_id=set_3b.id,
        )
        await create_test_bootresourcefilesync_entry(
            fixture,
            size=100,
            file_id=file_3b.id,
            region_id=region["id"],
        )

        services.boot_resource_files.temporal_service = Mock(TemporalService)

        await services.image_sync.delete_old_boot_resource_sets()

        boot_resource_sets = await fixture.get_typed(
            BootResourceSetTable.name, BootResourceSet
        )
        assert len(boot_resource_sets) == 2
        assert set_3a not in boot_resource_sets
        assert set_3b in boot_resource_sets
        assert set_2 in boot_resource_sets

        boot_resource_files = await fixture.get_typed(
            BootResourceFileTable.name, BootResourceFile
        )
        assert len(boot_resource_files) == 2
        assert file_3a not in boot_resource_files
        assert file_3b in boot_resource_files
        assert file_2 in boot_resource_files

        boot_resources = await fixture.get_typed(
            BootResourceTable.name, BootResource
        )
        assert len(boot_resources) == 2
        assert br_1 not in boot_resources
        assert br_2 in boot_resources
        assert br_3 in boot_resources

        services.boot_resource_files.temporal_service.register_or_update_workflow_call.assert_called_once_with(
            DELETE_BOOTRESOURCE_WORKFLOW_NAME,
            parameter=ResourceDeleteParam(
                files=[
                    ResourceIdentifier(
                        sha256=file_3a.sha256,
                        filename_on_disk=file_3a.filename_on_disk,
                    )
                ]
            ),
            parameter_merge_func=ANY,
        )
