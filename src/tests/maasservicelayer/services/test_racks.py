# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, call, MagicMock, Mock, patch

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.agents import AgentsClauseFactory
from maasservicelayer.db.repositories.bootstraptokens import (
    BootstrapTokensClauseFactory,
)
from maasservicelayer.db.repositories.racks import RacksRepository
from maasservicelayer.models.racks import Rack
from maasservicelayer.services.agents import AgentsService
from maasservicelayer.services.bootstraptoken import BootstrapTokensService
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.racks import RacksService
from maasservicelayer.services.secrets import SecretsService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestRacksService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> RacksService:
        return RacksService(
            context=Context(),
            repository=Mock(RacksRepository),
            agents_service=Mock(AgentsService),
            bootstraptokens_service=Mock(BootstrapTokensService),
            configurations_service=Mock(ConfigurationsService),
            secrets_service=Mock(SecretsService),
        )

    @pytest.fixture
    def test_instance(self) -> Rack:
        now = utcnow()
        return Rack(id=1, created=now, updated=now, name="rack")

    async def test_delete(self, test_instance: Rack):
        rack = test_instance

        repository_mock = Mock(RacksRepository)
        repository_mock.get_one.return_value = rack
        repository_mock.delete_by_id.return_value = rack

        agents_service_mock = Mock(AgentsService)
        bootstraptokens_service_mock = Mock(BootstrapTokensService)
        configurations_service_mock = Mock(ConfigurationsService)
        secrets_service_mock = Mock(SecretsService)

        rack_service = RacksService(
            context=Context(),
            repository=repository_mock,
            agents_service=agents_service_mock,
            bootstraptokens_service=bootstraptokens_service_mock,
            configurations_service=configurations_service_mock,
            secrets_service=secrets_service_mock,
        )

        query = Mock(QuerySpec)
        await rack_service.delete_one(query)

        repository_mock.delete_by_id.assert_called_once_with(id=rack.id)

        bootstraptokens_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=BootstrapTokensClauseFactory.with_rack_id(rack.id)
            )
        )
        agents_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(where=AgentsClauseFactory.with_rack_id(rack.id))
        )

    @patch("maasservicelayer.services.racks.get_maas_cluster_cert_paths")
    @patch("maasservicelayer.services.racks.Certificate.from_pem")
    @patch("aiofiles.open")
    async def test_generate_bootstrap_token(
        self,
        mock_aiofiles_open,
        mock_certificate_from_pem,
        mock_get_maas_cluster_cert_paths,
        test_instance: Rack,
    ):
        rack = test_instance

        repository_mock = Mock(RacksRepository)
        agents_service_mock = Mock(AgentsService)
        bootstraptokens_service_mock = Mock(BootstrapTokensService)
        configurations_service_mock = Mock(ConfigurationsService)
        secrets_service_mock = Mock(SecretsService)
        configurations_service_mock.get.return_value = (
            "https://example.com:5240/MAAS"
        )

        mock_cert_path = "/var/lib/maas/certificates/cluster.pem"
        mock_key_path = "/var/lib/maas/certificates/cluster.key"
        mock_cacerts_path = "/var/lib/maas/certificates/cacerts.pem"
        mock_get_maas_cluster_cert_paths.return_value = (
            mock_cert_path,
            mock_key_path,
            mock_cacerts_path,
        )
        mock_key = "-----BEGIN PRIVATE KEY-----\nMOCK_CLUSTER_KEY\n-----END PRIVATE KEY-----"
        mock_cert = "-----BEGIN CERTIFICATE-----\nMOCK_CLUSTER_CERT\n-----END CERTIFICATE-----"
        mock_cacerts = "-----BEGIN CERTIFICATE-----\nMOCK_CLUSTER_CA\n-----END CERTIFICATE-----"

        mock_key_file = MagicMock()
        mock_key_file.read = AsyncMock(return_value=mock_key)
        mock_cert_file = MagicMock()
        mock_cert_file.read = AsyncMock(return_value=mock_cert)
        mock_cacerts_file = MagicMock()
        mock_cacerts_file.read = AsyncMock(return_value=mock_cacerts)
        mock_aiofiles_open.side_effect = [
            MagicMock(__aenter__=AsyncMock(return_value=mock_key_file)),
            MagicMock(__aenter__=AsyncMock(return_value=mock_cert_file)),
            MagicMock(__aenter__=AsyncMock(return_value=mock_cacerts_file)),
        ]

        mock_certificate = Mock()
        mock_certificate.cert_hash.return_value = "fingerprint"
        mock_certificate_from_pem.return_value = mock_certificate

        rack_service = RacksService(
            context=Context(),
            repository=repository_mock,
            agents_service=agents_service_mock,
            bootstraptokens_service=bootstraptokens_service_mock,
            configurations_service=configurations_service_mock,
            secrets_service=secrets_service_mock,
        )

        token = await rack_service.generate_bootstrap_token(rack)

        # verify token
        assert len(token["secret"]) == 64
        assert token["url"] == "https://example.com:5242"
        assert token["fingerprint"] == "fingerprint"

        # verify calls
        mock_certificate_from_pem.assert_called_once_with(
            mock_key,
            mock_cert,
            ca_certs_material=mock_cacerts,
        )
        bootstraptokens_service_mock.create.assert_called_once()
        configurations_service_mock.get.assert_called_once_with(
            name="maas_url"
        )
        mock_get_maas_cluster_cert_paths.assert_called_once()

        mock_aiofiles_open.assert_has_calls(
            [
                call(mock_key_path, "r"),
                call(mock_cert_path, "r"),
                call(mock_cacerts_path, "r"),
            ],
            any_order=True,
        )

    @patch("maasservicelayer.services.racks.get_maas_cluster_cert_paths")
    @patch("aiofiles.open")
    async def test_generate_bootstrap_token_no_cluster_certs(
        self,
        mock_aiofiles_open,
        mock_get_maas_cluster_cert_paths,
        test_instance: Rack,
    ):
        rack = test_instance

        repository_mock = Mock(RacksRepository)
        agents_service_mock = Mock(AgentsService)
        bootstraptokens_service_mock = Mock(BootstrapTokensService)
        configurations_service_mock = Mock(ConfigurationsService)
        secrets_service_mock = Mock(SecretsService)
        configurations_service_mock.get.return_value = (
            "https://example.com:5240/MAAS"
        )

        mock_cert_path = "/var/lib/maas/certificates/cluster.pem"
        mock_key_path = "/var/lib/maas/certificates/cluster.key"
        mock_cacerts_path = ""
        mock_get_maas_cluster_cert_paths.return_value = (
            mock_cert_path,
            mock_key_path,
            mock_cacerts_path,
        )
        mock_key = "-----BEGIN PRIVATE KEY-----\nMOCK_CLUSTER_KEY\n-----END PRIVATE KEY-----"
        mock_cert = "-----BEGIN CERTIFICATE-----\nMOCK_CLUSTER_CERT\n-----END CERTIFICATE-----"

        mock_key_file = MagicMock()
        mock_key_file.read = AsyncMock(return_value=mock_key)
        mock_cert_file = MagicMock()
        mock_cert_file.read = AsyncMock(return_value=mock_cert)
        mock_aiofiles_open.side_effect = [
            MagicMock(__aenter__=AsyncMock(return_value=mock_key_file)),
            MagicMock(__aenter__=AsyncMock(return_value=mock_cert_file)),
        ]

        mock_get_maas_cluster_cert_paths.return_value = None

        rack_service = RacksService(
            context=Context(),
            repository=repository_mock,
            agents_service=agents_service_mock,
            bootstraptokens_service=bootstraptokens_service_mock,
            configurations_service=configurations_service_mock,
            secrets_service=secrets_service_mock,
        )

        token = await rack_service.generate_bootstrap_token(rack)

        # verify token
        assert len(token["secret"]) == 64
        assert token["url"] == "https://example.com:5242"
        assert token["fingerprint"] == ""

        # verify calls
        bootstraptokens_service_mock.create.assert_called_once()
        bootstraptokens_service_mock.create.assert_called_once()
        configurations_service_mock.get.assert_called_once_with(
            name="maas_url"
        )
        mock_get_maas_cluster_cert_paths.assert_called_once()

    async def test_list_with_summary_calls_repository(
        self, service_instance: RacksService
    ) -> None:
        mock_repository = Mock(RacksRepository)
        service_instance.repository = mock_repository
        await service_instance.list_with_summary(1, 20)

        mock_repository.list_with_summary.assert_called_once_with(1, 20)
