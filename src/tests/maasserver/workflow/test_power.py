from collections import namedtuple
from unittest.mock import Mock

import pytest

from maasserver.models import bmc as model_bmc
from maasserver.workflow import power as power_workflow
from maasserver.workflow.power import (
    convert_power_action_to_power_workflow,
    get_temporal_task_queue_for_bmc,
    PowerCycleParam,
    PowerOffParam,
    PowerOnParam,
    PowerQueryParam,
    UnknownPowerActionException,
    UnroutablePowerWorkflowException,
)


@pytest.mark.usefixtures("maasdb")
class TestGetTemporalQueueForMachine:
    def test_get_temporal_task_queue_for_bmc_machine_with_no_bmc(
        self, factory
    ):
        machine = factory.make_Machine(bmc=None)
        machine.save()
        with pytest.raises(UnroutablePowerWorkflowException):
            get_temporal_task_queue_for_bmc(machine)

    def test_get_temporal_task_queue_for_bmc_machine_with_bmc_with_vlan(
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
        queue = get_temporal_task_queue_for_bmc(machine)
        assert queue == f"agent:vlan-{vlan.id}"

    def test_get_temporal_task_queue_for_bmc_machine_with_bmc_without_vlan(
        self, factory, mocker
    ):
        subnet = factory.make_Subnet()
        rack = factory.make_RackController()
        factory.make_Interface(
            node=rack,
            ip=subnet.get_next_ip_for_allocation()[0],
        )
        bmc_ip = factory.make_StaticIPAddress(
            ip=subnet.get_next_ip_for_allocation()[0]
        )
        bmc = factory.make_BMC(ip_address=bmc_ip)
        machine = factory.make_Machine(bmc=bmc)
        factory.make_BMCRoutableRackControllerRelationship(bmc, rack)

        mocked_get_all_clients = mocker.patch.object(
            model_bmc, "getAllClients"
        )

        client = Mock()
        client.ident = rack.system_id

        mocked_get_all_clients.return_value = [client]

        queue = get_temporal_task_queue_for_bmc(machine)
        assert queue == f"{rack.system_id}@agent"

    def test_convert_power_action_to_power_workflow(self, factory, mocker):
        power_actions = {
            "power_on": PowerOnParam,
            "power_off": PowerOffParam,
            "power_query": PowerQueryParam,
            "power_cycle": PowerCycleParam,
        }
        machine = factory.make_Machine()
        params = namedtuple("params", ["power_type", "power_parameters"])(
            {}, {}
        )

        mocked_get_temporal_task_queue_for_bmc = mocker.patch.object(
            power_workflow, "get_temporal_task_queue_for_bmc"
        )
        mocked_get_temporal_task_queue_for_bmc.return_value = "agent:vlan-1"

        for power_action, param in power_actions.items():
            (
                workfow_type,
                workflow_param,
            ) = convert_power_action_to_power_workflow(
                power_action.replace("_", "-"), machine, params
            )

            assert workfow_type == power_action.replace("_", "-")
            assert workflow_param == power_actions[power_action](
                system_id=machine.system_id,
                task_queue="agent:vlan-1",
                driver_type=params.power_type,
                driver_opts=params.power_parameters,
            )

    def test_convert_power_action_to_power_workflow_fail_unknown(
        self, factory, mocker
    ):
        power_action = "unknown"
        machine = factory.make_Machine()
        params = namedtuple("params", ["power_type", "power_parameters"])(
            {}, {}
        )

        mocked_get_temporal_task_queue_for_bmc = mocker.patch.object(
            power_workflow, "get_temporal_task_queue_for_bmc"
        )
        mocked_get_temporal_task_queue_for_bmc.return_value = "agent:vlan-1"
        with pytest.raises(UnknownPowerActionException):
            convert_power_action_to_power_workflow(
                power_action, machine, params
            )
