# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.hardwareprofile import HardwareProfileBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.hardwareprofile import (
    HardwareProfileRepository,
)
from maasservicelayer.models.hardwareprofile import HardwareProfile
from tests.fixtures.factories.hardwareprofile import (
    create_test_hardware_profile_entry,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


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
        return HardwareProfileBuilder(
            node_id=1,
            architecture="amd64/generic",
            cpu_cores=4,
            cpu_speed_mhz=2400,
            memory_mb=4096,
            disk_count=1,
            total_storage_bytes=512 * 1024 * 1024 * 1024,
            nic_count=1,
            gpu_count=0,
            system_vendor=None,
            system_product=None,
            hardware_fingerprint="a" * 64,
            storage=[],
            network=[],
            accelerators=[],
        )
