#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.sslkeys import SSLKeysRepository
from maasservicelayer.models.base import (
    MaasBaseModel,
    MaasTimestampedBaseModel,
)
from maasservicelayer.models.sslkeys import SSLKey
from maasservicelayer.services._base import BaseService
from maasservicelayer.services.sslkey import SSLKeysService
from maasservicelayer.utils.date import utcnow
from tests.fixtures import get_test_data_file
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestCommonSSLKeysService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return SSLKeysService(
            context=Context(), sslkey_repository=Mock(SSLKeysRepository)
        )

    @pytest.fixture
    def test_instance(self) -> MaasTimestampedBaseModel:
        now = utcnow()
        key = get_test_data_file("test_x509_0.pem")
        return SSLKey(
            id=1,
            key=key,
            created=now,
            updated=now,
            user_id=1,
        )

    async def test_update_many(
        self, service_instance, test_instance: MaasBaseModel
    ):
        with pytest.raises(NotImplementedError):
            await super().test_update_many(service_instance, test_instance)

    async def test_update_one(
        self, service_instance, test_instance: MaasBaseModel
    ):
        with pytest.raises(NotImplementedError):
            await super().test_update_many(service_instance, test_instance)

    async def test_update_one_not_found(
        self, service_instance, test_instance: MaasBaseModel
    ):
        with pytest.raises(NotImplementedError):
            await super().test_update_many(service_instance, test_instance)

    async def test_update_one_etag_match(
        self, service_instance, test_instance: MaasBaseModel
    ):
        with pytest.raises(NotImplementedError):
            await super().test_update_many(service_instance, test_instance)

    async def test_update_one_etag_not_matching(
        self, service_instance, test_instance: MaasBaseModel
    ):
        with pytest.raises(NotImplementedError):
            await super().test_update_many(service_instance, test_instance)

    async def test_update_by_id(
        self, service_instance, test_instance: MaasBaseModel
    ):
        with pytest.raises(NotImplementedError):
            await super().test_update_many(service_instance, test_instance)

    async def test_update_by_id_not_found(
        self, service_instance, test_instance: MaasBaseModel
    ):
        with pytest.raises(NotImplementedError):
            await super().test_update_many(service_instance, test_instance)

    async def test_update_by_id_etag_match(
        self, service_instance, test_instance: MaasBaseModel
    ):
        with pytest.raises(NotImplementedError):
            await super().test_update_many(service_instance, test_instance)

    async def test_update_by_id_etag_not_matching(
        self, service_instance, test_instance: MaasBaseModel
    ):
        with pytest.raises(NotImplementedError):
            await super().test_update_many(service_instance, test_instance)
