#  Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from pathlib import Path
from unittest.mock import AsyncMock, call, Mock, patch

import pytest

from maascommon.enums.boot_resources import (
    BootResourceFileType,
    BootResourceType,
)
from maascommon.enums.interface import InterfaceType
from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.builders.switches import SwitchBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.switches import SwitchesRepository
from maasservicelayer.exceptions.catalog import (
    ConflictException,
    NotFoundException,
)
from maasservicelayer.models.base import MaasBaseModel, ResourceBuilder
from maasservicelayer.models.bootresourcefiles import BootResourceFile
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.models.bootresourcesets import BootResourceSet
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.switches import Switch
from maasservicelayer.services import SwitchesService
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.bootresourcefiles import (
    BootResourceFilesService,
)
from maasservicelayer.services.bootresources import BootResourceService
from maasservicelayer.services.bootresourcesets import BootResourceSetsService
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests

TEST_SWITCH = Switch(
    id=1,
    target_image_id=None,
    created=utcnow(),
    updated=utcnow(),
)


@pytest.mark.asyncio
class TestCommonSwitchesService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return SwitchesService(
            context=Context(),
            switches_repository=Mock(SwitchesRepository),
            staticipaddress_service=Mock(StaticIPAddressService),
            interfaces_service=Mock(InterfacesService),
            boot_resources_service=Mock(BootResourceService),
            boot_resource_sets_service=Mock(BootResourceSetsService),
            boot_resource_files_service=Mock(BootResourceFilesService),
        )

    @pytest.fixture
    def builder_model(self) -> type[ResourceBuilder]:
        return SwitchBuilder

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        now = utcnow()
        return Switch(
            id=1,
            created=now,
            updated=now,
            target_image_id=2,
        )


