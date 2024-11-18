from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any
import uuid

import pytest
from pytest_mock import MockerFixture
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq
from temporalio import activity
from temporalio.client import WorkflowExecutionStatus
from temporalio.service import RPCError
from temporalio.testing import ActivityEnvironment, WorkflowEnvironment
from temporalio.worker import Worker

from maascommon.enums.node import NodeStatus
from maascommon.workflows.deploy import (
    DEPLOY_N_WORKFLOW_NAME,
    DEPLOY_WORKFLOW_NAME,
)
from maascommon.workflows.power import (
    PowerCycleParam,
    PowerOffParam,
    PowerOnParam,
    PowerParam,
    PowerQueryParam,
)
from maasservicelayer.db import Database
from maasservicelayer.db.tables import NodeTable
from maasservicelayer.models.nodes import Node
from maasservicelayer.services import CacheForServices
from maastemporalworker.workflow.deploy import (
    DeployActivity,
    DeployNParam,
    DeployNWorkflow,
    DeployParam,
    DeployWorkflow,
    GET_BOOT_ORDER_ACTIVITY_NAME,
    GetBootOrderParam,
    GetBootOrderResult,
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
    PowerCycleResult,
    PowerOffResult,
    PowerOnResult,
    PowerQueryResult,
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


@pytest.mark.asyncio
class TestDeployActivity:
    async def test_set_node_status(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ):
        node = await create_test_machine_entry(fixture, status=NodeStatus.NEW)
        env = ActivityEnvironment()
        services_cache = CacheForServices()
        activities = DeployActivity(
            db, services_cache, connection=db_connection
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
            db, services_cache, connection=db_connection
        )
        env = ActivityEnvironment()
        boot_order = await env.run(
            activities.get_boot_order,
            GetBootOrderParam(system_id=machine["system_id"], netboot=True),
        )

        assert boot_order.order == [
            _stringify_datetime_fields(dev)
            for dev in [boot_iface, other_iface, boot_disk, other_disk]
        ]

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
            db, services_cache, connection=db_connection
        )
        env = ActivityEnvironment()
        boot_order = await env.run(
            activities.get_boot_order,
            GetBootOrderParam(system_id=machine["system_id"], netboot=False),
        )
        assert boot_order.order == [
            _stringify_datetime_fields(dev)
            for dev in [boot_disk, other_disk, boot_iface, other_iface]
        ]


