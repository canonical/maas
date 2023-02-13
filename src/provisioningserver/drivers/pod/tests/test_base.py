# Copyright 2016-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.pod`."""

import random
from unittest.mock import sentinel

from jsonschema import validate

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers import make_setting_field
from provisioningserver.drivers.pod import (
    DiscoveredMachine,
    DiscoveredMachineBlockDevice,
    DiscoveredMachineInterface,
    DiscoveredPod,
    DiscoveredPodHints,
    get_error_message,
    InterfaceAttachType,
    JSON_POD_DRIVER_SCHEMA,
    KnownHostInterface,
    PodActionError,
    PodAuthError,
    PodConnError,
    PodDriverBase,
    PodError,
    RequestedMachine,
    RequestedMachineBlockDevice,
    RequestedMachineInterface,
)


class TestDiscoveredClasses(MAASTestCase):
    def test_interface_mac(self):
        mac = factory.make_mac_address()
        nic = DiscoveredMachineInterface(mac_address=mac)
        self.assertEqual(mac, nic.mac_address)
        self.assertEqual(-1, nic.vid)
        self.assertEqual([], nic.tags)

    def test_interface_mac_vid(self):
        mac = factory.make_mac_address()
        vid = random.randint(1, 300)
        nic = DiscoveredMachineInterface(mac_address=mac, vid=vid)
        self.assertEqual(mac, nic.mac_address)
        self.assertEqual(vid, nic.vid)
        self.assertEqual([], nic.tags)

    def test_interface_mac_vid_tags(self):
        mac = factory.make_mac_address()
        vid = random.randint(1, 300)
        tags = [factory.make_name("tag") for _ in range(3)]
        nic = DiscoveredMachineInterface(mac_address=mac, vid=vid, tags=tags)
        self.assertEqual(mac, nic.mac_address)
        self.assertEqual(vid, nic.vid)
        self.assertEqual(tags, nic.tags)

    def test_block_device_size(self):
        size = random.randint(512, 512 * 1024)
        device = DiscoveredMachineBlockDevice(
            model=None, serial=None, size=size
        )
        self.assertIsNone(device.model)
        self.assertIsNone(device.serial)
        self.assertEqual(size, device.size)
        self.assertIsNone(device.id_path)

    def test_block_device_size_id_path(self):
        size = random.randint(512, 512 * 1024)
        id_path = factory.make_name("id_path")
        device = DiscoveredMachineBlockDevice(
            model=None, serial=None, size=size, id_path=id_path
        )
        self.assertIsNone(device.model)
        self.assertIsNone(device.serial)
        self.assertEqual(size, device.size)
        self.assertEqual(id_path, device.id_path)

    def test_block_device_model_serial_size_block_size(self):
        model = factory.make_name("model")
        serial = factory.make_name("serial")
        size = random.randint(512, 512 * 1024)
        block_size = random.randint(512, 4096)
        device = DiscoveredMachineBlockDevice(
            model=model, serial=serial, size=size, block_size=block_size
        )
        self.assertEqual(model, device.model)
        self.assertEqual(serial, device.serial)
        self.assertEqual(size, device.size)
        self.assertEqual(block_size, device.block_size)

    def test_block_device_model_serial_size_block_size_tags(self):
        model = factory.make_name("model")
        serial = factory.make_name("serial")
        size = random.randint(512, 512 * 1024)
        block_size = random.randint(512, 4096)
        tags = [factory.make_name("tag") for _ in range(3)]
        device = DiscoveredMachineBlockDevice(
            model=model,
            serial=serial,
            size=size,
            block_size=block_size,
            tags=tags,
        )
        self.assertEqual(model, device.model)
        self.assertEqual(serial, device.serial)
        self.assertEqual(size, device.size)
        self.assertEqual(block_size, device.block_size)
        self.assertEqual(tags, device.tags)

    def test_machine(self):
        hostname = factory.make_name("hostname")
        cores = random.randint(1, 8)
        cpu_speed = random.randint(1000, 2000)
        memory = random.randint(4096, 8192)
        power_state = factory.make_name("unknown")
        interfaces = [
            DiscoveredMachineInterface(mac_address=factory.make_mac_address())
            for _ in range(3)
        ]
        block_devices = [
            DiscoveredMachineBlockDevice(
                model=factory.make_name("model"),
                serial=factory.make_name("serial"),
                size=random.randint(512, 1024),
            )
            for _ in range(3)
        ]
        tags = [factory.make_name("tag") for _ in range(3)]
        machine = DiscoveredMachine(
            hostname=hostname,
            architecture="amd64/generic",
            cores=cores,
            cpu_speed=cpu_speed,
            memory=memory,
            power_state=power_state,
            interfaces=interfaces,
            block_devices=block_devices,
            tags=tags,
        )
        self.assertEqual(cores, machine.cores)
        self.assertEqual(cpu_speed, machine.cpu_speed)
        self.assertEqual(memory, machine.memory)
        self.assertEqual(interfaces, machine.interfaces)
        self.assertEqual(block_devices, machine.block_devices)
        self.assertEqual(tags, machine.tags)

    def test_pod_hints(self):
        cores = random.randint(1, 8)
        cpu_speed = random.randint(1000, 2000)
        memory = random.randint(4096, 8192)
        local_storage = random.randint(4096, 8192)
        hints = DiscoveredPodHints(
            cores=cores,
            cpu_speed=cpu_speed,
            memory=memory,
            local_storage=local_storage,
        )
        self.assertEqual(cores, hints.cores)
        self.assertEqual(cpu_speed, hints.cpu_speed)
        self.assertEqual(memory, hints.memory)
        self.assertEqual(local_storage, hints.local_storage)

    def test_pod(self):
        hostname = factory.make_name("hostname")
        version = factory.make_name("version")
        cores = random.randint(1, 8)
        cpu_speed = random.randint(1000, 2000)
        memory = random.randint(4096, 8192)
        local_storage = random.randint(4096, 8192)
        hints = DiscoveredPodHints(
            cores=random.randint(1, 8),
            cpu_speed=random.randint(1000, 2000),
            memory=random.randint(4096, 8192),
            local_storage=random.randint(4096, 8192),
        )
        machines = []
        for _ in range(3):
            cores = random.randint(1, 8)
            cpu_speed = random.randint(1000, 2000)
            memory = random.randint(4096, 8192)
            power_state = factory.make_name("unknown")
            power_parameters = {"power_id": factory.make_name("power_id")}
            interfaces = [
                DiscoveredMachineInterface(
                    mac_address=factory.make_mac_address()
                )
                for _ in range(3)
            ]
            block_devices = [
                DiscoveredMachineBlockDevice(
                    model=factory.make_name("model"),
                    serial=factory.make_name("serial"),
                    size=random.randint(512, 1024),
                )
                for _ in range(3)
            ]
            tags = [factory.make_name("tag") for _ in range(3)]
            machines.append(
                DiscoveredMachine(
                    hostname=hostname,
                    architecture="amd64/generic",
                    cores=cores,
                    cpu_speed=cpu_speed,
                    memory=memory,
                    power_state=power_state,
                    power_parameters=power_parameters,
                    interfaces=interfaces,
                    block_devices=block_devices,
                    tags=tags,
                )
            )
        pod = DiscoveredPod(
            architectures=["amd64/generic"],
            cores=cores,
            version=version,
            cpu_speed=cpu_speed,
            memory=memory,
            local_storage=local_storage,
            hints=hints,
            machines=machines,
        )
        self.assertEqual(version, pod.version)
        self.assertEqual(cores, pod.cores)
        self.assertEqual(cpu_speed, pod.cpu_speed)
        self.assertEqual(memory, pod.memory)
        self.assertEqual(local_storage, pod.local_storage)
        self.assertEqual(machines, pod.machines)


