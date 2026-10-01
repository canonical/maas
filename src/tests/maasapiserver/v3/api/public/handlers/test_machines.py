# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Callable
from unittest.mock import AsyncMock, Mock

from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.machines import (
    MachineCommissionRequest,
)
from maasapiserver.v3.api.public.models.responses.machines import (
    HardwareDeviceTypeEnum,
    MachinesListResponse,
    PciDevicesListResponse,
    PowerDriverResponse,
    UsbDevicesListResponse,
)
from maasapiserver.v3.api.public.models.responses.operations import (
    OperationResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.node import NodeStatus, NodeTypeEnum
from maascommon.enums.operations import (
    OperationResourceType,
    OperationStatus,
    OperationType,
)
from maascommon.enums.power import PowerState
from maascommon.openfga.async_client import OpenFGAClient
from maascommon.openfga.base import MAASResourceEntitlement
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.machines import MachineClauseFactory
from maasservicelayer.enums.power_drivers import PowerTypeEnum
from maasservicelayer.exceptions.constants import (
    INVALID_MACHINE_STATUS_VIOLATION_TYPE,
    MACHINE_LOCKED_VIOLATION_TYPE,
    MISSING_PERMISSIONS_VIOLATION_TYPE,
    OPERATION_IN_PROGRESS_VIOLATION_TYPE,
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.bmc import Bmc
from maasservicelayer.models.machines import Machine, PciDevice, UsbDevice
from maasservicelayer.models.operations import Operation
from maasservicelayer.services import OpenFGATupleService, ServiceCollectionV3
from maasservicelayer.services.machines import MachinesService
from maasservicelayer.services.operations import OperationsService
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
    node_type=NodeTypeEnum.MACHINE,
    power_type=None,
    fqdn="maas.local",
    hostname="hostname",
    power_state=PowerState.ON,
)

TEST_COMMISSION_OPERATION = Operation(
    id=1,
    uuid="commission-uuid",
    op_type=OperationType.MACHINE_COMMISSION,
    resource_id=TEST_MACHINE.id,
    resource_type=OperationResourceType.MACHINE,
    status=OperationStatus.ACCEPTED,
    is_bulk=False,
    created=utcnow(),
    updated=utcnow(),
    user_id=0,
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
    node_type=NodeTypeEnum.MACHINE,
    power_type=None,
    fqdn="maas.local",
    hostname="hostname",
    power_state=PowerState.ON,
)

TEST_USB_DEVICE = UsbDevice(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    hardware_type=HardwareDeviceTypeEnum.NODE,
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
    hardware_type=HardwareDeviceTypeEnum.NODE,
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
    hardware_type=HardwareDeviceTypeEnum.NODE,
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
    hardware_type=HardwareDeviceTypeEnum.NODE,
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
    def endpoints_with_authorization(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="GET",
                path=f"{self.BASE_PATH}/1/usb_devices",
                permission=MAASResourceEntitlement.CAN_VIEW_MACHINES,
            ),
            Endpoint(
                method="GET",
                path=f"{self.BASE_PATH}/1/pci_devices",
                permission=MAASResourceEntitlement.CAN_VIEW_MACHINES,
            ),
            Endpoint(
                method="GET",
                path=f"{self.BASE_PATH}/abcdef/power_parameters",
                permission=MAASResourceEntitlement.CAN_EDIT_MACHINES,
            ),
        ]

    @pytest.fixture
    def endpoints_with_authentication_only(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="GET",
                path=self.BASE_PATH,
            ),
            Endpoint(
                method="POST",
                path=f"{self.BASE_PATH}/abcdef:commission",
            ),
        ]

    async def test_list_other_page(
        self, services_mock: ServiceCollectionV3, mocked_api_client_user
    ) -> None:
        openfga_client_mock = AsyncMock(OpenFGAClient)
        openfga_client_mock.list_pools_with_view_machines_access.return_value = []
        openfga_client_mock.list_pools_with_view_available_machines_access.return_value = [
            TEST_MACHINE_2.id,
        ]

        services_mock.openfga_tuples = Mock(OpenFGATupleService)
        services_mock.openfga_tuples.get_client.return_value = (
            openfga_client_mock
        )

        services_mock.machines = Mock(MachinesService)
        services_mock.machines.list.return_value = ListResult[Machine](
            items=[TEST_MACHINE_2], total=2
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        machines_response = MachinesListResponse(**response.json())
        assert len(machines_response.items) == 1
        assert machines_response.total == 2
        assert machines_response.next == f"{self.BASE_PATH}?page=2&size=1"

    async def test_list_no_other_page(
        self, services_mock: ServiceCollectionV3, mocked_api_client_user
    ) -> None:
        openfga_client_mock = AsyncMock(OpenFGAClient)
        openfga_client_mock.list_pools_with_view_machines_access.return_value = []
        openfga_client_mock.list_pools_with_view_available_machines_access.return_value = [
            TEST_MACHINE_2.id,
            TEST_MACHINE.id,
        ]

        services_mock.openfga_tuples = Mock(OpenFGATupleService)
        services_mock.openfga_tuples.get_client.return_value = (
            openfga_client_mock
        )

        services_mock.machines = Mock(MachinesService)
        services_mock.machines.list.return_value = ListResult[Machine](
            items=[TEST_MACHINE_2, TEST_MACHINE], total=2
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=2")
        assert response.status_code == 200
        machines_response = MachinesListResponse(**response.json())
        assert len(machines_response.items) == 2
        assert machines_response.total == 2
        assert machines_response.next is None

    async def test_list_user_perms(
        self, services_mock: ServiceCollectionV3, mocked_api_client_user
    ) -> None:
        openfga_client_mock = AsyncMock(OpenFGAClient)
        openfga_client_mock.list_pools_with_view_machines_access.return_value = [
            100
        ]
        openfga_client_mock.list_pools_with_view_available_machines_access.return_value = [
            TEST_MACHINE.id
        ]

        services_mock.openfga_tuples = Mock(OpenFGATupleService)
        services_mock.openfga_tuples.get_client.return_value = (
            openfga_client_mock
        )

        services_mock.machines = Mock(MachinesService)
        services_mock.machines.list.return_value = ListResult[Machine](
            items=[TEST_MACHINE], total=1
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=2")
        assert response.status_code == 200
        machines_response = MachinesListResponse(**response.json())
        assert len(machines_response.items) == 1
        assert machines_response.total == 1
        assert machines_response.next is None
        services_mock.machines.list.assert_called_once_with(
            page=1,
            size=2,
            query=QuerySpec(
                where=MachineClauseFactory.or_clauses(
                    [
                        MachineClauseFactory.with_resource_pool_ids({100}),
                        MachineClauseFactory.and_clauses(
                            [
                                MachineClauseFactory.or_clauses(
                                    [
                                        MachineClauseFactory.with_owner(None),
                                        MachineClauseFactory.with_owner(
                                            "username"
                                        ),
                                    ]
                                ),
                                MachineClauseFactory.with_resource_pool_ids(
                                    {TEST_MACHINE.id}
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
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_MACHINES,
        )
        services_mock.machines = Mock(MachinesService)
        services_mock.machines.get_bmc.return_value = TEST_BMC
        response = await client.get(f"{self.BASE_PATH}/1/power_parameters")
        assert response.status_code == 200
        power_driver_response = PowerDriverResponse(**response.json())
        assert power_driver_response.power_type == TEST_BMC.power_type
        assert (
            power_driver_response.power_parameters == TEST_BMC.power_parameters
        )

    async def test_get_machine_power_parameters_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_MACHINES,
        )
        services_mock.machines = Mock(MachinesService)
        services_mock.machines.get_bmc.return_value = None
        response = await client.get(f"{self.BASE_PATH}/1/power_parameters")
        assert response.status_code == 404
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_commission_machine_requires_authentication(
        self, mocked_api_client: AsyncClient
    ) -> None:
        response = await mocked_api_client.post(
            f"{self.BASE_PATH}/abcdef:commission"
        )
        assert response.status_code == 401

    def _mock_commission_services(
        self,
        services_mock: ServiceCollectionV3,
        machine: Machine,
        can_edit: bool = True,
    ) -> AsyncMock:
        """Create an openfga client mock and set up the necessary service mocks."""
        openfga_client_mock = AsyncMock(OpenFGAClient)
        # OpenFGA itself deals with determining if a user has global or pool-specific permissions.
        # Here we just mock the response.
        openfga_client_mock.can_edit_machines.return_value = can_edit
        openfga_client_mock.can_edit_machines_in_pool.return_value = can_edit
        services_mock.openfga_tuples = Mock(OpenFGATupleService)
        services_mock.openfga_tuples.get_client.return_value = (
            openfga_client_mock
        )
        services_mock.machines = Mock(MachinesService)
        services_mock.machines.get_one.return_value = machine
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.has_active_operation_for_resource.return_value = False
        services_mock.operations.create_accepted_operation.return_value = (
            TEST_COMMISSION_OPERATION
        )
        return openfga_client_mock

    async def test_commission_machine_without_body_uses_defaults(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        self._mock_commission_services(services_mock, TEST_MACHINE)

        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}/{TEST_MACHINE.system_id}:commission"
        )

        assert response.status_code == 202
        parameters = services_mock.operations.create_accepted_operation.call_args.kwargs[
            "parameters"
        ]
        assert parameters == {
            "system_id": TEST_MACHINE.system_id,
            **MachineCommissionRequest().model_dump(),
        }

    async def test_commission_machine_in_pool(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        machine = TEST_MACHINE.model_copy(update={"pool_id": 5})
        openfga_client_mock = self._mock_commission_services(
            services_mock, machine
        )

        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}/{machine.system_id}:commission"
        )

        assert response.status_code == 202
        operation_response = OperationResponse(**response.json())
        assert operation_response.uuid == TEST_COMMISSION_OPERATION.uuid
        openfga_client_mock.can_edit_machines_in_pool.assert_awaited_once_with(
            0, 5
        )
        openfga_client_mock.can_edit_machines.assert_not_awaited()

    async def test_commission_machine_without_pool_uses_global_permission(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        openfga_client_mock = self._mock_commission_services(
            services_mock, TEST_MACHINE
        )

        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}/{TEST_MACHINE.system_id}:commission"
        )

        assert response.status_code == 202
        openfga_client_mock.can_edit_machines.assert_awaited_once_with(0)
        openfga_client_mock.can_edit_machines_in_pool.assert_not_awaited()

    async def test_commission_machine_403_without_edit_permission(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        machine = TEST_MACHINE.model_copy(update={"pool_id": 5})
        self._mock_commission_services(services_mock, machine, can_edit=False)

        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}/{machine.system_id}:commission"
        )

        assert response.status_code == 403
        error_response = ErrorBodyResponse(**response.json())
        assert (
            error_response.details[0].type
            == MISSING_PERMISSIONS_VIOLATION_TYPE
        )
        services_mock.operations.create_accepted_operation.assert_not_awaited()

    async def test_commission_machine_409_locked(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        machine = TEST_MACHINE.model_copy(update={"locked": True})
        self._mock_commission_services(services_mock, machine)

        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}/{machine.system_id}:commission"
        )

        assert response.status_code == 409
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.details[0].type == MACHINE_LOCKED_VIOLATION_TYPE
        services_mock.operations.create_accepted_operation.assert_not_awaited()

    async def test_commission_machine_404_unknown_machine(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        self._mock_commission_services(services_mock, TEST_MACHINE)
        services_mock.machines.get_one.return_value = None

        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}/unknown:commission"
        )

        assert response.status_code == 404
        error_response = ErrorBodyResponse(**response.json())
        assert (
            error_response.details[0].type
            == UNEXISTING_RESOURCE_VIOLATION_TYPE
        )
        services_mock.operations.create_accepted_operation.assert_not_awaited()

    @pytest.mark.parametrize(
        "status",
        [
            NodeStatus.COMMISSIONING,
            NodeStatus.ALLOCATED,
            NodeStatus.DEPLOYED,
        ],
    )
    async def test_commission_machine_409_status_not_commissionable(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
        status: NodeStatus,
    ) -> None:
        machine = TEST_MACHINE.model_copy(update={"status": status})
        self._mock_commission_services(services_mock, machine)

        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}/{machine.system_id}:commission"
        )

        assert response.status_code == 409
        error_response = ErrorBodyResponse(**response.json())
        assert (
            error_response.details[0].type
            == INVALID_MACHINE_STATUS_VIOLATION_TYPE
        )
        services_mock.operations.create_accepted_operation.assert_not_awaited()

    async def test_commission_machine_409_active_operation(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        self._mock_commission_services(services_mock, TEST_MACHINE)
        services_mock.operations.has_active_operation_for_resource.return_value = True

        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}/{TEST_MACHINE.system_id}:commission"
        )

        assert response.status_code == 409
        error_response = ErrorBodyResponse(**response.json())
        assert (
            error_response.details[0].type
            == OPERATION_IN_PROGRESS_VIOLATION_TYPE
        )
        services_mock.operations.has_active_operation_for_resource.assert_awaited_once_with(
            resource_type=OperationResourceType.MACHINE,
            resource_id=TEST_MACHINE.id,
        )
        services_mock.operations.create_accepted_operation.assert_not_awaited()


class TestUsbDevicesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/machines/1/usb_devices"

    @pytest.fixture
    def endpoints_with_authorization(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="GET",
                path=f"{self.BASE_PATH}",
                permission=MAASResourceEntitlement.CAN_VIEW_MACHINES,
            ),
        ]

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_MACHINES,
        )
        services_mock.machines = Mock(MachinesService)
        services_mock.machines.list_machine_usb_devices.return_value = (
            ListResult[UsbDevice](
                items=[TEST_USB_DEVICE_2],
                total=2,
            )
        )
        response = await client.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        devices_response = UsbDevicesListResponse(**response.json())
        assert len(devices_response.items) == 1
        assert devices_response.total == 2
        assert devices_response.next == f"{self.BASE_PATH}?page=2&size=1"

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_MACHINES,
        )
        services_mock.machines = Mock(MachinesService)
        services_mock.machines.list_machine_usb_devices.return_value = (
            ListResult[UsbDevice](
                items=[TEST_USB_DEVICE_2, TEST_USB_DEVICE], total=2
            )
        )
        response = await client.get(f"{self.BASE_PATH}?size=2")
        assert response.status_code == 200
        devices_response = UsbDevicesListResponse(**response.json())
        assert len(devices_response.items) == 2
        assert devices_response.total == 2
        assert devices_response.next is None


class TestPciDevicesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/machines/1/pci_devices"

    @pytest.fixture
    def endpoints_with_authorization(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="GET",
                path=f"{self.BASE_PATH}",
                permission=MAASResourceEntitlement.CAN_VIEW_MACHINES,
            ),
        ]

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_MACHINES,
        )
        services_mock.machines = Mock(MachinesService)
        services_mock.machines.list_machine_pci_devices.return_value = (
            ListResult[PciDevice](items=[TEST_PCI_DEVICE_2], total=2)
        )
        response = await client.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        devices_response = PciDevicesListResponse(**response.json())
        assert len(devices_response.items) == 1
        assert devices_response.total == 2
        assert devices_response.next == f"{self.BASE_PATH}?page=2&size=1"

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_MACHINES,
        )
        services_mock.machines = Mock(MachinesService)
        services_mock.machines.list_machine_pci_devices.return_value = (
            ListResult[PciDevice](
                items=[TEST_PCI_DEVICE_2, TEST_PCI_DEVICE], total=2
            )
        )
        response = await client.get(f"{self.BASE_PATH}?size=2")
        assert response.status_code == 200
        devices_response = PciDevicesListResponse(**response.json())
        assert len(devices_response.items) == 2
        assert devices_response.total == 2
        assert devices_response.next is None
