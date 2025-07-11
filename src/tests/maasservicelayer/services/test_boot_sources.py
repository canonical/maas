# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import b64decode
import os
from unittest.mock import ANY, call, MagicMock, Mock, patch

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootsources import BootSourcesRepository
from maasservicelayer.models.bootsources import BootSource
from maasservicelayer.services.boot_sources import BootSourcesService
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.utils.date import utcnow
from maasservicelayer.utils.images.boot_image_mapping import BootImageMapping
from maastesting.factory import factory
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestBootSourcesService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BootSourcesService:
        return BootSourcesService(
            context=Context(),
            repository=Mock(BootSourcesRepository),
            configuration_service=Mock(ConfigurationsService),
        )

    @pytest.fixture
    def test_instance(self) -> BootSource:
        now = utcnow()
        return BootSource(
            id=1,
            created=now,
            updated=now,
            url="http://example.com",
            keyring_filename="/path/to/keyring_file.gpg",
            keyring_data=b"",
            priority=10,
            skip_keyring_verification=False,
        )

    @patch("maasservicelayer.services.boot_sources.RepoDumper.sync")
    @patch("maasservicelayer.services.boot_sources.UrlMirrorReader")
    async def test_fetch_calls_repodumper_with_correct_urlmirrorreader(
        self,
        mock_urlmirrorreader: MagicMock,
        mock_repodumper_sync: MagicMock,
        service_instance: BootSourcesService,
    ) -> None:
        source_url = factory.make_url()
        user_agent = "maas/3.6.4/g.12345678"

        expected_mirror_url = "streams/v1/index.sjson"

        service_instance._fetch(source_url, user_agent=user_agent)

        mock_repodumper_sync.assert_called_once_with(
            mock_urlmirrorreader.return_value,
            expected_mirror_url,
        )
        mock_urlmirrorreader.assert_called_once_with(
            source_url,
            policy=ANY,
            user_agent=user_agent,
        )

    @patch("maasservicelayer.services.boot_sources.BootSourcesService._fetch")
    async def test_fetch_gets_maas_user_agent(
        self,
        mock_fetch_submethod: MagicMock,
        service_instance: BootSourcesService,
    ) -> None:
        source_url = factory.make_url()
        user_agent = "maas/3.6.4/g.12345678"

        mock_configurations_service = service_instance.configuration_service
        mock_configurations_service.get_maas_user_agent.return_value = (
            user_agent
        )

        # Test the async fetch calls the _fetch submethod with the maas user agent.
        await service_instance.fetch(source_url)

        mock_configurations_service.get_maas_user_agent.assert_called_once()
        mock_fetch_submethod.assert_called_once_with(
            source_url,  # source_url
            user_agent,  # user_agent
            None,  # keyring_path
            None,  # keyring_data
            True,  # validate_products
        )

    @patch("maasservicelayer.services.boot_sources.RepoDumper.sync")
    @patch("maasservicelayer.services.boot_sources.UrlMirrorReader")
    async def test_fetch_passes_maas_user_agent_through(
        self,
        mock_urlmirrorreader: MagicMock,
        mock_repodumper_sync: MagicMock,
        service_instance: BootSourcesService,
    ) -> None:
        source_url = factory.make_url()
        expected_mirror_url = "streams/v1/index.sjson"
        user_agent = "maas/3.6.4/g.12345678"

        service_instance._fetch(source_url, user_agent=user_agent)

        # Also doesn't pass user agent when not set.
        mock_repodumper_sync.assert_called_once_with(
            mock_urlmirrorreader.return_value,
            expected_mirror_url,
        )
        mock_urlmirrorreader.assert_called_once_with(
            source_url,
            policy=ANY,
            user_agent=user_agent,
        )

    @patch("maasservicelayer.services.boot_sources.RepoDumper.sync")
    @patch("maasservicelayer.services.boot_sources.UrlMirrorReader")
    async def test_fetch_doesnt_pass_user_agent_on_fallback(
        self,
        mock_urlmirrorreader: MagicMock,
        mock_repodumper_sync: MagicMock,
        service_instance: BootSourcesService,
    ) -> None:
        # This is a test covering simplestream-specific behavior that could be
        # removed should we move away from this library.
        # TODO: Remove this test if/when we stop using simplestreams.
        source_url = factory.make_url()
        user_agent = "maas/3.6.4/g.12345678"

        mock_configurations_service = service_instance.configuration_service
        mock_configurations_service.get_maas_user_agent.return_value = (
            user_agent
        )

        mock_urlmirrorreader.side_effect = [TypeError(), MagicMock()]

        service_instance._fetch(source_url, user_agent=user_agent)

        mock_repodumper_sync.assert_called()
        mock_urlmirrorreader.assert_has_calls(
            [
                call(source_url, policy=ANY, user_agent=user_agent),
                call(source_url, policy=ANY),
            ]
        )

    @patch("maasservicelayer.services.boot_sources.RepoDumper.sync")
    @patch("maasservicelayer.services.boot_sources.UrlMirrorReader")
    @patch("maasservicelayer.services.boot_sources.write_keyring")
    @patch("maasservicelayer.services.boot_sources.calculate_keyring_name")
    @patch("maasservicelayer.services.boot_sources.tempdir")
    async def test_fetch_writes_keyring_data_to_tempdir(
        self,
        mock_tempdir: MagicMock,
        mock_calculate_keyring_name: MagicMock,
        mock_write_keyring: MagicMock,
        mock_urlmirrorreader: MagicMock,
        mock_repodumper_sync: MagicMock,
        service_instance: BootSourcesService,
    ) -> None:
        source_url = factory.make_url()
        keyring_data = b64decode("a2V5cmluZ19kYXRh")
        user_agent = "maas/3.6.4/g.12345678"

        tmp_path = "/tmp/abc_keyrings"
        calc_keyring_name = "calculated_keyring_name"

        expected_keyring_path = os.path.join(tmp_path, calc_keyring_name)

        mock_configurations_service = service_instance.configuration_service
        mock_configurations_service.get_maas_user_agent.return_value = (
            user_agent
        )

        mock_tempdir.return_value.__enter__.return_value = tmp_path
        mock_calculate_keyring_name.return_value = calc_keyring_name

        service_instance._fetch(
            source_url,
            user_agent=user_agent,
            keyring_path=None,
            keyring_data=keyring_data,
        )

        mock_write_keyring.assert_called_once_with(
            expected_keyring_path, keyring_data
        )
        mock_repodumper_sync.assert_called_once()
        mock_urlmirrorreader.assert_called_once()

    @patch("maasservicelayer.services.boot_sources.BootSourcesService._fetch")
    @patch("maasservicelayer.services.boot_sources.write_keyring")
    async def test_fetch_doesnt_write_keyring_when_path_given(
        self,
        mock_write_keyring: MagicMock,
        mock_fetch_submethod: MagicMock,
        service_instance: BootSourcesService,
    ) -> None:
        source_url = factory.make_url()
        keyring_path = "/tmp/keyrings/abc"
        user_agent = "maas/3.6.4/g.12345678"

        mock_configurations_service = service_instance.configuration_service
        mock_configurations_service.get_maas_user_agent.return_value = (
            user_agent
        )

        mock_fetch_submethod.return_value = BootImageMapping()

        await service_instance.fetch(
            source_url,
            keyring_path=keyring_path,
            keyring_data=None,
        )

        mock_write_keyring.assert_not_called()
