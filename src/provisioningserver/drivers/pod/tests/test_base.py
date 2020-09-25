# Copyright 2016-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.pod`."""

import random
from unittest.mock import sentinel

from jsonschema import validate
from testtools.matchers import (
    Equals,
    Is,
    IsInstance,
    MatchesAll,
    MatchesDict,
    MatchesListwise,
    MatchesStructure,
)

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers import make_setting_field
from provisioningserver.drivers.pod import (
    BlockDeviceType,
    DiscoveredMachine,
    DiscoveredMachineBlockDevice,
    DiscoveredMachineInterface,
    DiscoveredPod,
    DiscoveredPodHints,
    DiscoveredPodStoragePool,
    get_error_message,
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
    def make_iscsi_target(self):
        return "%s:6:3260:0:iqn.maas.io:%s" % (
            factory.make_ipv4_address(),
            factory.make_name("target"),
        )

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
        tags = [factory.make_name("tag") for _ in range(3)]
        nic = DiscoveredMachineInterface(mac_address=mac, vid=vid, tags=tags)
        self.assertEquals(mac, nic.mac_address)
        self.assertEquals(vid, nic.vid)
        self.assertEquals(tags, nic.tags)

    def test_block_device_size(self):
        size = random.randint(512, 512 * 1024)
        device = DiscoveredMachineBlockDevice(
            model=None, serial=None, size=size
        )
        self.assertEquals(None, device.model)
        self.assertEquals(None, device.serial)
        self.assertEquals(size, device.size)
        self.assertEquals(None, device.id_path)

    def test_block_device_size_id_path(self):
        size = random.randint(512, 512 * 1024)
        id_path = factory.make_name("id_path")
        device = DiscoveredMachineBlockDevice(
            model=None, serial=None, size=size, id_path=id_path
        )
        self.assertEquals(None, device.model)
        self.assertEquals(None, device.serial)
        self.assertEquals(size, device.size)
        self.assertEquals(id_path, device.id_path)

    def test_block_device_model_serial_size_block_size(self):
        model = factory.make_name("model")
        serial = factory.make_name("serial")
        size = random.randint(512, 512 * 1024)
        block_size = random.randint(512, 4096)
        device = DiscoveredMachineBlockDevice(
            model=model, serial=serial, size=size, block_size=block_size
        )
        self.assertEquals(model, device.model)
        self.assertEquals(serial, device.serial)
        self.assertEquals(size, device.size)
        self.assertEquals(block_size, device.block_size)

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
        self.assertEquals(model, device.model)
        self.assertEquals(serial, device.serial)
        self.assertEquals(size, device.size)
        self.assertEquals(block_size, device.block_size)
        self.assertEquals(tags, device.tags)

    def test_block_device_iscsi(self):
        size = random.randint(512, 512 * 1024)
        block_size = random.randint(512, 4096)
        tags = [factory.make_name("tag") for _ in range(3)]
        iscsi_target = "%s:6:3260:0:iqn.maas.io:%s" % (
            factory.make_ipv4_address(),
            factory.make_name("target"),
        )
        device = DiscoveredMachineBlockDevice(
            model=None,
            serial=None,
            size=size,
            block_size=block_size,
            tags=tags,
            type=BlockDeviceType.ISCSI,
            iscsi_target=iscsi_target,
        )
        self.assertIsNone(device.model)
        self.assertIsNone(device.serial)
        self.assertEquals(size, device.size)
        self.assertEquals(block_size, device.block_size)
        self.assertEquals(tags, device.tags)
        self.assertEquals(BlockDeviceType.ISCSI, device.type)
        self.assertEquals(iscsi_target, device.iscsi_target)

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
        self.assertEquals(cores, machine.cores)
        self.assertEquals(cpu_speed, machine.cpu_speed)
        self.assertEquals(memory, machine.memory)
        self.assertEquals(interfaces, machine.interfaces)
        self.assertEquals(block_devices, machine.block_devices)
        self.assertEquals(tags, machine.tags)

    def test_pod_hints(self):
        cores = random.randint(1, 8)
        cpu_speed = random.randint(1000, 2000)
        memory = random.randint(4096, 8192)
        local_storage = random.randint(4096, 8192)
        local_disks = random.randint(1, 8)
        iscsi_storage = random.randint(4096, 8192)
        hints = DiscoveredPodHints(
            cores=cores,
            cpu_speed=cpu_speed,
            memory=memory,
            local_storage=local_storage,
            local_disks=local_disks,
            iscsi_storage=iscsi_storage,
        )
        self.assertEquals(cores, hints.cores)
        self.assertEquals(cpu_speed, hints.cpu_speed)
        self.assertEquals(memory, hints.memory)
        self.assertEquals(local_storage, hints.local_storage)
        self.assertEquals(iscsi_storage, hints.iscsi_storage)

    def test_pod(self):
        hostname = factory.make_name("hostname")
        cores = random.randint(1, 8)
        cpu_speed = random.randint(1000, 2000)
        memory = random.randint(4096, 8192)
        local_storage = random.randint(4096, 8192)
        iscsi_storage = random.randint(4096, 8192)
        hints = DiscoveredPodHints(
            cores=random.randint(1, 8),
            cpu_speed=random.randint(1000, 2000),
            memory=random.randint(4096, 8192),
            local_storage=random.randint(4096, 8192),
            iscsi_storage=random.randint(4096, 8192),
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
            for _ in range(3):
                block_devices.append(
                    DiscoveredMachineBlockDevice(
                        model=None,
                        serial=None,
                        size=random.randint(512, 1024),
                        type=BlockDeviceType.ISCSI,
                        iscsi_target=self.make_iscsi_target(),
                    )
                )
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
            cpu_speed=cpu_speed,
            memory=memory,
            local_storage=local_storage,
            iscsi_storage=iscsi_storage,
            hints=hints,
            machines=machines,
        )
        self.assertEquals(cores, pod.cores)
        self.assertEquals(cpu_speed, pod.cpu_speed)
        self.assertEquals(memory, pod.memory)
        self.assertEquals(local_storage, pod.local_storage)
        self.assertEquals(iscsi_storage, pod.iscsi_storage)
        self.assertEquals(machines, pod.machines)

    def test_pod_asdict(self):
        hostname = factory.make_name("hostname")
        cores = random.randint(1, 8)
        cpu_speed = random.randint(1000, 2000)
        memory = random.randint(4096, 8192)
        local_storage = random.randint(4096, 8192)
        local_disks = random.randint(1, 8)
        iscsi_storage = random.randint(4096, 8192)
        hints = DiscoveredPodHints(
            cores=random.randint(1, 8),
            cpu_speed=random.randint(1000, 2000),
            memory=random.randint(4096, 8192),
            local_storage=random.randint(4096, 8192),
            local_disks=random.randint(1, 8),
            iscsi_storage=random.randint(4096, 8192),
        )
        machines = []
        tags = [factory.make_name("tag") for _ in range(3)]
        storage_pools = [
            DiscoveredPodStoragePool(
                id=factory.make_name("id"),
                name=factory.make_name("name"),
                storage=random.randint(4096, 8192),
                type="dir",
                path="/var/%s" % factory.make_name("dir"),
            )
            for _ in range(3)
        ]
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
                    id_path=factory.make_name("/dev/vda"),
                )
                for _ in range(3)
            ]
            for _ in range(3):
                block_devices.append(
                    DiscoveredMachineBlockDevice(
                        model=None,
                        serial=None,
                        size=random.randint(512, 1024),
                        type=BlockDeviceType.ISCSI,
                        iscsi_target=self.make_iscsi_target(),
                        storage_pool=factory.make_name("pool"),
                    )
                )
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
                    hugepages_backed=True,
                )
            )
        pod = DiscoveredPod(
            architectures=["amd64/generic"],
            cores=cores,
            cpu_speed=cpu_speed,
            memory=memory,
            local_storage=local_storage,
            local_disks=local_disks,
            iscsi_storage=iscsi_storage,
            hints=hints,
            machines=machines,
            tags=tags,
            storage_pools=storage_pools,
        )
        self.assertThat(
            pod.asdict(),
            MatchesDict(
                {
                    "architectures": Equals(["amd64/generic"]),
                    "name": Equals(None),
                    "cores": Equals(cores),
                    "cpu_speed": Equals(cpu_speed),
                    "memory": Equals(memory),
                    "local_storage": Equals(local_storage),
                    "local_disks": Equals(local_disks),
                    "iscsi_storage": Equals(iscsi_storage),
                    "mac_addresses": Equals([]),
                    "capabilities": Equals(pod.capabilities),
                    "hints": MatchesDict(
                        {
                            "cores": Equals(hints.cores),
                            "cpu_speed": Equals(hints.cpu_speed),
                            "memory": Equals(hints.memory),
                            "local_storage": Equals(hints.local_storage),
                            "local_disks": Equals(hints.local_disks),
                            "iscsi_storage": Equals(hints.iscsi_storage),
                        }
                    ),
                    "machines": MatchesListwise(
                        [
                            MatchesDict(
                                {
                                    "hostname": Equals(machine.hostname),
                                    "architecture": Equals("amd64/generic"),
                                    "cores": Equals(machine.cores),
                                    "cpu_speed": Equals(machine.cpu_speed),
                                    "memory": Equals(machine.memory),
                                    "power_state": Equals(machine.power_state),
                                    "power_parameters": Equals(
                                        machine.power_parameters
                                    ),
                                    "interfaces": MatchesListwise(
                                        [
                                            MatchesDict(
                                                {
                                                    "mac_address": Equals(
                                                        interface.mac_address
                                                    ),
                                                    "vid": Equals(
                                                        interface.vid
                                                    ),
                                                    "tags": Equals(
                                                        interface.tags
                                                    ),
                                                    "boot": Equals(False),
                                                    "attach_type": Is(None),
                                                    "attach_name": Is(None),
                                                }
                                            )
                                            for interface in machine.interfaces
                                        ]
                                    ),
                                    "block_devices": MatchesListwise(
                                        [
                                            MatchesDict(
                                                {
                                                    "model": Equals(
                                                        block_device.model
                                                    ),
                                                    "serial": Equals(
                                                        block_device.serial
                                                    ),
                                                    "size": Equals(
                                                        block_device.size
                                                    ),
                                                    "block_size": Equals(
                                                        block_device.block_size
                                                    ),
                                                    "tags": Equals(
                                                        block_device.tags
                                                    ),
                                                    "id_path": Equals(
                                                        block_device.id_path
                                                    ),
                                                    "type": Equals(
                                                        block_device.type
                                                    ),
                                                    "iscsi_target": Equals(
                                                        block_device.iscsi_target
                                                    ),
                                                    "storage_pool": Equals(
                                                        block_device.storage_pool
                                                    ),
                                                }
                                            )
                                            for block_device in machine.block_devices
                                        ]
                                    ),
                                    "tags": Equals(machine.tags),
                                    "hugepages_backed": Equals(True),
                                    "pinned_cores": Equals([]),
                                    "bios_boot_method": Is(None),
                                }
                            )
                            for machine in machines
                        ]
                    ),
                    "tags": Equals(tags),
                    "storage_pools": MatchesListwise(
                        [
                            MatchesDict(
                                {
                                    "id": Equals(pool.id),
                                    "name": Equals(pool.name),
                                    "storage": Equals(pool.storage),
                                    "type": Equals(pool.type),
                                    "path": Equals(pool.path),
                                }
                            )
                            for pool in storage_pools
                        ]
                    ),
                }
            ),
        )

    def test_pod_fromdict(self):
        hostname = factory.make_name("hostname")
        cores = random.randint(1, 8)
        cpu_speed = random.randint(1000, 2000)
        memory = random.randint(4096, 8192)
        local_storage = random.randint(4096, 8192)
        iscsi_storage = random.randint(4096, 8192)
        hints = dict(
            cores=random.randint(1, 8),
            cpu_speed=random.randint(1000, 2000),
            memory=random.randint(4096, 8192),
            local_storage=random.randint(4096, 8192),
            iscsi_storage=random.randint(4096, 8192),
        )
        machines_data = []
        for _ in range(3):
            cores = random.randint(1, 8)
            cpu_speed = random.randint(1000, 2000)
            memory = random.randint(4096, 8192)
            interfaces = [
                dict(mac_address=factory.make_mac_address()) for _ in range(3)
            ]
            block_devices = [
                dict(
                    model=factory.make_name("model"),
                    serial=factory.make_name("serial"),
                    size=random.randint(512, 1024),
                )
                for _ in range(3)
            ]
            for _ in range(3):
                block_devices.append(
                    dict(
                        model=None,
                        serial=None,
                        size=random.randint(512, 1024),
                        type=BlockDeviceType.ISCSI,
                        iscsi_target=self.make_iscsi_target(),
                    )
                )
            machines_data.append(
                dict(
                    hostname=hostname,
                    architecture="amd64/generic",
                    cores=cores,
                    cpu_speed=cpu_speed,
                    memory=memory,
                    interfaces=interfaces,
                    block_devices=block_devices,
                )
            )
        pod_data = dict(
            architectures=["amd64/generic"],
            cores=cores,
            cpu_speed=cpu_speed,
            memory=memory,
            local_storage=local_storage,
            iscsi_storage=iscsi_storage,
            hints=hints,
            machines=machines_data,
        )
        pod = DiscoveredPod.fromdict(pod_data)
        self.assertThat(pod, IsInstance(DiscoveredPod))
        self.assertThat(
            pod,
            MatchesStructure(
                architectures=Equals(["amd64/generic"]),
                cores=Equals(cores),
                cpu_speed=Equals(cpu_speed),
                memory=Equals(memory),
                local_storage=Equals(local_storage),
                iscsi_storage=Equals(iscsi_storage),
                hints=MatchesAll(
                    IsInstance(DiscoveredPodHints),
                    MatchesStructure(
                        cores=Equals(hints["cores"]),
                        cpu_speed=Equals(hints["cpu_speed"]),
                        memory=Equals(hints["memory"]),
                        local_storage=Equals(hints["local_storage"]),
                        iscsi_storage=Equals(hints["iscsi_storage"]),
                    ),
                ),
                machines=MatchesListwise(
                    [
                        MatchesAll(
                            IsInstance(DiscoveredMachine),
                            MatchesStructure(
                                architecture=Equals("amd64/generic"),
                                cores=Equals(machine["cores"]),
                                cpu_speed=Equals(machine["cpu_speed"]),
                                memory=Equals(machine["memory"]),
                                interfaces=MatchesListwise(
                                    [
                                        MatchesAll(
                                            IsInstance(
                                                DiscoveredMachineInterface
                                            ),
                                            MatchesStructure(
                                                mac_address=Equals(
                                                    interface["mac_address"]
                                                ),
                                                vid=Equals(-1),
                                                tags=Equals([]),
                                            ),
                                        )
                                        for interface in machine["interfaces"]
                                    ]
                                ),
                                block_devices=MatchesListwise(
                                    [
                                        MatchesAll(
                                            IsInstance(
                                                DiscoveredMachineBlockDevice
                                            ),
                                            MatchesStructure(
                                                model=Equals(
                                                    block_device["model"]
                                                ),
                                                serial=Equals(
                                                    block_device["serial"]
                                                ),
                                                size=Equals(
                                                    block_device["size"]
                                                ),
                                                block_size=Equals(512),
                                                tags=Equals([]),
                                                type=Equals(
                                                    BlockDeviceType.PHYSICAL
                                                ),
                                            ),
                                        )
                                        for block_device in machine[
                                            "block_devices"
                                        ]
                                        if "type" not in block_device
                                    ]
                                    + [
                                        MatchesAll(
                                            IsInstance(
                                                DiscoveredMachineBlockDevice
                                            ),
                                            MatchesStructure(
                                                model=Is(None),
                                                serial=Is(None),
                                                size=Equals(
                                                    block_device["size"]
                                                ),
                                                block_size=Equals(512),
                                                tags=Equals([]),
                                                type=Equals(
                                                    BlockDeviceType.ISCSI
                                                ),
                                                iscsi_target=Equals(
                                                    block_device[
                                                        "iscsi_target"
                                                    ]
                                                ),
                                            ),
                                        )
                                        for block_device in machine[
                                            "block_devices"
                                        ]
                                        if "type" in block_device
                                    ]
                                ),
                            ),
                        )
                        for machine in machines_data
                    ]
                ),
            ),
        )


