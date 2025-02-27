#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from collections import namedtuple
from typing import Any
from unittest.mock import Mock
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio import activity
from temporalio.testing import ActivityEnvironment, WorkflowEnvironment
from temporalio.worker import Worker

from maascommon.enums.node import NodeStatus
from maascommon.enums.power import PowerState
from maascommon.workflows.power import (
    PowerCycleParam,
    PowerOffParam,
    PowerOnParam,
    PowerQueryParam,
    PowerResetParam,
)
from maasserver.models import bmc as model_bmc
from maasservicelayer.db import Database
from maasservicelayer.db.tables import NodeTable
from maasservicelayer.services import CacheForServices
from maasservicelayer.utils.date import utcnow
from maastemporalworker.workflow import power as power_workflow
from maastemporalworker.workflow.power import (
    convert_power_action_to_power_workflow,
    get_temporal_task_queue_for_bmc,
    POWER_RESET_ACTIVITY_NAME,
    PowerActivity,
    PowerResetResult,
    PowerResetWorkflow,
    SetPowerStateParam,
    UnknownPowerActionException,
    UnroutablePowerWorkflowException,
)
from tests.fixtures.factories.node import create_test_machine_entry
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("maasdb")
class TestGetTemporalQueueForMachine:
    def test_get_temporal_task_queue_for_bmc_machine_with_no_bmc(
        self, factory, mocker
    ):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        machine = factory.make_Machine(bmc=None)
        machine.save()
        with pytest.raises(UnroutablePowerWorkflowException):
            get_temporal_task_queue_for_bmc(machine)

    def test_get_temporal_task_queue_for_bmc_machine_with_bmc_with_vlan(
        self, factory, mocker
    ):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")

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
        assert queue == f"agent:power@vlan-{vlan.id}"

    def test_get_temporal_task_queue_for_bmc_machine_with_bmc_without_vlan(
        self, factory, mocker
    ):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")

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
        assert queue == f"{rack.system_id}@agent:power"

    def test_convert_power_action_to_power_workflow(self, factory, mocker):
        power_actions = {
            "power_on": PowerOnParam,
            "power_off": PowerOffParam,
            "power_query": PowerQueryParam,
            "power_cycle": PowerCycleParam,
            "power_reset": PowerResetParam,
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

        for power_action, param in power_actions.items():  # noqa: B007
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


@pytest.mark.asyncio
class TestPowerResetWorkflow:
    async def test_power_reset_workflow(self):
        # The task queue here must be the same between the Worker below and in
        # the PowerResetParam for this unit testing configuration to work.
        # In actual MAAS, the workflow is submitted to the "region" task queue
        # whilst the `task_queue` in the PowerResetParam specifies the specific
        # power task queue on the controller (e.g. {controller_id}@agent:power)
        # that manages the system_id you want to restart.
        power_task_queue = "def456@agent:power"

        calls = {}
        param = PowerResetParam(
            system_id="abc123",
            task_queue=power_task_queue,
            driver_type="redfish",
            driver_opts={
                "power_address": "0.0.0.0",
                "power_user": "maas",
                "power_pass": "maas",
            },
        )

        # The PowerResetParam in the workflow in python is defined as:
        # system_id: str,
        # task_queue: str,
        # driver_type: str,
        # driver_opts: dict[str,str]
        # but the activity in go maas-agent (src/maasagent/internal/power/service.go)
        # only uses the driver information, so we change the receiving param here
        @activity.defn(name=POWER_RESET_ACTIVITY_NAME)
        async def mock_power_reset_activity(
            param: dict[str, Any],
        ) -> PowerResetResult:
            calls[POWER_RESET_ACTIVITY_NAME] = param
            return PowerResetResult(state="on")

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue=power_task_queue,
                workflows=[PowerResetWorkflow],
                activities=[mock_power_reset_activity],
            ) as worker:
                return_value = await env.client.execute_workflow(
                    workflow=PowerResetWorkflow.run,
                    arg=param,
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert return_value.state == "on"

        # Check that the passed-in parameters to the activity match those of
        # the workflow's parameter.
        # NOTE: If the power parameters in the maas-agent change, these
        #       assertions will need to be updated.
        assert (
            calls[POWER_RESET_ACTIVITY_NAME]["driver_opts"]
            == param.driver_opts
        )
        assert (
            calls[POWER_RESET_ACTIVITY_NAME]["driver_type"]
            == param.driver_type
        )
