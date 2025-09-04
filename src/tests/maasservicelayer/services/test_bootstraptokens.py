# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootstraptokens import (
    BootstrapTokensRepository,
)
from maasservicelayer.models.bootstraptokens import BootstrapToken
from maasservicelayer.services.bootstraptoken import BootstrapTokensService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestBootstrapTokenService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BootstrapTokensService:
        return BootstrapTokensService(
            context=Context(), repository=Mock(BootstrapTokensRepository)
        )

    @pytest.fixture
    def test_instance(self) -> BootstrapToken:
        one_month_from_now = utcnow() + timedelta(days=30)
        return BootstrapToken(
            id=1, expires_at=one_month_from_now, secret="secret", rack_id=1
        )