class TestRequestClasses(MAASTestCase):
    def test_block_device_size(self):
        size = random.randint(512, 512 * 1024)
        tags = [factory.make_name("tag") for _ in range(3)]
        device = RequestedMachineBlockDevice(size=size, tags=tags)
        self.assertEqual(size, device.size)
        self.assertEqual(tags, device.tags)

    def test_machine(self):
        hostname = factory.make_name("hostname")
        cores = random.randint(1, 8)
        cpu_speed = random.randint(1000, 2000)
        memory = random.randint(4096, 8192)
        interfaces = [RequestedMachineInterface() for _ in range(3)]
        block_devices = [
            RequestedMachineBlockDevice(
                size=random.randint(512, 1024),
                tags=[factory.make_name("tag") for _ in range(3)],
            )
            for _ in range(3)
        ]
        machine = RequestedMachine(
            hostname=hostname,
            architecture="amd64/generic",
            cores=cores,
            cpu_speed=cpu_speed,
            memory=memory,
            interfaces=interfaces,
            block_devices=block_devices,
        )
        self.assertEqual(hostname, machine.hostname)
        self.assertEqual(cores, machine.cores)
        self.assertEqual(cpu_speed, machine.cpu_speed)
        self.assertEqual(memory, machine.memory)
        self.assertEqual(interfaces, machine.interfaces)
        self.assertEqual(block_devices, machine.block_devices)

    def test_machine_without_cpu_speed(self):
        hostname = factory.make_name("hostname")
        cores = random.randint(1, 8)
        memory = random.randint(4096, 8192)
        interfaces = [RequestedMachineInterface() for _ in range(3)]
        block_devices = [
            RequestedMachineBlockDevice(size=random.randint(512, 1024))
            for _ in range(3)
        ]
        machine = RequestedMachine(
            hostname=hostname,
            architecture="amd64/generic",
            cores=cores,
            cpu_speed=None,
            memory=memory,
            interfaces=interfaces,
            block_devices=block_devices,
        )
        self.assertEqual(hostname, machine.hostname)
        self.assertEqual(cores, machine.cores)
        self.assertIsNone(machine.cpu_speed)
        self.assertEqual(memory, machine.memory)
        self.assertEqual(interfaces, machine.interfaces)
        self.assertEqual(block_devices, machine.block_devices)


