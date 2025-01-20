#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
from maasapiserver.v3.api.public.models.responses.machines import (
    HardwareDeviceTypeEnum,
    MachinesListResponse,
    PciDevicesListResponse,
    PowerDriverResponse,
    UsbDevicesListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.node import NodeStatus
from maascommon.enums.power import PowerState
from maasservicelayer.auth.macaroons.macaroon_client import RbacAsyncClient
from maasservicelayer.auth.macaroons.models.responses import (
    PermissionResourcesMapping,
)
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.machines import MachineClauseFactory
from maasservicelayer.enums.power_drivers import PowerTypeEnum
from maasservicelayer.enums.rbac import RbacPermission
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.bmc import Bmc
from maasservicelayer.models.machines import Machine, PciDevice, UsbDevice
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.external_auth import ExternalAuthService
from maasservicelayer.services.machines import MachinesService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_MACHINE = Machine(
    id=1,
    description="test_description",
    created=utcnow(),
    updated=utcnow(),
    system_id="y7nwea",
    owner="username",
    cpu_speed=1800,
    memory=16384,
    osystem="ubuntu",
    architecture="amd64/generic",
    distro_series="jammy",
    hwe_kernel=None,
    locked=False,
    cpu_count=8,
    status=NodeStatus.NEW,
    power_type=None,
    fqdn="maas.local",
    hostname="hostname",
    power_state=PowerState.ON,
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
    status=NodeStatus.NEW,
    power_type=None,
    fqdn="maas.local",
    hostname="hostname",
    power_state=PowerState.ON,
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

TEST_BMC = Bmc(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    power_type=PowerTypeEnum.AMT,
    power_parameters={
        "power_address": "10.10.10.10",
        "power_pass": "password",
    },
)


class TestMachinesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/machines"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=self.BASE_PATH),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1/usb_devices"),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1/pci_devices"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="GET", path=f"{self.BASE_PATH}/abcdef/power_parameters"
            ),
        ]

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.machines = Mock(MachinesService)
        services_mock.machines.list.return_value = ListResult[Machine](
            items=[TEST_MACHINE_2], next_token=str(TEST_MACHINE.id)
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
        services_mock.machines.list.return_value = ListResult[Machine](
            items=[TEST_MACHINE_2, TEST_MACHINE], next_token=None
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=2")
        assert response.status_code == 200
        machines_response = MachinesListResponse(**response.json())
        assert len(machines_response.items) == 2
        assert machines_response.next is None

    async def test_list_user_perms(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.machines = Mock(MachinesService)
        services_mock.machines.list.return_value = ListResult[Machine](
            items=[TEST_MACHINE], next_token=None
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=2")
        assert response.status_code == 200
        machines_response = MachinesListResponse(**response.json())
        assert len(machines_response.items) == 1
        assert machines_response.next is None
        services_mock.machines.list.assert_called_once_with(
            token=None,
            size=2,
            query=QuerySpec(
                where=MachineClauseFactory.or_clauses(
                    [
                        MachineClauseFactory.with_owner(None),
                        MachineClauseFactory.with_owner("username"),
                    ]
                )
            ),
        )

    async def test_list_admin_perms(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.machines = Mock(MachinesService)
        services_mock.machines.list.return_value = ListResult[Machine](
            items=[TEST_MACHINE_2], next_token=None
        )
        response = await mocked_api_client_admin.get(
            f"{self.BASE_PATH}?size=2"
        )
        assert response.status_code == 200
        machines_response = MachinesListResponse(**response.json())
        assert len(machines_response.items) == 1
        assert machines_response.next is None
        services_mock.machines.list.assert_called_once_with(
            token=None, size=2, query=QuerySpec(where=None)
        )

    async def test_list_rbac(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_rbac: AsyncClient,
    ) -> None:
        services_mock.external_auth = Mock(ExternalAuthService)

        rbac_client_mock = Mock(RbacAsyncClient)

        rbac_client_mock.get_resource_pool_ids.return_value = [
            PermissionResourcesMapping(
                permission=RbacPermission.VIEW, resources=[0, 1]
            ),
            PermissionResourcesMapping(
                permission=RbacPermission.VIEW_ALL, resources=[0]
            ),
            PermissionResourcesMapping(
                permission=RbacPermission.ADMIN_MACHINES, resources=[]
            ),
        ]
        services_mock.external_auth.get_rbac_client.return_value = (
            rbac_client_mock
        )
        services_mock.machines = Mock(MachinesService)
        services_mock.machines.list.return_value = ListResult[Machine](
            items=[TEST_MACHINE], next_token=None
        )
        response = await mocked_api_client_user_rbac.get(self.BASE_PATH)
        assert response.status_code == 200
        machines_response = MachinesListResponse(**response.json())
        assert len(machines_response.items) == 1
        assert machines_response.next is None
        rbac_client_mock.get_resource_pool_ids.assert_called_once_with(
            user="username",
            permissions={
                RbacPermission.VIEW,
                RbacPermission.VIEW_ALL,
                RbacPermission.ADMIN_MACHINES,
            },
        )
        services_mock.machines.list.assert_called_once_with(
            token=None,
            size=20,
            query=QuerySpec(
                where=MachineClauseFactory.or_clauses(
                    [
                        # view_all pools
                        MachineClauseFactory.with_resource_pool_ids({0}),
                        MachineClauseFactory.and_clauses(
                            [
                                MachineClauseFactory.or_clauses(
                                    [
                                        MachineClauseFactory.with_owner(None),
                                        MachineClauseFactory.with_owner(
                                            "username"
                                        ),
                                        # admin_pools
                                        MachineClauseFactory.with_resource_pool_ids(
                                            None
                                        ),
                                    ]
                                ),
                                # visible_pools
                                MachineClauseFactory.with_resource_pool_ids(
                                    {0, 1}
                                ),
                            ]
                        ),
                    ]
                )
            ),
        )

    async def test_get_machine_power_parameters(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.machines = Mock(MachinesService)
        services_mock.machines.get_bmc.return_value = TEST_BMC
        response = await mocked_api_client_admin.get(
            f"{self.BASE_PATH}/1/power_parameters"
        )
        assert response.status_code == 200
        power_driver_response = PowerDriverResponse(**response.json())
        assert power_driver_response.power_type == TEST_BMC.power_type
        assert (
            power_driver_response.power_parameters == TEST_BMC.power_parameters
        )

    async def test_get_machine_power_parameters_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.machines = Mock(MachinesService)
        services_mock.machines.get_bmc.return_value = None
        response = await mocked_api_client_admin.get(
            f"{self.BASE_PATH}/1/power_parameters"
        )
        assert response.status_code == 404
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404


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
        services_mock.machines.list_machine_usb_devices.return_value = (
            ListResult[UsbDevice](
                items=[TEST_USB_DEVICE_2],
                next_token=str(TEST_USB_DEVICE.id),
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
        services_mock.machines.list_machine_usb_devices.return_value = (
            ListResult[UsbDevice](
                items=[TEST_USB_DEVICE_2, TEST_USB_DEVICE], next_token=None
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
