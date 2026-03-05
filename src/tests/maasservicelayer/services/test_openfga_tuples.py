# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import and_
from sqlalchemy.sql.operators import eq

from maasservicelayer.builders.openfga_tuple import OpenFGATupleBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.openfga_tuples import (
    OpenFGATuplesClauseFactory,
    OpenFGATuplesRepository,
)
from maasservicelayer.db.tables import OpenFGATupleTable
from maasservicelayer.services import OpenFGATupleService, ServiceCollectionV3
from maasservicelayer.services.openfga_tuples import (
    EntitlementsBuilderFactory,
    MAASTupleBuilderFactory,
    OpenFGAServiceCache,
    PoolTupleBuilderFactory,
    UndefinedEntitlementError,
)
from tests.fixtures.factories.openfga_tuples import create_openfga_tuple
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.asyncio
class TestIntegrationOpenFGAService:
    async def test_upsert(
        self,
        fixture: Fixture,
        services: ServiceCollectionV3,
    ):
        await services.openfga_tuples.upsert(
            OpenFGATupleBuilder.build_pool("1000")
        )
        retrieved_pool = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c.object_type, "pool"),
                eq(OpenFGATupleTable.c.object_id, "1000"),
            ),
        )
        assert len(retrieved_pool) == 1
        assert retrieved_pool[0]["_user"] == "maas:0"
        assert retrieved_pool[0]["object_type"] == "pool"
        assert retrieved_pool[0]["object_id"] == "1000"
        assert retrieved_pool[0]["relation"] == "parent"

    async def test_upsert_overrides(
        self,
        fixture: Fixture,
        services: ServiceCollectionV3,
    ):
        await create_openfga_tuple(
            fixture, "user:1", "user", "member", "group", "2000"
        )

        await services.openfga_tuples.upsert(
            OpenFGATupleBuilder.build_user_member_group(1, 2000)
        )

        retrieved_tuple = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c.object_type, "group"),
                eq(OpenFGATupleTable.c.object_id, "2000"),
                eq(OpenFGATupleTable.c._user, "user:1"),
            ),
        )
        assert len(retrieved_tuple) == 1
        assert retrieved_tuple[0]["_user"] == "user:1"
        assert retrieved_tuple[0]["object_type"] == "group"
        assert retrieved_tuple[0]["object_id"] == "2000"
        assert retrieved_tuple[0]["relation"] == "member"

    async def test_delete_many(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        await create_openfga_tuple(
            fixture, "user:1", "user", "member", "group", "2000"
        )
        await services.openfga_tuples.delete_many(
            QuerySpec(where=OpenFGATuplesClauseFactory.with_user("user:1"))
        )
        retrieved_tuple = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c.object_type, "group"),
                eq(OpenFGATupleTable.c.object_id, "2000"),
                eq(OpenFGATupleTable.c._user, "user:1"),
            ),
        )
        assert len(retrieved_tuple) == 0

    async def test_delete_pool(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        await create_openfga_tuple(
            fixture, "maas:0", "user", "parent", "pool", "100"
        )
        await services.openfga_tuples.delete_pool(100)
        retrieved_tuple = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c.object_type, "pool"),
                eq(OpenFGATupleTable.c.object_id, "100"),
                eq(OpenFGATupleTable.c._user, "maas:0"),
            ),
        )
        assert len(retrieved_tuple) == 0

    async def test_delete_user(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        await create_openfga_tuple(
            fixture, "user:1", "user", "member", "group", "2000"
        )
        await services.openfga_tuples.delete_user(1)
        retrieved_tuple = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c.object_type, "group"),
                eq(OpenFGATupleTable.c.object_id, "2000"),
                eq(OpenFGATupleTable.c._user, "user:1"),
            ),
        )
        assert len(retrieved_tuple) == 0

    async def test_remove_user_from_group(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        await create_openfga_tuple(
            fixture, "user:1", "user", "member", "group", "2000"
        )
        await services.openfga_tuples.remove_user_from_group(2000, 1)
        retrieved_tuple = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c.object_type, "group"),
                eq(OpenFGATupleTable.c.object_id, "2000"),
                eq(OpenFGATupleTable.c._user, "user:1"),
            ),
        )
        assert len(retrieved_tuple) == 0