class FakePodDriverBase(PodDriverBase):
    name = ""
    chassis = True
    can_probe = True
    can_set_boot_order = True
    description = ""
    settings = []
    ip_extractor = None
    queryable = True

    def __init__(self, name, description, settings):
        self.name = name
        self.description = description
        self.settings = settings
        super().__init__()

    def discover(self, context, pod_id=None):
        raise NotImplementedError

    def compose(self, pod_id, context, request):
        raise NotImplementedError

    def decompose(self, pod_id, context):
        raise NotImplementedError

    def query(self, system_id, context):
        raise NotImplementedError

    def on(self, system_id, context):
        raise NotImplementedError

    def off(self, system_id, context):
        raise NotImplementedError

    def cycle(self, system_id, context):
        raise NotImplementedError

    def detect_missing_packages(self):
        return []


def make_pod_driver_base(name=None, description=None, settings=None):
    if name is None:
        name = factory.make_name("pod")
    if description is None:
        description = factory.make_name("description")
    if settings is None:
        settings = []
    return FakePodDriverBase(name, description, settings)


class TestFakePodDriverBase(MAASTestCase):
    def test_attributes(self):
        fake_name = factory.make_name("name")
        fake_description = factory.make_name("description")
        fake_setting = factory.make_name("setting")
        fake_settings = [
            make_setting_field(fake_setting, fake_setting.title())
        ]
        attributes = {
            "name": fake_name,
            "description": fake_description,
            "settings": fake_settings,
        }
        fake_driver = FakePodDriverBase(
            fake_name, fake_description, fake_settings
        )
        self.assertAttributes(fake_driver, attributes)

    def test_make_pod_driver_base(self):
        fake_name = factory.make_name("name")
        fake_description = factory.make_name("description")
        fake_setting = factory.make_name("setting")
        fake_settings = [
            make_setting_field(fake_setting, fake_setting.title())
        ]
        attributes = {
            "name": fake_name,
            "description": fake_description,
            "settings": fake_settings,
        }
        fake_driver = make_pod_driver_base(
            name=fake_name,
            description=fake_description,
            settings=fake_settings,
        )
        self.assertAttributes(fake_driver, attributes)

    def test_make_pod_driver_base_makes_name_and_description(self):
        fake_driver = make_pod_driver_base()
        self.assertNotEqual("", fake_driver.name)
        self.assertNotEqual("", fake_driver.description)

    def test_discover_raises_not_implemented(self):
        fake_driver = make_pod_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.discover,
            sentinel.system_id,
            sentinel.context,
        )

    def test_compose_raises_not_implemented(self):
        fake_driver = make_pod_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.compose,
            sentinel.system_id,
            sentinel.context,
            sentinel.request,
        )

    def test_decompose_raises_not_implemented(self):
        fake_driver = make_pod_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.decompose,
            sentinel.system_id,
            sentinel.context,
        )

    def test_set_boot_order(self):
        fake_driver = make_pod_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.set_boot_order,
            sentinel.system_id,
            sentinel.context,
            sentinel.order,
        )


