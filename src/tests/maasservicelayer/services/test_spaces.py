# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.spaces import SpacesRepository
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.spaces import Space
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.spaces import SpacesService
from maasservicelayer.services.vlans import VlansService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestCommonSpacesService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return SpacesService(
            context=Context(),
            vlans_service=Mock(VlansService),
            spaces_repository=Mock(SpacesRepository),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        return Space(
            id=1,
            name="test_space_name",
            description="test_space_description",
            created=utcnow(),
            updated=utcnow(),
        )

    async def test_delete_many(
        self, service_instance, test_instance: MaasBaseModel
    ):
        with pytest.raises(NotImplementedError):
            await super().test_delete_many(service_instance, test_instance)