@pytest.mark.asyncio
class TestOpenFGAService:
    async def test_get_client_is_cached(self) -> None:
        cache = OpenFGAServiceCache()
        agents_service = OpenFGATupleService(
            context=Context(),
            openfga_tuple_repository=Mock(OpenFGATuplesRepository),
            cache=cache,
        )

        agents_service2 = OpenFGATupleService(
            context=Context(),
            openfga_tuple_repository=Mock(OpenFGATuplesRepository),
            cache=cache,
        )

        apiclient = await agents_service.get_client()
        apiclient_again = await agents_service.get_client()

        apiclient2 = await agents_service2.get_client()
        apiclient2_again = await agents_service2.get_client()

        assert (
            id(apiclient)
            == id(apiclient2)
            == id(apiclient_again)
            == id(apiclient2_again)
        )

    async def test_delete_entitlement_maas(self) -> None:
        mock_repository = Mock(OpenFGATuplesRepository)
        mock_repository.delete_many = AsyncMock(return_value=None)
        service = OpenFGATupleService(
            context=Context(),
            openfga_tuple_repository=mock_repository,
            cache=OpenFGAServiceCache(),
        )

        await service.delete_entitlement(
            group_id=1,
            entitlement_name="can_edit_machines",
            resource_type="maas",
            resource_id=0,
        )

        mock_repository.delete_many.assert_called_once()
        query = mock_repository.delete_many.call_args[0][0]
        assert query.where is not None
        compiled = query.where.condition.compile(
            compile_kwargs={"literal_binds": True}
        )
        sql_str = str(compiled)
        assert "group:1#member" in sql_str
        assert "can_edit_machines" in sql_str
        assert "'maas'" in sql_str

    async def test_delete_entitlement_pool(self) -> None:
        mock_repository = Mock(OpenFGATuplesRepository)
        mock_repository.delete_many = AsyncMock(return_value=None)
        service = OpenFGATupleService(
            context=Context(),
            openfga_tuple_repository=mock_repository,
            cache=OpenFGAServiceCache(),
        )

        await service.delete_entitlement(
            group_id=5,
            entitlement_name="can_deploy_machines",
            resource_type="pool",
            resource_id=42,
        )

        mock_repository.delete_many.assert_called_once()
        query = mock_repository.delete_many.call_args[0][0]
        compiled = query.where.condition.compile(
            compile_kwargs={"literal_binds": True}
        )
        sql_str = str(compiled)
        assert "group:5#member" in sql_str
        assert "can_deploy_machines" in sql_str
        assert "'pool'" in sql_str
        assert "'42'" in sql_str


class TestMAASTupleBuilderFactory:
    @pytest.mark.parametrize(
        "entitlement_name",
        list(MAASTupleBuilderFactory.ENTITLEMENTS.keys()),
    )
    def test_build_all_maas_entitlements(self, entitlement_name: str) -> None:
        group_id = 42
        factory = MAASTupleBuilderFactory(entitlement_name)
        builder = factory.build_tuple(group_id, 0)
        assert builder.user == f"group:{group_id}#member"
        assert builder.user_type == "userset"
        assert builder.relation == entitlement_name
        assert builder.object_type == "maas"
        assert builder.object_id == "0"

    def test_rejects_nonzero_resource_id(self) -> None:
        factory = MAASTupleBuilderFactory("can_edit_machines")
        with pytest.raises(
            UndefinedEntitlementError,
            match="Resource ID must be 0",
        ):
            factory.build_tuple(1, 5)

    def test_rejects_undefined_entitlement(self) -> None:
        with pytest.raises(UndefinedEntitlementError, match="not defined"):
            MAASTupleBuilderFactory("nonexistent")

    def test_validate_entitlement_valid(self) -> None:
        is_valid, error = MAASTupleBuilderFactory.validate_entitlement(
            "can_edit_machines"
        )
        assert is_valid is True
        assert error is None

    def test_validate_entitlement_invalid(self) -> None:
        is_valid, error = MAASTupleBuilderFactory.validate_entitlement(
            "nonexistent"
        )
        assert is_valid is False
        assert "not defined" in error


