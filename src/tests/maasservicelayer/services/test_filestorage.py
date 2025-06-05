#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.filestorage import FileStorageRepository
from maasservicelayer.models.filestorage import FileStorage
from maasservicelayer.services.filestorage import FileStorageService
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestFileStorageService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> FileStorageService:
        return FileStorageService(
            context=Context(),
            repository=Mock(FileStorageRepository),
        )

    @pytest.fixture
    def test_instance(self) -> FileStorage:
        return FileStorage(
            id=1,
            filename="test_file",
            content="content",
            key="key",
            owner_id=None,
        )

    async def test_update_many(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_many(
                service_instance, test_instance, builder_model
            )

    async def test_update_one(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one(
                service_instance, test_instance, builder_model
            )

    async def test_update_one_not_found(self, service_instance, builder_model):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one_not_found(
                service_instance, builder_model
            )

    async def test_update_one_etag_match(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one_etag_match(
                service_instance, test_instance, builder_model
            )

    async def test_update_one_etag_not_matching(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one_etag_not_matching(
                service_instance, test_instance, builder_model
            )

    async def test_update_by_id(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id(
                service_instance, test_instance, builder_model
            )

    async def test_update_by_id_not_found(
        self, service_instance, builder_model
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id_not_found(
                service_instance, builder_model
            )

    async def test_update_by_id_etag_match(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id_etag_match(
                service_instance, test_instance, builder_model
            )

    async def test_update_by_id_etag_not_matching(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id_etag_not_matching(
                service_instance, test_instance, builder_model
            )