class TestRequestClasses(MAASTestCase):
    def test_block_device_size(self):
        size = random.randint(512, 512 * 1024)
        tags = [factory.make_name("tag") for _ in range(3)]
        device = RequestedMachineBlockDevice(size=size, tags=tags)
        self.assertEquals(size, device.size)
        self.assertEquals(tags, device.tags)

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
        self.assertEquals(hostname, machine.hostname)
        self.assertEquals(cores, machine.cores)
        self.assertEquals(cpu_speed, machine.cpu_speed)
        self.assertEquals(memory, machine.memory)
        self.assertEquals(interfaces, machine.interfaces)
        self.assertEquals(block_devices, machine.block_devices)

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
        self.assertEquals(hostname, machine.hostname)
        self.assertEquals(cores, machine.cores)
        self.assertIsNone(machine.cpu_speed)
        self.assertEquals(memory, machine.memory)
        self.assertEquals(interfaces, machine.interfaces)
        self.assertEquals(block_devices, machine.block_devices)

    def test_machine_asdict(self):
        hostname = factory.make_name("hostname")
        cores = random.randint(1, 8)
        cpu_speed = random.randint(1000, 2000)
        memory = random.randint(4096, 8192)
        interfaces = [RequestedMachineInterface() for _ in range(3)]
        known_host_interfaces = [KnownHostInterface() for _ in range(3)]
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
            known_host_interfaces=known_host_interfaces,
            block_devices=block_devices,
        )
        self.assertThat(
            machine.asdict(),
            MatchesDict(
                {
                    "hostname": Equals(hostname),
                    "architecture": Equals("amd64/generic"),
                    "cores": Equals(cores),
                    "cpu_speed": Equals(cpu_speed),
                    "memory": Equals(memory),
                    "interfaces": MatchesListwise(
                        [
                            MatchesDict(
                                {
                                    "ifname": Is(None),
                                    "requested_ips": Equals([]),
                                    "ip_mode": Is(None),
                                    "attach_name": Equals(
                                        interface.attach_name
                                    ),
                                    "attach_type": Equals(
                                        interface.attach_type
                                    ),
                                    "attach_vlan": Is(None),
                                    "attach_options": Equals(
                                        interface.attach_options
                                    ),
                                }
                            )
                            for interface in interfaces
                        ]
                    ),
                    "known_host_interfaces": MatchesListwise(
                        [
                            MatchesDict(
                                {
                                    "ifname": Equals(
                                        known_host_interface.ifname
                                    ),
                                    "attach_name": Equals(
                                        known_host_interface.attach_name
                                    ),
                                    "attach_type": Equals(
                                        known_host_interface.attach_type
                                    ),
                                    "attach_vlan": Is(None),
                                    "dhcp_enabled": Equals(False),
                                }
                            )
                            for known_host_interface in known_host_interfaces
                        ]
                    ),
                    "block_devices": MatchesListwise(
                        [
                            MatchesDict(
                                {
                                    "size": Equals(block_device.size),
                                    "tags": Equals(block_device.tags),
                                }
                            )
                            for block_device in block_devices
                        ]
                    ),
                }
            ),
        )

    def test_machine_fromdict(self):
        hostname = factory.make_name("hostname")
        cores = random.randint(1, 8)
        cpu_speed = random.randint(1000, 2000)
        memory = random.randint(4096, 8192)
        interfaces = [dict() for _ in range(3)]
        block_devices = [
            dict(
                size=random.randint(512, 1024),
                tags=[factory.make_name("tag") for _ in range(3)],
            )
            for _ in range(3)
        ]
        machine_data = dict(
            hostname=hostname,
            architecture="amd64/generic",
            cores=cores,
            cpu_speed=cpu_speed,
            memory=memory,
            interfaces=interfaces,
            block_devices=block_devices,
        )
        machine = RequestedMachine.fromdict(machine_data)
        self.assertThat(machine, IsInstance(RequestedMachine))
        self.assertThat(
            machine,
            MatchesStructure(
                hostname=Equals(hostname),
                architecture=Equals("amd64/generic"),
                cores=Equals(cores),
                cpu_speed=Equals(cpu_speed),
                memory=Equals(memory),
                interfaces=MatchesListwise(
                    [
                        IsInstance(RequestedMachineInterface)
                        for interface in interfaces
                    ]
                ),
                block_devices=MatchesListwise(
                    [
                        MatchesAll(
                            IsInstance(RequestedMachineBlockDevice),
                            MatchesStructure(
                                size=Equals(block_device["size"]),
                                tags=Equals(block_device["tags"]),
                            ),
                        )
                        for block_device in block_devices
                    ]
                ),
            ),
        )


class FakePodDriverBase(PodDriverBase):

    name = ""
    chassis = True
    can_probe = True
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
        self.assertEquals(
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
        #: doesn't raise ValidationError
        validate(fake_driver.get_schema(), JSON_POD_DRIVER_SCHEMA)


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
