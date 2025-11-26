# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import json
from unittest.mock import ANY, AsyncMock, call, Mock

import pytest

from maascommon.constants import (
    BOOTLOADERS_DIR,
    DEFAULT_IMAGES_URL,
    DEFAULT_KEYRINGS_PATH,
)
from maascommon.enums.boot_resources import (
    BootResourceFileType,
    BootResourceType,
)
from maascommon.enums.msm import MSMStatusEnum
from maascommon.enums.notifications import NotificationCategoryEnum
from maascommon.workflows.bootresource import (
    DELETE_BOOTRESOURCE_WORKFLOW_NAME,
    ResourceDeleteParam,
    ResourceDownloadParam,
    ResourceIdentifier,
)
from maasservicelayer.builders.bootsources import BootSourceBuilder
from maasservicelayer.builders.bootsourceselections import (
    BootSourceSelectionBuilder,
)
from maasservicelayer.builders.notifications import NotificationBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresourcefiles import (
    BootResourceFileClauseFactory,
)
from maasservicelayer.db.repositories.bootsources import (
    BootSourcesClauseFactory,
)
from maasservicelayer.db.repositories.notifications import (
    NotificationsClauseFactory,
)
from maasservicelayer.db.tables import (
    BootResourceFileTable,
    BootResourceSetTable,
    BootResourceTable,
)
from maasservicelayer.models.bootresourcefiles import BootResourceFile
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.models.bootresourcesets import BootResourceSet
from maasservicelayer.models.bootsourcecache import BootSourceCache
from maasservicelayer.models.bootsources import BootSource
from maasservicelayer.models.bootsourceselections import BootSourceSelection
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.boot_sources import BootSourcesService
from maasservicelayer.services.bootresourcefiles import (
    BootResourceFilesService,
)
from maasservicelayer.services.bootresources import BootResourceService
from maasservicelayer.services.bootresourcesets import BootResourceSetsService
from maasservicelayer.services.bootsourcecache import BootSourceCacheService
from maasservicelayer.services.bootsourceselections import (
    BootSourceSelectionsService,
)
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.image_sync import ImageSyncService
from maasservicelayer.services.msm import MSMService, MSMStatus
from maasservicelayer.services.notifications import NotificationsService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.simplestreams.models import (
    BootloaderProduct,
    BootloaderVersion,
    Datatype,
    MultiFileImageVersion,
    MultiFileProduct,
    SimpleStreamsBootloaderProductList,
    SimpleStreamsManifest,
    SimpleStreamsMultiFileProductList,
    SimpleStreamsProductListFactory,
    SimpleStreamsSingleFileProductList,
    SingleFileProduct,
)
from maasservicelayer.utils.date import utcnow
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
from tests.fixtures.factories.node import create_test_region_controller_entry
from tests.maasapiserver.fixtures.db import Fixture

MSM_SS_EP = "site/v1/images/latest/stable/streams/v1/index.json"

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
BOOT_SOURCE_MSM = BootSource(
    id=2,
    url=f"http://maas-site-manager.io/{MSM_SS_EP}",
    keyring_filename=None,
    keyring_data=b"some bytes",
    priority=2,
    skip_keyring_verification=True,
)

BOOT_SELECTION_NOBLE_SOURCE_1 = BootSourceSelection(
    id=1,
    os="ubuntu",
    release="noble",
    arch="amd64",
    boot_source_id=BOOT_SOURCE_1.id,
)

BOOT_SELECTION_NOBLE_SOURCE_2 = BootSourceSelection(
    id=1,
    os="ubuntu",
    release="noble",
    arch="amd64",
    boot_source_id=BOOT_SOURCE_2.id,
)
BOOT_SELECTION_ORACULAR_SOURCE_1 = BootSourceSelection(
    id=2,
    os="ubuntu",
    release="oracular",
    arch="amd64",
    boot_source_id=BOOT_SOURCE_1.id,
)

