#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio.client import Client
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.db import Database
from maasservicelayer.db.tables import InterfaceIPAddressTable
from maasservicelayer.services import CacheForServices
from maasservicelayer.services.temporal import TemporalService
from maastemporalworker.workflow.commission import (
    CommissionActivity,
    PrepareCommissioningParam,
)
from tests.fixtures.factories.interface import create_test_interface_dict
from tests.fixtures.factories.node import create_test_machine_entry
from tests.fixtures.factories.node_config import create_test_node_config_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture


@pytest.fixture
def commission_activities(
    db: Database, db_connection: AsyncConnection, mocker: MockerFixture
) -> CommissionActivity:
    # clear_networking_configuration deletes IPs, and
    # StaticIPAddressService.post_delete_hook queues a ConfigureDHCP workflow
    # for each one. start_transaction runs TemporalService.post_commit,
    # which connects to a real Temporal server, so we should mock it.
    mocker.patch.object(TemporalService, "post_commit", AsyncMock())
    return CommissionActivity(
        db,
        CacheForServices(),
        temporal_client=Mock(Client),
        connection=db_connection,
    )


@pytest.fixture
async def machine_with_linked_ip(fixture: Fixture) -> dict:
    machine = await create_test_machine_entry(fixture)
    config = await create_test_node_config_entry(fixture, node=machine)
    machine["current_config_id"] = config["id"]
    subnet = await create_test_subnet_entry(fixture)
    [ip] = await create_test_staticipaddress_entry(
        fixture, subnet=subnet, alloc_type=IpAddressType.AUTO
    )
    await create_test_interface_dict(fixture, node=machine, ips=[ip])
    return machine


@pytest.mark.asyncio
class TestPrepareCommissioning:
    async def test_clears_networking_configuration(
        self,
        fixture: Fixture,
        commission_activities: CommissionActivity,
        machine_with_linked_ip: dict,
    ) -> None:
        assert len(await fixture.get(InterfaceIPAddressTable.name)) == 1

        await ActivityEnvironment().run(
            commission_activities.prepare_commissioning,
            PrepareCommissioningParam(
                system_id=machine_with_linked_ip["system_id"]
            ),
        )

        assert len(await fixture.get(InterfaceIPAddressTable.name)) == 0

    async def test_skip_networking_keeps_links(
        self,
        fixture: Fixture,
        commission_activities: CommissionActivity,
        machine_with_linked_ip: dict,
    ) -> None:
        assert len(await fixture.get(InterfaceIPAddressTable.name)) == 1

        await ActivityEnvironment().run(
            commission_activities.prepare_commissioning,
            PrepareCommissioningParam(
                system_id=machine_with_linked_ip["system_id"],
                skip_networking=True,
            ),
        )

        assert len(await fixture.get(InterfaceIPAddressTable.name)) == 1

    async def test_unknown_node_fails_without_retry(
        self, commission_activities: CommissionActivity
    ) -> None:
        with pytest.raises(ApplicationError) as exc_info:
            await ActivityEnvironment().run(
                commission_activities.prepare_commissioning,
                PrepareCommissioningParam(system_id="missing"),
            )

        assert exc_info.value.non_retryable
