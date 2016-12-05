# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.chassis`."""

__all__ = []

import random
from unittest.mock import sentinel

from jsonschema import validate
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers import make_setting_field
from provisioningserver.drivers.chassis import (
    ChassisActionError,
    ChassisAuthError,
    ChassisConnError,
    ChassisDriver,
    ChassisDriverBase,
    ChassisDriverRegistry,
    ChassisError,
    DiscoveredChassis,
    DiscoveredChassisHints,
    DiscoveredMachine,
    DiscoveredMachineBlockDevice,
    DiscoveredMachineInterface,
    get_error_message,
    JSON_CHASSIS_DRIVER_SCHEMA,
)
from provisioningserver.utils.testing import RegistryFixture
from testtools.matchers import (
    Equals,
    IsInstance,
    MatchesAll,
    MatchesDict,
    MatchesListwise,
    MatchesStructure,
)


class TestDiscoveredClasses(MAASTestCase):

    def test_interface_mac(self):
        mac = factory.make_mac_address()
        nic = DiscoveredMachineInterface(mac_address=mac)
        self.assertEquals(mac, nic.mac_address)
        self.assertEquals(-1, nic.vid)
        self.assertEquals([], nic.tags)

    def test_interface_mac_vid(self):
        mac = factory.make_mac_address()
        vid = random.randint(1, 300)
        nic = DiscoveredMachineInterface(mac_address=mac, vid=vid)
        self.assertEquals(mac, nic.mac_address)
        self.assertEquals(vid, nic.vid)
        self.assertEquals([], nic.tags)

    def test_interface_mac_vid_tags(self):
        mac = factory.make_mac_address()
        vid = random.randint(1, 300)
        tags = [
            factory.make_name("tag")
            for _ in range(3)
        ]
        nic = DiscoveredMachineInterface(mac_address=mac, vid=vid, tags=tags)
        self.assertEquals(mac, nic.mac_address)
        self.assertEquals(vid, nic.vid)
        self.assertEquals(tags, nic.tags)

    def test_block_device_model_serial_size(self):
        model = factory.make_name("model")
        serial = factory.make_name("serial")
        size = random.randint(512, 512 * 1024)
        device = DiscoveredMachineBlockDevice(
            model=model, serial=serial, size=size)
        self.assertEquals(model, device.model)
        self.assertEquals(serial, device.serial)
        self.assertEquals(size, device.size)

    def test_block_device_model_serial_size_block_size(self):
        model = factory.make_name("model")
        serial = factory.make_name("serial")
        size = random.randint(512, 512 * 1024)
        block_size = random.randint(512, 4096)
        device = DiscoveredMachineBlockDevice(
            model=model, serial=serial, size=size, block_size=block_size)
        self.assertEquals(model, device.model)
        self.assertEquals(serial, device.serial)
        self.assertEquals(size, device.size)
        self.assertEquals(block_size, device.block_size)

    def test_block_device_model_serial_size_block_size_tags(self):
        model = factory.make_name("model")
        serial = factory.make_name("serial")
        size = random.randint(512, 512 * 1024)
        block_size = random.randint(512, 4096)
        tags = [
            factory.make_name("tag")
            for _ in range(3)
        ]
        device = DiscoveredMachineBlockDevice(
            model=model, serial=serial, size=size, block_size=block_size,
            tags=tags)
        self.assertEquals(model, device.model)
        self.assertEquals(serial, device.serial)
        self.assertEquals(size, device.size)
        self.assertEquals(block_size, device.block_size)
        self.assertEquals(tags, device.tags)

    def test_machine(self):
        cores = random.randint(1, 8)
        cpu_speed = random.randint(1000, 2000)
        memory = random.randint(4096, 8192)
        interfaces = [
            DiscoveredMachineInterface(mac_address=factory.make_mac_address())
            for _ in range(3)
        ]
        block_devices = [
            DiscoveredMachineBlockDevice(
                model=factory.make_name("model"),
                serial=factory.make_name("serial"),
                size=random.randint(512, 1024))
            for _ in range(3)
        ]
        machine = DiscoveredMachine(
            cores=cores, cpu_speed=cpu_speed, memory=memory,
            interfaces=interfaces, block_devices=block_devices)
        self.assertEquals(cores, machine.cores)
        self.assertEquals(cpu_speed, machine.cpu_speed)
        self.assertEquals(memory, machine.memory)
        self.assertEquals(interfaces, machine.interfaces)
        self.assertEquals(block_devices, machine.block_devices)

    def test_chassis_hints(self):
        cores = random.randint(1, 8)
        memory = random.randint(4096, 8192)
        local_storage = random.randint(4096, 8192)
        hints = DiscoveredChassisHints(
            cores=cores, memory=memory, local_storage=local_storage)
        self.assertEquals(cores, hints.cores)
        self.assertEquals(memory, hints.memory)
        self.assertEquals(local_storage, hints.local_storage)

    def test_chassis(self):
        cores = random.randint(1, 8)
        cpu_speed = random.randint(1000, 2000)
        memory = random.randint(4096, 8192)
        local_storage = random.randint(4096, 8192)
        hints = DiscoveredChassisHints(
            cores=random.randint(1, 8), memory=random.randint(4096, 8192),
            local_storage=random.randint(4096, 8192))
        machines = []
        for _ in range(3):
            cores = random.randint(1, 8)
            cpu_speed = random.randint(1000, 2000)
            memory = random.randint(4096, 8192)
            interfaces = [
                DiscoveredMachineInterface(
                    mac_address=factory.make_mac_address())
                for _ in range(3)
            ]
            block_devices = [
                DiscoveredMachineBlockDevice(
                    model=factory.make_name("model"),
                    serial=factory.make_name("serial"),
                    size=random.randint(512, 1024))
                for _ in range(3)
            ]
            machines.append(
                DiscoveredMachine(
                    cores=cores, cpu_speed=cpu_speed, memory=memory,
                    interfaces=interfaces, block_devices=block_devices))
        chassis = DiscoveredChassis(
            cores=cores, cpu_speed=cpu_speed, memory=memory,
            local_storage=local_storage, hints=hints, machines=machines)
        self.assertEquals(cores, chassis.cores)
        self.assertEquals(cpu_speed, chassis.cpu_speed)
        self.assertEquals(memory, chassis.memory)
        self.assertEquals(local_storage, chassis.local_storage)
        self.assertEquals(machines, chassis.machines)

    def test_chassis_asdict(self):
        cores = random.randint(1, 8)
        cpu_speed = random.randint(1000, 2000)
        memory = random.randint(4096, 8192)
        local_storage = random.randint(4096, 8192)
        hints = DiscoveredChassisHints(
            cores=random.randint(1, 8), memory=random.randint(4096, 8192),
            local_storage=random.randint(4096, 8192))
        machines = []
        for _ in range(3):
            cores = random.randint(1, 8)
            cpu_speed = random.randint(1000, 2000)
            memory = random.randint(4096, 8192)
            interfaces = [
                DiscoveredMachineInterface(
                    mac_address=factory.make_mac_address())
                for _ in range(3)
            ]
            block_devices = [
                DiscoveredMachineBlockDevice(
                    model=factory.make_name("model"),
                    serial=factory.make_name("serial"),
                    size=random.randint(512, 1024))
                for _ in range(3)
            ]
            machines.append(
                DiscoveredMachine(
                    cores=cores, cpu_speed=cpu_speed, memory=memory,
                    interfaces=interfaces, block_devices=block_devices))
        chassis = DiscoveredChassis(
            cores=cores, cpu_speed=cpu_speed, memory=memory,
            local_storage=local_storage, hints=hints, machines=machines)
        self.assertThat(chassis.asdict(), MatchesDict({
            "cores": Equals(cores),
            "cpu_speed": Equals(cpu_speed),
            "memory": Equals(memory),
            "local_storage": Equals(local_storage),
            "hints": MatchesDict({
                "cores": Equals(hints.cores),
                "memory": Equals(hints.memory),
                "local_storage": Equals(hints.local_storage),
            }),
            "machines": MatchesListwise([
                MatchesDict({
                    "cores": Equals(machine.cores),
                    "cpu_speed": Equals(machine.cpu_speed),
                    "memory": Equals(machine.memory),
                    "interfaces": MatchesListwise([
                        MatchesDict({
                            "mac_address": Equals(interface.mac_address),
                            "vid": Equals(interface.vid),
                            "tags": Equals(interface.tags),
                        })
                        for interface in machine.interfaces
                    ]),
                    "block_devices": MatchesListwise([
                        MatchesDict({
                            "model": Equals(block_device.model),
                            "serial": Equals(block_device.serial),
                            "size": Equals(block_device.size),
                            "block_size": Equals(block_device.block_size),
                            "tags": Equals(block_device.tags),
                        })
                        for block_device in machine.block_devices
                    ]),
                })
                for machine in machines
            ]),
        }))

    def test_chassis_fromdict(self):
        cores = random.randint(1, 8)
        cpu_speed = random.randint(1000, 2000)
        memory = random.randint(4096, 8192)
        local_storage = random.randint(4096, 8192)
        hints = dict(
            cores=random.randint(1, 8), memory=random.randint(4096, 8192),
            local_storage=random.randint(4096, 8192))
        machines_data = []
        for _ in range(3):
            cores = random.randint(1, 8)
            cpu_speed = random.randint(1000, 2000)
            memory = random.randint(4096, 8192)
            interfaces = [
                dict(
                    mac_address=factory.make_mac_address())
                for _ in range(3)
            ]
            block_devices = [
                dict(
                    model=factory.make_name("model"),
                    serial=factory.make_name("serial"),
                    size=random.randint(512, 1024))
                for _ in range(3)
            ]
            machines_data.append(
                dict(
                    cores=cores, cpu_speed=cpu_speed, memory=memory,
                    interfaces=interfaces, block_devices=block_devices))
        chassis_data = dict(
            cores=cores, cpu_speed=cpu_speed, memory=memory,
            local_storage=local_storage, hints=hints, machines=machines_data)
        chassis = DiscoveredChassis.fromdict(chassis_data)
        self.assertThat(chassis, IsInstance(DiscoveredChassis))
        self.assertThat(chassis, MatchesStructure(
            cores=Equals(cores),
            cpu_speed=Equals(cpu_speed),
            memory=Equals(memory),
            local_storage=Equals(local_storage),
            hints=MatchesAll(
                IsInstance(DiscoveredChassisHints),
                MatchesStructure(
                    cores=Equals(hints['cores']),
                    memory=Equals(hints['memory']),
                    local_storage=Equals(hints['local_storage']),
                ),
            ),
            machines=MatchesListwise([
                MatchesAll(
                    IsInstance(DiscoveredMachine),
                    MatchesStructure(
                        cores=Equals(machine['cores']),
                        cpu_speed=Equals(machine['cpu_speed']),
                        memory=Equals(machine['memory']),
                        interfaces=MatchesListwise([
                            MatchesAll(
                                IsInstance(DiscoveredMachineInterface),
                                MatchesStructure(
                                    mac_address=Equals(
                                        interface['mac_address']),
                                    vid=Equals(-1),
                                    tags=Equals([]),
                                ),
                            )
                            for interface in machine['interfaces']
                        ]),
                        block_devices=MatchesListwise([
                            MatchesAll(
                                IsInstance(DiscoveredMachineBlockDevice),
                                MatchesStructure(
                                    model=Equals(block_device['model']),
                                    serial=Equals(block_device['serial']),
                                    size=Equals(block_device['size']),
                                    block_size=Equals(512),
                                    tags=Equals([]),
                                ),
                            )
                            for block_device in machine['block_devices']
                        ]),
                    ),
                )
                for machine in machines_data
            ]),
        ))


