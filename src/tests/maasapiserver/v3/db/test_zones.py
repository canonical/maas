from datetime import datetime, timezone
from math import ceil

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.models.exceptions import AlreadyExistsException
from maasapiserver.v3.api.models.requests.query import PaginationParams
from maasapiserver.v3.api.models.requests.zones import ZoneRequest
from maasapiserver.v3.db.zones import ZonesRepository
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.fixtures.factories.zones import create_test_zone


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestZonesRepository:
    async def test_create(self, db_connection: AsyncConnection) -> None:
        now = datetime.utcnow()
        zones_dao = ZonesRepository(db_connection)
        created_zone = await zones_dao.create(
            ZoneRequest(name="my_zone", description="my description")
        )
        assert created_zone.id > 1
        assert created_zone.name == "my_zone"
        assert created_zone.description == "my description"
        assert created_zone.created.astimezone(timezone.utc) >= now.astimezone(
            timezone.utc
        )
        assert created_zone.updated.astimezone(timezone.utc) >= now.astimezone(
            timezone.utc
        )

    async def test_create_duplicated(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        zones_dao = ZonesRepository(db_connection)
        created_zone = await create_test_zone(fixture)

        with pytest.raises(AlreadyExistsException):
            await zones_dao.create(
                ZoneRequest(
                    name=created_zone.name,
                    description=created_zone.description,
                )
            )

    async def test_find_by_id(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        zones_dao = ZonesRepository(db_connection)
        created_zone = await create_test_zone(fixture)

        zone = await zones_dao.find_by_id(created_zone.id)
        assert zone.id == created_zone.id
        assert zone.name == created_zone.name
        assert zone.description == created_zone.description
        assert zone.updated == created_zone.updated
        assert zone.created == created_zone.created

        zone = await zones_dao.find_by_id(1234)
        assert zone is None

    @pytest.mark.parametrize("page_size", range(1, 12))
    async def test_list(
        self, page_size: int, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        zones_dao = ZonesRepository(db_connection)
        # The "default" zone with id=1 is created at startup with the migrations. By consequence, we create zones_size-1 zones
        # here.
        created_zones = [
            (await create_test_zone(fixture, name=str(i), description=str(i)))
            for i in range(0, 9)
        ][::-1]
        total_pages = ceil(10 / page_size)
        for page in range(1, total_pages + 1):
            zones_result = await zones_dao.list(
                PaginationParams(size=page_size, page=page)
            )
            assert zones_result.total == 10
            assert total_pages == ceil(zones_result.total / page_size)
            if page == total_pages:  # last page may have fewer elements
                assert len(zones_result.items) == (
                    page_size
                    - ((total_pages * page_size) % zones_result.total)
                )
            else:
                assert len(zones_result.items) == page_size
            for zone in created_zones[
                ((page - 1) * page_size) : ((page * page_size))
            ]:
                assert zone in zones_result.items
