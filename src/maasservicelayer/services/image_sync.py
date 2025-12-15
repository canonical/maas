# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import os
import re
from urllib.parse import urljoin

from structlog import get_logger

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
from maascommon.osystem.ubuntu import UbuntuOS
from maascommon.workflows.bootresource import ResourceDownloadParam
from maasservicelayer.builders.bootresources import BootResourceBuilder
from maasservicelayer.builders.bootsources import BootSourceBuilder
from maasservicelayer.builders.bootsourceselections import (
    BootSourceSelectionBuilder,
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
from maasservicelayer.db.repositories.bootsources import (
    BootSourcesClauseFactory,
)
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionClauseFactory,
)
from maasservicelayer.db.repositories.notifications import (
    NotificationsClauseFactory,
)
from maasservicelayer.models.bootsources import BootSource
from maasservicelayer.models.bootsourceselections import BootSourceSelection
from maasservicelayer.models.configurations import (
    CommissioningDistroSeriesConfig,
    CommissioningOSystemConfig,
)
from maasservicelayer.services.base import Service, ServiceCache
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
from maasservicelayer.services.msm import MSMService
from maasservicelayer.services.notifications import NotificationsService
from maasservicelayer.simplestreams.models import (
    BootloaderProduct,
    ImageProduct,
    MultiFileProduct,
    Product,
    SimpleStreamsManifest,
    SingleFileProduct,
)
from provisioningserver.utils.arch import get_architecture

logger = get_logger()

# Compile a regex to validate Ubuntu product names. This only allows V2 and V3
# Ubuntu images. "v3+platform" is intended for platform-optimised kernels.
UBUNTU_REGEX = re.compile(r".*:v([23]|3\+platform):.*", re.IGNORECASE)
# Compile a regex to validate bootloader product names. This only allows V1
# bootloaders.
BOOTLOADER_REGEX = re.compile(".*:1:.*", re.IGNORECASE)
# Validate MAAS supports the specific bootloader_type, os, arch
# combination.
SUPPORTED_BOOTLOADERS = {
    "pxe": [{"os": "pxelinux", "arch": "i386"}],
    "uefi": [
        {"os": "grub-efi-signed", "arch": "amd64"},
        {"os": "grub-efi", "arch": "arm64"},
    ],
    "open-firmware": [{"os": "grub-ieee1275", "arch": "ppc64el"}],
}


