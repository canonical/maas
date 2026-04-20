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
from maasservicelayer.models.openfga_tuple import EntitlementDeleteSpec
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
    async def test_list_entitlements(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        await create_openfga_tuple(
            fixture,
            "group:999#member",
            "userset",
            "can_view_machines",
            "pool",
            "0",
        )
        await create_openfga_tuple(
            fixture,
            "group:1000#member",
            "userset",
            "can_view_machines",
            "pool",
            "0",
        )

        tuples = await services.openfga_tuples.list_entitlements(999)

        assert len(tuples) == 1
        assert tuples[0].relation == "can_view_machines"
        assert tuples[0].object_type == "pool"
        assert tuples[0].object_id == "0"
        assert tuples[0].user == "group:999#member"

    async def test_list_entitlements_page(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        await create_openfga_tuple(
            fixture,
            "group:888#member",
            "userset",
            "can_edit_machines",
            "maas",
            "0",
        )
        await create_openfga_tuple(
            fixture,
            "group:888#member",
            "userset",
            "can_view_machines",
            "pool",
            "10",
        )
        # unrelated group that should not appear
        await create_openfga_tuple(
            fixture,
            "group:889#member",
            "userset",
            "can_view_machines",
            "pool",
            "10",
        )

        first_page = await services.openfga_tuples.list_entitlements_page(
            888, page=1, size=1
        )
        assert first_page.total == 2
        assert len(first_page.items) == 1

        second_page = await services.openfga_tuples.list_entitlements_page(
            888, page=2, size=1
        )
        assert second_page.total == 2
        assert len(second_page.items) == 1

        all_relations = {
            first_page.items[0].relation,
            second_page.items[0].relation,
        }
        assert all_relations == {"can_edit_machines", "can_view_machines"}

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

    async def test_bulk_remove_users_from_group(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        await create_openfga_tuple(
            fixture, "user:1", "user", "member", "group", "10"
        )
        await create_openfga_tuple(
            fixture, "user:2", "user", "member", "group", "10"
        )
        await create_openfga_tuple(
            fixture, "user:3", "user", "member", "group", "10"
        )
        # unrelated group membership that should not be removed
        await create_openfga_tuple(
            fixture, "user:99", "user", "member", "group", "20"
        )

        await services.openfga_tuples.bulk_remove_users_from_group(
            10, [1, 2, 3]
        )

        removed = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c.object_type, "group"),
                eq(OpenFGATupleTable.c.object_id, "10"),
            ),
        )
        assert len(removed) == 0

        unrelated = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c.object_type, "group"),
                eq(OpenFGATupleTable.c.object_id, "20"),
                eq(OpenFGATupleTable.c._user, "user:99"),
            ),
        )
        assert len(unrelated) == 1

    async def test_bulk_add_users_to_group(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        await services.openfga_tuples.bulk_add_users_to_group(
            4000, [10, 20, 30]
        )

        tuples = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c.object_type, "group"),
                eq(OpenFGATupleTable.c.object_id, "4000"),
                eq(OpenFGATupleTable.c.relation, "member"),
            ),
        )
        assert len(tuples) == 3
        users = {t["_user"] for t in tuples}
        assert users == {"user:10", "user:20", "user:30"}

    async def test_bulk_delete_entitlements(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        await create_openfga_tuple(
            fixture,
            "group:5000#member",
            "userset",
            "can_edit_machines",
            "maas",
            "0",
        )
        await create_openfga_tuple(
            fixture,
            "group:5000#member",
            "userset",
            "can_view_machines",
            "pool",
            "99",
        )
        # unrelated group entitlement that should not be removed
        await create_openfga_tuple(
            fixture,
            "group:6000#member",
            "userset",
            "can_edit_machines",
            "maas",
            "0",
        )

        await services.openfga_tuples.bulk_delete_entitlements(
            5000,
            [
                EntitlementDeleteSpec(
                    entitlement="can_edit_machines",
                    resource_type="maas",
                    resource_id=0,
                ),
                EntitlementDeleteSpec(
                    entitlement="can_view_machines",
                    resource_type="pool",
                    resource_id=99,
                ),
            ],
        )

        deleted = await fixture.get(
            OpenFGATupleTable.fullname,
            eq(OpenFGATupleTable.c._user, "group:5000#member"),
        )
        assert len(deleted) == 0

        unrelated = await fixture.get(
            OpenFGATupleTable.fullname,
            eq(OpenFGATupleTable.c._user, "group:6000#member"),
        )
        assert len(unrelated) == 1


@pytest.mark.asyncio
class TestOpenFGAService:
    async def test_get_client_is_cached(self) -> None:
        cache = OpenFGAServiceCache()
        openfga_service = OpenFGATupleService(
            context=Context(),
            openfga_tuple_repository=Mock(OpenFGATuplesRepository),
            cache=cache,
        )

        openfga_service2 = OpenFGATupleService(
            context=Context(),
            openfga_tuple_repository=Mock(OpenFGATuplesRepository),
            cache=cache,
        )

        apiclient = openfga_service.get_client()
        apiclient_again = openfga_service.get_client()

        apiclient2 = openfga_service2.get_client()
        apiclient2_again = openfga_service2.get_client()

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

    async def test_bulk_remove_users_from_group(self) -> None:
        mock_repository = Mock(OpenFGATuplesRepository)
        mock_repository.delete_many = AsyncMock(return_value=None)
        service = OpenFGATupleService(
            context=Context(),
            openfga_tuple_repository=mock_repository,
            cache=OpenFGAServiceCache(),
        )

        await service.bulk_remove_users_from_group(
            group_id=7, user_ids=[10, 20, 30]
        )

        mock_repository.delete_many.assert_called_once()
        query = mock_repository.delete_many.call_args[0][0]
        compiled = query.where.condition.compile(
            compile_kwargs={"literal_binds": True}
        )
        sql_str = str(compiled)
        assert "user:10" in sql_str
        assert "user:20" in sql_str
        assert "user:30" in sql_str
        assert "member" in sql_str
        assert "'group'" in sql_str
        assert "'7'" in sql_str

    async def test_bulk_add_users_to_group(self) -> None:
        mock_repository = Mock(OpenFGATuplesRepository)
        mock_repository.bulk_upsert = AsyncMock(return_value=None)
        service = OpenFGATupleService(
            context=Context(),
            openfga_tuple_repository=mock_repository,
            cache=OpenFGAServiceCache(),
        )

        await service.bulk_add_users_to_group(group_id=8, user_ids=[1, 2, 3])

        mock_repository.bulk_upsert.assert_called_once()
        builders = mock_repository.bulk_upsert.call_args[0][0]
        assert len(builders) == 3
        users = {b.user for b in builders}
        assert users == {"user:1", "user:2", "user:3"}
        assert all(b.relation == "member" for b in builders)
        assert all(b.object_type == "group" for b in builders)
        assert all(b.object_id == "8" for b in builders)

    async def test_bulk_delete_entitlements(self) -> None:
        mock_repository = Mock(OpenFGATuplesRepository)
        mock_repository.delete_many = AsyncMock(return_value=None)
        service = OpenFGATupleService(
            context=Context(),
            openfga_tuple_repository=mock_repository,
            cache=OpenFGAServiceCache(),
        )

        await service.bulk_delete_entitlements(
            group_id=9,
            items=[
                EntitlementDeleteSpec(
                    entitlement="can_edit_machines",
                    resource_type="maas",
                    resource_id=0,
                ),
                EntitlementDeleteSpec(
                    entitlement="can_view_machines",
                    resource_type="pool",
                    resource_id=42,
                ),
            ],
        )

        mock_repository.delete_many.assert_called_once()
        query = mock_repository.delete_many.call_args[0][0]
        compiled = query.where.condition.compile(
            compile_kwargs={"literal_binds": True}
        )
        sql_str = str(compiled)
        assert "group:9#member" in sql_str
        assert "can_edit_machines" in sql_str
        assert "'maas'" in sql_str
        assert "can_view_machines" in sql_str
        assert "'pool'" in sql_str
        assert "'42'" in sql_str

    async def test_list_entitlements_page(self) -> None:
        mock_repository = Mock(OpenFGATuplesRepository)
        mock_repository.list_entitlements = AsyncMock(
            return_value=Mock(items=[], total=0)
        )
        service = OpenFGATupleService(
            context=Context(),
            openfga_tuple_repository=mock_repository,
            cache=OpenFGAServiceCache(),
        )

        await service.list_entitlements_page(group_id=3, page=2, size=10)

        mock_repository.list_entitlements.assert_called_once()
        call_args = mock_repository.list_entitlements.call_args[0]
        page, size, query = call_args
        assert page == 2
        assert size == 10
        compiled = query.where.condition.compile(
            compile_kwargs={"literal_binds": True}
        )
        assert "group:3#member" in str(compiled)


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
