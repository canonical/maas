from collections import defaultdict

import pytest
from pytest_mock import MockerFixture
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from maascommon.workflows.dns import (
    CONFIGURE_DNS_WORKFLOW_NAME,
    ConfigureDNSParam,
)
from maastemporalworker.workflow.dns import (
    CHECK_SERIAL_UPDATE_NAME,
    CheckSerialUpdateParam,
    ConfigureDNSWorkflow,
    DNSPublication,
    DNSUpdateResult,
    DYNAMIC_UPDATE_DNS_CONFIGURATION_NAME,
    DynamicUpdateParam,
    FULL_RELOAD_DNS_CONFIGURATION_NAME,
    GET_CHANGES_SINCE_CURRENT_SERIAL_NAME,
    GET_REGION_CONTROLLERS_NAME,
    RegionControllersResult,
    SerialChangesResult,
)


@pytest.mark.asyncio
class TestDNSConfigWorkflow:
    async def test_dns_config_workflow_full_reload(
        self, mocker: MockerFixture
    ):
        # TODO create DNSPublications, Domains and DNSResources for update

        mocker.patch(
            "maastemporalworker.workflow.dns.get_task_queue_for_update"
        ).return_value = "region"

        calls = defaultdict(list)

        @activity.defn(name=GET_CHANGES_SINCE_CURRENT_SERIAL_NAME)
        async def get_changes_since_current_serial() -> (
            SerialChangesResult | None
        ):
            calls[GET_CHANGES_SINCE_CURRENT_SERIAL_NAME].append(True)
            return None

        @activity.defn(name=GET_REGION_CONTROLLERS_NAME)
        async def get_region_controllers() -> RegionControllersResult:
            calls[GET_REGION_CONTROLLERS_NAME].append(True)
            return RegionControllersResult(
                region_controller_system_ids=["abc"]
            )

        @activity.defn(name=FULL_RELOAD_DNS_CONFIGURATION_NAME)
        async def full_reload_dns_configuration() -> DNSUpdateResult:
            calls[FULL_RELOAD_DNS_CONFIGURATION_NAME].append(True)
            return DNSUpdateResult(serial=1)

        @activity.defn(name=DYNAMIC_UPDATE_DNS_CONFIGURATION_NAME)
        async def dynamic_update_dns_configuration(
            param: DynamicUpdateParam,
        ) -> DNSUpdateResult:
            calls[DYNAMIC_UPDATE_DNS_CONFIGURATION_NAME].append(True)
            return DNSUpdateResult(serial=1)

        @activity.defn(name=CHECK_SERIAL_UPDATE_NAME)
        async def check_serial_update(serial: CheckSerialUpdateParam) -> None:
            calls[CHECK_SERIAL_UPDATE_NAME].append(True)

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[ConfigureDNSWorkflow],
                activities=[
                    get_changes_since_current_serial,
                    get_region_controllers,
                    full_reload_dns_configuration,
                    dynamic_update_dns_configuration,
                    check_serial_update,
                ],
            ) as worker:
                await env.client.execute_workflow(
                    CONFIGURE_DNS_WORKFLOW_NAME,
                    ConfigureDNSParam(need_full_reload=True),
                    id="configure-dns",
                    task_queue=worker.task_queue,
                )

                assert len(calls[GET_CHANGES_SINCE_CURRENT_SERIAL_NAME]) == 0
                assert len(calls[GET_REGION_CONTROLLERS_NAME]) == 1
                assert len(calls[FULL_RELOAD_DNS_CONFIGURATION_NAME]) == 1
                assert len(calls[DYNAMIC_UPDATE_DNS_CONFIGURATION_NAME]) == 0
                assert len(calls[CHECK_SERIAL_UPDATE_NAME]) == 1

    async def test_dns_config_workflow_dynamic_update(
        self, mocker: MockerFixture
    ):
        # TODO create DNSPublications, Domains and DNSResources for update

        mocker.patch(
            "maastemporalworker.workflow.dns.get_task_queue_for_update"
        ).return_value = "region"

        calls = defaultdict(list)

        @activity.defn(name=GET_CHANGES_SINCE_CURRENT_SERIAL_NAME)
        async def get_changes_since_current_serial() -> (
            SerialChangesResult | None
        ):
            calls[GET_CHANGES_SINCE_CURRENT_SERIAL_NAME].append(True)
            return SerialChangesResult(
                updates=[DNSPublication(serial=1, source="", update="")]
            )

        @activity.defn(name=GET_REGION_CONTROLLERS_NAME)
        async def get_region_controllers() -> RegionControllersResult:
            calls[GET_REGION_CONTROLLERS_NAME].append(True)
            return RegionControllersResult(
                region_controller_system_ids=["abc"]
            )

        @activity.defn(name=FULL_RELOAD_DNS_CONFIGURATION_NAME)
        async def full_reload_dns_configuration() -> DNSUpdateResult:
            calls[FULL_RELOAD_DNS_CONFIGURATION_NAME].append(True)
            return DNSUpdateResult(serial=1)

        @activity.defn(name=DYNAMIC_UPDATE_DNS_CONFIGURATION_NAME)
        async def dynamic_update_dns_configuration(
            param: DynamicUpdateParam,
        ) -> DNSUpdateResult:
            calls[DYNAMIC_UPDATE_DNS_CONFIGURATION_NAME].append(True)
            return DNSUpdateResult(serial=1)

        @activity.defn(name=CHECK_SERIAL_UPDATE_NAME)
        async def check_serial_update(serial: CheckSerialUpdateParam) -> None:
            calls[CHECK_SERIAL_UPDATE_NAME].append(True)

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="region",
                workflows=[ConfigureDNSWorkflow],
                activities=[
                    get_changes_since_current_serial,
                    get_region_controllers,
                    full_reload_dns_configuration,
                    dynamic_update_dns_configuration,
                    check_serial_update,
                ],
            ) as worker:
                await env.client.execute_workflow(
                    CONFIGURE_DNS_WORKFLOW_NAME,
                    ConfigureDNSParam(need_full_reload=False),
                    id="configure-dns",
                    task_queue=worker.task_queue,
                )

                assert len(calls[GET_CHANGES_SINCE_CURRENT_SERIAL_NAME]) == 1
                assert len(calls[GET_REGION_CONTROLLERS_NAME]) == 1
                assert len(calls[FULL_RELOAD_DNS_CONFIGURATION_NAME]) == 0
                assert len(calls[DYNAMIC_UPDATE_DNS_CONFIGURATION_NAME]) == 1
                assert len(calls[CHECK_SERIAL_UPDATE_NAME]) == 1
