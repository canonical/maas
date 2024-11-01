# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Result, select
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import CancelledError, ChildWorkflowError

from maascommon.enums.node import NodeStatus
from maasserver.workflow.power import (
    PowerCycleParam,
    PowerOnParam,
    PowerParam,
    PowerQueryParam,
)
from maasservicelayer.db.repositories.nodes import (
    NodeCreateOrUpdateResourceBuilder,
)
from maasservicelayer.db.tables import (
    BlockDeviceTable,
    InterfaceIPAddressTable,
    InterfaceTable,
    NodeTable,
    PhysicalBlockDeviceTable,
    StaticIPAddressTable,
    VirtualBlockDeviceTable,
)
from maastemporalworker.workflow.activity import ActivityBase

DEFAULT_DEPLOY_ACTIVITY_TIMEOUT = timedelta(seconds=30)
DEFAULT_DEPLOY_RETRY_TIMEOUT = timedelta(seconds=60)


class InvalidMachineStateException(Exception):
    pass


@dataclass
class DeployParam:
    system_id: str
    ephemeral_deploy: bool
    can_set_boot_order: bool
    task_queue: str
    power_params: PowerParam


@dataclass
class DeployNParam:
    params: list[DeployParam]


@dataclass
class SetNodeStatusParam:
    system_id: str
    status: NodeStatus


@dataclass
class GetBootOrderParam:
    system_id: str
    netboot: bool


@dataclass
class GetBootOrderResult:
    system_id: str
    order: list[dict[str, Any]]


@dataclass
class SetBootOrderParam:
    system_id: str
    power_params: PowerParam
    order: list[dict[str, Any]]


@dataclass
class DeployResult:
    system_id: str
    success: bool


