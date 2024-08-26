from unittest.mock import AsyncMock, Mock

from httpx import AsyncClient
import pytest

from maasapiserver.common.utils.date import utcnow
from maasapiserver.v3.api.models.requests.query import TokenPaginationParams
from maasapiserver.v3.api.models.responses.machines import (
    HardwareDeviceTypeEnum,
    MachinesListResponse,
    MachineStatusEnum,
    PciDevicesListResponse,
    UsbDevicesListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.machines import Machine, PciDevice, UsbDevice
from maasapiserver.v3.services import ServiceCollectionV3
from maasapiserver.v3.services.machines import MachinesService
from tests.maasapiserver.v3.api.base import ApiCommonTests, Endpoint

TEST_MACHINE = Machine(
    id=1,
    description="test_description",
    created=utcnow(),
    updated=utcnow(),
    system_id="y7nwea",
    owner="admin",
    cpu_speed=1800,
    memory=16384,
    osystem="ubuntu",
    architecture="amd64/generic",
    distro_series="jammy",
    hwe_kernel=None,
    locked=False,
    cpu_count=8,
    status=MachineStatusEnum.new,
    power_type=None,
    fqdn="maas.local",
    hostname="hostname",
)

TEST_MACHINE_2 = Machine(
    id=2,
    description="test_description_2",
    created=utcnow(),
    updated=utcnow(),
    system_id="e8slyu",
    owner="admin",
    cpu_speed=1800,
    memory=16384,
    osystem="ubuntu",
    architecture="amd64/generic",
    distro_series="jammy",
    hwe_kernel=None,
    locked=False,
    cpu_count=8,
    status=MachineStatusEnum.new,
    power_type=None,
    fqdn="maas.local",
    hostname="hostname",
)

TEST_USB_DEVICE = UsbDevice(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    hardware_type=HardwareDeviceTypeEnum.node,
    vendor_id="0000",
    product_id="0000",
    vendor_name="vendor",
    product_name="product",
    commissioning_driver="driver",
    bus_number=0,
    device_number=0,
)
TEST_USB_DEVICE_2 = UsbDevice(
    id=2,
    created=utcnow(),
    updated=utcnow(),
    hardware_type=HardwareDeviceTypeEnum.node,
    vendor_id="0000",
    product_id="0000",
    vendor_name="vendor_2",
    product_name="product_2",
    commissioning_driver="driver_2",
    bus_number=0,
    device_number=0,
)

TEST_PCI_DEVICE = PciDevice(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    hardware_type=HardwareDeviceTypeEnum.node,
    vendor_id="0000",
    product_id="0000",
    vendor_name="vendor",
    product_name="product",
    commissioning_driver="driver",
    bus_number=0,
    device_number=0,
    pci_address="0000:00:00.1",
)
TEST_PCI_DEVICE_2 = PciDevice(
    id=2,
    created=utcnow(),
    updated=utcnow(),
    hardware_type=HardwareDeviceTypeEnum.node,
    vendor_id="0000",
    product_id="0000",
    vendor_name="vendor_2",
    product_name="product_2",
    commissioning_driver="driver_2",
    bus_number=0,
    device_number=0,
    pci_address="0000:00:00.2",
)


class TestMachinesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/machines"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=self.BASE_PATH),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1/usb_devices"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.machines = Mock(MachinesService)
        services_mock.machines.list = AsyncMock(
            return_value=ListResult[Machine](
                items=[TEST_MACHINE_2], next_token=str(TEST_MACHINE.id)
            )
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        machines_response = MachinesListResponse(**response.json())
        assert len(machines_response.items) == 1
        assert (
            machines_response.next
            == f"{self.BASE_PATH}?{TokenPaginationParams.to_href_format(token=str(TEST_MACHINE.id), size='1')}"
        )

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.machines = Mock(MachinesService)
        services_mock.machines.list = AsyncMock(
            return_value=ListResult[Machine](
                items=[TEST_MACHINE_2, TEST_MACHINE], next_token=None
            )
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        machines_response = MachinesListResponse(**response.json())
        assert len(machines_response.items) == 2
        assert machines_response.next is None


class TestUsbDevicesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/machines/1/usb_devices"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=f"{self.BASE_PATH}"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.machines = Mock(MachinesService)
        services_mock.machines.list_machine_usb_devices = AsyncMock(
            return_value=(
                ListResult[UsbDevice](
                    items=[TEST_USB_DEVICE_2],
                    next_token=str(TEST_USB_DEVICE.id),
                )
            )
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        devices_response = UsbDevicesListResponse(**response.json())
        assert len(devices_response.items) == 1
        assert (
            devices_response.next
            == f"{self.BASE_PATH}?{TokenPaginationParams.to_href_format(token=str(TEST_USB_DEVICE.id), size='1')}"
        )

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.machines = Mock(MachinesService)
        services_mock.machines.list_machine_usb_devices = AsyncMock(
            return_value=(
                ListResult[UsbDevice](
                    items=[TEST_USB_DEVICE_2, TEST_USB_DEVICE], next_token=None
                )
            )
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        devices_response = UsbDevicesListResponse(**response.json())
        assert len(devices_response.items) == 2
        assert devices_response.next is None


class TestPciDevicesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/machines/1/pci_devices"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=f"{self.BASE_PATH}"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.machines = Mock(MachinesService)
        services_mock.machines.list_machine_pci_devices = AsyncMock()
        services_mock.machines.list_machine_pci_devices.return_value = (
            ListResult[PciDevice](
                items=[TEST_PCI_DEVICE_2], next_token=str(TEST_PCI_DEVICE.id)
            )
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        devices_response = PciDevicesListResponse(**response.json())
        assert len(devices_response.items) == 1
        assert (
            devices_response.next
            == f"{self.BASE_PATH}?{TokenPaginationParams.to_href_format(token=str(TEST_PCI_DEVICE.id), size='1')}"
        )

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.machines = Mock(MachinesService)
        services_mock.machines.list_machine_pci_devices = AsyncMock()
        services_mock.machines.list_machine_pci_devices.return_value = (
            ListResult[PciDevice](
                items=[TEST_PCI_DEVICE_2, TEST_PCI_DEVICE], next_token=None
            )
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        devices_response = PciDevicesListResponse(**response.json())
        assert len(devices_response.items) == 2
        assert devices_response.next is None
