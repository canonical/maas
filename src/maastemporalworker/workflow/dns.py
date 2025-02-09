# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity, workflow

from maascommon.workflows.dns import (
    CONFIGURE_DNS_WORKFLOW_NAME,
    ConfigureDNSParam,
)
from maastemporalworker.workflow.activity import ActivityBase

GET_CHANGES_SINCE_CURRENT_SERIAL_TIMEOUT = timedelta(minutes=5)
GET_REGION_CONTROLLERS_TIMEOUT = timedelta(minutes=5)
FULL_RELOAD_DNS_CONFIGURATION_TIMEOUT = timedelta(minutes=5)
DYNAMIC_UPDATE_DNS_CONFIGURATION_TIMEOUT = timedelta(minutes=5)
CHECK_SERIAL_UPDATE_TIMEOUT = timedelta(minutes=5)
DNS_RETRY_TIMEOUT = timedelta(minutes=5)


# Activities names
GET_CHANGES_SINCE_CURRENT_SERIAL_NAME = "get-changes-since-current-serial"
GET_REGION_CONTROLLERS_NAME = "get-region-controllers"
FULL_RELOAD_DNS_CONFIGURATION_NAME = "full-reload-dns-configuration"
DYNAMIC_UPDATE_DNS_CONFIGURATION_NAME = "dynamic-update-dns-configuration"
CHECK_SERIAL_UPDATE_NAME = "check-serial-update"


@dataclass
class DNSPublication:
    serial: int
    source: str
    update: str


@dataclass
class SerialChangesResult:
    updates: list[DNSPublication]


@dataclass
class RegionControllersResult:
    region_controller_system_ids: list[str]


@dataclass
class DynamicUpdateParam:
    new_serial: int
    updates: list[DNSPublication]


@dataclass
class DNSUpdateResult:
    serial: int


@dataclass
class CheckSerialUpdateParam:
    serial: int


def get_task_queue_for_update(system_id: str) -> str:
    return f"region:{system_id}"


class DNSConfigActivity(ActivityBase):
    @activity.defn(name=GET_CHANGES_SINCE_CURRENT_SERIAL_NAME)
    async def get_changes_since_current_serial(
        self,
    ) -> SerialChangesResult | None:
        # TODO determine current serial and fetch DNSPublications from there up to latest
        return None

    @activity.defn(name=GET_REGION_CONTROLLERS_NAME)
    async def get_region_controllers(self) -> RegionControllersResult:
        # TODO fetch all region controllers for DNS updates
        return RegionControllersResult(RegionControllers=[])

    @activity.defn(name=FULL_RELOAD_DNS_CONFIGURATION_NAME)
    async def full_reload_dns_configuration(self) -> DNSUpdateResult:
        # TODO fetch all DNS objects and apply to DNS configuration
        return DNSUpdateResult(serial=1)

    @activity.defn(name=DYNAMIC_UPDATE_DNS_CONFIGURATION_NAME)
    async def dynamic_update_dns_configuration(
        self, updates: DynamicUpdateParam
    ) -> DNSUpdateResult:
        # TODO apply dynamic updates
        return DNSUpdateResult(serial=1)

    @activity.defn(name=CHECK_SERIAL_UPDATE_NAME)
    async def check_serial_update(
        self, serial: CheckSerialUpdateParam
    ) -> None:
        pass


@workflow.defn(name=CONFIGURE_DNS_WORKFLOW_NAME, sandboxed=False)
class ConfigureDNSWorkflow:
    @workflow.run
    async def run(self, param: ConfigureDNSParam) -> None:
        updates = None
        need_full_reload = param.need_full_reload

        if not need_full_reload:
            updates = await workflow.execute_activity(
                GET_CHANGES_SINCE_CURRENT_SERIAL_NAME,
                start_to_close_timeout=GET_CHANGES_SINCE_CURRENT_SERIAL_TIMEOUT,
            )

            for publication in updates["updates"]:
                if publication["update"] == "RELOAD":
                    need_full_reload = True

        region_controllers = await workflow.execute_activity(
            GET_REGION_CONTROLLERS_NAME,
            start_to_close_timeout=GET_REGION_CONTROLLERS_TIMEOUT,
        )

        for region_controller_system_id in region_controllers[
            "region_controller_system_ids"
        ]:
            if need_full_reload:
                new_serial = await workflow.execute_activity(
                    FULL_RELOAD_DNS_CONFIGURATION_NAME,
                    start_to_close_timeout=FULL_RELOAD_DNS_CONFIGURATION_TIMEOUT,
                    task_queue=get_task_queue_for_update(
                        region_controller_system_id
                    ),
                )
            elif updates:
                new_serial = await workflow.execute_activity(
                    DYNAMIC_UPDATE_DNS_CONFIGURATION_NAME,
                    DynamicUpdateParam(
                        new_serial=updates["updates"][-1]["serial"],
                        updates=updates["updates"],
                    ),
                    start_to_close_timeout=DYNAMIC_UPDATE_DNS_CONFIGURATION_TIMEOUT,
                    task_queue=get_task_queue_for_update(
                        region_controller_system_id
                    ),
                )

            await workflow.execute_activity(
                CHECK_SERIAL_UPDATE_NAME,
                CheckSerialUpdateParam(serial=new_serial["serial"]),
                start_to_close_timeout=CHECK_SERIAL_UPDATE_TIMEOUT,
                task_queue=get_task_queue_for_update(
                    region_controller_system_id
                ),
            )
