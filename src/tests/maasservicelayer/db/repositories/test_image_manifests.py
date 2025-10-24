# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import json

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.image_manifests import ImageManifestBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.image_manifests import (
    ImageManifestsRepository,
)
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    NotFoundException,
)
from maasservicelayer.models.base import UNSET
from maasservicelayer.models.image_manifests import ImageManifest
from maasservicelayer.utils.date import utcnow
from tests.fixtures import get_test_data_file
from tests.fixtures.factories.imagemanifests import (
    create_test_image_manifest_entry,
)
from tests.maasservicelayer.db.repositories.base import Fixture


class TestImageManifestsRepository:
    @pytest.fixture
    def repository(self, db_connection: AsyncConnection):
        return ImageManifestsRepository(
            context=Context(connection=db_connection)
        )

    @pytest.fixture
    async def instance(self, fixture: Fixture):
        return await create_test_image_manifest_entry(fixture, 1)

    @pytest.fixture
    async def builder(self) -> ImageManifestBuilder:
        manifest = get_test_data_file("simplestreams_ubuntu.json")
        manifest = json.loads(manifest)
        return ImageManifestBuilder(
            boot_source_id=1,
            manifest=[manifest],
            last_update=utcnow(),
        )

    async def test_get(
        self, repository: ImageManifestsRepository, instance: ImageManifest
    ) -> None:
        m = await repository.get(instance.boot_source_id)
        assert isinstance(m, ImageManifest)
        assert m == instance

    async def test_get_not_found(
        self, repository: ImageManifestsRepository
    ) -> None:
        m = await repository.get(10)
        assert m is None

    async def test_create(
        self,
        repository: ImageManifestsRepository,
        builder: ImageManifestBuilder,
    ) -> None:
        m = await repository.create(builder)
        assert isinstance(m, ImageManifest)
        assert m.boot_source_id == builder.boot_source_id
        assert m.manifest == builder.manifest
        assert m.last_update == builder.last_update

    async def test_create_already_existing(
        self,
        repository: ImageManifestsRepository,
        instance: ImageManifest,
        builder: ImageManifestBuilder,
    ) -> None:
        with pytest.raises(AlreadyExistsException):
            await repository.create(builder)

    async def test_update(
        self,
        repository: ImageManifestsRepository,
        instance: ImageManifest,
        builder: ImageManifestBuilder,
    ) -> None:
        m = await repository.update(builder)
        assert isinstance(m, ImageManifest)
        assert m.last_update > instance.last_update

    async def test_update_not_found(
        self,
        repository: ImageManifestsRepository,
        builder: ImageManifestBuilder,
    ) -> None:
        with pytest.raises(NotFoundException):
            await repository.update(builder)

    async def test_update_missing_boot_source_id(
        self,
        repository: ImageManifestsRepository,
        builder: ImageManifestBuilder,
    ) -> None:
        builder.boot_source_id = UNSET
        with pytest.raises(ReferenceError):
            await repository.update(builder)

    async def test_delete(
        self, repository: ImageManifestsRepository, instance: ImageManifest
    ) -> None:
        await repository.delete(instance.boot_source_id)

    async def test_delete_not_found(
        self, repository: ImageManifestsRepository
    ) -> None:
        await repository.delete(100)
