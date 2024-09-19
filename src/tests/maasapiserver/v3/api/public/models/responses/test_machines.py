# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.public.models.responses.machines import (
    HardwareDeviceTypeEnum,
    MachineResponse,
    PciDeviceResponse,
    PowerDriverResponse,
    UsbDeviceResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.node import NodeStatus
from maasservicelayer.enums.power_drivers import PowerTypeEnum
from maasservicelayer.models.bmc import Bmc
from maasservicelayer.models.machines import Machine, PciDevice, UsbDevice
from maasservicelayer.utils.date import utcnow


class TestMachineResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        machine = Machine(
            id=1,
            created=now,
            updated=now,
            system_id="y7nwea",
            description="test description",
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
        )

        response = MachineResponse.from_model(
            machine=machine, self_base_hyperlink=f"{V3_API_PREFIX}/machines"
        )
        assert response.id == machine.id
        assert response.system_id == machine.system_id
        assert response.description == machine.description
        assert response.owner == machine.owner
        assert response.cpu_speed_MHz == machine.cpu_speed
        assert response.memory_MiB == machine.memory
        assert response.osystem == machine.osystem
        assert response.architecture == machine.architecture
        assert response.distro_series == machine.distro_series
        assert response.hwe_kernel == machine.hwe_kernel
        assert response.locked == machine.locked
        assert response.cpu_count == machine.cpu_count
        assert response.status == machine.status
        assert response.power_type == machine.power_type
        assert response.fqdn == machine.fqdn
        assert (
            response.hal_links.self.href
            == f"{V3_API_PREFIX}/machines/{machine.id}"
        )


class TestUsbDeviceResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        device = UsbDevice(
            id=1,
            created=now,
            updated=now,
            hardware_type=HardwareDeviceTypeEnum.node,
            vendor_id="0000",
            product_id="0000",
            vendor_name="vendor",
            product_name="product",
            commissioning_driver="driver",
            bus_number=0,
            device_number=0,
        )

        response = UsbDeviceResponse.from_model(
            usb_device=device,
            self_base_hyperlink=f"{V3_API_PREFIX}/machines/y7nwea/usb_devices",
        )

        assert response.id == device.id
        assert response.type == device.hardware_type
        assert response.vendor_id == device.vendor_id
        assert response.product_id == device.product_id
        assert response.vendor_name == device.vendor_name
        assert response.product_name == device.product_name
        assert response.commissioning_driver == device.commissioning_driver
        assert response.bus_number == device.bus_number
        assert response.device_number == device.device_number
        assert (
            response.hal_links.self.href
            == f"{V3_API_PREFIX}/machines/y7nwea/usb_devices/{device.id}"
        )


class TestPciDeviceResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        device = PciDevice(
            id=1,
            created=now,
            updated=now,
            hardware_type=HardwareDeviceTypeEnum.node,
            vendor_id="0000",
            product_id="0000",
            vendor_name="vendor",
            product_name="product",
            commissioning_driver="driver",
            bus_number=0,
            device_number=0,
            pci_address="",
        )

        response = PciDeviceResponse.from_model(
            pci_device=device,
            self_base_hyperlink=f"{V3_API_PREFIX}/machines/y7nwea/pci_devices",
        )

        assert response.id == device.id
        assert response.type == device.hardware_type
        assert response.vendor_id == device.vendor_id
        assert response.product_id == device.product_id
        assert response.vendor_name == device.vendor_name
        assert response.product_name == device.product_name
        assert response.commissioning_driver == device.commissioning_driver
        assert response.bus_number == device.bus_number
        assert response.device_number == device.device_number
        assert response.pci_address == device.pci_address
        assert (
            response.hal_links.self.href
            == f"{V3_API_PREFIX}/machines/y7nwea/pci_devices/{device.id}"
        )


class TestPowerDriverResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        bmc = Bmc(
            id=1,
            created=now,
            updated=now,
            power_type=PowerTypeEnum.IPMI,
            power_parameters={},
        )
        response = PowerDriverResponse.from_model(
            bmc=bmc,
            self_base_hyperlink=f"{V3_API_PREFIX}/machines/y7nwea/power_parameters",
        )
        assert response.power_type == bmc.power_type
        assert response.power_parameters == bmc.power_parameters
        assert (
            response.hal_links.self.href
            == f"{V3_API_PREFIX}/machines/y7nwea/power_parameters"
        )