@pytest.mark.asyncio
class TestDeployNWorkflow:
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

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[DeployNWorkflow, DeployWorkflow],
                activities=[
                    set_node_status,
                    get_boot_order,
                    power_query,
                    power_cycle,
                    power_on,
                    power_off,
                ],
            ) as worker:
                wf = await env.client.start_workflow(
                    DEPLOY_N_WORKFLOW_NAME,
                    DeployNParam(
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
                                ),
                            ),
                        ],
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    WorkflowExecutionStatus.RUNNING
                    == (await wf.describe()).status
                )

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

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[DeployNWorkflow, DeployWorkflow],
                activities=[
                    set_node_status,
                    get_boot_order,
                    power_query,
                    power_cycle,
                    power_on,
                    power_off,
                ],
            ) as worker:
                wf = await env.client.start_workflow(
                    DEPLOY_N_WORKFLOW_NAME,
                    DeployNParam(
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
                                ),
                            ),
                        ],
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    WorkflowExecutionStatus.RUNNING
                    == (await wf.describe()).status
                )

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

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[DeployNWorkflow, DeployWorkflow],
                activities=[
                    set_node_status,
                    get_boot_order,
                    power_query,
                    power_cycle,
                    power_on,
                    power_off,
                ],
            ) as worker:
                wf = await env.client.start_workflow(
                    DEPLOY_N_WORKFLOW_NAME,
                    DeployNParam(
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
                                ),
                            )
                            for machine in machines
                        ],
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    WorkflowExecutionStatus.RUNNING
                    == (await wf.describe()).status
                )

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

        @activity.defn(name=SET_BOOT_ORDER_ACTIVITY_NAME)
        async def set_boot_order(params: SetBootOrderParam) -> None:
            calls["set_boot_order"].append(True)

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[DeployNWorkflow, DeployWorkflow],
                activities=[
                    set_node_status,
                    get_boot_order,
                    set_boot_order,
                    power_query,
                    power_cycle,
                    power_on,
                    power_off,
                ],
            ) as worker:
                wf = await env.client.start_workflow(
                    DEPLOY_N_WORKFLOW_NAME,
                    DeployNParam(
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
                                ),
                            )
                            for i, machine in enumerate(machines)
                        ],
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    WorkflowExecutionStatus.RUNNING
                    == (await wf.describe()).status
                )

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
                assert len(calls["get_boot_order"]) == 1
                assert len(calls["power_query"]) == 3
                assert len(calls["power_on"]) == 3
                assert len(calls["power_cycle"]) == 0

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

        @activity.defn(name=SET_BOOT_ORDER_ACTIVITY_NAME)
        async def set_boot_order(params: SetBootOrderParam) -> None:
            calls["set_boot_order"].append(True)
            return

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[DeployNWorkflow, DeployWorkflow],
                activities=[
                    set_node_status,
                    get_boot_order,
                    set_boot_order,
                    power_query,
                    power_cycle,
                    power_on,
                    power_off,
                ],
            ) as worker:
                wf = await env.client.start_workflow(
                    DEPLOY_N_WORKFLOW_NAME,
                    DeployNParam(
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
                                ),
                            )
                            for i, machine in enumerate(machines)
                        ],
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    WorkflowExecutionStatus.RUNNING
                    == (await wf.describe()).status
                )

                await env.sleep(duration=timedelta(seconds=5))

                for i, machine in enumerate(machines):
                    deploy_wf = env.client.get_workflow_handle(
                        f"deploy:{machine['system_id']}"
                    )
                    await deploy_wf.signal("netboot-finished")
                    await env.sleep(duration=timedelta(seconds=1))
                    if i != 2:
                        await deploy_wf.signal("deployed-os-ready")

                await env.sleep(duration=timedelta(seconds=5))

                await wf.result()

                assert len(calls["set_node_status"]) == 3
                assert len(calls["get_boot_order"]) == 0
                assert len(calls["power_query"]) == 3
                assert len(calls["power_on"]) == 3
                assert len(calls["power_cycle"]) == 0


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

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[DeployWorkflow],
                activities=[
                    set_node_status,
                    get_boot_order,
                    power_query,
                    power_cycle,
                    power_on,
                    power_off,
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
                        ),
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    WorkflowExecutionStatus.RUNNING
                    == (await wf.describe()).status
                )

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
                        ),
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    WorkflowExecutionStatus.RUNNING
                    == (await wf.describe()).status
                )

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

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[DeployWorkflow],
                activities=[
                    set_node_status,
                    get_boot_order,
                    power_query,
                    power_cycle,
                    power_on,
                    power_off,
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
                        ),
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    WorkflowExecutionStatus.RUNNING
                    == (await wf.describe()).status
                )

                await env.sleep(duration=timedelta(seconds=5))
                await wf.signal("netboot-finished")
                await env.sleep(duration=timedelta(seconds=5))

                await wf.result()

                assert len(calls["set_node_status"]) == 0
                assert len(calls["get_boot_order"]) == 0
                assert len(calls["power_query"]) == 1
                assert len(calls["power_on"]) == 1
                assert len(calls["power_cycle"]) == 0

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

        @activity.defn(name=SET_BOOT_ORDER_ACTIVITY_NAME)
        async def set_boot_order(params: SetBootOrderParam) -> None:
            calls["set_boot_order"].append(True)
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
                    power_query,
                    power_cycle,
                    power_on,
                    power_off,
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
                        ),
                    ),
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

                assert (
                    WorkflowExecutionStatus.RUNNING
                    == (await wf.describe()).status
                )

                await env.sleep(duration=timedelta(seconds=5))
                await wf.signal("netboot-finished")
                await env.sleep(duration=timedelta(seconds=5))
                await wf.signal("deployed-os-ready")
                await env.sleep(duration=timedelta(seconds=5))

                await wf.result()

                assert len(calls["set_node_status"]) == 0
                assert len(calls["get_boot_order"]) == 1
                assert len(calls["set_boot_order"]) == 1
                assert len(calls["power_query"]) == 1
                assert len(calls["power_on"]) == 1
                assert len(calls["power_cycle"]) == 0
