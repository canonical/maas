#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import b64encode
from typing import Any
from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.nodeuserdata import (
    NodeUserDataRepository,
)
from maasservicelayer.db.tables import NodeUserDataTable
from maasservicelayer.models.nodeuserdata import NodeUserData
from maasservicelayer.services.nodeuserdata import NodeUserDataService
from tests.fixtures.factories.node import create_test_machine_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestCommonNodeUserDataService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> NodeUserDataService:
        return NodeUserDataService(
            context=Context(),
            nodeuserdata_repository=Mock(NodeUserDataRepository),
        )

    @pytest.fixture
    def test_instance(self) -> NodeUserData:
        return NodeUserData(
            id=1, node_id=1, data=b"user-data", for_ephemeral_environment=True
        )


@pytest.mark.asyncio
class TestNodeUserDataService:
    async def test_set_user_data_to_None_when_none_exists_does_nothing(
        self,
    ) -> None:
        repository = Mock(NodeUserDataRepository)
        repository.get_one.return_value = None
        repository.get_many.return_value = []
        repository.delete_many.return_value = []
        service = NodeUserDataService(
            context=Context(), nodeuserdata_repository=repository
        )

        await service.set_user_data_for_ephemeral_env(node_id=1, data=None)


async def create_nodeuserdata_entry(
    fixture: Fixture,
    node_id: int,
    data: bytes,
    for_ephemeral_environment: bool,
) -> dict[str, Any]:
    [created] = await fixture.create(
        "maasserver_nodeuserdata",
        [
            {
                "node_id": node_id,
                "data": b64encode(data).decode(),
                "for_ephemeral_environment": for_ephemeral_environment,
            }
        ],
    )
    return created


async def get_nodeuserdata_rows(
    fixture: Fixture, node_id: int
) -> list[dict[str, Any]]:
    return await fixture.get(
        "maasserver_nodeuserdata", NodeUserDataTable.c.node_id == node_id
    )


@pytest.mark.asyncio
class TestIntegrationNodeUserDataService:
    @pytest.fixture
    def service(self, db_connection: AsyncConnection) -> NodeUserDataService:
        context = Context(connection=db_connection)
        return NodeUserDataService(
            context=context,
            nodeuserdata_repository=NodeUserDataRepository(context),
        )

    async def test_set_user_data_to_None_when_none_exists_does_nothing(
        self, fixture: Fixture, service: NodeUserDataService
    ) -> None:
        node = await create_test_machine_entry(fixture)

        await service.set_user_data_for_ephemeral_env(
            node_id=node["id"], data=None
        )

        assert await fixture.get("maasserver_nodeuserdata") == []

    async def test_set_user_data_creates_new_nodeuserdata_if_needed(
        self, fixture: Fixture, service: NodeUserDataService
    ) -> None:
        node = await create_test_machine_entry(fixture)

        await service.set_user_data_for_ephemeral_env(
            node_id=node["id"], data=b"user-data"
        )

        [row] = await get_nodeuserdata_rows(fixture, node["id"])
        assert row["data"] == b64encode(b"user-data").decode()
        assert row["for_ephemeral_environment"] is True

    async def test_set_user_data_overwrites_existing_userdata(
        self, fixture: Fixture, service: NodeUserDataService
    ) -> None:
        node = await create_test_machine_entry(fixture)
        existing = await create_nodeuserdata_entry(
            fixture, node["id"], b"old-data", for_ephemeral_environment=True
        )

        await service.set_user_data_for_ephemeral_env(
            node_id=node["id"], data=b"new-data"
        )

        [row] = await get_nodeuserdata_rows(fixture, node["id"])
        assert row["id"] == existing["id"]
        assert row["data"] == b64encode(b"new-data").decode()

    async def test_set_user_data_leaves_data_for_other_nodes_alone(
        self, fixture: Fixture, service: NodeUserDataService
    ) -> None:
        node = await create_test_machine_entry(fixture)
        other_node = await create_test_machine_entry(fixture)
        other_entry = await create_nodeuserdata_entry(
            fixture,
            other_node["id"],
            b"other-data",
            for_ephemeral_environment=True,
        )

        await service.set_user_data_for_ephemeral_env(
            node_id=node["id"], data=b"user-data"
        )

        assert await get_nodeuserdata_rows(fixture, other_node["id"]) == [
            other_entry
        ]

    async def test_set_user_data_leaves_user_env_data_alone(
        self, fixture: Fixture, service: NodeUserDataService
    ) -> None:
        node = await create_test_machine_entry(fixture)
        user_env_entry = await create_nodeuserdata_entry(
            fixture,
            node["id"],
            b"deploy-data",
            for_ephemeral_environment=False,
        )

        await service.set_user_data_for_ephemeral_env(
            node_id=node["id"], data=b"ephemeral-data"
        )

        rows = await get_nodeuserdata_rows(fixture, node["id"])
        assert len(rows) == 2
        assert user_env_entry in rows

    async def test_set_user_data_to_None_removes_user_data(
        self, fixture: Fixture, service: NodeUserDataService
    ) -> None:
        node = await create_test_machine_entry(fixture)
        await create_nodeuserdata_entry(
            fixture, node["id"], b"user-data", for_ephemeral_environment=True
        )

        await service.set_user_data_for_ephemeral_env(
            node_id=node["id"], data=None
        )

        assert await get_nodeuserdata_rows(fixture, node["id"]) == []

    async def test_set_user_data_to_None_leaves_user_env_data_alone(
        self, fixture: Fixture, service: NodeUserDataService
    ) -> None:
        node = await create_test_machine_entry(fixture)
        await create_nodeuserdata_entry(
            fixture,
            node["id"],
            b"ephemeral-data",
            for_ephemeral_environment=True,
        )
        user_env_entry = await create_nodeuserdata_entry(
            fixture,
            node["id"],
            b"deploy-data",
            for_ephemeral_environment=False,
        )

        await service.set_user_data_for_ephemeral_env(
            node_id=node["id"], data=None
        )

        assert await get_nodeuserdata_rows(fixture, node["id"]) == [
            user_env_entry
        ]

    async def test_get_user_data_for_ephemeral_env_returns_data(
        self, fixture: Fixture, service: NodeUserDataService
    ) -> None:
        node = await create_test_machine_entry(fixture)
        await create_nodeuserdata_entry(
            fixture, node["id"], b"user-data", for_ephemeral_environment=True
        )

        assert (
            await service.get_user_data_for_ephemeral_env(node["id"])
            == b"user-data"
        )

    async def test_get_user_data_for_ephemeral_env_returns_none_if_unset(
        self, fixture: Fixture, service: NodeUserDataService
    ) -> None:
        node = await create_test_machine_entry(fixture)

        assert (
            await service.get_user_data_for_ephemeral_env(node["id"]) is None
        )

    async def test_get_user_data_for_ephemeral_env_ignores_user_env_data(
        self, fixture: Fixture, service: NodeUserDataService
    ) -> None:
        node = await create_test_machine_entry(fixture)
        await create_nodeuserdata_entry(
            fixture,
            node["id"],
            b"deploy-data",
            for_ephemeral_environment=False,
        )

        assert (
            await service.get_user_data_for_ephemeral_env(node["id"]) is None
        )
