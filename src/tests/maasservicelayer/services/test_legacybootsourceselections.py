# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.builders.legacybootsourceselections import (
    LegacyBootSourceSelectionBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.legacybootsourceselections import (
    LegacyBootSourceSelectionRepository,
)
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.legacybootsourceselections import (
    LegacyBootSourceSelection,
)
from maasservicelayer.services.legacybootsourceselections import (
    LegacyBootSourceSelectionService,
)
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


class TestLegacyBootSourceSelectionService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> LegacyBootSourceSelectionService:
        return LegacyBootSourceSelectionService(
            context=Context(),
            repository=Mock(LegacyBootSourceSelectionRepository),
        )

    @pytest.fixture
    def test_instance(self) -> LegacyBootSourceSelection:
        now = utcnow()
        return LegacyBootSourceSelection(
            id=1,
            created=now,
            updated=now,
            os="ubuntu",
            release="focal",
            arches=["amd64"],
            subarches=["*"],
            labels=["*"],
            boot_source_id=1,
        )

    @pytest.fixture
    def builder_model(self) -> type[ResourceBuilder]:
        return LegacyBootSourceSelectionBuilder
