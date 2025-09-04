# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.agentcertificates import (
    AgentCertificatesRepository,
)
from maasservicelayer.models.agentcertificates import AgentCertificate
from maasservicelayer.services.agentcertificates import AgentCertificateService
from tests.maasservicelayer.services.base import ServiceCommonTests


class TestAgentCertificateService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> AgentCertificateService:
        return AgentCertificateService(
            context=Context(),
            repository=Mock(AgentCertificatesRepository),
        )

    @pytest.fixture
    def test_instance(self) -> AgentCertificate:
        return AgentCertificate(
            id=1,
            certificate=b"certificate",
            certificate_fingerprint="fingerprint",
            agent_id=1,
            revoked_at=None,
        )

    async def test_update_many(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(
            NotImplementedError,
            match="Update is not supported for agent certificates",
        ):
            await super().test_update_many(
                service_instance, test_instance, builder_model
            )

    async def test_update_one(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(
            NotImplementedError,
            match="Update is not supported for agent certificates",
        ):
            await super().test_update_one(
                service_instance, test_instance, builder_model
            )

    async def test_update_one_not_found(self, service_instance, builder_model):
        with pytest.raises(
            NotImplementedError,
            match="Update is not supported for agent certificates",
        ):
            await super().test_update_one_not_found(
                service_instance, builder_model
            )

    async def test_update_one_etag_match(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(
            NotImplementedError,
            match="Update is not supported for agent certificates",
        ):
            await super().test_update_one_etag_match(
                service_instance, test_instance, builder_model
            )

    async def test_update_one_etag_not_matching(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(
            NotImplementedError,
            match="Update is not supported for agent certificates",
        ):
            await super().test_update_one_etag_not_matching(
                service_instance, test_instance, builder_model
            )

    async def test_update_by_id(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(
            NotImplementedError,
            match="Update is not supported for agent certificates",
        ):
            await super().test_update_by_id(
                service_instance, test_instance, builder_model
            )

    async def test_update_by_id_not_found(
        self, service_instance, builder_model
    ):
        with pytest.raises(
            NotImplementedError,
            match="Update is not supported for agent certificates",
        ):
            await super().test_update_by_id_not_found(
                service_instance, builder_model
            )

    async def test_update_by_id_etag_match(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(
            NotImplementedError,
            match="Update is not supported for agent certificates",
        ):
            await super().test_update_by_id_etag_match(
                service_instance, test_instance, builder_model
            )

    async def test_update_by_id_etag_not_matching(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(
            NotImplementedError,
            match="Update is not supported for agent certificates",
        ):
            await super().test_update_by_id_etag_not_matching(
                service_instance, test_instance, builder_model
            )
