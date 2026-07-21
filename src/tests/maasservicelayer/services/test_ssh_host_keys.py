#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from maasservicelayer.builders.ssh_host_keys import TrustedSshHostKeyBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.ssh_host_keys import (
    TrustedSshHostKeyRepository,
)
from maasservicelayer.models.ssh_host_keys import TrustedSshHostKey
from maasservicelayer.services.ssh_host_keys import TrustedSshHostKeysService
from tests.maasservicelayer.services.base import ServiceCommonTests

TEST_KEY = TrustedSshHostKey(
    id=1,
    created=datetime(2026, 1, 1, tzinfo=timezone.utc),
    updated=datetime(2026, 1, 1, tzinfo=timezone.utc),
    host="192.168.1.1",
    key_type="ssh-rsa",
    public_key="AAAAB3NzaC1yc2EAAAADAQABAAABAQC0",
    label="rack-1",
)


class TestTrustedSshHostKeysServiceCommon(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> TrustedSshHostKeysService:
        return TrustedSshHostKeysService(
            context=Mock(spec=Context),
            repository=Mock(spec=TrustedSshHostKeyRepository),
        )

    @pytest.fixture
    def test_instance(self) -> TrustedSshHostKey:
        return TEST_KEY

    @pytest.fixture
    def builder_model(self) -> type[TrustedSshHostKeyBuilder]:
        return TrustedSshHostKeyBuilder