class ImageSyncService(Service):
    def __init__(
        self,
        context: Context,
        boot_sources_service: BootSourcesService,
        boot_source_cache_service: BootSourceCacheService,
        boot_source_selections_service: BootSourceSelectionsService,
        boot_resources_service: BootResourceService,
        boot_resource_sets_service: BootResourceSetsService,
        boot_resource_files_service: BootResourceFilesService,
        configurations_service: ConfigurationsService,
        notifications_service: NotificationsService,
        msm_service: MSMService,
        cache: ServiceCache | None = None,
    ):
        self.boot_sources_service = boot_sources_service
        self.boot_source_cache_service = boot_source_cache_service
        self.boot_source_selections_service = boot_source_selections_service
        self.boot_resources_service = boot_resources_service
        self.boot_resource_sets_service = boot_resource_sets_service
        self.boot_resource_files_service = boot_resource_files_service
        self.configurations_service = configurations_service
        self.notifications_service = notifications_service
        self.msm_service = msm_service

        super().__init__(context, cache)

    async def ensure_boot_source_definition(self) -> bool:
        """Ensure that at least a boot source exists.

        If no boot source is defined, the default one will be created alongside
        with a selection.

        Originally defined in src/maasserver/bootsources.py
        """
        if not await self.boot_sources_service.exists(query=QuerySpec()):
            bootsource_builder = BootSourceBuilder(
                url=DEFAULT_IMAGES_URL,
                keyring_filename=DEFAULT_KEYRINGS_PATH,
                keyring_data=b"",
                priority=1,
                skip_keyring_verification=False,
            )
            boot_source = await self.boot_sources_service.create(
                bootsource_builder
            )
            # Default is to import newest Ubuntu LTS release, for the current
            # architecture.
            arch = get_architecture()
            # amd64 is the primary architecture for MAAS uses. Make sure its always
            # selected. If MAAS is running on another architecture select that as
            # well.
            if arch in ("", "amd64"):
                arches = ["amd64"]
            else:
                arches = [arch, "amd64"]

            ubuntu = UbuntuOS()
            for arch in arches:
                selection_builder = BootSourceSelectionBuilder(
                    boot_source_id=boot_source.id,
                    os=ubuntu.name,
                    release=ubuntu.get_default_commissioning_release(),
                    arch=arch,
                )
                await self.boot_source_selections_service.create_without_boot_source_cache(
                    selection_builder
                )
            return True
        else:
            # XXX ensure the default keyrings path in the database points to the
            # right file when running in a snap. (see LP: #1890468) The
            # DEFAULT_KEYRINGS_PATH points to the right file whether running from
            # deb or snap, but the path stored in the DB might be wrong if a
            # snap-to-deb transition happened with a script without the fix.
            if os.environ.get("SNAP"):
                if (
                    default_boot_source
                    := await self.boot_sources_service.get_one(
                        query=QuerySpec(
                            where=BootSourcesClauseFactory.with_url(
                                DEFAULT_IMAGES_URL
                            )
                        )
                    )
                ):
                    await self.boot_sources_service.update_by_id(
                        id=default_boot_source.id,
                        builder=BootSourceBuilder(
                            keyring_filename=DEFAULT_KEYRINGS_PATH
                        ),
                    )
            return False

    async def sync_boot_source_selections_from_msm(
        self, boot_sources: list[BootSource]
    ):
        msm_status = await self.msm_service.get_status()
        if not msm_status or not msm_status.running == MSMStatusEnum.CONNECTED:
            return

        for boot_source in boot_sources:
            if boot_source.url.startswith(msm_status.sm_url):
                for cache in await self.boot_source_cache_service.get_many(
                    query=QuerySpec(
                        where=BootSourceCacheClauseFactory.with_boot_source_id(
                            boot_source.id
                        )
                    )
                ):
                    if not await self.boot_source_selections_service.exists(
                        query=QuerySpec(
                            where=BootSourceSelectionClauseFactory.and_clauses(
                                [
                                    BootSourceSelectionClauseFactory.with_boot_source_id(
                                        boot_source.id
                                    ),
                                    BootSourceSelectionClauseFactory.with_os(
                                        cache.os
                                    ),
                                    BootSourceSelectionClauseFactory.with_release(
                                        cache.release
                                    ),
                                    BootSourceSelectionClauseFactory.with_arch(
                                        cache.arch
                                    ),
                                ]
                            )
                        )
                    ):
                        await self.boot_source_selections_service.create(
                            BootSourceSelectionBuilder(
                                os=cache.os,
                                release=cache.release,
                                boot_source_id=boot_source.id,
                                arch=cache.arch,
                            )
                        )

    async def check_commissioning_series_selected(self) -> bool:
        """Creates an error notification if the commissioning os and the commissioning
        series are not in the selections or in the boot source cache.
        """
        commissioning_os = await self.configurations_service.get(
            CommissioningOSystemConfig.name
        )
        commissioning_series = await self.configurations_service.get(
            CommissioningDistroSeriesConfig.name
        )
        no_error = True
        if not await self.boot_source_selections_service.exists(
            query=QuerySpec(
                where=BootSourceSelectionClauseFactory.and_clauses(
                    [
                        BootSourceSelectionClauseFactory.with_os(
                            commissioning_os
                        ),
                        BootSourceSelectionClauseFactory.with_release(
                            commissioning_series
                        ),
                    ]
                )
            )
        ):
            no_error = False
            await self.notifications_service.get_or_create(
                query=QuerySpec(
                    where=NotificationsClauseFactory.with_ident(
                        "commissioning_series_unselected"
                    )
                ),
                builder=NotificationBuilder(
                    ident="commissioning_series_unselected",
                    users=True,
                    admins=True,
                    message=f"{commissioning_os} {commissioning_series} is configured "
                    "as the commissioning release but it is not selected for download!",
                    context={},
                    user_id=None,
                    category=NotificationCategoryEnum.ERROR,
                    dismissable=True,
                ),
            )
        if not await self.boot_source_cache_service.exists(
            query=QuerySpec(
                where=BootSourceCacheClauseFactory.and_clauses(
                    [
                        BootSourceCacheClauseFactory.with_os(commissioning_os),
                        BootSourceCacheClauseFactory.with_release(
                            commissioning_series
                        ),
                    ]
                )
            )
        ):
            no_error = False
            await self.notifications_service.get_or_create(
                query=QuerySpec(
                    where=NotificationsClauseFactory.with_ident(
                        "commissioning_series_unavailable"
                    )
                ),
                builder=NotificationBuilder(
                    ident="commissioning_series_unavailable",
                    users=True,
                    admins=True,
                    message=f"{commissioning_os} {commissioning_series} is configured "
                    "as the commissioning release but it is unavailable in the "
                    "configured streams!",
                    context={},
                    user_id=None,
                    category=NotificationCategoryEnum.ERROR,
                    dismissable=True,
                ),
            )
        return no_error

    def _bootloader_matches_selection(
        self, product: BootloaderProduct
    ) -> bool:
        if BOOTLOADER_REGEX.search(product.product_name) is None:
            # Only insert V1 bootloaders from the stream
            return False
        for bootloader in SUPPORTED_BOOTLOADERS.get(
            product.bootloader_type, []
        ):
            if (
                product.os == bootloader["os"]
                and product.arch == bootloader["arch"]
            ):
                return True
        return False

    def _image_product_matches_selection(
        self, product: ImageProduct, selection: BootSourceSelection
    ) -> bool:
        if (
            product.os == selection.os
            and product.release == selection.release
            and product.arch == selection.arch
        ):
            return True
        return False

    def _single_file_image_matches_selection(
        self, product: SingleFileProduct, selection: BootSourceSelection
    ) -> bool:
        return self._image_product_matches_selection(product, selection)

    def _multi_file_image_matches_selection(
        self, product: MultiFileProduct, selection: BootSourceSelection
    ) -> bool:
        if UBUNTU_REGEX.search(product.product_name) is None:
            # Only insert v2 or v3 Ubuntu products.
            return False
        return self._image_product_matches_selection(product, selection)

    def product_matches_selection(
        self, product: Product, selection: BootSourceSelection
    ) -> bool:
        """Whether `product` matches our boot source selections.

        It's used to filter only the products that we are interested in.

        Args:
            - product: the simplestreams product being evaluated
            - selections: list of boot source selections
        """
        match = False
        if isinstance(product, BootloaderProduct):
            match = self._bootloader_matches_selection(product)
        elif isinstance(product, SingleFileProduct):
            match = self._single_file_image_matches_selection(
                product, selection
            )
        elif isinstance(product, MultiFileProduct):
            match = self._multi_file_image_matches_selection(
                product, selection
            )
        return match

    def filter_products_for_selection(
        self,
        selection: BootSourceSelection,
        manifest: SimpleStreamsManifest,
    ) -> SimpleStreamsManifest:
        """Filter simplestreams products to be downloaded for a selection.

        For each product list it will only keep the products that match the selection.

        Args:
            - selection: the `BootSourceSelection` to filter by
            - manifest: the simplestreams manifest to be filtered

        Returns:
            The updated simplestreams product list, containing only the products
            that must be downloaded.

        """
        filtered_manifest = [ss_list.copy() for ss_list in manifest]
        for product_list in filtered_manifest:
            new_product_list = []
            for product in product_list.products:
                if self.product_matches_selection(product, selection):
                    new_product_list.append(product)
            product_list.products = new_product_list
        return filtered_manifest

    async def get_files_to_download_from_product_list(
        self,
        boot_source: BootSource,
        filtered_manifest: SimpleStreamsManifest,
    ) -> list[ResourceDownloadParam]:
        """Get all the files that must be downloaded from simplestreams for this boot source.

        Args:
            - boot_source: The boot source
            - filtered_manifest: The filtered list of simplestreams products for this source

        Returns:
            A list of ResourceDownloadParam (to be later supplied to the Temporal workflow)
        """
        resources_to_download: dict[str, ResourceDownloadParam] = {}
        for product_list in filtered_manifest:
            for product in product_list.products:
                to_download = await self.get_files_to_download_from_product(
                    boot_source,
                    product,
                )
                for resource in to_download:
                    if existent := resources_to_download.get(resource.sha256):
                        # Multiple requests for the same SHA256 are combined in a single operation.
                        existent.rfile_ids.extend(resource.rfile_ids)
                        existent.source_list.extend(resource.source_list)
                        existent.extract_paths.extend(resource.extract_paths)

                    else:
                        resources_to_download[resource.sha256] = resource

        return list(resources_to_download.values())

    async def get_files_to_download_from_product(
        self,
        boot_source: BootSource,
        product: Product,
    ) -> list[ResourceDownloadParam]:
        """Returns the files to be downloaded from a simplestreams product.

        Filtering happens before this function. If we arrived here we have to
        download all the files from the product.

        Args:
            - boot_source_url: the URL of the boot source tied to this product
            - product: the simplestreams product to extract files from

        Returns:
            A list of `ResourceDownloadParam`
        """
        boot_resource_builder = BootResourceBuilder.from_simplestreams_product(
            product
        )
        (
            boot_resource,
            _,
        ) = await self.boot_resources_service.get_or_create(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_rtype(
                            boot_resource_builder.ensure_set(
                                boot_resource_builder.rtype
                            )
                        ),
                        BootResourceClauseFactory.with_name(
                            boot_resource_builder.ensure_set(
                                boot_resource_builder.name
                            )
                        ),
                        BootResourceClauseFactory.with_architecture(
                            boot_resource_builder.ensure_set(
                                boot_resource_builder.architecture
                            )
                        ),
                        BootResourceClauseFactory.with_alias(
                            boot_resource_builder.ensure_set(
                                boot_resource_builder.alias
                            )
                        ),
                    ]
                )
            ),
            builder=boot_resource_builder,
        )

        if (
            boot_resource.bootloader_type is None
            and boot_resource.selection_id is None
        ):
            # Add the selection id only to the non-bootloader images
            osystem, release = boot_resource.name.split("/")
            arch, _ = boot_resource.architecture.split("/", maxsplit=1)
            related_selection = await self.boot_source_selections_service.get_one(
                query=QuerySpec(
                    where=BootSourceSelectionClauseFactory.and_clauses(
                        [
                            BootSourceSelectionClauseFactory.with_os(osystem),
                            BootSourceSelectionClauseFactory.with_release(
                                release
                            ),
                            BootSourceSelectionClauseFactory.with_arch(arch),
                            BootSourceSelectionClauseFactory.with_boot_source_id(
                                boot_source.id
                            ),
                        ]
                    )
                )
            )
            # This can't happen as we are processing the products that match our selections.
            assert related_selection is not None, (
                f"No suitable selection found for boot resource: {boot_resource}"
            )
            await self.boot_resources_service.update_by_id(
                boot_resource.id,
                BootResourceBuilder(selection_id=related_selection.id),
            )

        boot_resource_set = await self.boot_resource_sets_service.get_or_create_from_simplestreams_product(
            product, boot_resource.id
        )

        resources_to_download: list[ResourceDownloadParam] = []

        # TODO: user-provided version (product.get_version_by_name())
        version = product.get_latest_version()

        for file in version.get_downloadable_files():
            # A ROOT_IMAGE may already be downloaded for the release if the stream
            # switched from one not containg SquashFS images to one that does. We
            # want to use the SquashFS image so delete the tgz.
            if file.ftype == BootResourceFileType.SQUASHFS_IMAGE:
                # delete the root image
                deleted_root_images = await self.boot_resource_files_service.delete_many(
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
                if deleted_root_images:
                    logger.debug(
                        "Deleted a root image tarball in favour of a root squashfs."
                    )

            resource_file = await self.boot_resource_files_service.get_or_create_from_simplestreams_file(
                file, boot_resource_set.id
            )

            local_file = resource_file.create_local_file()

            if (
                await local_file.complete()
                and await self.boot_resource_files_service.is_sync_complete(
                    resource_file.id
                )
            ):
                logger.debug(
                    f"File with sha256 '{local_file.sha256}' already downloaded."
                )
                continue

            # Provide the extract path for bootloaders
            if (
                resource_file.filetype == BootResourceFileType.ARCHIVE_TAR_XZ
                and boot_resource.bootloader_type
            ):
                arch = boot_resource.architecture.split("/")[0]
                extract_path = (
                    f"{BOOTLOADERS_DIR}/{boot_resource.bootloader_type}/{arch}"
                )
            else:
                extract_path = None

            # Inside a Version, we can't have the same sha256
            resources_to_download.append(
                ResourceDownloadParam(
                    rfile_ids=[resource_file.id],
                    source_list=[
                        urljoin(boot_source.get_base_url(), file.path)
                    ],
                    sha256=resource_file.sha256,
                    filename_on_disk=resource_file.filename_on_disk,
                    total_size=resource_file.size,
                    extract_paths=[extract_path] if extract_path else [],
                )
            )

        return resources_to_download

    async def cleanup_boot_resource_sets_for_selection(
        self, selection_id: int
    ) -> None:
        """Deletes the old and incomplete boot resource sets.

        It cleans all the boot resources related to the `selection_id` passed.
        For each boot resource, the most recent complete resource set is found
        (if any) and kept, all the others are deleted. Incomplete resource sets
        are always deleted.
        """
        query = QuerySpec(
            where=BootResourceClauseFactory.and_clauses(
                [
                    BootResourceClauseFactory.with_rtype(
                        BootResourceType.SYNCED
                    ),
                    BootResourceClauseFactory.with_selection_id(selection_id),
                ]
            )
        )

        boot_resources = await self.boot_resources_service.get_many(
            query=query
        )
        boot_resource_sets_to_delete = set()
        for boot_resource in boot_resources:
            found_first_complete_set = False
            resource_sets = await self.boot_resource_sets_service.get_many(
                query=QuerySpec(
                    where=BootResourceSetClauseFactory.with_resource_id(
                        boot_resource.id
                    ),
                    order_by=[
                        OrderByClauseFactory.desc_clause(
                            BootResourceSetsOrderByClauses.by_id()
                        )
                    ],
                )
            )
            for resource_set in resource_sets:
                if (
                    found_first_complete_set
                    or not await self.boot_resource_sets_service.is_sync_complete(
                        resource_set.id
                    )
                ):
                    boot_resource_sets_to_delete.add(resource_set.id)
                else:
                    found_first_complete_set = True

        await self.boot_resource_sets_service.delete_many(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.with_ids(
                    boot_resource_sets_to_delete
                )
            )
        )

        await self.boot_resources_service.delete_all_without_sets(query=query)