class FakeChassisDriverBase(ChassisDriverBase):

    name = ""
    description = ""
    settings = []
    ip_extractor = None
    queryable = True
    composable = False

    def __init__(self, name, description, settings):
        self.name = name
        self.description = description
        self.settings = settings
        super(FakeChassisDriverBase, self).__init__()

    def discover(self, system_id, context):
        raise NotImplementedError

    def compose(self, system_id, context):
        raise NotImplementedError

    def decompose(self, system_id, context):
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


def make_chassis_driver_base(name=None, description=None, settings=None):
    if name is None:
        name = factory.make_name('chassis')
    if description is None:
        description = factory.make_name('description')
    if settings is None:
        settings = []
    return FakeChassisDriverBase(name, description, settings)


class TestFakeChassisDriverBase(MAASTestCase):

    def test_attributes(self):
        fake_name = factory.make_name('name')
        fake_description = factory.make_name('description')
        fake_setting = factory.make_name('setting')
        fake_settings = [
            make_setting_field(
                fake_setting, fake_setting.title()),
            ]
        attributes = {
            'name': fake_name,
            'description': fake_description,
            'settings': fake_settings,
            }
        fake_driver = FakeChassisDriverBase(
            fake_name, fake_description, fake_settings)
        self.assertAttributes(fake_driver, attributes)

    def test_make_chassis_driver_base(self):
        fake_name = factory.make_name('name')
        fake_description = factory.make_name('description')
        fake_setting = factory.make_name('setting')
        fake_settings = [
            make_setting_field(
                fake_setting, fake_setting.title()),
            ]
        attributes = {
            'name': fake_name,
            'description': fake_description,
            'settings': fake_settings,
            }
        fake_driver = make_chassis_driver_base(
            name=fake_name, description=fake_description,
            settings=fake_settings)
        self.assertAttributes(fake_driver, attributes)

    def test_make_chassis_driver_base_makes_name_and_description(self):
        fake_driver = make_chassis_driver_base()
        self.assertNotEqual("", fake_driver.name)
        self.assertNotEqual("", fake_driver.description)

    def test_discover_raises_not_implemented(self):
        fake_driver = make_chassis_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.discover, sentinel.system_id, sentinel.context)

    def test_compose_raises_not_implemented(self):
        fake_driver = make_chassis_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.compose, sentinel.system_id, sentinel.context)

    def test_decompose_raises_not_implemented(self):
        fake_driver = make_chassis_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.decompose, sentinel.system_id, sentinel.context)


