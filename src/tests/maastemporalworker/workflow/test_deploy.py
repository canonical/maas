from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, Mock
import uuid

import pytest
from pytest_mock import MockerFixture
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq
from temporalio import activity
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.service import RPCError
from temporalio.testing import ActivityEnvironment, WorkflowEnvironment
from temporalio.worker import Worker

from maascommon.constants import NODE_TIMEOUT
from maascommon.enums.node import NodeStatus
from maascommon.enums.power import PowerState
from maascommon.workflows.deploy import (
    DEPLOY_MANY_WORKFLOW_NAME,
    DEPLOY_WORKFLOW_NAME,
)
from maascommon.workflows.power import (
    PowerCycleParam,
    PowerOffParam,
    PowerOnParam,
    PowerParam,
    PowerQueryParam,
    PowerResetParam,
)
from maasservicelayer.db import Database
from maasservicelayer.db.tables import NodeTable
from maasservicelayer.models.nodes import Node
from maasservicelayer.services import CacheForServices
from maastemporalworker.workflow.deploy import (
    CONFIRM_POWERED_ON_MAX_ATTEMPTS,
    DeployActivity,
    DeployManyParam,
    DeployManyWorkflow,
    DeployParam,
    DeployWorkflow,
    GET_BOOT_ORDER_ACTIVITY_NAME,
    GetBootOrderParam,
    GetBootOrderResult,
    MARK_NODE_FAILED_ACTIVITY_NAME,
    MarkNodeFailedParam,
    SET_BOOT_ORDER_ACTIVITY_NAME,
    SET_NODE_STATUS_ACTIVITY_NAME,
    SetBootOrderParam,
    SetNodeStatusParam,
)
from maastemporalworker.workflow.power import (
    POWER_CYCLE_ACTIVITY_NAME,
    POWER_OFF_ACTIVITY_NAME,
    POWER_ON_ACTIVITY_NAME,
    POWER_QUERY_ACTIVITY_NAME,
    POWER_RESET_ACTIVITY_NAME,
    PowerCycleResult,
    PowerOffResult,
    PowerOnResult,
    PowerQueryResult,
    PowerResetResult,
    SET_POWER_STATE_ACTIVITY_NAME,
    SetPowerStateParam,
)
from tests.fixtures.factories.block_device import create_test_blockdevice_entry
from tests.fixtures.factories.bmc import create_test_bmc_entry
from tests.fixtures.factories.interface import create_test_interface_dict
from tests.fixtures.factories.node import create_test_machine_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maastemporalworker.workflow import TemporalCalls


def _stringify_datetime_fields(obj: dict[str, Any]) -> dict[str, Any]:
    for k, v in obj.items():
        if isinstance(v, datetime):
            obj[k] = str(v)
        elif isinstance(v, list):
            for i, o in enumerate(v):
                if isinstance(o, datetime):
                    v[i] = str(o)
                elif isinstance(o, dict):
                    for k2, v2 in o.items():
                        if isinstance(v2, datetime):
                            o[k2] = str(v2)
        elif isinstance(v, dict):
            for k2, v2 in v.items():
                if isinstance(v2, datetime):
                    v[k2] = str(v2)
    return obj


def _expected_boot_disk(block_device: dict[str, Any]) -> dict[str, Any]:
    """Project a block device fixture to the fields get_boot_order returns.

    The activity only selects the base block device id/name/id_path plus the
    physical block device model/serial (the fields the power drivers need), so
    the expected boot-order entry for a disk is that narrowed projection.
    """
    return {
        "id": block_device["id"],
        "name": block_device["name"],
        "id_path": block_device["id_path"],
        "model": block_device["model"],
        "serial": block_device["serial"],
    }


@pytest.mark.asyncio
class TestDeployActivity:
    async def test_set_node_status(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ):
        node = await create_test_machine_entry(fixture, status=NodeStatus.NEW)
        env = ActivityEnvironment()
        services_cache = CacheForServices()
        activities = DeployActivity(
            db,
            services_cache,
            temporal_client=Mock(Client),
            connection=db_connection,
        )
        await env.run(
            activities.set_node_status,
            SetNodeStatusParam(
                system_id=node["system_id"],
                status=NodeStatus.READY,
            ),
        )
        [retrieved_node] = await fixture.get_typed(
            NodeTable.name, Node, eq(NodeTable.c.system_id, node["system_id"])
        )
        assert retrieved_node.status == NodeStatus.READY

    async def test_get_boot_order_with_netboot(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ):
        subnet = await create_test_subnet_entry(fixture)
        [ip1] = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        [ip2] = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        machine = await create_test_machine_entry(fixture)
        boot_iface = await create_test_interface_dict(
            fixture, node=machine, ips=[ip1]
        )
        await db_connection.execute(
            update(NodeTable)
            .values(
                boot_interface_id=boot_iface["id"],
            )
            .where(NodeTable.c.system_id == machine["system_id"])
            .where(
                NodeTable.c.system_id == machine["system_id"],
            ),
        )
        for link in boot_iface["links"]:
            link["ip"] = str(link["ip"])
        other_iface = await create_test_interface_dict(
            fixture, node=machine, ips=[ip2]
        )
        for link in other_iface["links"]:
            link["ip"] = str(link["ip"])
        boot_disk = await create_test_blockdevice_entry(fixture, node=machine)
        other_disk = await create_test_blockdevice_entry(fixture, node=machine)
        services_cache = CacheForServices()
        activities = DeployActivity(
            db,
            services_cache,
            temporal_client=Mock(Client),
            connection=db_connection,
        )
        env = ActivityEnvironment()
        boot_order = await env.run(
            activities.get_boot_order,
            GetBootOrderParam(system_id=machine["system_id"], netboot=True),
        )

        assert boot_order.order == [
            _stringify_datetime_fields(dev)
            for dev in [boot_iface, other_iface]
        ] + [_expected_boot_disk(dev) for dev in [boot_disk, other_disk]]

    async def test_get_boot_order_without_netboot(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ):
        subnet = await create_test_subnet_entry(fixture)
        [ip1] = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        [ip2] = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        machine = await create_test_machine_entry(fixture)
        boot_iface = await create_test_interface_dict(
            fixture, node=machine, ips=[ip1]
        )
        for link in boot_iface["links"]:
            link["ip"] = str(link["ip"])
        await db_connection.execute(
            update(NodeTable)
            .values(
                boot_interface_id=boot_iface["id"],
            )
            .where(NodeTable.c.system_id == machine["system_id"])
            .where(
                NodeTable.c.system_id == machine["system_id"],
            ),
        )
        other_iface = await create_test_interface_dict(
            fixture, node=machine, ips=[ip2]
        )
        for link in other_iface["links"]:
            link["ip"] = str(link["ip"])
        boot_disk = await create_test_blockdevice_entry(fixture, node=machine)
        other_disk = await create_test_blockdevice_entry(fixture, node=machine)
        services_cache = CacheForServices()
        activities = DeployActivity(
            db,
            services_cache,
            temporal_client=Mock(Client),
            connection=db_connection,
        )
        env = ActivityEnvironment()
        boot_order = await env.run(
            activities.get_boot_order,
            GetBootOrderParam(system_id=machine["system_id"], netboot=False),
        )
        assert boot_order.order == [
            _expected_boot_disk(dev) for dev in [boot_disk, other_disk]
        ] + [
            _stringify_datetime_fields(dev)
            for dev in [boot_iface, other_iface]
        ]


