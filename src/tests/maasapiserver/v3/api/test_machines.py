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

        async def create_machine_pagination_test_resources(
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

        async def create_machine(fixture: Fixture) -> Machine:
            bmc = await create_test_bmc(fixture)
            user = await create_test_user(fixture)
            machine = await create_test_machine(fixture, bmc=bmc, user=user)
            return machine

        async def create_usb_devices_pagination_test_resources(
            fixture: Fixture, size: int, machine: Machine
        ) -> list[UsbDevice]:
            config = await create_test_node_config_entry(
                fixture, node=machine.dict()
            )
            numa_node = await create_test_numa_node(
                fixture, node=machine.dict()
            )
            devices = [
                (
                    await create_test_usb_device(
                        fixture,
                        numa_node=numa_node,
                        config=config,
                        vendor_name=str(i),
                    )
                )
                for i in range(size)
            ]
            return devices

        return [
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/machines",
                user_role=UserRole.USER,
                pagination_config=PaginatedEndpointTestConfig[
                    Machine, MachinesListResponse
                ](
                    response_type=MachinesListResponse,
                    create_resources_routine=create_machine_pagination_test_resources,
                ),
            ),
            EndpointDetails(
                method="GET",
                path=V3_API_PREFIX + "/machines/{0.system_id}/usb_devices",
                user_role=UserRole.USER,
                objects_factories=[create_machine],
                pagination_config=PaginatedEndpointTestConfig[
                    UsbDevice, UsbDevicesListResponse
                ](
                    response_type=UsbDevicesListResponse,
                    create_resources_routine=create_usb_devices_pagination_test_resources,
                ),
            ),
        ]