class TestChassisDriverBase(MAASTestCase):

    def test_get_schema(self):
        fake_name = factory.make_name('name')
        fake_description = factory.make_name('description')
        fake_setting = factory.make_name('setting')
        fake_settings = [
            make_setting_field(
                fake_setting, fake_setting.title()),
            ]
        fake_driver = make_chassis_driver_base()
        self.assertItemsEqual({
            'name': fake_name,
            'description': fake_description,
            'fields': fake_settings,
            'queryable': fake_driver.queryable,
            'missing_packages': [],
            'composable': fake_driver.composable,
            },
            fake_driver.get_schema())

    def test_get_schema_returns_valid_schema(self):
        fake_driver = make_chassis_driver_base()
        #: doesn't raise ValidationError
        validate(fake_driver.get_schema(), JSON_CHASSIS_DRIVER_SCHEMA)


class TestChassisDriverRegistry(MAASTestCase):

    def setUp(self):
        super(TestChassisDriverRegistry, self).setUp()
        # Ensure the global registry is empty for each test run.
        self.useFixture(RegistryFixture())

    def test_registry(self):
        self.assertItemsEqual([], ChassisDriverRegistry)
        ChassisDriverRegistry.register_item("driver", sentinel.driver)
        self.assertIn(
            sentinel.driver,
            (item for name, item in ChassisDriverRegistry))

    def test_get_schema(self):
        fake_driver_one = make_chassis_driver_base()
        fake_driver_two = make_chassis_driver_base()
        ChassisDriverRegistry.register_item(
            fake_driver_one.name, fake_driver_one)
        ChassisDriverRegistry.register_item(
            fake_driver_two.name, fake_driver_two)
        self.assertItemsEqual([
            {
                'name': fake_driver_one.name,
                'description': fake_driver_one.description,
                'fields': [],
                'queryable': fake_driver_one.queryable,
                'missing_packages': fake_driver_one.detect_missing_packages(),
                'composable': fake_driver_one.composable,
            },
            {
                'name': fake_driver_two.name,
                'description': fake_driver_two.description,
                'fields': [],
                'queryable': fake_driver_two.queryable,
                'missing_packages': fake_driver_two.detect_missing_packages(),
                'composable': fake_driver_two.composable,
            }],
            ChassisDriverRegistry.get_schema())


