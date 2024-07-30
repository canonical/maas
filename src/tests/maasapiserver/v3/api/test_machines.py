from httpx import AsyncClient

from maasapiserver.v3.api.models.responses.machines import (
    MachinesListResponse,
    UsbDevicesListResponse,
)
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.machines import Machine, UsbDevice
from tests.fixtures.factories.bmc import create_test_bmc
from tests.fixtures.factories.machines import create_test_machine
from tests.fixtures.factories.node_config import (
    create_test_node_config_entry,
    create_test_numa_node,
    create_test_usb_device,
)
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.api.base import (
    ApiCommonTests,
    EndpointDetails,
    PaginatedEndpointTestConfig,
)


class TestMachinesApi(ApiCommonTests):
    def get_endpoints_configuration(self) -> list[EndpointDetails]:
        def _assert_machine_in_list(
            machine: Machine, machines_response: MachinesListResponse
        ) -> None:
            machine_response = next(
                filter(
                    lambda machine_response: machine.id == machine_response.id,
                    machines_response.items,
                )
            )
            assert machine.id == machine_response.id
            assert (
                machine.to_response(f"{V3_API_PREFIX}/machines")
                == machine_response
            )

        async def create_pagination_test_resources(
            fixture: Fixture, size: int
        ) -> list[Machine]:
            bmc = await create_test_bmc(fixture)
            user = await create_test_user(fixture)
            created_machines = [
                (
                    await create_test_machine(
                        fixture, description=str(i), bmc=bmc, user=user
                    )
                )
                for i in range(size)
            ]
            return created_machines

        return [
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/machines",
                user_role=UserRole.USER,
                pagination_config=PaginatedEndpointTestConfig[
                    MachinesListResponse
                ](
                    response_type=MachinesListResponse,
                    create_resources_routine=create_pagination_test_resources,
                    assert_routine=_assert_machine_in_list,
                ),
            ),
        ]

    # GET /machines/{system_id}/usb_devices
    async def test_list_machine_usb_devices(
        self, authenticated_user_api_client_v3: AsyncClient, fixture: Fixture
    ) -> None:
        def _assert_device_in_list(
            device: UsbDevice, devices_response: UsbDevicesListResponse
        ) -> None:
            device_response = next(
                r for r in devices_response.items if r.id == device.id
            )
            assert device_response.id == device.id
            assert device_response.type == device.hardware_type
            assert device_response.vendor_id == device.vendor_id
            assert device_response.product_id == device.product_id
            assert device_response.vendor_name == device.vendor_name
            assert device_response.product_name == device.product_name
            assert (
                device_response.commissioning_driver
                == device.commissioning_driver
            )
            assert device_response.bus_number == device.bus_number
            assert device_response.device_number == device.device_number

        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)
        machine = (
            await create_test_machine(fixture, bmc=bmc, user=user)
        ).dict()
        config = await create_test_node_config_entry(fixture, node=machine)
        numa_node = await create_test_numa_node(fixture, node=machine)
        devices = [
            (
                await create_test_usb_device(
                    fixture,
                    numa_node=numa_node,
                    config=config,
                    vendor_name=str(i),
                )
            )
            for i in range(3)
        ]

        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/machines/{machine['system_id']}/usb_devices?size=2"
        )
        assert response.status_code == 200
        typed_response = UsbDevicesListResponse(**response.json())
        assert typed_response.kind == "MachineHardwareDevicesList"
        assert typed_response.next is not None
        assert len(typed_response.items) == 2
        _assert_device_in_list(devices.pop(), typed_response)
        _assert_device_in_list(devices.pop(), typed_response)

        response = await authenticated_user_api_client_v3.get(
            typed_response.next
        )
        typed_response = UsbDevicesListResponse(**response.json())
        assert typed_response.kind == "MachineHardwareDevicesList"
        assert typed_response.next is None
        assert len(typed_response.items) == 1
        _assert_device_in_list(devices.pop(), typed_response)