class TestPoolTupleBuilderFactory:
    @pytest.mark.parametrize(
        "entitlement_name",
        list(PoolTupleBuilderFactory.ENTITLEMENTS.keys()),
    )
    def test_build_all_pool_entitlements(self, entitlement_name: str) -> None:
        group_id = 10
        pool_id = 99
        factory = PoolTupleBuilderFactory(entitlement_name)
        builder = factory.build_tuple(group_id, pool_id)
        assert builder.user == f"group:{group_id}#member"
        assert builder.user_type == "userset"
        assert builder.relation == entitlement_name
        assert builder.object_type == "pool"
        assert builder.object_id == str(pool_id)

    def test_rejects_undefined_entitlement(self) -> None:
        with pytest.raises(UndefinedEntitlementError, match="not defined"):
            PoolTupleBuilderFactory("can_edit_identities")

    def test_validate_entitlement_valid(self) -> None:
        is_valid, error = PoolTupleBuilderFactory.validate_entitlement(
            "can_edit_machines"
        )
        assert is_valid is True
        assert error is None

    def test_validate_entitlement_invalid(self) -> None:
        is_valid, error = PoolTupleBuilderFactory.validate_entitlement(
            "can_edit_identities"
        )
        assert is_valid is False
        assert "not defined" in error


class TestEntitlementsBuilderFactory:
    def test_get_factory_maas(self) -> None:
        factory = EntitlementsBuilderFactory.get_factory(
            "can_edit_machines", "maas"
        )
        assert isinstance(factory, MAASTupleBuilderFactory)

    def test_get_factory_pool(self) -> None:
        factory = EntitlementsBuilderFactory.get_factory(
            "can_edit_machines", "pool"
        )
        assert isinstance(factory, PoolTupleBuilderFactory)

    def test_get_factory_builds_maas_tuple(self) -> None:
        factory = EntitlementsBuilderFactory.get_factory(
            "can_edit_machines", "maas"
        )
        builder = factory.build_tuple(1, 0)
        assert builder.object_type == "maas"
        assert builder.object_id == "0"
        assert builder.relation == "can_edit_machines"

    def test_get_factory_builds_pool_tuple(self) -> None:
        factory = EntitlementsBuilderFactory.get_factory(
            "can_edit_machines", "pool"
        )
        builder = factory.build_tuple(1, 7)
        assert builder.object_type == "pool"
        assert builder.object_id == "7"
        assert builder.relation == "can_edit_machines"

    def test_get_factory_rejects_unsupported_resource_type(self) -> None:
        with pytest.raises(
            UndefinedEntitlementError, match="Resource type unknown"
        ):
            EntitlementsBuilderFactory.get_factory(
                "can_edit_machines", "unknown"
            )

    def test_get_factory_rejects_undefined_entitlement(self) -> None:
        with pytest.raises(UndefinedEntitlementError, match="not defined"):
            EntitlementsBuilderFactory.get_factory("nonexistent", "maas")

    def test_validate_entitlement_valid_maas(self) -> None:
        is_valid, error = EntitlementsBuilderFactory.validate_entitlement(
            "can_edit_machines", "maas"
        )
        assert is_valid is True
        assert error is None

    def test_validate_entitlement_valid_pool(self) -> None:
        is_valid, error = EntitlementsBuilderFactory.validate_entitlement(
            "can_edit_machines", "pool"
        )
        assert is_valid is True
        assert error is None

    def test_validate_entitlement_invalid_resource_type(self) -> None:
        is_valid, error = EntitlementsBuilderFactory.validate_entitlement(
            "can_edit_machines", "unknown"
        )
        assert is_valid is False
        assert "Resource type unknown" in error

    def test_validate_entitlement_invalid_entitlement(self) -> None:
        is_valid, error = EntitlementsBuilderFactory.validate_entitlement(
            "nonexistent", "maas"
        )
        assert is_valid is False
        assert "not defined" in error
