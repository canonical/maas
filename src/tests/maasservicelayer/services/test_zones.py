#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from maasapiserver.v3.constants import DEFAULT_ZONE_NAME
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.zones import (
    ZonesClauseFactory,
    ZonesRepository,
)
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    CANNOT_DELETE_DEFAULT_ZONE_VIOLATION_TYPE,
    ETAG_PRECONDITION_VIOLATION_TYPE,
)
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.zones import Zone
from maasservicelayer.services import (
    NodesService,
    VmClustersService,
    ZonesService,
)
from maasservicelayer.services._base import BaseService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests

DEFAULT_ZONE = Zone(
    id=1,
    name=DEFAULT_ZONE_NAME,
    description="",
    created=utcnow(),
    updated=utcnow(),
)

TEST_ZONE = Zone(
    id=4,
    name="test_zone",
    description="test_description",
    created=utcnow(),
    updated=utcnow(),
)


@pytest.mark.asyncio
class TestCommonZonesService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return ZonesService(
            context=Context(),
            zones_repository=Mock(ZonesRepository),
            nodes_service=Mock(NodesService),
            vmcluster_service=Mock(VmClustersService),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        return TEST_ZONE

    async def test_delete_many(
        self, service_instance, test_instance: MaasBaseModel
    ):
        with pytest.raises(NotImplementedError):
            await super().test_delete_many(service_instance, test_instance)


@pytest.mark.asyncio
class TestZonesService:
    async def test_list_with_summary_calls_repository(self) -> None:
        zones_repository = Mock(ZonesRepository)
        zones_service = ZonesService(
            context=Context(),
            zones_repository=zones_repository,
            nodes_service=Mock(NodesService),
            vmcluster_service=Mock(VmClustersService),
        )

        await zones_service.list_with_summary(1, 1)
        zones_repository.list_with_summary.assert_called_once_with(
            page=1, size=1
        )

    async def test_delete(self) -> None:
        zones_repository = Mock(ZonesRepository)
        zones_repository.delete_by_id.return_value = TEST_ZONE
        zones_repository.get_one.side_effect = [TEST_ZONE, None]
        zones_service = ZonesService(
            context=Context(),
            zones_repository=zones_repository,
            nodes_service=Mock(NodesService),
            vmcluster_service=Mock(VmClustersService),
        )

        await zones_service.delete_one(
            query=QuerySpec(ZonesClauseFactory.with_ids([TEST_ZONE.id]))
        )
        zones_repository.delete_by_id.assert_awaited_once_with(id=TEST_ZONE.id)

    async def test_delete_by_id(self) -> None:
        zones_repository = Mock(ZonesRepository)
        zones_repository.delete_by_id.return_value = TEST_ZONE
        zones_repository.get_by_id.side_effect = [TEST_ZONE, None]
        zones_service = ZonesService(
            context=Context(),
            zones_repository=zones_repository,
            nodes_service=Mock(NodesService),
            vmcluster_service=Mock(VmClustersService),
        )

        await zones_service.delete_by_id(TEST_ZONE.id)
        zones_repository.delete_by_id.assert_awaited_once_with(id=TEST_ZONE.id)

    async def test_delete_by_id_etag(
        self,
        mocker: MockerFixture,
    ) -> None:
        zones_repository = Mock(ZonesRepository)
        zones_repository.delete_by_id.return_value = TEST_ZONE
        zones_repository.get_by_id.side_effect = [TEST_ZONE, None]
        zones_service = ZonesService(
            context=Context(),
            zones_repository=zones_repository,
            nodes_service=Mock(NodesService),
            vmcluster_service=Mock(VmClustersService),
        )

        mocker.patch(
            "maasservicelayer.models.zones.Zone.etag", return_value="my-etag"
        )

        await zones_service.delete_by_id(TEST_ZONE.id, "my-etag")
        zones_repository.delete_by_id.assert_awaited_once_with(id=TEST_ZONE.id)

    async def test_delete_by_id_etag_fail(
        self,
        mocker: MockerFixture,
    ) -> None:
        zones_repository = Mock(ZonesRepository)
        zones_repository.get_by_id.return_value = TEST_ZONE
        zones_service = ZonesService(
            context=Context(),
            zones_repository=zones_repository,
            nodes_service=Mock(NodesService),
            vmcluster_service=Mock(VmClustersService),
        )

        mocker.patch(
            "maasservicelayer.models.zones.Zone.etag", return_value="my-etag"
        )

        with pytest.raises(PreconditionFailedException) as excinfo:
            await zones_service.delete_by_id(TEST_ZONE.id, "wrong-etag")
        assert (
            excinfo.value.details[0].type == ETAG_PRECONDITION_VIOLATION_TYPE
        )
        zones_repository.delete_by_id.assert_not_called()

    async def test_delete_by_id_default_zone(self) -> None:
        zones_repository = Mock(ZonesRepository)
        zones_repository.get_by_id.return_value = DEFAULT_ZONE
        zones_repository.get_default_zone.return_value = DEFAULT_ZONE
        zones_service = ZonesService(
            context=Context(),
            zones_repository=zones_repository,
            nodes_service=Mock(NodesService),
            vmcluster_service=Mock(VmClustersService),
        )

        with pytest.raises(BadRequestException) as excinfo:
            await zones_service.delete_by_id(DEFAULT_ZONE.id)
        assert (
            excinfo.value.details[0].type
            == CANNOT_DELETE_DEFAULT_ZONE_VIOLATION_TYPE
        )
        zones_repository.delete_by_id.assert_not_called()

    async def test_delete_by_id_related_objects_are_moved_to_default_zone(
        self,
    ) -> None:
        nodes_service_mock = Mock(NodesService)
        vmclusters_service_mock = Mock(VmClustersService)
        zones_repository = Mock(ZonesRepository)
        zones_repository.get_by_id.return_value = TEST_ZONE
        zones_repository.get_default_zone.return_value = DEFAULT_ZONE
        zones_repository.delete_by_id.return_value = TEST_ZONE

        zones_service = ZonesService(
            context=Context(),
            zones_repository=zones_repository,
            nodes_service=nodes_service_mock,
            vmcluster_service=vmclusters_service_mock,
        )

        await zones_service.delete_by_id(TEST_ZONE.id)

        nodes_service_mock.move_to_zone.assert_called_once_with(
            TEST_ZONE.id, DEFAULT_ZONE.id
        )
        nodes_service_mock.move_bmcs_to_zone.assert_called_once_with(
            TEST_ZONE.id, DEFAULT_ZONE.id
        )
        vmclusters_service_mock.move_to_zone.assert_called_once_with(
            TEST_ZONE.id, DEFAULT_ZONE.id
        )

    async def test_default_zone_is_cached(self) -> None:
        zones_repository = Mock(ZonesRepository)
        zones_repository.get_default_zone.return_value = DEFAULT_ZONE

        cache = ZonesService.build_cache_object()
        zones_service = ZonesService(
            context=Context(),
            nodes_service=Mock(NodesService),
            vmcluster_service=Mock(VmClustersService),
            zones_repository=zones_repository,
            cache=cache,
        )

        await zones_service.get_default_zone()
        await zones_service.get_default_zone()

        zones_repository.get_default_zone.assert_called_once()
        assert cache.default_zone == DEFAULT_ZONE
