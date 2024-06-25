# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from math import ceil

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.fabrics import FabricsRepository
from maasapiserver.v3.models.fabrics import Fabric
from tests.fixtures.factories.fabric import create_test_fabric_entry
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestFabricsRepository:
    @pytest.mark.parametrize("page_size", range(1, 12))
    async def test_list(
        self, page_size: int, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        fabrics_repository = FabricsRepository(db_connection)
        created_fabrics = [
            Fabric(**(await create_test_fabric_entry(fixture)))
            for _ in range(0, 10)
        ][::-1]
        total_pages = ceil(10 / page_size)
        current_token = None
        for page in range(1, total_pages + 1):
            fabrics_result = await fabrics_repository.list_with_token(
                token=current_token, size=page_size
            )
            if page == total_pages:  # last page may have fewer elements
                assert len(fabrics_result.items) == (
                    page_size
                    - ((total_pages * page_size) % (len(created_fabrics)))
                )
            else:
                assert len(fabrics_result.items) == page_size
            for fabric in created_fabrics[
                ((page - 1) * page_size) : ((page * page_size))
            ]:
                assert fabric in fabrics_result.items
            current_token = fabrics_result.next_token
