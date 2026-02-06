#  Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, Mock, mock_open, patch

from httpx import AsyncClient
import pytest

from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.boot_resources import (
    BootResourceFileType,
    BootResourceType,
)
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.bootresourcefiles import BootResourceFile
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.models.bootresourcesets import BootResourceSet
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.bootresourcefiles import (
    BootResourceFilesService,
)
from maasservicelayer.services.bootresources import BootResourceService
from maasservicelayer.services.bootresourcesets import BootResourceSetsService
from maasservicelayer.services.switches import SwitchesService
from maasservicelayer.utils.date import utcnow
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
    def user_endpoints(self) -> List[Endpoint]:
        """Endpoints - NOS installer doesn't require authentication."""
        return []

    @pytest.fixture
    def admin_endpoints(self) -> List[Endpoint]:
        """Endpoints accessible only to admins."""
        return []

    async def test_get_nos_installer_no_mac_address(
        self,
        mocked_api_client: AsyncClient,
    ) -> None:
        """Test that missing MAC address returns 400."""
        response = await mocked_api_client.get(self.BASE_PATH)
        assert response.status_code == 400
        assert "MAC address not found" in response.text

    async def test_get_nos_installer_no_onie_headers(
        self,
        mocked_api_client: AsyncClient,
    ) -> None:
        """Test that request without ONIE headers returns 400."""
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
        """Test that non-existent switch returns 204."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.check_installer_for_switch = AsyncMock(
            side_effect=NotFoundException()
        )

        response = await mocked_api_client.get(
            self.BASE_PATH,
            headers=TEST_HEADERS,
        )
        assert response.status_code == 204
        assert response.text == ""

    async def test_get_nos_installer_no_boot_resource(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        """Test that missing boot resource returns 204."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.check_installer_for_switch = AsyncMock(
            return_value=TEST_BOOT_RESOURCE_ID
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_by_id = AsyncMock(return_value=None)

        response = await mocked_api_client.get(
            self.BASE_PATH,
            headers=TEST_HEADERS,
        )
        assert response.status_code == 204
        assert response.text == ""

    async def test_get_nos_installer_boot_resource_not_found_exception(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        """Test that NotFoundException for boot resource returns 204."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.check_installer_for_switch = AsyncMock(
            return_value=TEST_BOOT_RESOURCE_ID
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_by_id = AsyncMock(
            side_effect=NotFoundException()
        )

        response = await mocked_api_client.get(
            self.BASE_PATH,
            headers=TEST_HEADERS,
        )
        assert response.status_code == 204
        assert response.text == ""

    async def test_get_nos_installer_no_resource_set(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        """Test that missing resource set returns 204."""
        boot_resource = BootResource(
            id=TEST_BOOT_RESOURCE_ID,
            name="test-image",
            rtype=BootResourceType.UPLOADED,
            architecture="amd64/generic",
            extra={},
            rolling=False,
            base_image="",
            created=utcnow(),
            updated=utcnow(),
        )

        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.check_installer_for_switch = AsyncMock(
            return_value=TEST_BOOT_RESOURCE_ID
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_by_id = AsyncMock(
            return_value=boot_resource
        )
        services_mock.boot_resource_sets = Mock(BootResourceSetsService)
        services_mock.boot_resource_sets.get_latest_complete_set_for_boot_resource = AsyncMock(
            return_value=None
        )

        response = await mocked_api_client.get(
            self.BASE_PATH,
            headers=TEST_HEADERS,
        )
        assert response.status_code == 204
        assert response.text == ""

    async def test_get_nos_installer_no_files(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        """Test that resource set with no files returns 204."""
        boot_resource = BootResource(
            id=TEST_BOOT_RESOURCE_ID,
            name="test-image",
            rtype=BootResourceType.UPLOADED,
            architecture="amd64/generic",
            extra={},
            rolling=False,
            base_image="",
            created=utcnow(),
            updated=utcnow(),
        )
        resource_set = BootResourceSet(
            id=TEST_RESOURCE_SET_ID,
            version="1.0",
            label="uploaded",
            resource_id=TEST_BOOT_RESOURCE_ID,
            created=utcnow(),
            updated=utcnow(),
        )

        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.check_installer_for_switch = AsyncMock(
            return_value=TEST_BOOT_RESOURCE_ID
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_by_id = AsyncMock(
            return_value=boot_resource
        )
        services_mock.boot_resource_sets = Mock(BootResourceSetsService)
        services_mock.boot_resource_sets.get_latest_complete_set_for_boot_resource = AsyncMock(
            return_value=resource_set
        )
        services_mock.boot_resource_files = Mock(BootResourceFilesService)
        services_mock.boot_resource_files.get_files_in_resource_set = (
            AsyncMock(return_value=[])
        )

        response = await mocked_api_client.get(
            self.BASE_PATH,
            headers=TEST_HEADERS,
        )
        assert response.status_code == 204
        assert response.text == ""

    @patch(
        "maasapiserver.v3.api.public.handlers.nos.get_bootresource_store_path"
    )
    @patch(
        "builtins.open", new_callable=mock_open, read_data=TEST_FILE_CONTENT
    )
    async def test_get_nos_installer_success(
        self,
        mock_file_open,
        mock_get_store_path,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        """Test successful installer download."""
        # Mock the store path to return a Path object
        mock_get_store_path.return_value = Path("/fake/boot/resources")

        boot_resource = BootResource(
            id=TEST_BOOT_RESOURCE_ID,
            name="test-image",
            rtype=BootResourceType.UPLOADED,
            architecture="amd64/generic",
            extra={},
            rolling=False,
            base_image="",
        )
        resource_set = BootResourceSet(
            id=TEST_RESOURCE_SET_ID,
            version="1.0",
            label="uploaded",
            resource_id=TEST_BOOT_RESOURCE_ID,
            created=utcnow(),
            updated=utcnow(),
        )
        boot_file = BootResourceFile(
            id=1,
            filename=TEST_FILENAME,
            filename_on_disk="test-file.bin",
            filetype=BootResourceFileType.ROOT_TGZ,
            extra={},
            sha256="abc123",
            size=len(TEST_FILE_CONTENT),
            resource_set_id=TEST_RESOURCE_SET_ID,
        )

        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.check_installer_for_switch = AsyncMock(
            return_value=TEST_BOOT_RESOURCE_ID
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_by_id = AsyncMock(
            return_value=boot_resource
        )
        services_mock.boot_resource_sets = Mock(BootResourceSetsService)
        services_mock.boot_resource_sets.get_latest_complete_set_for_boot_resource = AsyncMock(
            return_value=resource_set
        )
        services_mock.boot_resource_files = Mock(BootResourceFilesService)
        services_mock.boot_resource_files.get_files_in_resource_set = (
            AsyncMock(return_value=[boot_file])
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

        # Verify that open was called with the correct file path (Path object)
        mock_file_open.assert_called_once_with(
            Path("/fake/boot/resources/test-file.bin"), "rb"
        )

    async def test_onie_headers_validation(self) -> None:
        """Test that OnieHeaders correctly validates and parses request headers."""
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
        """Test that OnieHeaders works with only MAC address present."""
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
        """Test that OnieHeaders returns None when no ONIE headers present."""
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
