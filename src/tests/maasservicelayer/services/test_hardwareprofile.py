# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.builders.hardwareprofile import HardwareProfileBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.hardwareprofile import (
    HardwareProfileRepository,
)
from maasservicelayer.models.hardwareprofile import HardwareProfile
from maasservicelayer.services.hardwareprofile import HardwareProfileService
from tests.maasservicelayer.services.base import ServiceCommonTests


class TesthardwareprofilesServiceCommon(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> HardwareProfileService:
        return HardwareProfileService(
            context=Context(),
            hardware_profile_repository=Mock(HardwareProfileRepository),
        )

    @pytest.fixture
    def test_instance(self) -> HardwareProfile:
        return HardwareProfile(
            id=1,
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

    @pytest.fixture
    def builder_model(self) -> type[HardwareProfileBuilder]:
        return HardwareProfileBuilder