class DeployActivity(ActivityBase):
    @activity.defn(name="set-node-status")
    async def set_node_status(self, params: SetNodeStatusParam) -> None:
        async with self.start_transaction() as services:
            resource = (
                NodeCreateOrUpdateResourceBuilder()
                .with_status(status=params.status)
                .build()
            )
            await services.nodes.update_by_system_id(
                system_id=params.system_id, resource=resource
            )

    def _single_result_to_dict(self, result: Result) -> dict[str, Any]:
        obj = {}
        val = result.one_or_none()
        if val:
            for i, col in enumerate(result.keys()):
                obj[col] = val[i]
        return obj

    def _result_to_list(self, result: Result) -> list[dict[str, Any]]:
        rows = []
        for res in result.all():
            obj = {}
            for i, col in enumerate(result.keys()):
                obj[col] = res[i]
            rows.append(obj)
        return rows

    async def _get_ips_for_iface(
        self, tx: AsyncConnection, iface: dict[str, Any]
    ) -> list[dict[str, Any]]:
        ip_stmt = (
            select(StaticIPAddressTable)
            .select_from(StaticIPAddressTable)
            .join(
                InterfaceIPAddressTable,
                InterfaceIPAddressTable.c.staticipaddress_id
                == StaticIPAddressTable.c.id,
            )
            .filter(InterfaceIPAddressTable.c.interface_id == iface["id"])
        )
        ip_result = await tx.execute(ip_stmt)
        result = self._result_to_list(ip_result)
        for r in result:
            r["ip"] = str(r["ip"])
        return result

    async def _get_boot_iface(
        self, tx: AsyncConnection, system_id: str
    ) -> dict[str, Any]:
        boot_iface_stmt = (
            select(InterfaceTable)
            .select_from(NodeTable)
            .join(
                InterfaceTable,
                InterfaceTable.c.id == NodeTable.c.boot_interface_id,
            )
            .filter(NodeTable.c.system_id == system_id)
        )
        boot_iface_result = await tx.execute(boot_iface_stmt)
        boot_iface = self._single_result_to_dict(boot_iface_result)
        boot_iface["links"] = await self._get_ips_for_iface(tx, boot_iface)
        return boot_iface

    async def _get_boot_disk(
        self, tx: AsyncConnection, system_id: str
    ) -> dict[str, Any]:
        boot_disk_stmt = (
            select(BlockDeviceTable)
            .select_from(NodeTable)
            .join(
                BlockDeviceTable,
                BlockDeviceTable.c.id == NodeTable.c.boot_disk_id,
            )
            .join(
                PhysicalBlockDeviceTable,
                PhysicalBlockDeviceTable.c.blockdevice_ptr_id
                == BlockDeviceTable.c.id,
            )
            .join(
                VirtualBlockDeviceTable,
                VirtualBlockDeviceTable.c.blockdevice_ptr_id
                == BlockDeviceTable.c.id,
            )
            .filter(NodeTable.c.system_id == system_id)
        )
        boot_disk_result = await tx.execute(boot_disk_stmt)
        boot_disk = self._single_result_to_dict(boot_disk_result)
        actual_instance_id = boot_disk.get("actual_instance_id")
        if actual_instance_id:
            actual_stmt = (
                select("*")
                .select_from(BlockDeviceTable)
                .filter(id == actual_instance_id)
            )
            actual_result = await tx.execute(actual_stmt)
            boot_disk = self._single_result_to_dict(actual_result)
        return boot_disk

    def _stringify_datetime_fields(
        self, obj: dict[str, Any]
    ) -> dict[str, Any]:
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

    @activity.defn(name="get-boot-order")
    async def get_boot_order(
        self, params: GetBootOrderParam
    ) -> GetBootOrderResult:
        async with self._start_transaction() as tx:
            boot_iface = await self._get_boot_iface(tx, params.system_id)
            boot_disk = await self._get_boot_disk(tx, params.system_id)

            iface_stmt = (
                select(InterfaceTable)
                .select_from(NodeTable)
                .join(
                    InterfaceTable,
                    InterfaceTable.c.node_config_id
                    == NodeTable.c.current_config_id,
                )
                .filter(
                    NodeTable.c.system_id == params.system_id,
                    InterfaceTable.c.id != boot_iface.get("id"),
                )
            )
            ifaces_result = await tx.execute(iface_stmt)
            ifaces = self._result_to_list(ifaces_result)
            for iface in ifaces:
                iface["links"] = await self._get_ips_for_iface(tx, iface)

            if boot_iface:
                ifaces = [boot_iface] + ifaces

            block_dev_stmt = (
                select(BlockDeviceTable)
                .select_from(NodeTable)
                .join(
                    BlockDeviceTable,
                    BlockDeviceTable.c.node_config_id
                    == NodeTable.c.current_config_id,
                )
                .filter(
                    NodeTable.c.system_id == params.system_id,
                    BlockDeviceTable.c.id != boot_disk.get("id"),
                )
            )
            block_dev_result = await tx.execute(block_dev_stmt)
            block_devs = self._result_to_list(block_dev_result)
            if boot_disk:
                block_devs = [boot_disk] + block_devs

            order = []
            if params.netboot:
                order = ifaces + block_devs
            else:
                order = block_devs + ifaces
            return GetBootOrderResult(
                system_id=params.system_id,
                order=[self._stringify_datetime_fields(dev) for dev in order],
            )


@workflow.defn(name="deploy-n", sandboxed=False)
class DeployNWorkflow:
    @workflow.run
    async def run(self, params: DeployNParam) -> None:
        workflow.logger.info("starting bulk deployment job...")

        child_workflows = []
        for param in params.params:
            wf = await workflow.start_child_workflow(
                "deploy",
                param,
                id=f"deploy:{param.system_id}",
                task_queue=param.task_queue,
                retry_policy=RetryPolicy(
                    maximum_interval=DEFAULT_DEPLOY_RETRY_TIMEOUT
                ),
            )
            child_workflows.append((param.system_id, wf))

        for system_id, wf in child_workflows:
            status = None

            try:
                result = await wf
            except (CancelledError, asyncio.CancelledError):
                continue
            except ChildWorkflowError as e:
                if isinstance(e.cause, CancelledError):
                    continue

                status = NodeStatus.FAILED_DEPLOYMENT
            except Exception:  # TODO handle failed workflow more specifically
                status = NodeStatus.FAILED_DEPLOYMENT
            else:
                status = (
                    NodeStatus.DEPLOYED
                    if result["success"]
                    else NodeStatus.FAILED_DEPLOYMENT
                )

            await workflow.execute_activity(
                "set-node-status",
                SetNodeStatusParam(
                    system_id=system_id,
                    status=status,
                ),
                task_queue="region",
                start_to_close_timeout=DEFAULT_DEPLOY_ACTIVITY_TIMEOUT,
                retry_policy=RetryPolicy(
                    maximum_interval=DEFAULT_DEPLOY_RETRY_TIMEOUT
                ),
            )
        workflow.logger.info("finished bulk deployment job.")


