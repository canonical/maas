# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.agents import AgentsClauseFactory
from maasservicelayer.db.repositories.bootstraptokens import (
    BootstrapTokensClauseFactory,
)
from maasservicelayer.db.repositories.racks import RacksRepository
from maasservicelayer.models.racks import Rack
from maasservicelayer.services.agents import AgentsService
from maasservicelayer.services.bootstraptoken import BootstrapTokensService
from maasservicelayer.services.racks import RacksService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestRacksService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> RacksService:
        return RacksService(
            context=Context(),
            repository=Mock(RacksRepository),
            agents_service=Mock(AgentsService),
            bootstraptokens_service=Mock(BootstrapTokensService),
        )

    @pytest.fixture
    def test_instance(self) -> Rack:
        now = utcnow()
        return Rack(id=1, created=now, updated=now, name="rack")

    async def test_delete(self, test_instance: Rack):
        rack = test_instance

        repository_mock = Mock(RacksRepository)
        repository_mock.get_one.return_value = rack
        repository_mock.delete_by_id.return_value = rack

        agents_service_mock = Mock(AgentsService)
        bootstraptokens_service_mock = Mock(BootstrapTokensService)

        rack_service = RacksService(
            context=Context(),
            repository=repository_mock,
            agents_service=agents_service_mock,
            bootstraptokens_service=bootstraptokens_service_mock,
        )

        query = Mock(QuerySpec)
        await rack_service.delete_one(query)

        repository_mock.delete_by_id.assert_called_once_with(id=rack.id)

        bootstraptokens_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=BootstrapTokensClauseFactory.with_rack_id(rack.id)
            )
        )
        agents_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(where=AgentsClauseFactory.with_rack_id(rack.id))
        )
