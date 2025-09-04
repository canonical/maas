# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.ui_subnets import (
    UISubnetsClauseFactory,
    UISubnetsRepository,
)
from maasservicelayer.models.ui_subnets import UISubnet
from maasservicelayer.models.vlans import Vlan
from tests.fixtures.factories.spaces import create_test_space_entry
from tests.fixtures.factories.subnet import create_test_ui_subnet_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import (
    ReadOnlyRepositoryCommonTests,
)


class TestUISubnetsClauseFactory:
    def test_with_cidrs(self):
        clause = UISubnetsClauseFactory.with_cidrs(
            ["10.0.0.0/24", "192.168.1.0/24"]
        )
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == (
            "CAST(maasserver_ui_subnet_view.cidr AS VARCHAR) IN ('10.0.0.0/24', '192.168.1.0/24')"
        )

    def test_with_vlan_ids(self):
        clause = UISubnetsClauseFactory.with_vlan_ids([100, 200])
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_ui_subnet_view.vlan_id IN (100, 200)")

    def test_with_fabric_names(self):
        clause = UISubnetsClauseFactory.with_fabric_names(["fab1", "fab2"])
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_ui_subnet_view.fabric_name IN ('fab1', 'fab2')")

    def test_with_space_names(self):
        clause = UISubnetsClauseFactory.with_space_names(["spaceA", "spaceB"])
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_ui_subnet_view.space_name IN ('spaceA', 'spaceB')")

    def test_with_fabric_name_like(self):
        clause = UISubnetsClauseFactory.with_fabric_name_like("fab")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_ui_subnet_view.fabric_name LIKE '%' || 'fab' || '%'")

    def test_with_vlan_name_like(self):
        clause = UISubnetsClauseFactory.with_vlan_name_like("vlan")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_ui_subnet_view.vlan_name LIKE '%' || 'vlan' || '%'")

    def test_with_space_name_like(self):
        clause = UISubnetsClauseFactory.with_space_name_like("space")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == (
            "maasserver_ui_subnet_view.space_name LIKE '%' || 'space' || '%'"
        )

    def test_with_cidr_like(self):
        clause = UISubnetsClauseFactory.with_cidr_like("192.168")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "CAST(maasserver_ui_subnet_view.cidr AS VARCHAR) LIKE '%' || '192.168' || '%'"
        )


class TestUISubnetsRepository(ReadOnlyRepositoryCommonTests[UISubnet]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> UISubnetsRepository:
        return UISubnetsRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[UISubnet]:
        space = await create_test_space_entry(fixture)
        vlan = Vlan(**await create_test_vlan_entry(fixture, space_id=space.id))
        created_ui_subnets = [
            await create_test_ui_subnet_entry(
                fixture, space=space, vlan=vlan, cidr=f"10.0.0.{i}"
            )
            for i in range(num_objects)
        ]
        return created_ui_subnets

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> UISubnet:
        return await create_test_ui_subnet_entry(fixture, cidr="10.0.0.1")
