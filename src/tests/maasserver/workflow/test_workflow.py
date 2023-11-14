import pytest

from maasserver.workflow import get_temporal_queue_for_machine


@pytest.mark.usefixtures("maasdb")
class TestGetTemporalQueueForMachine:
    def test_get_temporal_queue_for_machine_with_configured_boot_interface(
        self, factory
    ):
        vlan = factory.make_VLAN()
        rack = factory.make_RackController()
        factory.make_Interface(node=rack, vlan=vlan)
        machine = factory.make_Machine()
        boot_iface = factory.make_Interface(node=machine, vlan=vlan)
        machine.boot_interface = boot_iface
        machine.save()
        queue = get_temporal_queue_for_machine(machine)
        assert queue == f"agent:vlan-{machine.boot_interface.vlan.id}"

    def test_get_temporal_queue_for_machine_with_unconfigured_boot_interface(
        self, factory
    ):
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        rack = factory.make_RackController()
        factory.make_Interface(
            node=rack,
            vlan=vlan,
            subnet=subnet,
            ip=subnet.get_next_ip_for_allocation()[0],
        )
        ip = factory.make_StaticIPAddress(subnet=subnet)
        bmc = factory.make_BMC(ip_address=ip)
        machine = factory.make_Machine(bmc=bmc)
        machine_iface = factory.make_Interface(node=machine)
        machine_iface.vlan = None
        machine_iface.save()
        machine.boot_interface = machine_iface
        machine.save()
        queue = get_temporal_queue_for_machine(machine)
        assert queue == f"{rack.system_id}@agent"

    def test_get_temporal_queue_for_machine_without_boot_interface(
        self, factory
    ):
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        rack = factory.make_RackController()
        factory.make_Interface(
            node=rack,
            vlan=vlan,
            subnet=subnet,
            ip=subnet.get_next_ip_for_allocation()[0],
        )
        ip = factory.make_StaticIPAddress(subnet=subnet)
        bmc = factory.make_BMC(ip_address=ip)
        machine = factory.make_Machine(bmc=bmc)
        queue = get_temporal_queue_for_machine(machine)
        assert queue == f"{rack.system_id}@agent"

    def test_get_temporal_queue_for_power_management(self, factory):
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        rack = factory.make_RackController()
        factory.make_Interface(
            node=rack,
            vlan=vlan,
            subnet=subnet,
            ip=subnet.get_next_ip_for_allocation()[0],
        )
        ip = factory.make_StaticIPAddress(subnet=subnet)
        bmc = factory.make_BMC(ip_address=ip)
        machine = factory.make_Machine(bmc=bmc)
        boot_iface = factory.make_Interface(node=machine, vlan=vlan)
        machine.boot_interface = boot_iface
        machine.save()
        queue = get_temporal_queue_for_machine(machine, for_power=True)
        assert queue == f"{rack.system_id}@agent"