@workflow.defn(name="deploy", sandboxed=False)
class DeployWorkflow:
    def __init__(self) -> None:
        self._has_netbooted = False
        self._deployed_os_ready = False

    @workflow.signal(name="netboot-finished")
    async def netboot_signal(self, *args: list[Any]) -> None:
        self._has_netbooted = True

    @workflow.signal(name="deployed-os-ready")
    async def deployed_os_signal(self, *args: list[Any]) -> None:
        self._deployed_os_ready = True

    async def _start_deployment(self, params: DeployParam) -> None:
        result = await workflow.execute_activity(
            "power-query",
            PowerQueryParam(
                system_id=params.power_params.system_id,
                driver_type=params.power_params.driver_type,
                driver_opts=params.power_params.driver_opts,
                task_queue=params.power_params.task_queue,
            ),
            task_queue=params.power_params.task_queue,
            start_to_close_timeout=DEFAULT_DEPLOY_ACTIVITY_TIMEOUT,
            retry_policy=RetryPolicy(
                maximum_interval=DEFAULT_DEPLOY_RETRY_TIMEOUT
            ),
        )

        if result["state"] == "on":
            await workflow.execute_activity(
                "power-cycle",
                PowerCycleParam(
                    system_id=params.power_params.system_id,
                    driver_type=params.power_params.driver_type,
                    driver_opts=params.power_params.driver_opts,
                    task_queue=params.power_params.task_queue,
                ),
                task_queue=params.power_params.task_queue,
                start_to_close_timeout=DEFAULT_DEPLOY_ACTIVITY_TIMEOUT,
                retry_policy=RetryPolicy(
                    maximum_interval=DEFAULT_DEPLOY_RETRY_TIMEOUT
                ),
            )
        else:
            await workflow.execute_activity(
                "power-on",
                PowerOnParam(
                    system_id=params.power_params.system_id,
                    driver_type=params.power_params.driver_type,
                    driver_opts=params.power_params.driver_opts,
                    task_queue=params.power_params.task_queue,
                ),
                task_queue=params.power_params.task_queue,
                start_to_close_timeout=DEFAULT_DEPLOY_ACTIVITY_TIMEOUT,
                retry_policy=RetryPolicy(
                    maximum_interval=DEFAULT_DEPLOY_RETRY_TIMEOUT,
                ),
            )

    async def _set_boot_order(self, params: DeployParam) -> None:
        boot_order = await workflow.execute_activity(
            "get-boot-order",
            GetBootOrderParam(
                system_id=params.system_id,
                netboot=False,
            ),
            task_queue="region",
            start_to_close_timeout=DEFAULT_DEPLOY_ACTIVITY_TIMEOUT,
            retry_policy=RetryPolicy(
                maximum_interval=DEFAULT_DEPLOY_RETRY_TIMEOUT
            ),
        )
        if boot_order:
            await workflow.execute_activity(
                "set-boot-order",
                SetBootOrderParam(
                    system_id=params.system_id,
                    power_params=params.power_params,
                    order=boot_order["order"],
                ),
                task_queue=params.power_params.task_queue,
                start_to_close_timeout=DEFAULT_DEPLOY_ACTIVITY_TIMEOUT,
                retry_policy=RetryPolicy(
                    maximum_interval=DEFAULT_DEPLOY_RETRY_TIMEOUT
                ),
            )
        else:
            raise InvalidMachineStateException("no boot order found")

    @workflow.run
    async def run(self, params: DeployParam) -> DeployResult:
        workflow.logger.info(f"deploying {params.system_id}")

        await self._start_deployment(params)

        await workflow.wait_condition(lambda: self._has_netbooted)

        workflow.logger.debug(f"{params.system_id} has finished netboot")

        if not params.ephemeral_deploy:
            if params.can_set_boot_order:
                await self._set_boot_order(params)

            await workflow.wait_condition(lambda: self._deployed_os_ready)
            workflow.logger.debug(
                f"{params.system_id} has booted into deployed OS"
            )

        return DeployResult(system_id=params.system_id, success=True)