BOOT_RESOURCE_NOBLE = BootResource(
    id=1,
    rtype=BootResourceType.SYNCED,
    name="ubuntu/noble",
    architecture="amd64/ga-24.04",
    extra={},
    rolling=False,
    base_image="",
    selection_id=BOOT_SELECTION_NOBLE_SOURCE_1.id,
)


BOOT_RESOURCE_SET_NOBLE = BootResourceSet(
    id=1,
    version="20250718",
    label="stable",
    resource_id=BOOT_RESOURCE_NOBLE.id,
)

BOOT_RESOURCE_ORACULAR = BootResource(
    id=2,
    rtype=BootResourceType.SYNCED,
    name="ubuntu/oracular",
    architecture="amd64/ga-24.10",
    extra={},
    rolling=False,
    base_image="",
    selection_id=BOOT_SELECTION_ORACULAR_SOURCE_1.id,
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
        self.msm_service = Mock(MSMService)
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
            msm_service=self.msm_service,
            configurations_service=self.configurations_service,
            notifications_service=self.notifications_service,
        )

    async def test_ensure_boot_source_definition_creates_default_source(
        self, mocker
    ):
        self.boot_sources_service.exists.return_value = False
        self.boot_sources_service.create.return_value = BootSource(
            id=1,
            url=DEFAULT_IMAGES_URL,
            keyring_filename=DEFAULT_KEYRINGS_PATH,
            keyring_data=b"",
            priority=1,
            skip_keyring_verification=False,
        )

        arch = "test-arch"
        mocker.patch(
            "maasservicelayer.services.image_sync.get_architecture"
        ).return_value = arch

        created = await self.service.ensure_boot_source_definition()
        assert created

        self.boot_sources_service.create.assert_awaited_once_with(
            BootSourceBuilder(
                url=DEFAULT_IMAGES_URL,
                keyring_filename=DEFAULT_KEYRINGS_PATH,
                keyring_data=b"",
                priority=1,
                skip_keyring_verification=False,
            )
        )
        self.boot_source_selections_service.create_without_boot_source_cache.assert_has_awaits(
            [
                call(
                    BootSourceSelectionBuilder(
                        boot_source_id=1,
                        os="ubuntu",
                        release="noble",
                        arch=arch,
                    )
                ),
                call(
                    BootSourceSelectionBuilder(
                        boot_source_id=1,
                        os="ubuntu",
                        release="noble",
                        arch="amd64",
                    )
                ),
            ]
        )

    async def test_ensure_boot_source_definition_creates_with_default_arch(
        self, mocker
    ):
        self.boot_sources_service.exists.return_value = False
        self.boot_sources_service.create.return_value = BootSource(
            id=1,
            url=DEFAULT_IMAGES_URL,
            keyring_filename=DEFAULT_KEYRINGS_PATH,
            keyring_data=b"",
            priority=1,
            skip_keyring_verification=False,
        )

        mocker.patch(
            "maasservicelayer.services.image_sync.get_architecture"
        ).return_value = ""

        created = await self.service.ensure_boot_source_definition()

        assert created
        self.boot_sources_service.create.assert_awaited_once_with(
            BootSourceBuilder(
                url=DEFAULT_IMAGES_URL,
                keyring_filename=DEFAULT_KEYRINGS_PATH,
                keyring_data=b"",
                priority=1,
                skip_keyring_verification=False,
            )
        )
        self.boot_source_selections_service.create_without_boot_source_cache.assert_awaited_once_with(
            BootSourceSelectionBuilder(
                boot_source_id=1,
                os="ubuntu",
                release="noble",
                arch="amd64",
            )
        )

    async def test_ensure_boot_source_definition_updates_default_source_snap(
        self, mocker, monkeypatch
    ):
        self.boot_sources_service.exists.return_value = True
        self.boot_sources_service.get_one.return_value = BootSource(
            id=1,
            url=DEFAULT_IMAGES_URL,
            keyring_filename=DEFAULT_KEYRINGS_PATH,
            keyring_data=b"",
            priority=1,
            skip_keyring_verification=False,
        )
        mocker.patch(
            "maasservicelayer.services.image_sync.DEFAULT_KEYRINGS_PATH",
            "/some/other/path/keyring.gpg",
        )
        monkeypatch.setenv("SNAP", "/snap/maas/current")

        created = await self.service.ensure_boot_source_definition()

        assert not created
        self.boot_sources_service.create.assert_not_awaited()
        self.boot_sources_service.get_one.assert_awaited_once_with(
            query=QuerySpec(
                where=BootSourcesClauseFactory.with_url(DEFAULT_IMAGES_URL)
            )
        )
        self.boot_sources_service.update_by_id.assert_awaited_once_with(
            id=1,
            builder=BootSourceBuilder(
                keyring_filename="/some/other/path/keyring.gpg"
            ),
        )

    async def test_ensure_boot_source_definition_skips_if_already_present(
        self, monkeypatch
    ):
        self.boot_sources_service.exists.return_value = True
        monkeypatch.delenv("SNAP", raising=False)

        created = await self.service.ensure_boot_source_definition()

        assert not created
        self.boot_sources_service.create.assert_not_awaited()
        self.boot_sources_service.update_by_id.assert_not_awaited()

    async def test_ensure_boot_source_definition_does_nothing_if_default_source_not_present(
        self, monkeypatch
    ):
        self.boot_sources_service.exists.return_value = True
        self.boot_sources_service.get_one.return_value = None
        monkeypatch.setenv("SNAP", "/snap/maas/current")

        created = await self.service.ensure_boot_source_definition()

        assert not created
        self.boot_sources_service.create.assert_not_awaited()
        self.boot_sources_service.update_by_id.assert_not_awaited()

    async def test_sync_boot_source_selections_from_msm(self) -> None:
        self.msm_service.get_status.return_value = MSMStatus(
            sm_url="http://maas-site-manager.io",
            sm_jwt="some-token",
            running=MSMStatusEnum.CONNECTED,
            start_time=None,
        )
        boot_sources = [
            BootSource(
                id=100,
                url=f"http://maas-site-manager.io/{MSM_SS_EP}",
                keyring_filename="",
                keyring_data=None,
                priority=1,
                skip_keyring_verification=True,
            )
        ]
        self.boot_source_cache_service.get_many.return_value = [
            BootSourceCache(
                id=100,
                os="ubuntu",
                arch="amd64",
                release="noble",
                subarch="generic",
                label="stable",
                boot_source_id=100,
                extra={},
            )
        ]
        self.boot_source_selections_service.exists.return_value = False

        await self.service.sync_boot_source_selections_from_msm(boot_sources)

        self.boot_source_selections_service.create.assert_awaited_once_with(
            BootSourceSelectionBuilder(
                os="ubuntu",
                release="noble",
                boot_source_id=100,
                arch="amd64",
            )
        )

    @pytest.mark.parametrize(
        "msm_status",
        [
            None,
            MSMStatus(
                sm_url="http://maas-site-manager.io",
                sm_jwt="",
                running=MSMStatusEnum.PENDING,
                start_time=None,
            ),
            MSMStatus(
                sm_url="http://maas-site-manager.io",
                sm_jwt="",
                running=MSMStatusEnum.NOT_CONNECTED,
                start_time=None,
            ),
        ],
    )
    async def test_sync_boot_source_selections_from_msm__not_connected(
        self, msm_status: MSMStatus | None
    ) -> None:
        self.msm_service.get_status.return_value = msm_status

        await self.service.sync_boot_source_selections_from_msm([])

        self.boot_source_cache_service.get_many.assert_not_awaited()
        self.boot_source_selections_service.exists.assert_not_awaited()
        self.boot_source_selections_service.create.assert_not_awaited()

    async def test_check_commissioning_series_selected__no_selection(
        self,
    ) -> None:
        self.configurations_service.get.side_effect = ["ubuntu", "noble"]
        self.boot_source_selections_service.exists.return_value = False
        self.boot_source_cache_service.exists.return_value = True

        await self.service.check_commissioning_series_selected()

        self.notifications_service.get_or_create.assert_awaited_once_with(
            query=QuerySpec(
                where=NotificationsClauseFactory.with_ident(
                    "commissioning_series_unselected"
                )
            ),
            builder=NotificationBuilder(
                ident="commissioning_series_unselected",
                users=True,
                admins=True,
                message="ubuntu noble is configured "
                "as the commissioning release but it is not selected for download!",
                context={},
                user_id=None,
                category=NotificationCategoryEnum.ERROR,
                dismissable=True,
            ),
        )

    async def test_check_commissioning_series_selected__no_cache(self) -> None:
        self.configurations_service.get.side_effect = ["ubuntu", "noble"]
        self.boot_source_selections_service.exists.return_value = True
        self.boot_source_cache_service.exists.return_value = False

        await self.service.check_commissioning_series_selected()

        self.notifications_service.get_or_create.assert_awaited_once_with(
            query=QuerySpec(
                where=NotificationsClauseFactory.with_ident(
                    "commissioning_series_unavailable"
                )
            ),
            builder=NotificationBuilder(
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
            ),
        )

    async def test_check_commissioning_series_selected__no_notifications(
        self,
    ) -> None:
        self.configurations_service.get.side_effect = ["ubuntu", "noble"]
        self.boot_source_selections_service.exists.return_value = True
        self.boot_source_cache_service.exists.return_value = True

        await self.service.check_commissioning_series_selected()

        self.notifications_service.create.assert_not_awaited()

    def test_bootloader_matches_selection(self):
        good = BOOTLOADER_PRODUCT
        bad_arch = BOOTLOADER_PRODUCT.copy()
        bad_arch.arch = "ppc64el"
        bad_name = BOOTLOADER_PRODUCT.copy()
        bad_name.product_name = (
            "com.ubuntu.maas.stable:9:grub-efi-signed:uefi:amd64"
        )

        assert self.service._bootloader_matches_selection(good) is True
        assert self.service._bootloader_matches_selection(bad_arch) is False
        assert self.service._bootloader_matches_selection(bad_name) is False

    def test_single_file_image_matches_selection(self) -> None:
        selection = BootSourceSelection(
            id=1,
            os="centos",
            release="centos70",
            arch="amd64",
            boot_source_id=1,
        )
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
            self.service._single_file_image_matches_selection(good, selection)
            is True
        )
        assert (
            self.service._single_file_image_matches_selection(
                bad_release, selection
            )
            is False
        )

    def test_multi_file_image_matches_selection(self) -> None:
        selection = BOOT_SELECTION_ORACULAR_SOURCE_1

        good = MULTIFILE_PRODUCT_ORACULAR
        bad_name = MULTIFILE_PRODUCT_ORACULAR.copy()
        bad_name.product_name = (
            "com.ubuntu.maas.stable:v4:boot:24.10:amd64:ga-24.10"
        )
        bad_release = MULTIFILE_PRODUCT_ORACULAR.copy()
        bad_release.release = "noble"

        assert (
            self.service._multi_file_image_matches_selection(good, selection)
            is True
        )
        assert (
            self.service._multi_file_image_matches_selection(
                bad_name, selection
            )
            is False
        )
        assert (
            self.service._multi_file_image_matches_selection(
                bad_release, selection
            )
            is False
        )

    async def test_product_matches_selection_calls_right_function(
        self,
    ) -> None:
        self.service._single_file_image_matches_selection = Mock(
            return_value=True
        )
        self.service._multi_file_image_matches_selection = Mock(
            return_value=True
        )
        self.service._bootloader_matches_selection = Mock(return_value=True)

        match = self.service.product_matches_selection(
            Mock(BootloaderProduct), Mock(BootSourceSelection)
        )
        assert match is True
        self.service._bootloader_matches_selection.assert_called_once()

        match = self.service.product_matches_selection(
            Mock(SingleFileProduct), Mock(BootSourceSelection)
        )
        assert match is True
        self.service._single_file_image_matches_selection.assert_called_once()

        match = self.service.product_matches_selection(
            Mock(MultiFileProduct), Mock(BootSourceSelection)
        )
        assert match is True
        self.service._multi_file_image_matches_selection.assert_called_once()

        match = self.service.product_matches_selection(
            Mock(), Mock(BootSourceSelection)
        )
        assert match is False

    async def test_filter_products_for_selection(self) -> None:
        updated = utcnow()
        product_list = [
            SimpleStreamsMultiFileProductList(
                content_id="com.ubuntu.maas:stable:v3:download",
                datatype=Datatype.image_ids,
                format="products:1.0",
                updated=updated,
                products=[MULTIFILE_PRODUCT_NOBLE, MULTIFILE_PRODUCT_ORACULAR],
            )
        ]

        result = self.service.filter_products_for_selection(
            BOOT_SELECTION_NOBLE_SOURCE_1, product_list
        )
        expected = [
            SimpleStreamsMultiFileProductList(
                content_id="com.ubuntu.maas:stable:v3:download",
                datatype=Datatype.image_ids,
                format="products:1.0",
                updated=updated,
                products=[MULTIFILE_PRODUCT_NOBLE],
            )
        ]

        assert result == expected

        result = self.service.filter_products_for_selection(
            BOOT_SELECTION_ORACULAR_SOURCE_1, product_list
        )
        expected = [
            SimpleStreamsMultiFileProductList(
                content_id="com.ubuntu.maas:stable:v3:download",
                datatype=Datatype.image_ids,
                format="products:1.0",
                updated=updated,
                products=[MULTIFILE_PRODUCT_ORACULAR],
            )
        ]

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

        self.boot_resources_service.get_or_create.return_value = (
            boot_resource,
            False,
        )
        self.boot_source_selections_service.get_one.return_value = (
            BOOT_SELECTION_ORACULAR_SOURCE_1
        )
        self.boot_resource_sets_service.get_or_create_from_simplestreams_product.return_value = boot_resource_set
        self.boot_resource_files_service.get_or_create_from_simplestreams_file.side_effect = resource_files
        # mark all the files as not complete
        self.boot_resource_files_service.is_sync_complete.return_value = False
        res_to_download = (
            await self.service.get_files_to_download_from_product(
                BOOT_SOURCE_1, product
            )
        )

        assert res_to_download == [
            ResourceDownloadParam(
                rfile_ids=[file.id],
                source_list=[f"{BOOT_SOURCE_1.url}/{path}"],
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

        self.boot_resources_service.get_or_create.assert_awaited_once()
        # boot resource already had the selection id
        self.boot_source_selections_service.get_one.assert_not_awaited()
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

        self.boot_resources_service.get_or_create.return_value = (
            boot_resource,
            False,
        )
        self.boot_resource_sets_service.get_or_create_from_simplestreams_product.return_value = boot_resource_set
        self.boot_resource_files_service.get_or_create_from_simplestreams_file.side_effect = resource_files
        # mark all the files as not complete
        self.boot_resource_files_service.is_sync_complete.return_value = False
        res_to_download = (
            await self.service.get_files_to_download_from_product(
                BOOT_SOURCE_1, product
            )
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

        self.boot_resources_service.get_or_create.assert_awaited_once()
        self.boot_source_selections_service.get_one.assert_not_awaited()
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
            side_effect=[[r1], [r2]]
        )

        product_list = SimpleStreamsBootloaderProductList(
            content_id="com.ubuntu.maas:stable:1:bootloader-download",
            datatype=Datatype.image_ids,
            format="products:1.0",
            updated=utcnow(),
            products=[BOOTLOADER_PRODUCT, BOOTLOADER_PRODUCT],
        )

        resources_to_download = (
            await self.service.get_files_to_download_from_product_list(
                BOOT_SOURCE_1, [product_list]
            )
        )

        assert len(resources_to_download) == 1
        assert resources_to_download[0] == ResourceDownloadParam(
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

    @pytest.fixture
    async def manifest(
        self,
    ) -> SimpleStreamsManifest:
        bootloader_products = json.loads(
            get_test_data_file("simplestreams_bootloaders.json")
        )

        ubuntu_products = json.loads(
            get_test_data_file("simplestreams_ubuntu.json")
        )

        centos_products = json.loads(
            get_test_data_file("simplestreams_centos.json")
        )
        return [
            SimpleStreamsProductListFactory.produce(p)
            for p in (bootloader_products, ubuntu_products, centos_products)
        ]

    async def test_get_resources_to_download_single_boot_source(
        self,
        fixture: Fixture,
        services: ServiceCollectionV3,
        test_boot_source_1: BootSource,
        manifest: SimpleStreamsManifest,
    ) -> None:
        """Tests the following flow:

        Given a manifest for a boot_source, and a selection:
            - Filter products for a selection
            - Get files to be downloaded
        """
        selection_noble_amd = await create_test_bootsourceselection_entry(
            fixture,
            os="ubuntu",
            release="noble",
            boot_source_id=test_boot_source_1.id,
            arch="amd64",
        )

        # 4.
        filtered_products_list = (
            services.image_sync.filter_products_for_selection(
                selection_noble_amd, manifest
            )
        )
        for product_list in filtered_products_list:
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
                os_release_arch_subarch = [
                    (p.os, p.release, p.arch, p.subarch)
                    for p in product_list.products
                ]
                assert len(product_list.products) == 1
                os_release_arch_subarch = [
                    (p.os, p.release, p.arch, p.subarch)
                    for p in product_list.products
                ]
                assert os_release_arch_subarch == [
                    ("ubuntu", "noble", "amd64", "ga-24.04"),
                ]
            elif isinstance(product_list, SimpleStreamsSingleFileProductList):
                assert len(product_list.products) == 0

        # 5.
        existing_boot_resources = await fixture.get(BootResourceTable.name)
        assert existing_boot_resources == []
        resources_to_download = (
            await services.image_sync.get_files_to_download_from_product_list(
                test_boot_source_1, filtered_products_list
            )
        )

        sha256s = {
            file.sha256
            for products_list in filtered_products_list
            for product in products_list.products
            for file in product.get_latest_version().get_downloadable_files()
        }
        assert {r.sha256 for r in resources_to_download} == sha256s

    async def test_cleanup_boot_resource_sets_for_selection(
        self,
        fixture: Fixture,
        test_boot_source_1: BootSource,
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
        selection = await create_test_bootsourceselection_entry(
            fixture,
            os="ubuntu",
            release="noble",
            arch="amd64",
            boot_source_id=test_boot_source_1.id,
        )
        br_1 = await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.SYNCED,
            name="ubuntu/noble",
            architecture="amd64/ga-24.04-lowlatency",
            selection_id=selection.id,
        )
        await create_test_bootresourceset_entry(
            fixture, version="20250618", label="stable", resource_id=br_1.id
        )

        br_2 = await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.SYNCED,
            name="ubuntu/noble",
            architecture="amd64/hwe24.04",
            selection_id=selection.id,
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
            architecture="arm64/ga24.04",
            selection_id=selection.id,
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

        await services.image_sync.cleanup_boot_resource_sets_for_selection(
            selection.id
        )

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