class TestGetErrorMessage(MAASTestCase):

    scenarios = [
        ('auth', dict(
            exception=ChassisAuthError('auth'),
            message="Could not authenticate to chassis: auth",
            )),
        ('conn', dict(
            exception=ChassisConnError('conn'),
            message="Could not contact chassis: conn",
            )),
        ('action', dict(
            exception=ChassisActionError('action'),
            message="Failed to complete chassis action: action",
            )),
        ('unknown', dict(
            exception=ChassisError('unknown error'),
            message="Failed talking to chassis: unknown error",
            )),
    ]

    def test_return_msg(self):
        self.assertEqual(self.message, get_error_message(self.exception))


class FakeChassisDriver(ChassisDriver):

    name = ""
    description = ""
    settings = []
    ip_extractor = None
    queryable = True

    def __init__(self, name, description, settings):
        self.name = name
        self.description = description
        self.settings = settings
        super(FakeChassisDriver, self).__init__()

    def detect_missing_packages(self):
        raise NotImplementedError

    def power_on(self, system_id, context):
        raise NotImplementedError

    def power_off(self, system_id, context):
        raise NotImplementedError

    def power_query(self, system_id, context):
        raise NotImplementedError


def make_chassis_driver(name=None, description=None, settings=None):
    if name is None:
        name = factory.make_name('diskless')
    if description is None:
        description = factory.make_name('description')
    if settings is None:
        settings = []
    return FakeChassisDriver(
        name, description, settings)
