#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.builders.bmc import BmcBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bmcs import (
    BmcClauseFactory,
    BmcsRepository,
)
from tests.fixtures.factories.bmc import create_test_bmc_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture


class TestBmcClauseFactory:
    def test_with_ip_address_id(self) -> None:
        clause = BmcClauseFactory.with_ip_address_id(1)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_bmc.ip_address_id = 1"
        )


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestBmcsRepository:
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> BmcsRepository:
        return BmcsRepository(Context(connection=db_connection))

    async def test_update_many_moves_bmcs_to_another_ip(
        self, repository_instance: BmcsRepository, fixture: Fixture
    ):
        subnet = await create_test_subnet_entry(fixture)
        [old_ip, new_ip, other_ip] = [
            (
                await create_test_staticipaddress_entry(
                    fixture, subnet=subnet, alloc_type=IpAddressType.STICKY
                )
            )[0]
            for _ in range(3)
        ]
        bmc = await create_test_bmc_entry(
            fixture,
            ip_address_id=old_ip["id"],
            power_parameters={"power_address": str(old_ip["ip"])},
        )
        other_bmc = await create_test_bmc_entry(
            fixture,
            ip_address_id=other_ip["id"],
            power_parameters={"power_address": str(other_ip["ip"])},
        )

        updated = await repository_instance.update_many(
            query=QuerySpec(
                where=BmcClauseFactory.with_ip_address_id(old_ip["id"])
            ),
            builder=BmcBuilder(ip_address_id=new_ip["id"]),
        )

        assert [updated_bmc.id for updated_bmc in updated] == [bmc["id"]]
        assert updated[0].ip_address_id == new_ip["id"]
        unchanged = await repository_instance.get_by_id(other_bmc["id"])
        assert unchanged is not None
        assert unchanged.ip_address_id == other_ip["id"]
