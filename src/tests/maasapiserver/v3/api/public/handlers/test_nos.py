#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, Mock, mock_open, patch

from httpx import AsyncClient
import pytest

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
        assert response.status_code == 400
        assert "MAC address not found" in response.text

    async def test_get_nos_installer_no_onie_headers(
        self,
        mocked_api_client: AsyncClient,
    ) -> None:
        response = await mocked_api_client.get(
            self.BASE_PATH, headers={"some-header": "value"}
        )
        assert response.status_code == 400
        assert "MAC address not found" in response.text

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
        assert response.text == ""

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
        assert response.text == ""

    @patch(
        "builtins.open", new_callable=mock_open, read_data=TEST_FILE_CONTENT
    )
    async def test_get_nos_installer_success(
        self,
        mock_file_open,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        file_path = Path("/fake/boot/resources/test-file.bin")

        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.get_installer_file_for_switch = AsyncMock(
            return_value=(file_path, TEST_FILENAME, len(TEST_FILE_CONTENT))
        )

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

        mock_file_open.assert_called_once_with(file_path, "rb")

    async def test_onie_headers_validation(self) -> None:
        from fastapi import Request

        from maasapiserver.v3.api.public.handlers.nos import OnieHeaders

        # Create a mock request with valid ONIE headers
        mock_request = Mock(spec=Request)
        mock_request.headers = TEST_HEADERS

        onie_headers = OnieHeaders.from_request(mock_request)
        assert onie_headers is not None
        assert onie_headers.eth_address == TEST_HEADERS["onie-eth-addr"]
        assert onie_headers.serial_number == TEST_HEADERS["onie-serial-number"]
        assert onie_headers.vendor_id == TEST_HEADERS["onie-vendor-id"]
        assert onie_headers.machine == TEST_HEADERS["onie-machine"]
        assert onie_headers.machine_rev == TEST_HEADERS["onie-machine-rev"]
        assert onie_headers.arch == TEST_HEADERS["onie-arch"]
        assert onie_headers.security_key == TEST_HEADERS["onie-security-key"]
        assert onie_headers.operation == TEST_HEADERS["onie-operation"]
        assert onie_headers.version == TEST_HEADERS["onie-version"]

    async def test_onie_headers_validation_only_mac_address(self) -> None:
        from fastapi import Request

        from maasapiserver.v3.api.public.handlers.nos import OnieHeaders

        # Create a mock request with only the MAC address header
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "onie-eth-addr": TEST_MAC_ADDRESS,
            "some-other-header": "value",
        }

        onie_headers = OnieHeaders.from_request(mock_request)
        assert onie_headers is not None
        assert onie_headers.eth_address == TEST_MAC_ADDRESS

    async def test_onie_headers_validation_no_onie_headers(self) -> None:
        from fastapi import Request

        from maasapiserver.v3.api.public.handlers.nos import OnieHeaders

        # Create a mock request with no ONIE headers
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "user-agent": "test",
            "accept": "*/*",
        }

        onie_headers = OnieHeaders.from_request(mock_request)
        assert onie_headers is None