@pytest.mark.asyncio
class TestDeployManyWorkflow:
    async def test_deploy_n_workflow_1_node(
        self,
        fixture: Fixture,
        db_connection: AsyncConnection,
        db: Database,
        mocker: MockerFixture,
    ) -> None:
        bmc = await create_test_bmc_entry(fixture)
        machine = await create_test_machine_entry(fixture, bmc_id=bmc["id"])
        subnet = await create_test_subnet_entry(fixture)
        [ip] = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        boot_iface = await create_test_interface_dict(
            fixture, node=machine, ips=[ip]
        )
        boot_disk = await create_test_blockdevice_entry(fixture, node=machine)

        calls = defaultdict(list)

        @activity.defn(name=SET_NODE_STATUS_ACTIVITY_NAME)
        async def set_node_status(params: SetNodeStatusParam) -> None:
            calls["set_node_status"].append(params.status)

        @activity.defn(name=GET_BOOT_ORDER_ACTIVITY_NAME)
        async def get_boot_order(
            params: GetBootOrderParam,
        ) -> GetBootOrderResult:
            calls["get_boot_order"].append(True)
            order = []
            if params.netboot:
                order = [boot_iface, boot_disk]
            else:
                order = [boot_disk, boot_iface]
            return GetBootOrderResult(
                system_id=machine["system_id"],
                order=[_stringify_datetime_fields(dev) for dev in order],
            )

        @activity.defn(name=POWER_QUERY_ACTIVITY_NAME)
        async def power_query(params: PowerQueryParam) -> PowerQueryResult:
            calls["power_query"].append(True)
            return PowerQueryResult(state="off")

        @activity.defn(name=POWER_CYCLE_ACTIVITY_NAME)
        async def power_cycle(params: PowerCycleParam) -> PowerCycleResult:
            calls["power_cycle"].append(True)
            return PowerCycleResult(state="on")

        @activity.defn(name=POWER_ON_ACTIVITY_NAME)
        async def power_on(params: PowerOnParam) -> PowerOnResult:
            calls["power_on"].append(True)
            return PowerOnResult(state="on")

        @activity.defn(name=POWER_OFF_ACTIVITY_NAME)
        async def power_off(params: PowerOffParam) -> PowerOffResult:
            calls["power_off"].append(True)
            return PowerOffResult(state="off")

        @activity.defn(name=POWER_RESET_ACTIVITY_NAME)
        async def power_reset(params: PowerResetParam) -> PowerResetResult:
            calls["power_reset"].append(True)
            return PowerResetResult(state="on")

        @activity.defn(name=SET_POWER_STATE_ACTIVITY_NAME)
        async def set_power_state(params: SetPowerStateParam) -> None:
            calls["set_power_state"].append(True)
            return

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[DeployManyWorkflow, DeployWorkflow],
                activities=[
                    set_node_status,
                    get_boot_order,
                    set_power_state,
                    power_query,
                    power_cycle,
                    power_on,
                    power_off,
                    power_reset,
                ],
            ) as worker:
                wf = await env.client.start_workflow(
                    DEPLOY_MANY_WORKFLOW_NAME,
                    DeployManyParam(
                        params=[
                            DeployParam(
                                system_id=machine["system_id"],
                                ephemeral_deploy=False,
                                can_set_boot_order=False,
                                task_queue=worker.task_queue,
                                power_params=PowerParam(
                                    system_id=machine["system_id"],
                                    driver_type=bmc["power_type"],
                                    driver_opts=bmc["power_parameters"],
                                    task_queue=worker.task_queue,
                                    is_dpu=machine["is_dpu"],
                                ),
                            ),
                        ],
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    await wf.describe()
                ).status == WorkflowExecutionStatus.RUNNING

                await env.sleep(duration=timedelta(seconds=5))

                deploy_wf = env.client.get_workflow_handle(
                    f"deploy:{machine['system_id']}"
                )
                await deploy_wf.signal("netboot-finished")
                await env.sleep(duration=timedelta(seconds=1))
                await deploy_wf.signal("deployed-os-ready")

                await env.sleep(duration=timedelta(seconds=1))

                await wf.result()

                assert len(calls["set_node_status"]) == 1
                assert calls["set_node_status"][0] == NodeStatus.DEPLOYED
                assert len(calls["get_boot_order"]) == 0
                assert len(calls["power_query"]) == 1
                assert len(calls["power_on"]) == 1
                assert len(calls["power_cycle"]) == 0
                assert len(calls["set_power_state"]) == 1
                assert len(calls["power_reset"]) == 0

    async def test_deploy_n_workflow_handles_aborted_deployment(
        self,
        fixture: Fixture,
        db_connection: AsyncConnection,
        db: Database,
        mocker: MockerFixture,
    ) -> None:
        bmc = await create_test_bmc_entry(fixture)
        machine = await create_test_machine_entry(fixture, bmc_id=bmc["id"])
        subnet = await create_test_subnet_entry(fixture)
        [ip] = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        boot_iface = await create_test_interface_dict(
            fixture, node=machine, ips=[ip]
        )
        boot_disk = await create_test_blockdevice_entry(fixture, node=machine)

        calls = defaultdict(list)

        @activity.defn(name=SET_NODE_STATUS_ACTIVITY_NAME)
        async def set_node_status(params: SetNodeStatusParam) -> None:
            calls["set_node_status"].append(True)

        @activity.defn(name=GET_BOOT_ORDER_ACTIVITY_NAME)
        async def get_boot_order(
            params: GetBootOrderParam,
        ) -> GetBootOrderResult:
            calls["get_boot_order"].append(True)
            order = []
            if params.netboot:
                order = [boot_iface, boot_disk]
            else:
                order = [boot_disk, boot_iface]
            return GetBootOrderResult(
                system_id=machine["system_id"],
                order=[_stringify_datetime_fields(dev) for dev in order],
            )

        @activity.defn(name=POWER_QUERY_ACTIVITY_NAME)
        async def power_query(params: PowerQueryParam) -> PowerQueryResult:
            calls["power_query"].append(True)
            return PowerQueryResult(state="off")

        @activity.defn(name=POWER_CYCLE_ACTIVITY_NAME)
        async def power_cycle(params: PowerCycleParam) -> PowerCycleResult:
            calls["power_cycle"].append(True)
            return PowerCycleResult(state="on")

        @activity.defn(name=POWER_ON_ACTIVITY_NAME)
        async def power_on(params: PowerOnParam) -> PowerOnResult:
            calls["power_on"].append(True)
            return PowerOnResult(state="on")

        @activity.defn(name=POWER_OFF_ACTIVITY_NAME)
        async def power_off(params: PowerOffParam) -> PowerOffResult:
            calls["power_off"].append(True)
            return PowerOffResult(state="off")

        @activity.defn(name=POWER_RESET_ACTIVITY_NAME)
        async def power_reset(params: PowerResetParam) -> PowerResetResult:
            calls["power_reset"].append(True)
            return PowerResetResult(state="on")

        @activity.defn(name=SET_POWER_STATE_ACTIVITY_NAME)
        async def set_power_state(params: SetPowerStateParam) -> None:
            calls["set_power_state"].append(True)
            return

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[DeployManyWorkflow, DeployWorkflow],
                activities=[
                    set_node_status,
                    get_boot_order,
                    power_query,
                    power_cycle,
                    power_on,
                    power_off,
                    set_power_state,
                    power_reset,
                ],
            ) as worker:
                wf = await env.client.start_workflow(
                    DEPLOY_MANY_WORKFLOW_NAME,
                    DeployManyParam(
                        params=[
                            DeployParam(
                                system_id=machine["system_id"],
                                ephemeral_deploy=False,
                                can_set_boot_order=False,
                                task_queue=worker.task_queue,
                                power_params=PowerParam(
                                    system_id=machine["system_id"],
                                    driver_type=bmc["power_type"],
                                    driver_opts=bmc["power_parameters"],
                                    task_queue=worker.task_queue,
                                    is_dpu=machine["is_dpu"],
                                ),
                            ),
                        ],
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    await wf.describe()
                ).status == WorkflowExecutionStatus.RUNNING

                await env.sleep(duration=timedelta(seconds=1))

                deploy_wf = env.client.get_workflow_handle(
                    f"deploy:{machine['system_id']}"
                )
                await deploy_wf.cancel()

                await env.sleep(duration=timedelta(seconds=5))

                await wf.result()

                assert len(calls["set_node_status"]) == 0
                assert len(calls["get_boot_order"]) == 0
                assert len(calls["power_query"]) == 1
                assert len(calls["power_on"]) <= 1
                assert len(calls["power_cycle"]) == 0
                assert len(calls["power_reset"]) == 0

    async def test_multiple_machine_deploy_success(
        self,
        fixture: Fixture,
        db_connection: AsyncConnection,
        db: Database,
    ) -> None:
        subnet = await create_test_subnet_entry(fixture)

        async def create_machine() -> dict[str, Any]:
            [ip] = await create_test_staticipaddress_entry(
                fixture, subnet=subnet
            )
            bmc = await create_test_bmc_entry(
                fixture, power_parameters={"address": str(ip["ip"])}
            )
            machine = await create_test_machine_entry(
                fixture, bmc_id=bmc["id"]
            )
            machine["bmc"] = bmc
            boot_iface = await create_test_interface_dict(
                fixture, node=machine, ips=[ip]
            )
            machine["boot_iface"] = boot_iface
            boot_disk = await create_test_blockdevice_entry(
                fixture, node=machine
            )
            machine["boot_disk"] = boot_disk
            return machine

        machines = [await create_machine() for _ in range(3)]

        calls = defaultdict(list)

        @activity.defn(name=SET_NODE_STATUS_ACTIVITY_NAME)
        async def set_node_status(params: SetNodeStatusParam) -> None:
            calls["set_node_status"].append(params.status)

        @activity.defn(name=GET_BOOT_ORDER_ACTIVITY_NAME)
        async def get_boot_order(
            params: GetBootOrderParam,
        ) -> GetBootOrderResult:
            calls["get_boot_order"].append(True)
            order = []
            for machine in machines:
                if machine["system_id"] == params.system_id:
                    if params.netboot:
                        order = [machine["boot_iface"], machine["boot_disk"]]
                    else:
                        order = [machine["boot_disk"], machine["boot_iface"]]
                    return GetBootOrderResult(
                        system_id=machine["system_id"],
                        order=[
                            _stringify_datetime_fields(dev) for dev in order
                        ],
                    )

        @activity.defn(name=POWER_QUERY_ACTIVITY_NAME)
        async def power_query(params: PowerQueryParam) -> PowerQueryResult:
            calls["power_query"].append(True)
            return PowerQueryResult(state="off")

        @activity.defn(name=POWER_CYCLE_ACTIVITY_NAME)
        async def power_cycle(params: PowerCycleParam) -> PowerCycleResult:
            calls["power_cycle"].append(True)
            return PowerCycleResult(state="on")

        @activity.defn(name=POWER_ON_ACTIVITY_NAME)
        async def power_on(params: PowerOnParam) -> PowerOnResult:
            calls["power_on"].append(True)
            return PowerOnResult(state="on")

        @activity.defn(name=POWER_OFF_ACTIVITY_NAME)
        async def power_off(params: PowerOffParam) -> PowerOffResult:
            calls["power_off"].append(True)
            return PowerOffResult(state="off")

        @activity.defn(name=POWER_RESET_ACTIVITY_NAME)
        async def power_reset(params: PowerResetParam) -> PowerResetResult:
            calls["power_reset"].append(True)
            return PowerResetResult(state="on")

        @activity.defn(name=SET_POWER_STATE_ACTIVITY_NAME)
        async def set_power_state(params: SetPowerStateParam) -> None:
            calls["set_power_state"].append(True)
            return

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[DeployManyWorkflow, DeployWorkflow],
                activities=[
                    set_node_status,
                    get_boot_order,
                    set_power_state,
                    power_query,
                    power_cycle,
                    power_on,
                    power_off,
                    power_reset,
                ],
            ) as worker:
                wf = await env.client.start_workflow(
                    DEPLOY_MANY_WORKFLOW_NAME,
                    DeployManyParam(
                        params=[
                            DeployParam(
                                system_id=machine["system_id"],
                                ephemeral_deploy=False,
                                can_set_boot_order=False,
                                task_queue=worker.task_queue,
                                power_params=PowerParam(
                                    system_id=machine["system_id"],
                                    driver_type=machine["bmc"]["power_type"],
                                    driver_opts=machine["bmc"][
                                        "power_parameters"
                                    ],
                                    task_queue=worker.task_queue,
                                    is_dpu=machine["is_dpu"],
                                ),
                            )
                            for machine in machines
                        ],
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    await wf.describe()
                ).status == WorkflowExecutionStatus.RUNNING

                await env.sleep(duration=timedelta(seconds=5))

                for machine in machines:
                    deploy_wf = env.client.get_workflow_handle(
                        f"deploy:{machine['system_id']}"
                    )
                    await deploy_wf.signal("netboot-finished")
                    await env.sleep(duration=timedelta(seconds=1))
                    await deploy_wf.signal("deployed-os-ready")

                await env.sleep(duration=timedelta(seconds=5))

                await wf.result()

                assert len(calls["set_node_status"]) == 3
                assert calls["set_node_status"] == [
                    NodeStatus.DEPLOYED for _ in range(3)
                ]
                assert len(calls["get_boot_order"]) == 0
                assert len(calls["power_query"]) == 3
                assert len(calls["power_on"]) == 3
                assert len(calls["power_cycle"]) == 0
                assert len(calls["set_power_state"]) == 3
                assert len(calls["power_reset"]) == 0

    async def test_one_set_boot_order(
        self,
        fixture: Fixture,
        db_connection: AsyncConnection,
        db: Database,
    ) -> None:
        subnet = await create_test_subnet_entry(fixture)

        async def create_machine() -> dict[str, Any]:
            [ip] = await create_test_staticipaddress_entry(
                fixture, subnet=subnet
            )
            bmc = await create_test_bmc_entry(
                fixture, power_parameters={"address": str(ip["ip"])}
            )
            machine = await create_test_machine_entry(
                fixture, bmc_id=bmc["id"]
            )
            machine["bmc"] = bmc
            boot_iface = await create_test_interface_dict(
                fixture, node=machine, ips=[ip]
            )
            machine["boot_iface"] = boot_iface
            boot_disk = await create_test_blockdevice_entry(
                fixture, node=machine
            )
            machine["boot_disk"] = boot_disk
            return machine

        machines = [await create_machine() for _ in range(3)]

        calls = defaultdict(list)

        @activity.defn(name=SET_NODE_STATUS_ACTIVITY_NAME)
        async def set_node_status(params: SetNodeStatusParam) -> None:
            calls["set_node_status"].append(True)

        @activity.defn(name=GET_BOOT_ORDER_ACTIVITY_NAME)
        async def get_boot_order(
            params: GetBootOrderParam,
        ) -> GetBootOrderResult:
            calls["get_boot_order"].append(True)
            order = []
            for machine in machines:
                if machine["system_id"] == params.system_id:
                    for link in machine["boot_iface"]["links"]:
                        link["ip"] = str(link["ip"])
                    if params.netboot:
                        order = [machine["boot_iface"], machine["boot_disk"]]
                    else:
                        order = [machine["boot_disk"], machine["boot_iface"]]
                    result = GetBootOrderResult(
                        system_id=machine["system_id"],
                        order=[
                            _stringify_datetime_fields(dev) for dev in order
                        ],
                    )
                    return result

        @activity.defn(name=POWER_QUERY_ACTIVITY_NAME)
        async def power_query(params: PowerQueryParam) -> PowerQueryResult:
            calls["power_query"].append(True)
            return PowerQueryResult(state="off")

        @activity.defn(name=POWER_CYCLE_ACTIVITY_NAME)
        async def power_cycle(params: PowerCycleParam) -> PowerCycleResult:
            calls["power_cycle"].append(True)
            return PowerCycleResult(state="on")

        @activity.defn(name=POWER_ON_ACTIVITY_NAME)
        async def power_on(params: PowerOnParam) -> PowerOnResult:
            calls["power_on"].append(True)
            return PowerOnResult(state="on")

        @activity.defn(name=POWER_OFF_ACTIVITY_NAME)
        async def power_off(params: PowerOffParam) -> PowerOffResult:
            calls["power_off"].append(True)
            return PowerOffResult(state="off")

        @activity.defn(name=POWER_RESET_ACTIVITY_NAME)
        async def power_reset(params: PowerResetParam) -> PowerResetResult:
            calls["power_reset"].append(True)
            return PowerResetResult(state="on")

        @activity.defn(name=SET_BOOT_ORDER_ACTIVITY_NAME)
        async def set_boot_order(params: SetBootOrderParam) -> None:
            calls["set_boot_order"].append(True)

        @activity.defn(name=SET_POWER_STATE_ACTIVITY_NAME)
        async def set_power_state(params: SetPowerStateParam) -> None:
            calls["set_power_state"].append(True)
            return

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[DeployManyWorkflow, DeployWorkflow],
                activities=[
                    set_node_status,
                    get_boot_order,
                    set_boot_order,
                    set_power_state,
                    power_query,
                    power_cycle,
                    power_on,
                    power_off,
                    power_reset,
                ],
            ) as worker:
                wf = await env.client.start_workflow(
                    DEPLOY_MANY_WORKFLOW_NAME,
                    DeployManyParam(
                        params=[
                            DeployParam(
                                system_id=machine["system_id"],
                                ephemeral_deploy=False,
                                can_set_boot_order=i == 2,
                                task_queue=worker.task_queue,
                                power_params=PowerParam(
                                    system_id=machine["system_id"],
                                    driver_type=machine["bmc"]["power_type"],
                                    driver_opts=machine["bmc"][
                                        "power_parameters"
                                    ],
                                    task_queue=worker.task_queue,
                                    is_dpu=machine["is_dpu"],
                                ),
                            )
                            for i, machine in enumerate(machines)
                        ],
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    await wf.describe()
                ).status == WorkflowExecutionStatus.RUNNING

                await env.sleep(duration=timedelta(seconds=5))

                for machine in machines:
                    deploy_wf = env.client.get_workflow_handle(
                        f"deploy:{machine['system_id']}"
                    )
                    await deploy_wf.signal("netboot-finished")
                    await env.sleep(duration=timedelta(seconds=1))
                    await deploy_wf.signal("deployed-os-ready")

                await env.sleep(duration=timedelta(seconds=5))

                await wf.result()

                assert len(calls["set_node_status"]) == 3
                assert len(calls["get_boot_order"]) == 2
                # 3 deploy-start queries + CONFIRM_POWERED_ON_MAX_ATTEMPTS
                # confirm polls for the single can_set_boot_order machine
                # after its switch-to-local-boot power-on. The mocked query
                # never reports "on", so the confirm loop runs to exhaustion;
                # its settle/debounce logic is covered in TestConfirmPoweredOn.
                assert (
                    len(calls["power_query"])
                    == 3 + CONFIRM_POWERED_ON_MAX_ATTEMPTS
                )
                # 3 initial deploy power-ons + 1 extra power-on for the single
                # can_set_boot_order machine, which MAAS power-cycles to switch
                # its boot device to disk (power off -> set boot order ->
                # power on).
                assert len(calls["power_on"]) == 4
                assert len(calls["power_off"]) == 1
                assert len(calls["power_cycle"]) == 0
                # 3 deploy-start persists + one confirm-loop persist.
                assert len(calls["set_power_state"]) == 4
                assert len(calls["power_reset"]) == 0

    async def test_one_ephemeral(
        self,
        fixture: Fixture,
        db_connection: AsyncConnection,
        db: Database,
    ) -> None:
        subnet = await create_test_subnet_entry(fixture)

        async def create_machine() -> dict[str, Any]:
            [ip] = await create_test_staticipaddress_entry(
                fixture, subnet=subnet
            )
            bmc = await create_test_bmc_entry(
                fixture, power_parameters={"address": str(ip["ip"])}
            )
            machine = await create_test_machine_entry(
                fixture, bmc_id=bmc["id"]
            )
            machine["bmc"] = bmc
            boot_iface = await create_test_interface_dict(
                fixture, node=machine, ips=[ip]
            )
            machine["boot_iface"] = boot_iface
            boot_disk = await create_test_blockdevice_entry(
                fixture, node=machine
            )
            machine["boot_disk"] = boot_disk
            return machine

        machines = [await create_machine() for _ in range(3)]

        calls = defaultdict(list)

        @activity.defn(name=SET_NODE_STATUS_ACTIVITY_NAME)
        async def set_node_status(params: SetNodeStatusParam) -> None:
            calls["set_node_status"].append(True)

        @activity.defn(name=GET_BOOT_ORDER_ACTIVITY_NAME)
        async def get_boot_order(
            params: GetBootOrderParam,
        ) -> GetBootOrderResult:
            calls["get_boot_order"].append(True)
            order = []
            for machine in machines:
                if machine["system_id"] == params.system_id:
                    if params.netboot:
                        order = [machine["boot_iface"], machine["boot_disk"]]
                    else:
                        order = [machine["boot_disk"], machine["boot_iface"]]
                    return GetBootOrderResult(
                        system_id=machine["system_id"],
                        order=[
                            _stringify_datetime_fields(dev) for dev in order
                        ],
                    )

        @activity.defn(name=POWER_QUERY_ACTIVITY_NAME)
        async def power_query(params: PowerQueryParam) -> PowerQueryResult:
            calls["power_query"].append(True)
            return PowerQueryResult(state="off")

        @activity.defn(name=POWER_CYCLE_ACTIVITY_NAME)
        async def power_cycle(params: PowerCycleParam) -> PowerCycleResult:
            calls["power_cycle"].append(True)
            return PowerCycleResult(state="on")

        @activity.defn(name=POWER_ON_ACTIVITY_NAME)
        async def power_on(params: PowerOnParam) -> PowerOnResult:
            calls["power_on"].append(True)
            return PowerOnResult(state="on")

        @activity.defn(name=POWER_OFF_ACTIVITY_NAME)
        async def power_off(params: PowerOffParam) -> PowerOffResult:
            calls["power_off"].append(True)
            return PowerOffResult(state="off")

        @activity.defn(name=POWER_RESET_ACTIVITY_NAME)
        async def power_reset(params: PowerResetParam) -> PowerResetResult:
            calls["power_reset"].append(True)
            return PowerResetResult(state="on")

        @activity.defn(name=SET_BOOT_ORDER_ACTIVITY_NAME)
        async def set_boot_order(params: SetBootOrderParam) -> None:
            calls["set_boot_order"].append(True)
            return

        @activity.defn(name=SET_POWER_STATE_ACTIVITY_NAME)
        async def set_power_state(params: SetPowerStateParam) -> None:
            calls["set_power_state"].append(True)
            return

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[DeployManyWorkflow, DeployWorkflow],
                activities=[
                    set_node_status,
                    get_boot_order,
                    set_boot_order,
                    set_power_state,
                    power_query,
                    power_cycle,
                    power_on,
                    power_off,
                    power_reset,
                ],
            ) as worker:
                wf = await env.client.start_workflow(
                    DEPLOY_MANY_WORKFLOW_NAME,
                    DeployManyParam(
                        params=[
                            DeployParam(
                                system_id=machine["system_id"],
                                ephemeral_deploy=i == 2,
                                can_set_boot_order=False,
                                task_queue=worker.task_queue,
                                power_params=PowerParam(
                                    system_id=machine["system_id"],
                                    driver_type=machine["bmc"]["power_type"],
                                    driver_opts=machine["bmc"][
                                        "power_parameters"
                                    ],
                                    task_queue=worker.task_queue,
                                    is_dpu=machine["is_dpu"],
                                ),
                            )
                            for i, machine in enumerate(machines)
                        ],
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    await wf.describe()
                ).status == WorkflowExecutionStatus.RUNNING

                await env.sleep(duration=timedelta(seconds=5))

                for i, machine in enumerate(machines):  # noqa: B007
                    deploy_wf = env.client.get_workflow_handle(
                        f"deploy:{machine['system_id']}"
                    )
                    await deploy_wf.signal("netboot-finished")
                    await env.sleep(duration=timedelta(seconds=1))
                    await deploy_wf.signal("deployed-os-ready")

                await env.sleep(duration=timedelta(seconds=5))

                await wf.result()

                assert len(calls["set_node_status"]) == 3
                assert len(calls["get_boot_order"]) == 0
                assert len(calls["power_query"]) == 3
                assert len(calls["power_on"]) == 3
                assert len(calls["power_cycle"]) == 0
                assert len(calls["set_power_state"]) == 3
                assert len(calls["power_reset"]) == 0

    async def test_power_on_always_failing_marks_node_failed_deployment(
        self,
        fixture: Fixture,
        db_connection: AsyncConnection,
        db: Database,
    ) -> None:
        bmc = await create_test_bmc_entry(fixture)
        machine = await create_test_machine_entry(fixture, bmc_id=bmc["id"])
        subnet = await create_test_subnet_entry(fixture)
        [ip] = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        await create_test_interface_dict(fixture, node=machine, ips=[ip])
        await create_test_blockdevice_entry(fixture, node=machine)

        deploy_timeout_minutes = 2 * NODE_TIMEOUT
        deploy_many_timeout_minutes = 2 * NODE_TIMEOUT + 10

        calls = defaultdict(list)

        @activity.defn(name=SET_NODE_STATUS_ACTIVITY_NAME)
        async def set_node_status(params: SetNodeStatusParam) -> None:
            calls["set_node_status"].append(params.status)

        @activity.defn(name=GET_BOOT_ORDER_ACTIVITY_NAME)
        async def get_boot_order(
            params: GetBootOrderParam,
        ) -> GetBootOrderResult:
            calls["get_boot_order"].append(True)
            return GetBootOrderResult(system_id=params.system_id, order=[])

        @activity.defn(name=MARK_NODE_FAILED_ACTIVITY_NAME)
        async def mark_node_failed(params: MarkNodeFailedParam) -> None:
            calls["mark_node_failed"].append(params.system_id)

        @activity.defn(name=POWER_QUERY_ACTIVITY_NAME)
        async def power_query(params: PowerQueryParam) -> PowerQueryResult:
            calls["power_query"].append(True)
            return PowerQueryResult(state="off")

        @activity.defn(name=POWER_ON_ACTIVITY_NAME)
        async def power_on(params: PowerOnParam) -> PowerOnResult:
            calls["power_on"].append(True)
            raise RuntimeError("power on failed")

        @activity.defn(name=POWER_CYCLE_ACTIVITY_NAME)
        async def power_cycle(params: PowerCycleParam) -> PowerCycleResult:
            calls["power_cycle"].append(True)
            return PowerCycleResult(state="on")

        @activity.defn(name=POWER_OFF_ACTIVITY_NAME)
        async def power_off(params: PowerOffParam) -> PowerOffResult:
            calls["power_off"].append(True)
            return PowerOffResult(state="off")

        @activity.defn(name=POWER_RESET_ACTIVITY_NAME)
        async def power_reset(params: PowerResetParam) -> PowerResetResult:
            calls["power_reset"].append(True)
            return PowerResetResult(state="on")

        @activity.defn(name=SET_POWER_STATE_ACTIVITY_NAME)
        async def set_power_state(params: SetPowerStateParam) -> None:
            calls["set_power_state"].append(True)

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[DeployManyWorkflow, DeployWorkflow],
                activities=[
                    set_node_status,
                    get_boot_order,
                    mark_node_failed,
                    power_query,
                    power_cycle,
                    power_on,
                    power_off,
                    power_reset,
                    set_power_state,
                ],
            ) as worker:
                wf = await env.client.start_workflow(
                    DEPLOY_MANY_WORKFLOW_NAME,
                    DeployManyParam(
                        params=[
                            DeployParam(
                                system_id=machine["system_id"],
                                ephemeral_deploy=False,
                                can_set_boot_order=False,
                                task_queue=worker.task_queue,
                                power_params=PowerParam(
                                    system_id=machine["system_id"],
                                    driver_type=bmc["power_type"],
                                    driver_opts=bmc["power_parameters"],
                                    task_queue=worker.task_queue,
                                    is_dpu=machine["is_dpu"],
                                ),
                                timeout=deploy_timeout_minutes,
                            ),
                        ],
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                    execution_timeout=timedelta(
                        minutes=deploy_many_timeout_minutes
                    ),
                )

                await env.sleep(
                    duration=timedelta(minutes=deploy_many_timeout_minutes + 5)
                )
                await wf.result()

                assert len(calls["set_node_status"]) == 0
                assert len(calls["mark_node_failed"]) == 1
                assert calls["mark_node_failed"][0] == machine["system_id"]
                assert len(calls["power_query"]) == 1
                assert len(calls["power_on"]) == 3
                assert len(calls["power_cycle"]) == 0
                assert len(calls["set_power_state"]) == 0


@pytest.mark.asyncio
class TestDeployWorkflow:
    async def test_deploy_workflow_non_ephemeral_success(
        self,
        fixture: Fixture,
        db_connection: AsyncConnection,
        db: Database,
    ) -> None:
        bmc = await create_test_bmc_entry(fixture)
        machine = await create_test_machine_entry(fixture, bmc_id=bmc["id"])
        subnet = await create_test_subnet_entry(fixture)
        [ip] = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        boot_iface = await create_test_interface_dict(
            fixture, node=machine, ips=[ip]
        )
        boot_disk = await create_test_blockdevice_entry(fixture, node=machine)

        calls = defaultdict(list)

        @activity.defn(name=SET_NODE_STATUS_ACTIVITY_NAME)
        async def set_node_status(params: SetNodeStatusParam) -> None:
            calls["set_node_status"].append(True)

        @activity.defn(name=GET_BOOT_ORDER_ACTIVITY_NAME)
        async def get_boot_order(
            params: GetBootOrderParam,
        ) -> GetBootOrderResult:
            calls["get_boot_order"].append(True)
            order = []
            if params.netboot:
                order = [boot_iface, boot_disk]
            else:
                order = [boot_disk, boot_iface]
            return GetBootOrderResult(
                system_id=machine["system_id"],
                order=[_stringify_datetime_fields(dev) for dev in order],
            )

        @activity.defn(name=POWER_QUERY_ACTIVITY_NAME)
        async def power_query(params: PowerQueryParam) -> PowerQueryResult:
            calls["power_query"].append(True)
            return PowerQueryResult(state="off")

        @activity.defn(name=POWER_CYCLE_ACTIVITY_NAME)
        async def power_cycle(params: PowerCycleParam) -> PowerCycleResult:
            calls["power_cycle"].append(True)
            return PowerCycleResult(state="on")

        @activity.defn(name=POWER_ON_ACTIVITY_NAME)
        async def power_on(params: PowerOnParam) -> PowerOnResult:
            calls["power_on"].append(True)
            return PowerOnResult(state="on")

        @activity.defn(name=POWER_OFF_ACTIVITY_NAME)
        async def power_off(params: PowerOffParam) -> PowerOffResult:
            calls["power_off"].append(True)
            return PowerOffResult(state="off")

        @activity.defn(name=POWER_RESET_ACTIVITY_NAME)
        async def power_reset(params: PowerResetParam) -> PowerResetResult:
            calls["power_reset"].append(True)
            return PowerResetResult(state="on")

        @activity.defn(name=SET_POWER_STATE_ACTIVITY_NAME)
        async def set_power_state(params: SetPowerStateParam) -> None:
            calls["set_power_state"].append(True)
            return

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[DeployWorkflow],
                activities=[
                    set_node_status,
                    get_boot_order,
                    set_power_state,
                    power_query,
                    power_cycle,
                    power_on,
                    power_off,
                    power_reset,
                ],
            ) as worker:
                wf = await env.client.start_workflow(
                    DEPLOY_WORKFLOW_NAME,
                    DeployParam(
                        system_id=machine["system_id"],
                        ephemeral_deploy=False,
                        can_set_boot_order=False,
                        task_queue=worker.task_queue,
                        power_params=PowerParam(
                            system_id=machine["system_id"],
                            driver_type=bmc["power_type"],
                            driver_opts=bmc["power_parameters"],
                            task_queue=worker.task_queue,
                            is_dpu=machine["is_dpu"],
                        ),
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    await wf.describe()
                ).status == WorkflowExecutionStatus.RUNNING

                await env.sleep(duration=timedelta(seconds=5))
                await wf.signal("netboot-finished")
                await env.sleep(duration=timedelta(seconds=5))
                await wf.signal("deployed-os-ready")
                await env.sleep(duration=timedelta(seconds=5))

                await wf.result()

                assert len(calls["set_node_status"]) == 0
                assert len(calls["get_boot_order"]) == 0
                assert len(calls["power_query"]) == 1
                assert len(calls["power_on"]) == 1
                assert len(calls["power_cycle"]) == 0
                assert len(calls["set_power_state"]) == 1
                assert len(calls["power_reset"]) == 0

    async def test_deploy_workflow_timeout(
        self,
        fixture: Fixture,
        db_connection: AsyncConnection,
        db: Database,
    ) -> None:
        bmc = await create_test_bmc_entry(fixture)
        machine = await create_test_machine_entry(fixture, bmc_id=bmc["id"])
        subnet = await create_test_subnet_entry(fixture)
        [ip] = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        await create_test_interface_dict(fixture, node=machine, ips=[ip])
        await create_test_blockdevice_entry(fixture, node=machine)

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[DeployWorkflow],
                activities=[],
            ) as worker:
                wf = await env.client.start_workflow(
                    DEPLOY_WORKFLOW_NAME,
                    DeployParam(
                        system_id=machine["system_id"],
                        ephemeral_deploy=False,
                        can_set_boot_order=False,
                        task_queue=worker.task_queue,
                        power_params=PowerParam(
                            system_id=machine["system_id"],
                            driver_type=bmc["power_type"],
                            driver_opts=bmc["power_parameters"],
                            task_queue=worker.task_queue,
                            is_dpu=machine["is_dpu"],
                        ),
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    await wf.describe()
                ).status == WorkflowExecutionStatus.RUNNING

                try:
                    await env.sleep(duration=timedelta(minutes=30))

                    await wf.result()
                except Exception as e:
                    assert isinstance(e, RPCError)

    async def test_deploy_workflow_ephemeral_deploy(
        self,
        fixture: Fixture,
        db_connection: AsyncConnection,
        db: Database,
    ) -> None:
        bmc = await create_test_bmc_entry(fixture)
        machine = await create_test_machine_entry(fixture, bmc_id=bmc["id"])
        subnet = await create_test_subnet_entry(fixture)
        [ip] = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        boot_iface = await create_test_interface_dict(
            fixture, node=machine, ips=[ip]
        )
        boot_disk = await create_test_blockdevice_entry(fixture, node=machine)

        calls = defaultdict(list)

        @activity.defn(name=SET_NODE_STATUS_ACTIVITY_NAME)
        async def set_node_status(params: SetNodeStatusParam) -> None:
            calls["set_node_status"].append(True)

        @activity.defn(name=GET_BOOT_ORDER_ACTIVITY_NAME)
        async def get_boot_order(
            params: GetBootOrderParam,
        ) -> GetBootOrderResult:
            calls["get_boot_order"].append(True)
            order = []
            if params.netboot:
                order = [boot_iface, boot_disk]
            else:
                order = [boot_disk, boot_iface]
            return GetBootOrderResult(
                system_id=machine["system_id"],
                order=[_stringify_datetime_fields(dev) for dev in order],
            )

        @activity.defn(name=POWER_QUERY_ACTIVITY_NAME)
        async def power_query(params: PowerQueryParam) -> PowerQueryResult:
            calls["power_query"].append(True)
            return PowerQueryResult(state="off")

        @activity.defn(name=POWER_CYCLE_ACTIVITY_NAME)
        async def power_cycle(params: PowerCycleParam) -> PowerCycleResult:
            calls["power_cycle"].append(True)
            return PowerCycleResult(state="on")

        @activity.defn(name=POWER_ON_ACTIVITY_NAME)
        async def power_on(params: PowerOnParam) -> PowerOnResult:
            calls["power_on"].append(True)
            return PowerOnResult(state="on")

        @activity.defn(name=POWER_OFF_ACTIVITY_NAME)
        async def power_off(params: PowerOffParam) -> PowerOffResult:
            calls["power_off"].append(True)
            return PowerOffResult(state="off")

        @activity.defn(name=POWER_RESET_ACTIVITY_NAME)
        async def power_reset(params: PowerResetParam) -> PowerResetResult:
            calls["power_reset"].append(True)
            return PowerResetResult(state="on")

        @activity.defn(name=SET_POWER_STATE_ACTIVITY_NAME)
        async def set_power_state(params: SetPowerStateParam) -> None:
            calls["set_power_state"].append(True)
            return

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[DeployWorkflow],
                activities=[
                    set_node_status,
                    get_boot_order,
                    set_power_state,
                    power_query,
                    power_cycle,
                    power_on,
                    power_off,
                    power_reset,
                ],
            ) as worker:
                wf = await env.client.start_workflow(
                    DEPLOY_WORKFLOW_NAME,
                    DeployParam(
                        system_id=machine["system_id"],
                        ephemeral_deploy=True,
                        can_set_boot_order=False,
                        task_queue=worker.task_queue,
                        power_params=PowerParam(
                            system_id=machine["system_id"],
                            driver_type=bmc["power_type"],
                            driver_opts=bmc["power_parameters"],
                            task_queue=worker.task_queue,
                            is_dpu=machine["is_dpu"],
                        ),
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    await wf.describe()
                ).status == WorkflowExecutionStatus.RUNNING

                await env.sleep(duration=timedelta(seconds=5))
                await wf.signal("netboot-finished")
                await env.sleep(duration=timedelta(seconds=5))
                await wf.signal("deployed-os-ready")

                await wf.result()

                assert len(calls["set_node_status"]) == 0
                assert len(calls["get_boot_order"]) == 0
                assert len(calls["power_query"]) == 1
                assert len(calls["power_on"]) == 1
                assert len(calls["power_cycle"]) == 0
                assert len(calls["set_power_state"]) == 1
                assert len(calls["power_reset"]) == 0

    async def test_deploy_workflow_set_boot_order(
        self,
        fixture: Fixture,
        db_connection: AsyncConnection,
        db: Database,
    ) -> None:
        bmc = await create_test_bmc_entry(fixture)
        machine = await create_test_machine_entry(fixture, bmc_id=bmc["id"])
        subnet = await create_test_subnet_entry(fixture)
        [ip] = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        boot_iface = await create_test_interface_dict(
            fixture, node=machine, ips=[ip]
        )
        boot_disk = await create_test_blockdevice_entry(fixture, node=machine)

        calls = defaultdict(list)

        @activity.defn(name=SET_NODE_STATUS_ACTIVITY_NAME)
        async def set_node_status(params: SetNodeStatusParam) -> None:
            calls["set_node_status"].append(True)

        @activity.defn(name=GET_BOOT_ORDER_ACTIVITY_NAME)
        async def get_boot_order(
            params: GetBootOrderParam,
        ) -> GetBootOrderResult:
            calls["get_boot_order"].append(True)
            order = []
            for link in boot_iface["links"]:
                link["ip"] = str(link["ip"])
            if params.netboot:
                order = [boot_iface, boot_disk]
            else:
                order = [boot_disk, boot_iface]
            return GetBootOrderResult(
                system_id=machine["system_id"],
                order=[_stringify_datetime_fields(dev) for dev in order],
            )

        @activity.defn(name=POWER_QUERY_ACTIVITY_NAME)
        async def power_query(params: PowerQueryParam) -> PowerQueryResult:
            calls["power_query"].append(True)
            return PowerQueryResult(state="off")

        @activity.defn(name=POWER_CYCLE_ACTIVITY_NAME)
        async def power_cycle(params: PowerCycleParam) -> PowerCycleResult:
            calls["power_cycle"].append(True)
            return PowerCycleResult(state="on")

        @activity.defn(name=POWER_ON_ACTIVITY_NAME)
        async def power_on(params: PowerOnParam) -> PowerOnResult:
            calls["power_on"].append(True)
            return PowerOnResult(state="on")

        @activity.defn(name=POWER_OFF_ACTIVITY_NAME)
        async def power_off(params: PowerOffParam) -> PowerOffResult:
            calls["power_off"].append(True)
            return PowerOffResult(state="off")

        @activity.defn(name=POWER_RESET_ACTIVITY_NAME)
        async def power_reset(params: PowerResetParam) -> PowerResetResult:
            calls["power_reset"].append(True)
            return PowerResetResult(state="on")

        @activity.defn(name=SET_BOOT_ORDER_ACTIVITY_NAME)
        async def set_boot_order(params: SetBootOrderParam) -> None:
            calls["set_boot_order"].append(True)
            return

        @activity.defn(name=SET_POWER_STATE_ACTIVITY_NAME)
        async def set_power_state(params: SetPowerStateParam) -> None:
            calls["set_power_state"].append(True)
            return

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[DeployWorkflow],
                activities=[
                    set_node_status,
                    get_boot_order,
                    set_boot_order,
                    set_power_state,
                    power_query,
                    power_cycle,
                    power_on,
                    power_off,
                    power_reset,
                ],
            ) as worker:
                wf = await env.client.start_workflow(
                    DEPLOY_WORKFLOW_NAME,
                    DeployParam(
                        system_id=machine["system_id"],
                        ephemeral_deploy=False,
                        can_set_boot_order=True,
                        task_queue=worker.task_queue,
                        power_params=PowerParam(
                            system_id=machine["system_id"],
                            driver_type=bmc["power_type"],
                            driver_opts=bmc["power_parameters"],
                            task_queue=worker.task_queue,
                            is_dpu=machine["is_dpu"],
                        ),
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    await wf.describe()
                ).status == WorkflowExecutionStatus.RUNNING

                await env.sleep(duration=timedelta(seconds=5))
                await wf.signal("netboot-finished")
                await env.sleep(duration=timedelta(seconds=5))
                await wf.signal("deployed-os-ready")
                await env.sleep(duration=timedelta(seconds=5))

                await wf.result()

                assert len(calls["set_node_status"]) == 0
                assert len(calls["get_boot_order"]) == 2
                assert len(calls["set_boot_order"]) == 2
                # 1 deploy-start query + CONFIRM_POWERED_ON_MAX_ATTEMPTS
                # confirm polls after the switch-to-local-boot power-on. The
                # mocked query never reports "on", so the confirm loop runs to
                # exhaustion; its settle/debounce logic is covered in
                # TestConfirmPoweredOn.
                assert (
                    len(calls["power_query"])
                    == 1 + CONFIRM_POWERED_ON_MAX_ATTEMPTS
                )
                # Two power-ons: the initial deploy start, plus the
                # MAAS-driven power-on after switching the boot device to
                # disk (power off -> set boot order -> power on).
                assert len(calls["power_on"]) == 2
                assert len(calls["power_off"]) == 1
                assert len(calls["power_cycle"]) == 0
                # deploy-start persist + one confirm-loop persist.
                assert len(calls["set_power_state"]) == 2
                assert len(calls["power_reset"]) == 0

    async def test_deploy_workflow_ephemeral_sets_network_boot_order(
        self,
        fixture: Fixture,
        db_connection: AsyncConnection,
        db: Database,
    ) -> None:
        bmc = await create_test_bmc_entry(fixture)
        machine = await create_test_machine_entry(fixture, bmc_id=bmc["id"])
        subnet = await create_test_subnet_entry(fixture)
        [ip] = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        boot_iface = await create_test_interface_dict(
            fixture, node=machine, ips=[ip]
        )
        boot_disk = await create_test_blockdevice_entry(fixture, node=machine)

        calls = defaultdict(list)

        @activity.defn(name=SET_NODE_STATUS_ACTIVITY_NAME)
        async def set_node_status(params: SetNodeStatusParam) -> None:
            calls["set_node_status"].append(True)

        @activity.defn(name=GET_BOOT_ORDER_ACTIVITY_NAME)
        async def get_boot_order(
            params: GetBootOrderParam,
        ) -> GetBootOrderResult:
            calls["get_boot_order"].append(params.netboot)
            for link in boot_iface["links"]:
                link["ip"] = str(link["ip"])
            if params.netboot:
                order = [boot_iface, boot_disk]
            else:
                order = [boot_disk, boot_iface]
            return GetBootOrderResult(
                system_id=machine["system_id"],
                order=[_stringify_datetime_fields(dev) for dev in order],
            )

        @activity.defn(name=POWER_QUERY_ACTIVITY_NAME)
        async def power_query(params: PowerQueryParam) -> PowerQueryResult:
            calls["power_query"].append(True)
            return PowerQueryResult(state="off")

        @activity.defn(name=POWER_CYCLE_ACTIVITY_NAME)
        async def power_cycle(params: PowerCycleParam) -> PowerCycleResult:
            calls["power_cycle"].append(True)
            return PowerCycleResult(state="on")

        @activity.defn(name=POWER_ON_ACTIVITY_NAME)
        async def power_on(params: PowerOnParam) -> PowerOnResult:
            calls["power_on"].append(True)
            return PowerOnResult(state="on")

        @activity.defn(name=POWER_OFF_ACTIVITY_NAME)
        async def power_off(params: PowerOffParam) -> PowerOffResult:
            calls["power_off"].append(True)
            return PowerOffResult(state="off")

        @activity.defn(name=POWER_RESET_ACTIVITY_NAME)
        async def power_reset(params: PowerResetParam) -> PowerResetResult:
            calls["power_reset"].append(True)
            return PowerResetResult(state="on")

        @activity.defn(name=SET_BOOT_ORDER_ACTIVITY_NAME)
        async def set_boot_order(params: SetBootOrderParam) -> None:
            calls["set_boot_order"].append(True)
            return

        @activity.defn(name=SET_POWER_STATE_ACTIVITY_NAME)
        async def set_power_state(params: SetPowerStateParam) -> None:
            calls["set_power_state"].append(True)
            return

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[DeployWorkflow],
                activities=[
                    set_node_status,
                    get_boot_order,
                    set_boot_order,
                    set_power_state,
                    power_query,
                    power_cycle,
                    power_on,
                    power_off,
                    power_reset,
                ],
            ) as worker:
                wf = await env.client.start_workflow(
                    DEPLOY_WORKFLOW_NAME,
                    DeployParam(
                        system_id=machine["system_id"],
                        ephemeral_deploy=True,
                        can_set_boot_order=True,
                        task_queue=worker.task_queue,
                        power_params=PowerParam(
                            system_id=machine["system_id"],
                            driver_type=bmc["power_type"],
                            driver_opts=bmc["power_parameters"],
                            task_queue=worker.task_queue,
                            is_dpu=machine["is_dpu"],
                        ),
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    await wf.describe()
                ).status == WorkflowExecutionStatus.RUNNING

                await env.sleep(duration=timedelta(seconds=5))
                await wf.signal("deployed-os-ready")
                await env.sleep(duration=timedelta(seconds=5))

                await wf.result()

                # Only the network boot order is armed at the start; an
                # ephemeral deploy never switches to local disk boot.
                assert calls["get_boot_order"] == [True]
                assert len(calls["set_boot_order"]) == 1
                assert len(calls["power_query"]) == 1
                assert len(calls["power_on"]) == 1

    async def test_deploy_workflow_manual_power_skips_power_actions(
        self,
        fixture: Fixture,
        temporal_calls: TemporalCalls,
        worker_test_interceptor,
    ) -> None:
        bmc = await create_test_bmc_entry(fixture, power_type="manual")
        machine = await create_test_machine_entry(fixture, bmc_id=bmc["id"])

        @activity.defn(name=SET_NODE_STATUS_ACTIVITY_NAME)
        async def set_node_status(params: SetNodeStatusParam) -> None:
            return

        @activity.defn(name=GET_BOOT_ORDER_ACTIVITY_NAME)
        async def get_boot_order(
            params: GetBootOrderParam,
        ) -> GetBootOrderResult:
            return GetBootOrderResult(
                system_id=machine["system_id"],
                order=[],
            )

        @activity.defn(name=POWER_QUERY_ACTIVITY_NAME)
        async def power_query(params: PowerQueryParam) -> PowerQueryResult:
            return PowerQueryResult(state="unknown")

        @activity.defn(name=POWER_CYCLE_ACTIVITY_NAME)
        async def power_cycle(params: PowerCycleParam) -> PowerCycleResult:
            return PowerCycleResult(state="unknown")

        @activity.defn(name=POWER_ON_ACTIVITY_NAME)
        async def power_on(params: PowerOnParam) -> PowerOnResult:
            return PowerOnResult(state="unknown")

        @activity.defn(name=POWER_OFF_ACTIVITY_NAME)
        async def power_off(params: PowerOffParam) -> PowerOffResult:
            return PowerOffResult(state="unknown")

        @activity.defn(name=POWER_RESET_ACTIVITY_NAME)
        async def power_reset(params: PowerResetParam) -> PowerResetResult:
            return PowerResetResult(state="unknown")

        @activity.defn(name=SET_POWER_STATE_ACTIVITY_NAME)
        async def set_power_state(params: SetPowerStateParam) -> None:
            return

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[DeployWorkflow],
                activities=[
                    set_node_status,
                    get_boot_order,
                    set_power_state,
                    power_query,
                    power_cycle,
                    power_on,
                    power_off,
                    power_reset,
                ],
                interceptors=[worker_test_interceptor],
            ) as worker:
                wf = await env.client.start_workflow(
                    DEPLOY_WORKFLOW_NAME,
                    DeployParam(
                        system_id=machine["system_id"],
                        ephemeral_deploy=False,
                        can_set_boot_order=False,
                        task_queue=worker.task_queue,
                        power_params=PowerParam(
                            system_id=machine["system_id"],
                            driver_type="manual",
                            driver_opts={},
                            task_queue="",
                            is_dpu=False,
                        ),
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    await wf.describe()
                ).status == WorkflowExecutionStatus.RUNNING

                await env.sleep(duration=timedelta(seconds=5))
                await wf.signal("netboot-finished")
                await env.sleep(duration=timedelta(seconds=5))
                await wf.signal("deployed-os-ready")
                await env.sleep(duration=timedelta(seconds=5))

                await wf.result()

                temporal_calls.assert_activity_calls([])


@pytest.mark.asyncio
class TestConfirmPoweredOn:
    """Unit tests for `DeployWorkflow._confirm_powered_on`.

    Drives the method directly with `workflow.execute_activity` and
    `asyncio.sleep` mocked, so the query sequence (and thus the settle and
    debounce behavior) can be scripted deterministically without a Temporal
    server.
    """

    def _params(self) -> DeployParam:
        return DeployParam(
            system_id="abc",
            ephemeral_deploy=False,
            can_set_boot_order=True,
            task_queue="agent:1",
            power_params=PowerParam(
                system_id="abc",
                driver_type="hmcz",
                driver_opts={},
                task_queue="agent:1",
                is_dpu=False,
            ),
        )

    async def _drive(
        self, mocker: MockerFixture, query_states: list[str]
    ) -> tuple[int, list[PowerState], AsyncMock]:
        """Run `_confirm_powered_on` against a scripted query sequence.

        Returns the number of power-query calls, the list of states persisted
        via SET_POWER_STATE, and the patched sleep mock. Once `query_states`
        is exhausted the last value is repeated, so callers can pad to
        `CONFIRM_POWERED_ON_MAX_ATTEMPTS` or let a terminal state persist.
        """
        states = iter(query_states)
        last = None
        query_calls = 0
        persisted: list[PowerState] = []

        def execute_activity(name, *args, **kwargs):
            nonlocal query_calls, last
            if name == POWER_QUERY_ACTIVITY_NAME:
                query_calls += 1
                try:
                    last = next(states)
                except StopIteration:
                    pass
                return {"state": last}
            if name == SET_POWER_STATE_ACTIVITY_NAME:
                persisted.append(args[0].state)
                return None
            raise AssertionError(f"unexpected activity: {name}")

        mocker.patch(
            "maastemporalworker.workflow.deploy.workflow.execute_activity",
            AsyncMock(side_effect=execute_activity),
        )
        sleep = AsyncMock()
        mocker.patch("maastemporalworker.workflow.deploy.asyncio.sleep", sleep)

        await DeployWorkflow()._confirm_powered_on(self._params())
        return query_calls, persisted, sleep

    async def test_settles_after_two_consecutive_on_readings(
        self, mocker: MockerFixture
    ) -> None:
        query_calls, persisted, sleep = await self._drive(mocker, ["on", "on"])

        assert query_calls == 2
        assert persisted == [PowerState.ON]
        assert sleep.await_count == 1

    async def test_persists_each_state_as_it_settles(
        self, mocker: MockerFixture
    ) -> None:
        query_calls, persisted, _ = await self._drive(
            mocker, ["off", "off", "unknown", "unknown", "on", "on"]
        )

        assert query_calls == 6
        assert persisted == [
            PowerState.OFF,
            PowerState.UNKNOWN,
            PowerState.ON,
        ]

    async def test_gives_up_after_max_attempts_when_never_on(
        self, mocker: MockerFixture
    ) -> None:
        query_calls, persisted, sleep = await self._drive(mocker, ["off"])

        assert query_calls == CONFIRM_POWERED_ON_MAX_ATTEMPTS
        assert persisted == [PowerState.OFF]
        assert sleep.await_count == CONFIRM_POWERED_ON_MAX_ATTEMPTS

    async def test_ignores_single_flaky_reading(
        self, mocker: MockerFixture
    ) -> None:
        # A one-off "on" seen on a single poll (not confirmed on the next)
        # must never be persisted.
        _, persisted, _ = await self._drive(
            mocker, ["off", "off", "on", "off"]
        )

        assert PowerState.ON not in persisted
        assert persisted == [PowerState.OFF]
