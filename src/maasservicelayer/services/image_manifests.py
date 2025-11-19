# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiofiles

from maasservicelayer.builders.image_manifests import ImageManifestBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.image_manifests import (
    ImageManifestsRepository,
)
from maasservicelayer.models.bootsources import (
    BootSource,
    SourceAvailableImage,
)
from maasservicelayer.models.configurations import (
    BootImagesNoProxyConfig,
    EnableHttpProxyConfig,
    HttpProxyConfig,
)
from maasservicelayer.models.image_manifests import ImageManifest
from maasservicelayer.services.base import Service, ServiceCache
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.simplestreams.client import (
    SimpleStreamsClient,
    SimpleStreamsClientException,
)
from maasservicelayer.simplestreams.models import SimpleStreamsManifest


class ImageManifestsService(Service):
    def __init__(
        self,
        context: Context,
        repository: ImageManifestsRepository,
        configurations_service: ConfigurationsService,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, cache)
        self.repository = repository
        self.configurations_service = configurations_service

    async def _get_http_proxy(self) -> str | None:
        """Returns the http proxy to be used to download images metadata."""
        if not await self.configurations_service.get(
            EnableHttpProxyConfig.name
        ) or await self.configurations_service.get(
            BootImagesNoProxyConfig.name
        ):
            return None
        return await self.configurations_service.get(HttpProxyConfig.name)

    @asynccontextmanager
    async def _get_keyring_file(
        self, keyring_path: str | None, keyring_data: bytes | None
    ) -> AsyncIterator[str]:
        """Context manager to handle a keyring file.

        Creates a temporary file with the content in keyring_data and deletes
        the file on context exit. If `keyring_data` is None, `keyring_path` is
        returned.

        Args:
            - keyring_path: path to the keyring file on disk
            - keyring_data: bytes to be written in a temporary file

        Yields:
            The path of the keyring file.
        """
        if keyring_data:
            async with (
                aiofiles.tempfile.NamedTemporaryFile() as tmp_keyring_file
            ):
                await tmp_keyring_file.write(keyring_data)
                await tmp_keyring_file.flush()
                yield str(tmp_keyring_file.name)
        else:
            assert keyring_path is not None
            yield keyring_path

    async def fetch_image_metadata(
        self,
        source_url: str,
        keyring_path: str | None = None,
        keyring_data: bytes | None = None,
    ) -> list[SourceAvailableImage]:
        http_proxy = await self._get_http_proxy()

        async with self._get_keyring_file(
            keyring_path, keyring_data
        ) as keyring_file:
            async with SimpleStreamsClient(
                url=source_url,
                http_proxy=http_proxy,
                keyring_file=keyring_file,
            ) as client:
                products_list = await client.get_all_products()

        return [
            SourceAvailableImage.from_simplestreams_product(image)
            for product_list in products_list
            # we will have duplicates (lots of subarches)
            for image in set(product_list.products)
        ]

    async def fetch_image_metadata_for_boot_source(
        self, boot_source: BootSource
    ) -> SimpleStreamsManifest:
        """Fetch the images metadata from the simplestreams server for a boot source.

        For the boot source specified, it will fetch the simplestreams data (based on the
        boot source url) using `SimpleStreamsClient`. If the boot source specifies
        keyring_data, it will write that into a temporary file.

        Returns:
            A list of simplestreams products.
        """
        http_proxy = await self._get_http_proxy()

        async with self._get_keyring_file(
            boot_source.keyring_filename, boot_source.keyring_data
        ) as keyring_file:
            async with SimpleStreamsClient(
                url=boot_source.url,
                http_proxy=http_proxy,
                keyring_file=keyring_file,
                skip_pgp_verification=boot_source.skip_keyring_verification,
            ) as client:
                products_list = await client.get_all_products()

        if not products_list:
            raise SimpleStreamsClientException(
                f"No images metadata found in {boot_source.url}."
            )
        return products_list

    async def get_or_fetch(
        self, boot_source: BootSource
    ) -> tuple[ImageManifest, bool]:
        """Get the manifest from the db or fetch it from the boot source url if it's not available.

        Returns:
            a tuple with the ImageManifest and a bool, which is True if the object
            was created, False otherwise.
        """
        image_manifest = await self.get(boot_source.id)
        if image_manifest:
            return image_manifest, False
        products_list = await self.fetch_image_metadata_for_boot_source(
            boot_source
        )
        # The updated field is the same for all the products and reflects the
        # date of the last update
        last_update = products_list[0].updated

        builder = ImageManifestBuilder(
            boot_source_id=boot_source.id,
            manifest=products_list,
            last_update=last_update,
        )
        return await self.create(builder), True

    async def fetch_and_update(self, boot_source: BootSource) -> ImageManifest:
        """Fetch the latest manifest for the boot_source_id and store it in the db."""
        current, created = await self.get_or_fetch(boot_source)
        if created:
            return current

        products_list = await self.fetch_image_metadata_for_boot_source(
            boot_source
        )

        # The updated field is the same for all the products and reflects the
        # date of the last update
        last_update = products_list[0].updated

        if last_update > current.last_update:
            builder = ImageManifestBuilder(
                boot_source_id=boot_source.id,
                manifest=products_list,
                last_update=last_update,
            )
            return await self.update(builder)

        return current

    async def get(self, boot_source_id: int) -> ImageManifest | None:
        return await self.repository.get(boot_source_id)

    async def create(self, builder: ImageManifestBuilder) -> ImageManifest:
        return await self.repository.create(builder)

    async def update(self, builder: ImageManifestBuilder) -> ImageManifest:
        return await self.repository.update(builder)

    async def delete(self, boot_source_id: int) -> None:
        return await self.repository.delete(boot_source_id)
