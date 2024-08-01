from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maasapiserver.common.db.filters import FilterQuery
from maasapiserver.common.db.tables import ZoneTable
from maasapiserver.common.models.constants import (
    CANNOT_DELETE_DEFAULT_ZONE_VIOLATION_TYPE,
    ETAG_PRECONDITION_VIOLATION_TYPE,
)
from maasapiserver.common.models.exceptions import (
    BadRequestException,
    PreconditionFailedException,
)
from maasapiserver.v3.constants import DEFAULT_ZONE_NAME
from maasapiserver.v3.db.zones import ZonesRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.zones import Zone
from maasapiserver.v3.services import (
    BmcService,
    NodesService,
    VmClustersService,
    ZonesService,
)
from tests.fixtures.factories.zone import create_test_zone
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestZonesService:
    async def test_delete(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        zones_service = ZonesService(db_connection)
        created_zone = await create_test_zone(fixture)
        assert created_zone.id is not None

        await zones_service.delete(created_zone.id)
        assert (await zones_service.get_by_id(created_zone.id)) is None

    async def test_delete_etag(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        zones_service = ZonesService(db_connection)
        created_zone = await create_test_zone(fixture)
        assert created_zone.id is not None

        await zones_service.delete(created_zone.id, created_zone.etag())
        assert (await zones_service.get_by_id(created_zone.id)) is None

    async def test_delete_etag_fail(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        zones_service = ZonesService(db_connection)
        created_zone = await create_test_zone(fixture)
        assert created_zone.id is not None

        with pytest.raises(PreconditionFailedException) as excinfo:
            await zones_service.delete(created_zone.id, "")
        assert (
            excinfo.value.details[0].type == ETAG_PRECONDITION_VIOLATION_TYPE
        )

    async def test_delete_default_zone(
        self, db_connection: AsyncConnection
    ) -> None:
        zones_service = ZonesService(db_connection)
        default_zone = await zones_service.get_by_name(DEFAULT_ZONE_NAME)
        with pytest.raises(BadRequestException) as excinfo:
            await zones_service.delete(default_zone.id)
        assert (
            excinfo.value.details[0].type
            == CANNOT_DELETE_DEFAULT_ZONE_VIOLATION_TYPE
        )

    async def test_delete_related_objects_are_moved_to_default_zone(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        nodes_service_mock = Mock(NodesService)
        nodes_service_mock.move_to_zone = AsyncMock()
        bmc_service_mock = Mock(BmcService)
        bmc_service_mock.move_to_zone = AsyncMock()
        vmclusters_service_mock = Mock(VmClustersService)
        vmclusters_service_mock.move_to_zone = AsyncMock()

        zones_service = ZonesService(
            db_connection,
            nodes_service=nodes_service_mock,
            bmc_service=bmc_service_mock,
            vmcluster_service=vmclusters_service_mock,
        )

        [default_zone] = await fixture.get_typed(
            ZoneTable.name, Zone, eq(ZoneTable.c.name, DEFAULT_ZONE_NAME)
        )
        created_zone = await create_test_zone(fixture)
        await zones_service.delete(created_zone.id)

        nodes_service_mock.move_to_zone.assert_called_once_with(
            created_zone.id, default_zone.id
        )
        bmc_service_mock.move_to_zone.assert_called_once_with(
            created_zone.id, default_zone.id
        )
        vmclusters_service_mock.move_to_zone.assert_called_once_with(
            created_zone.id, default_zone.id
        )

    async def test_list(self, db_connection: AsyncConnection) -> None:
        zones_repository_mock = Mock(ZonesRepository)
        zones_repository_mock.list = AsyncMock(
            return_value=ListResult[ZonesRepository](items=[], next_token=None)
        )
        resource_pools_service = ZonesService(
            connection=db_connection,
            zones_repository=zones_repository_mock,
        )
        query_mock = Mock(FilterQuery)
        resource_pools_list = await resource_pools_service.list(
            token=None, size=1, query=query_mock
        )
        zones_repository_mock.list.assert_called_once_with(
            token=None, size=1, query=query_mock
        )
        assert resource_pools_list.next_token is None
        assert resource_pools_list.items == []