class TestPodDriverBase(MAASTestCase):
    def test_get_commissioning_data(self):
        fake_driver = make_pod_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.get_commissioning_data,
            random.randint(1, 100),
            {},
        )

    def test_get_schema(self):
        fake_name = factory.make_name("name")
        fake_description = factory.make_name("description")
        fake_setting = factory.make_name("setting")
        fake_settings = [
            make_setting_field(fake_setting, fake_setting.title())
        ]
        fake_driver = make_pod_driver_base(
            fake_name, fake_description, fake_settings
        )
        self.assertEqual(
            {
                "driver_type": "pod",
                "name": fake_name,
                "description": fake_description,
                "fields": fake_settings,
                "queryable": fake_driver.queryable,
                "missing_packages": [],
                "chassis": True,
                "can_probe": True,
            },
            fake_driver.get_schema(),
        )

    def test_get_schema_returns_valid_schema(self):
        fake_driver = make_pod_driver_base()
        # doesn't raise ValidationError
        validate(fake_driver.get_schema(), JSON_POD_DRIVER_SCHEMA)

    def test_get_default_interface_parent_only_dhcp_enabled(self):
        if1 = KnownHostInterface(
            ifname="eth0",
            attach_type=InterfaceAttachType.MACVLAN,
            attach_name="eth0",
            dhcp_enabled=False,
        )
        if2 = KnownHostInterface(
            ifname="br0",
            attach_type=InterfaceAttachType.BRIDGE,
            attach_name="br0",
            dhcp_enabled=False,
        )
        if3 = KnownHostInterface(
            ifname="eth1",
            attach_type=InterfaceAttachType.MACVLAN,
            attach_name="eth1",
            dhcp_enabled=True,
        )
        driver = make_pod_driver_base()
        self.assertEqual(
            driver.get_default_interface_parent([if1, if2, if3]), if3
        )

    def test_get_default_interface_parent_none(self):
        if1 = KnownHostInterface(
            ifname="eth0",
            attach_type=InterfaceAttachType.MACVLAN,
            attach_name="eth0",
            dhcp_enabled=False,
        )
        if2 = KnownHostInterface(
            ifname="br0",
            attach_type=InterfaceAttachType.BRIDGE,
            attach_name="br0",
            dhcp_enabled=False,
        )
        driver = make_pod_driver_base()
        self.assertIsNone(driver.get_default_interface_parent([if1, if2]))

    def test_get_default_interface_parent_order(self):
        def make_interface(attach_type):
            name = factory.make_name()
            return KnownHostInterface(
                ifname=name,
                attach_type=attach_type,
                attach_name=name,
                dhcp_enabled=True,
            )

        if1 = make_interface(InterfaceAttachType.MACVLAN)
        if2 = make_interface(InterfaceAttachType.NETWORK)
        if3 = make_interface(InterfaceAttachType.SRIOV)
        if4 = make_interface(InterfaceAttachType.BRIDGE)
        driver = make_pod_driver_base()
        self.assertEqual(
            driver.get_default_interface_parent([if1, if2, if3, if4]), if4
        )
        self.assertEqual(
            driver.get_default_interface_parent([if1, if2, if3]), if3
        )
        self.assertEqual(driver.get_default_interface_parent([if1, if2]), if2)


class TestGetErrorMessage(MAASTestCase):
    scenarios = [
        (
            "auth",
            dict(
                exception=PodAuthError("auth"),
                message="Could not authenticate to pod: auth",
            ),
        ),
        (
            "conn",
            dict(
                exception=PodConnError("conn"),
                message="Could not contact pod: conn",
            ),
        ),
        (
            "action",
            dict(
                exception=PodActionError("action"),
                message="Failed to complete pod action: action",
            ),
        ),
        (
            "unknown",
            dict(
                exception=PodError("unknown error"),
                message="Failed talking to pod: unknown error",
            ),
        ),
    ]

    def test_return_msg(self):
        self.assertEqual(self.message, get_error_message(self.exception))
