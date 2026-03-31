#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, Mock, patch

from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.switches import SwitchesService
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

# Test data
TEST_MAC_ADDRESS = "00:11:22:33:44:55"
TEST_BOOT_RESOURCE_ID = 1
TEST_RESOURCE_SET_ID = 10
TEST_FILENAME = "onie-installer.bin"
TEST_FILE_CONTENT = b"test installer binary content"
TEST_HEADERS = {
    "onie-eth-addr": TEST_MAC_ADDRESS,
    "onie-serial-number": "TEST123",
    "onie-vendor-id": "123",
    "onie-machine": "test-machine",
    "onie-machine-rev": "1.0",
    "onie-arch": "x86_64",
    "onie-security-key": "key",
    "onie-operation": "install",
    "onie-version": "1.0",
}


class TestNOSInstallerApi(ApiCommonTests):
    """Tests for the NOS Installer API endpoints."""

    BASE_PATH = f"{V3_API_PREFIX}/nos-installer"

    @pytest.fixture
    def endpoints_with_authorization(self) -> List[Endpoint]:
        """NOS installer endpoint doesn't require authentication."""
        return []

    async def test_get_nos_installer_no_mac_address(
        self,
        mocked_api_client: AsyncClient,
    ) -> None:
        response = await mocked_api_client.get(self.BASE_PATH)
        assert response.status_code == 422

    async def test_get_nos_installer_no_onie_headers(
        self,
        mocked_api_client: AsyncClient,
    ) -> None:
        response = await mocked_api_client.get(
            self.BASE_PATH, headers={"some-header": "value"}
        )
        assert response.status_code == 422

    async def test_get_nos_installer_switch_not_found(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.get_installer_file_for_switch = AsyncMock(
            side_effect=NotFoundException()
        )

        response = await mocked_api_client.get(
            self.BASE_PATH,
            headers=TEST_HEADERS,
        )
        assert response.status_code == 404

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_get_nos_installer_no_installer_assigned(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.get_installer_file_for_switch = AsyncMock(
            return_value=None
        )

        response = await mocked_api_client.get(
            self.BASE_PATH,
            headers=TEST_HEADERS,
        )
        assert response.status_code == 404

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_get_nos_installer_success(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        file_path = Path("/fake/boot/resources/test-file.bin")

        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.get_installer_file_for_switch = AsyncMock(
            return_value=(file_path, TEST_FILENAME, len(TEST_FILE_CONTENT))
        )

        # Create async mock for file operations
        mock_file = Mock()
        mock_file.read = AsyncMock(side_effect=[TEST_FILE_CONTENT, b""])

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_file
        mock_context_manager.__aexit__.return_value = None

        mock_aiofiles_open = Mock(return_value=mock_context_manager)

        with patch(
            "maasapiserver.v3.api.public.handlers.nos.aiofiles_open",
            mock_aiofiles_open,
        ):
            response = await mocked_api_client.get(
                self.BASE_PATH,
                headers=TEST_HEADERS,
            )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/octet-stream"
        assert (
            response.headers["content-disposition"]
            == f'attachment; filename="{TEST_FILENAME}"'
        )
        assert response.headers["content-length"] == str(
            len(TEST_FILE_CONTENT)
        )
        assert response.content == TEST_FILE_CONTENT

        mock_aiofiles_open.assert_called_once_with(file_path, "rb")
