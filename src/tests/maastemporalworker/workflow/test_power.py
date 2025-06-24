#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from collections import namedtuple
from unittest.mock import Mock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio.testing import ActivityEnvironment

from maascommon.enums.node import NodeStatus
from maascommon.enums.power import PowerState
from maascommon.workflows.power import (
    PowerCycleParam,
    PowerOffParam,
    PowerOnParam,
    PowerQueryParam,
)
from maasservicelayer.db import Database
from maasservicelayer.db.tables import NodeTable
from maasservicelayer.services import CacheForServices
from maasservicelayer.utils.date import utcnow
from maastemporalworker.workflow import power as power_workflow
from maastemporalworker.workflow.power import (
    convert_power_action_to_power_workflow,
    get_temporal_task_queue_for_bmc,
    PowerActivity,
    SetPowerStateParam,
    UnknownPowerActionException,
    UnroutablePowerWorkflowException,
)
from tests.fixtures.factories.node import create_test_machine_entry
from tests.maasapiserver.fixtures.db import Fixture


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
        self, factory, mocker
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

        mocked_get_all_clients = mocker.patch(
            "maastemporalworker.workflow.power.getAllClients"
        )
        client = Mock()
        client.ident = rack.system_id
        mocked_get_all_clients.return_value = [client]

        queue = get_temporal_task_queue_for_bmc(machine)
        assert queue == f"agent:power@vlan-{vlan.id}"

    def test_get_temporal_task_queue_for_bmc_machine_with_rackd_offline_on_vlan(
        self, factory, mocker
    ):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")

        vlan1 = factory.make_VLAN()
        subnet1 = factory.make_Subnet(vlan=vlan1)
        rack1 = factory.make_RackController()
        factory.make_Interface(
            node=rack1,
            vlan=vlan1,
            subnet=subnet1,
            ip=subnet1.get_next_ip_for_allocation()[0],
        )

        ip = factory.make_StaticIPAddress(subnet=subnet1)
        bmc = factory.make_BMC(ip_address=ip)
        machine = factory.make_Machine(bmc=bmc)

        subnet2 = factory.make_Subnet()
        rack2 = factory.make_RackController()
        factory.make_Interface(
            node=rack2,
            ip=subnet2.get_next_ip_for_allocation()[0],
        )

        factory.make_BMCRoutableRackControllerRelationship(bmc, rack2)

        mocked_get_all_clients = mocker.patch(
            "maastemporalworker.workflow.power.getAllClients"
        )
        mocked_bmc_get_all_clients = mocker.patch(
            "maasserver.models.bmc.getAllClients"
        )

        client = Mock()
        client.ident = rack2.system_id

        mocked_get_all_clients.return_value = [client]
        mocked_bmc_get_all_clients.return_value = [client]

        queue = get_temporal_task_queue_for_bmc(machine)
        assert queue == f"{rack2.system_id}@agent:power"

    def test_get_temporal_task_queue_for_bmc_machine_with_rackd_online_on_vlan(
        self, factory, mocker
    ):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")

        vlan1 = factory.make_VLAN()
        subnet1 = factory.make_Subnet(vlan=vlan1)
        rack1 = factory.make_RackController()
        factory.make_Interface(
            node=rack1,
            vlan=vlan1,
            subnet=subnet1,
            ip=subnet1.get_next_ip_for_allocation()[0],
        )

        ip = factory.make_StaticIPAddress(subnet=subnet1)
        bmc = factory.make_BMC(ip_address=ip)
        machine = factory.make_Machine(bmc=bmc)

        subnet2 = factory.make_Subnet()
        rack2 = factory.make_RackController()
        factory.make_Interface(
            node=rack2,
            ip=subnet2.get_next_ip_for_allocation()[0],
        )

        factory.make_BMCRoutableRackControllerRelationship(bmc, rack2)
        mocked_get_all_clients = mocker.patch(
            "maastemporalworker.workflow.power.getAllClients"
        )

        client = Mock()
        client.ident = rack1.system_id
        mocked_get_all_clients.return_value = [client]

        queue = get_temporal_task_queue_for_bmc(machine)
        assert queue == f"agent:power@vlan-{vlan1.id}"

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

        mocked_get_all_clients = mocker.patch(
            "maasserver.models.bmc.getAllClients"
        )

        client = Mock()
        client.ident = rack.system_id

        mocked_get_all_clients.return_value = [client]

        queue = get_temporal_task_queue_for_bmc(machine)
        assert queue == f"{rack.system_id}@agent:power"

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
        mocked_get_temporal_task_queue_for_bmc.return_value = (
            "agent:power@vlan-1"
        )

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
                task_queue="agent:power@vlan-1",
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
        mocked_get_temporal_task_queue_for_bmc.return_value = (
            "agent:power@vlan-1"
        )
        with pytest.raises(UnknownPowerActionException):
            convert_power_action_to_power_workflow(
                power_action, machine, params
            )


@pytest.mark.asyncio
class TestPowerActivity:
    async def test_set_power_state(
        self,
        fixture: Fixture,
        db_connection: AsyncConnection,
        db: Database,
    ):
        node = await create_test_machine_entry(
            fixture, status=NodeStatus.DEPLOYING
        )
        env = ActivityEnvironment()
        services_cache = CacheForServices()
        power_activity = PowerActivity(
            db, services_cache, connection=db_connection
        )
        now = utcnow()
        await env.run(
            power_activity.set_power_state,
            SetPowerStateParam(
                system_id=node["system_id"], state=PowerState.ON, timestamp=now
            ),
        )

        stmt = (
            select(NodeTable.c.power_state, NodeTable.c.power_state_updated)
            .select_from(NodeTable)
            .filter(NodeTable.c.system_id == node["system_id"])
        )

        result = (await db_connection.execute(stmt)).one()

        assert result[0] == PowerState.ON
        assert result[1] == now
