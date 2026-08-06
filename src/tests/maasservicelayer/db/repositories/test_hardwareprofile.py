# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maasservicelayer.builders.hardwareprofile import HardwareProfileBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.hardwareprofile import (
    HardwareProfileRepository,
)
from maasservicelayer.db.tables import HardwareProfileTable
from maasservicelayer.models.hardwareprofile import HardwareProfile
from tests.fixtures.factories.hardwareprofile import (
    create_test_hardware_profile_entry,
    make_hardware_profile_dict,
)
from tests.fixtures.factories.node import create_test_machine_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


def make_builder(node_id: int, **kwargs) -> HardwareProfileBuilder:
    fields = make_hardware_profile_dict(node_id, **kwargs)
    return HardwareProfileBuilder(**fields)


class TestHardwareProfilesRepository(RepositoryCommonTests[HardwareProfile]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> HardwareProfileRepository:
        return HardwareProfileRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[HardwareProfile]:
        created_hardware_profiles = [
            await create_test_hardware_profile_entry(fixture)
            for _ in range(num_objects)
        ]
        return created_hardware_profiles

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> HardwareProfile:
        return await create_test_hardware_profile_entry(fixture)

    @pytest.fixture
    async def instance_builder_model(
        self, *args, **kwargs
    ) -> type[HardwareProfileBuilder]:
        return HardwareProfileBuilder

    @pytest.fixture
    async def instance_builder(self) -> HardwareProfileBuilder:
        return make_builder(node_id=1)


class TestHardwareProfileRepositoryCreateOrUpdate:
    @pytest.fixture
    def repository(
        self, db_connection: AsyncConnection
    ) -> HardwareProfileRepository:
        return HardwareProfileRepository(Context(connection=db_connection))

    async def test_creates_profile_for_new_node(
        self, repository: HardwareProfileRepository, fixture: Fixture
    ) -> None:
        node = await create_test_machine_entry(fixture)
        hw_profiles = await fixture.get_typed(
            HardwareProfileTable.name,
            HardwareProfile,
            eq(HardwareProfileTable.c.node_id, node["id"]),
        )
        assert len(hw_profiles) == 0

        profile = await repository.create_or_update(make_builder(node["id"]))

        assert profile.id is not None
        assert profile.node_id == node["id"]
        assert profile.cpu_cores == 4
        assert profile.system_vendor == "LENOVO"

        hw_profiles = await fixture.get_typed(
            HardwareProfileTable.name,
            HardwareProfile,
            eq(HardwareProfileTable.c.node_id, node["id"]),
        )
        assert len(hw_profiles) == 1

    async def test_updates_existing_profile(
        self, repository: HardwareProfileRepository, fixture: Fixture
    ) -> None:
        node = await create_test_machine_entry(fixture)
        created = await repository.create_or_update(make_builder(node["id"]))

        updated = await repository.create_or_update(
            make_builder(node["id"], cpu_cores=64, memory_mb=262144)
        )

        assert updated.id == created.id
        assert updated.cpu_cores == 64
        assert updated.memory_mb == 262144

        hw_profiles = await fixture.get_typed(
            HardwareProfileTable.name,
            HardwareProfile,
            eq(HardwareProfileTable.c.node_id, node["id"]),
        )
        assert len(hw_profiles) == 1

    async def test_update_preserves_created_and_bumps_updated(
        self, repository: HardwareProfileRepository, fixture: Fixture
    ) -> None:
        node = await create_test_machine_entry(fixture)
        created_profile = await repository.create_or_update(
            make_builder(node["id"])
        )

        updated_profile = await repository.create_or_update(
            make_builder(node["id"], cpu_cores=64)
        )

        assert updated_profile.created == created_profile.created
        assert updated_profile.updated >= created_profile.updated