@pytest.mark.asyncio
class TestSwitchesService:
    """Specific tests for SwitchesService business logic."""

    @pytest.fixture
    async def switches_repository(self):
        return Mock(SwitchesRepository)

    @pytest.fixture
    async def staticipaddress_service(self):
        return Mock(StaticIPAddressService)

    @pytest.fixture
    async def interfaces_service(self):
        return Mock(InterfacesService)

    @pytest.fixture
    async def boot_resources_service(self):
        return Mock(BootResourceService)

    @pytest.fixture
    async def boot_resource_sets_service(self):
        return Mock(BootResourceSetsService)

    @pytest.fixture
    async def boot_resource_files_service(self):
        return Mock(BootResourceFilesService)

    @pytest.fixture
    async def service(
        self,
        switches_repository,
        staticipaddress_service,
        interfaces_service,
        boot_resources_service,
        boot_resource_sets_service,
        boot_resource_files_service,
    ):
        return SwitchesService(
            context=Context(),
            switches_repository=switches_repository,
            staticipaddress_service=staticipaddress_service,
            interfaces_service=interfaces_service,
            boot_resources_service=boot_resources_service,
            boot_resource_sets_service=boot_resource_sets_service,
            boot_resource_files_service=boot_resource_files_service,
        )

    async def test_get_switch_by_mac_address(
        self,
        service,
        switches_repository,
        interfaces_service,
    ) -> None:
        """Test getting a switch by its management interface MAC address."""
        test_switch = TEST_SWITCH
        test_interface = Mock()
        test_interface.switch_id = test_switch.id

        interfaces_service.get_one.return_value = test_interface
        switches_repository.get_by_id.return_value = test_switch

        result = await service.get_switch_by_mac_address("00:11:22:33:44:55")

        assert result == test_switch
        interfaces_service.get_one.assert_called_once()
        switches_repository.get_by_id.assert_called_once_with(
            id=test_switch.id
        )

    async def test_check_installer_for_switch(
        self,
        service,
        switches_repository,
        interfaces_service,
    ) -> None:
        """Test checking for an assigned NOS installer for a switch."""
        test_switch = TEST_SWITCH
        test_switch.target_image_id = 42
        test_interface = Mock()
        test_interface.switch_id = test_switch.id

        interfaces_service.get_one.return_value = test_interface
        switches_repository.get_by_id.return_value = test_switch

        result = await service.check_installer_for_switch("00:11:22:33:44:55")

        assert result == 42
        interfaces_service.get_one.assert_called_once()
        switches_repository.get_by_id.assert_called_with(id=test_switch.id)

    @pytest.mark.parametrize(
        "test_id,setup_mocks,expected_exception",
        [
            pytest.param(
                "switch_not_found",
                lambda: {
                    "interface_exists": False,
                },
                NotFoundException,
            ),
            pytest.param(
                "no_installer_assigned",
                lambda: {
                    "target_image_id": None,
                    "interface_exists": True,
                },
                None,
            ),
            pytest.param(
                "boot_resource_not_found",
                lambda: {
                    "target_image_id": 42,
                    "interface_exists": True,
                    "boot_resource": None,
                },
                NotFoundException,
            ),
            pytest.param(
                "no_resource_set",
                lambda: {
                    "target_image_id": 42,
                    "interface_exists": True,
                    "boot_resource": BootResource(
                        id=42,
                        name="test-nos",
                        rtype=BootResourceType.UPLOADED,
                        architecture="amd64/generic",
                        extra={},
                        rolling=False,
                        base_image="",
                        created=utcnow(),
                        updated=utcnow(),
                    ),
                    "resource_set": None,
                },
                NotFoundException,
            ),
            pytest.param(
                "no_files",
                lambda: {
                    "target_image_id": 42,
                    "interface_exists": True,
                    "boot_resource": BootResource(
                        id=42,
                        name="test-nos",
                        rtype=BootResourceType.UPLOADED,
                        architecture="amd64/generic",
                        extra={},
                        rolling=False,
                        base_image="",
                        created=utcnow(),
                        updated=utcnow(),
                    ),
                    "resource_set": BootResourceSet(
                        id=10,
                        version="1.0",
                        label="uploaded",
                        resource_id=42,
                        created=utcnow(),
                        updated=utcnow(),
                    ),
                    "files": [],
                },
                NotFoundException,
            ),
            pytest.param(
                "multiple_files",
                lambda: {
                    "target_image_id": 42,
                    "interface_exists": True,
                    "boot_resource": BootResource(
                        id=42,
                        name="test-nos",
                        rtype=BootResourceType.UPLOADED,
                        architecture="amd64/generic",
                        extra={},
                        rolling=False,
                        base_image="",
                        created=utcnow(),
                        updated=utcnow(),
                    ),
                    "resource_set": BootResourceSet(
                        id=10,
                        version="1.0",
                        label="uploaded",
                        resource_id=42,
                        created=utcnow(),
                        updated=utcnow(),
                    ),
                    "files": [
                        BootResourceFile(
                            id=1,
                            filename="nos-installer-1.bin",
                            filename_on_disk="abc123.bin",
                            filetype=BootResourceFileType.SELF_EXTRACTING,
                            extra={},
                            sha256="abc123",
                            size=1024000,
                            resource_set_id=10,
                            created=utcnow(),
                            updated=utcnow(),
                        ),
                        BootResourceFile(
                            id=2,
                            filename="nos-installer-2.bin",
                            filename_on_disk="def456.bin",
                            filetype=BootResourceFileType.SELF_EXTRACTING,
                            extra={},
                            sha256="def456",
                            size=2048000,
                            resource_set_id=10,
                            created=utcnow(),
                            updated=utcnow(),
                        ),
                    ],
                },
                ConflictException,
            ),
        ],
    )
    async def test_get_installer_file_for_switch_error_cases(
        self,
        test_id,
        service,
        setup_mocks,
        expected_exception,
        interfaces_service,
        switches_repository,
        boot_resources_service,
        boot_resource_sets_service,
        boot_resource_files_service,
    ) -> None:
        setup = setup_mocks()

        if setup.get("interface_exists", True):
            test_switch = Switch(
                id=1,
                target_image_id=setup.get("target_image_id", 42),
                created=utcnow(),
                updated=utcnow(),
            )
            test_interface = Mock()
            test_interface.switch_id = test_switch.id
            interfaces_service.get_one.return_value = test_interface
            switches_repository.get_by_id.return_value = test_switch
        else:
            interfaces_service.get_one.return_value = None

        if "boot_resource" in setup:
            boot_resources_service.get_by_id = AsyncMock(
                return_value=setup["boot_resource"]
            )

        if "resource_set" in setup:
            boot_resource_sets_service.get_latest_complete_set_for_boot_resource = AsyncMock(
                return_value=setup["resource_set"]
            )

        if "files" in setup:
            boot_resource_files_service.get_files_in_resource_set = AsyncMock(
                return_value=setup["files"]
            )

        if expected_exception:
            with pytest.raises(expected_exception):
                await service.get_installer_file_for_switch(
                    "00:11:22:33:44:55"
                )
        else:
            result = await service.get_installer_file_for_switch(
                "00:11:22:33:44:55"
            )
            assert result is None

    @patch("maasservicelayer.services.switches.get_bootresource_store_path")
    async def test_get_installer_file_for_switch_success(
        self,
        mock_get_store_path,
        service,
        interfaces_service,
        switches_repository,
        boot_resources_service,
        boot_resource_sets_service,
        boot_resource_files_service,
    ) -> None:
        mock_store_path = Path("/fake/boot/resources")
        mock_get_store_path.return_value = mock_store_path

        test_switch = Switch(
            id=1,
            target_image_id=42,
            created=utcnow(),
            updated=utcnow(),
        )
        test_interface = Mock()
        test_interface.switch_id = test_switch.id

        boot_resource = BootResource(
            id=42,
            name="test-nos",
            rtype=BootResourceType.UPLOADED,
            architecture="amd64/generic",
            extra={},
            rolling=False,
            base_image="",
            created=utcnow(),
            updated=utcnow(),
        )

        resource_set = BootResourceSet(
            id=10,
            version="1.0",
            label="uploaded",
            resource_id=42,
            created=utcnow(),
            updated=utcnow(),
        )

        boot_file = BootResourceFile(
            id=1,
            filename="nos-installer.bin",
            filename_on_disk="abc123.bin",
            filetype=BootResourceFileType.SELF_EXTRACTING,
            extra={},
            sha256="abc123",
            size=1024000,
            resource_set_id=10,
            created=utcnow(),
            updated=utcnow(),
        )

        interfaces_service.get_one.return_value = test_interface
        switches_repository.get_by_id.return_value = test_switch
        boot_resources_service.get_by_id = AsyncMock(
            return_value=boot_resource
        )
        boot_resource_sets_service.get_latest_complete_set_for_boot_resource = AsyncMock(
            return_value=resource_set
        )
        boot_resource_files_service.get_files_in_resource_set = AsyncMock(
            return_value=[boot_file]
        )

        with patch.object(Path, "exists", return_value=True):
            result = await service.get_installer_file_for_switch(
                "00:11:22:33:44:55"
            )

        assert result is not None
        file_path, filename, size = result
        assert file_path == mock_store_path / "abc123.bin"
        assert filename == "nos-installer.bin"
        assert size == 1024000

        boot_resources_service.get_by_id.assert_called_once_with(id=42)
        boot_resource_sets_service.get_latest_complete_set_for_boot_resource.assert_called_once_with(
            42
        )
        boot_resource_files_service.get_files_in_resource_set.assert_called_once_with(
            10
        )

    @patch("maasservicelayer.services.switches.get_bootresource_store_path")
    async def test_get_installer_file_for_switch_file_not_on_disk(
        self,
        mock_get_store_path,
        service,
        interfaces_service,
        switches_repository,
        boot_resources_service,
        boot_resource_sets_service,
        boot_resource_files_service,
    ) -> None:
        mock_store_path = Path("/fake/boot/resources")
        mock_get_store_path.return_value = mock_store_path

        test_switch = Switch(
            id=1,
            target_image_id=42,
            created=utcnow(),
            updated=utcnow(),
        )
        test_interface = Mock()
        test_interface.switch_id = test_switch.id
        boot_resource = BootResource(
            id=42,
            name="test-nos",
            rtype=BootResourceType.UPLOADED,
            architecture="amd64/generic",
            extra={},
            rolling=False,
            base_image="",
            created=utcnow(),
            updated=utcnow(),
        )
        resource_set = BootResourceSet(
            id=10,
            version="1.0",
            label="uploaded",
            resource_id=42,
            created=utcnow(),
            updated=utcnow(),
        )
        boot_file = BootResourceFile(
            id=1,
            filename="nos-installer.bin",
            filename_on_disk="abc123.bin",
            filetype=BootResourceFileType.SELF_EXTRACTING,
            extra={},
            sha256="abc123",
            size=1024000,
            resource_set_id=10,
            created=utcnow(),
            updated=utcnow(),
        )
        interfaces_service.get_one.return_value = test_interface
        switches_repository.get_by_id.return_value = test_switch
        boot_resources_service.get_by_id = AsyncMock(
            return_value=boot_resource
        )
        boot_resource_sets_service.get_latest_complete_set_for_boot_resource = AsyncMock(
            return_value=resource_set
        )
        boot_resource_files_service.get_files_in_resource_set = AsyncMock(
            return_value=[boot_file]
        )
        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(NotFoundException):
                await service.get_installer_file_for_switch(
                    "00:11:22:33:44:55"
                )

    async def test_create_switch_and_link_interface(
        self,
        service,
        switches_repository,
        interfaces_service,
    ) -> None:
        """Test creating a switch and linking an existing interface.

        This should claim an UNKNOWN interface and convert it to PHYSICAL.
        """
        test_switch = TEST_SWITCH
        # The interface should be updated from UNKNOWN to PHYSICAL
        updated_interface = Interface(
            id=10,
            name="eth0",
            mac_address="00:11:22:33:44:55",
            type=InterfaceType.PHYSICAL,
            switch_id=test_switch.id,
        )

        switches_repository.create.return_value = test_switch
        interfaces_service.link_interface_to_switch.return_value = (
            updated_interface
        )

        builder = SwitchBuilder()
        result = await service.create_switch_and_link_interface(
            builder, interface_id=10
        )

        assert result == test_switch
        switches_repository.create.assert_called_once()
        interfaces_service.link_interface_to_switch.assert_called_once_with(
            interface_id=10, switch_id=test_switch.id
        )

    async def test_pre_delete_hook_with_no_interfaces(
        self,
        service,
        interfaces_service,
        staticipaddress_service,
    ) -> None:
        """Test pre_delete_hook when switch has no interfaces."""
        # No interfaces for this switch
        interfaces_service.get_many.return_value = []

        # Should complete without any IP operations
        await service.pre_delete_hook(TEST_SWITCH)

        interfaces_service.get_many.assert_called_once()
        # No IP operations should be called
        staticipaddress_service.get_ips_for_interfaces_without_other_links.assert_not_called()
        interfaces_service.unlink_interfaces_from_ips.assert_not_called()

    async def test_pre_delete_hook_with_interface_own_ip(
        self,
        service,
        interfaces_service,
        staticipaddress_service,
    ) -> None:
        """Test pre_delete_hook with interface having its own IP (not shared)."""
        # One interface with one IP
        test_interface = Interface(
            id=10,
            name="eth0",
            mac_address="00:11:22:33:44:55",
            type=InterfaceType.PHYSICAL,
            enabled=True,
            created=utcnow(),
            updated=utcnow(),
        )
        test_ip = StaticIPAddress(
            id=100,
            ip="192.168.1.10",
            alloc_type=IpAddressType.AUTO,
            lease_time=0,
        )

        interfaces_service.get_many.return_value = [test_interface]
        staticipaddress_service.get_ips_for_interfaces_without_other_links.return_value = [
            test_ip
        ]

        await service.pre_delete_hook(TEST_SWITCH)

        interfaces_service.get_many.assert_called_once()
        staticipaddress_service.get_ips_for_interfaces_without_other_links.assert_called_once_with(
            [test_interface.id]
        )
        interfaces_service.unlink_interfaces_from_ips.assert_called_once_with(
            interface_ids=[test_interface.id]
        )
        interfaces_service.delete_many_by_id.assert_called_once_with(
            [test_interface.id]
        )
        staticipaddress_service.delete_by_id.assert_called_once_with(
            test_ip.id
        )

    async def test_pre_delete_hook_with_multiple_interfaces_and_ips(
        self,
        service,
        interfaces_service,
        staticipaddress_service,
    ) -> None:
        """Test pre_delete_hook with multiple interfaces and various IP scenarios."""
        # Two interfaces
        interface1 = Interface(
            id=10,
            name="eth0",
            mac_address="00:11:22:33:44:55",
            type=InterfaceType.PHYSICAL,
            enabled=True,
            created=utcnow(),
            updated=utcnow(),
        )
        interface2 = Interface(
            id=20,
            name="eth1",
            mac_address="00:11:22:33:44:66",
            type=InterfaceType.PHYSICAL,
            enabled=True,
            created=utcnow(),
            updated=utcnow(),
        )

        # Three IPs with different sharing patterns
        ip1 = StaticIPAddress(
            id=100,
            ip="192.168.1.10",
            alloc_type=IpAddressType.AUTO,
            lease_time=0,
        )
        ip3 = StaticIPAddress(
            id=300,
            ip="192.168.1.30",
            alloc_type=IpAddressType.AUTO,
            lease_time=0,
        )

        interfaces_service.get_many.return_value = [interface1, interface2]
        # The batch query returns only IPs that would be orphaned
        staticipaddress_service.get_ips_for_interfaces_without_other_links.return_value = [
            ip1,
            ip3,
        ]

        await service.pre_delete_hook(TEST_SWITCH)

        # Verify batch operations were called once
        staticipaddress_service.get_ips_for_interfaces_without_other_links.assert_called_once_with(
            [10, 20]
        )
        interfaces_service.unlink_interfaces_from_ips.assert_called_once_with(
            interface_ids=[10, 20]
        )
        interfaces_service.delete_many_by_id.assert_called_once_with([10, 20])

        # Only orphaned IPs should be deleted
        assert staticipaddress_service.delete_by_id.call_count == 2
        assert staticipaddress_service.delete_by_id.call_args_list == [
            call(100),
            call(300),
        ]

    async def test_list_with_target_image(
        self,
        switches_repository,
        service,
    ) -> None:
        await service.list_with_target_image(12, 5)
        switches_repository.list_with_target_image.assert_called_once_with(
            12, 5
        )

    async def test_get_with_target_image(
        self,
        switches_repository,
        service,
    ) -> None:
        await service.get_one_with_target_image(12)
        switches_repository.get_one_with_target_image.assert_called_once_with(
            12
        )
