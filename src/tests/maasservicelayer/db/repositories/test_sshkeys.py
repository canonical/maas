# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.sshkeys import SshKeysProtocolType
from maasservicelayer.context import Context
from maasservicelayer.db.filters import SQLQuerySpec
from maasservicelayer.db.mappers.base import UnsupportedFilterError
from maasservicelayer.db.repositories.sshkeys import SshKeysRepository
from maasservicelayer.filters.base import FieldFilter, Filter, Operator
from maasservicelayer.filters.query import OrderBy, QuerySpec
from maasservicelayer.filters.sshkeys import SshKeyFilters
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.events import Event
from maasservicelayer.models.sshkeys import SshKey
from tests.fixtures.factories.user import (
    create_test_user,
    create_test_user_sshkey,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


@pytest.fixture
async def filter_keys(fixture: Fixture) -> dict[str, SshKey]:
    user = await create_test_user(fixture)
    keys = {}
    for name, protocol, auth_id in [
        ("manual", None, None),
        ("launchpad", SshKeysProtocolType.LP, "alice"),
        ("github", SshKeysProtocolType.GH, "bob"),
    ]:
        keys[name] = await create_test_user_sshkey(
            fixture,
            key=f"ssh-ed25519 {name} comment",
            user_id=user.id,
            protocol=protocol,
            auth_id=auth_id,
        )
    return keys


class TestSshKeysRepository(RepositoryCommonTests[SshKey]):
    @pytest.mark.parametrize("descending", [False, True])
    async def test_order_by_domain_field(
        self, repository_instance, filter_keys, descending
    ):
        keys = await repository_instance.get_many(
            QuerySpec(order_by=(OrderBy(SshKey, "key", descending),))
        )
        assert keys == sorted(
            filter_keys.values(), key=lambda key: key.key, reverse=descending
        )

    async def test_order_by_multiple_fields(
        self, repository_instance, fixture
    ):
        user = await create_test_user(fixture)
        keys = [
            await create_test_user_sshkey(
                fixture,
                key=f"ssh-ed25519 {name} comment",
                user_id=user.id,
                protocol=SshKeysProtocolType.LP,
                auth_id=auth_id,
            )
            for name, auth_id in [("a", "z"), ("b", "a"), ("c", "z")]
        ]
        result = await repository_instance.get_many(
            QuerySpec(
                order_by=(
                    OrderBy(SshKey, "auth_id"),
                    OrderBy(SshKey, "key", True),
                )
            )
        )
        assert result == [keys[1], keys[2], keys[0]]

    async def test_rejects_sql_query_before_delete(
        self, repository_instance, filter_keys
    ):
        with pytest.raises(TypeError):
            await repository_instance.delete_many(SQLQuerySpec())
        assert {
            key.id for key in await repository_instance.get_many(QuerySpec())
        } == {key.id for key in filter_keys.values()}

    async def test_rejects_order_for_another_model(
        self, repository_instance, filter_keys
    ):
        with pytest.raises(UnsupportedFilterError):
            await repository_instance.get_many(
                QuerySpec(order_by=(OrderBy(Event, "id"),))
            )
        assert {
            key.id for key in await repository_instance.get_many(QuerySpec())
        } == {key.id for key in filter_keys.values()}

    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> SshKeysRepository:
        return SshKeysRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[SshKey]:
        user = await create_test_user(fixture)
        created_sshkeys = [
            (
                await create_test_user_sshkey(
                    fixture,
                    key=f"ssh-ed25519 randomkey-{i} comment",
                    user_id=user.id,
                )
            )
            for i in range(num_objects)
        ]
        return created_sshkeys

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> SshKey:
        user = await create_test_user(fixture)
        return await create_test_user_sshkey(
            fixture, key="ssh-ed25519 randomkey comment", user_id=user.id
        )

    @pytest.fixture
    async def instance_builder_model(self, *args, **kwargs):
        pass

    @pytest.fixture
    async def instance_builder(self, *args, **kwargs) -> ResourceBuilder:
        raise NotImplementedError()

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_create(self, repository_instance, instance_builder):
        raise NotImplementedError()

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        raise NotImplementedError()

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_create_many(self, repository_instance, instance_builder):
        raise NotImplementedError()

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_create_many_duplicated(
        self, repository_instance, instance_builder
    ):
        raise NotImplementedError()

    @pytest.mark.skip(reason="Does not apply to ssh keys")
    async def test_update_one(self, repository_instance, instance_builder):
        raise NotImplementedError()

    @pytest.mark.skip(reason="Does not apply to ssh keys")
    async def test_update_one_multiple_results(
        self, repository_instance, _setup_test_list, num_objects
    ):
        raise NotImplementedError()

    @pytest.mark.skip(reason="Does not apply to ssh keys")
    async def test_update_many(
        self, repository_instance, _setup_test_list, num_objects
    ):
        raise NotImplementedError()

    @pytest.mark.skip(reason="Does not apply to ssh keys")
    async def test_update_by_id(self, repository_instance, instance_builder):
        raise NotImplementedError()

    async def test_get_many_filters_on_null_protocol(
        self, repository_instance: SshKeysRepository, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        manual_key = await create_test_user_sshkey(
            fixture, key="ssh-ed25519 manual comment", user_id=user.id
        )
        await create_test_user_sshkey(
            fixture,
            key="ssh-ed25519 imported comment",
            user_id=user.id,
            protocol=SshKeysProtocolType.LP,
            auth_id="someone",
        )

        keys = await repository_instance.get_many(
            QuerySpec(
                where=SshKeyFilters.and_filters(
                    [
                        SshKeyFilters.with_user_id(user.id),
                        SshKeyFilters.with_protocol(None),
                    ]
                )
            )
        )

        assert keys == [manual_key]

    async def test_delete_many_only_deletes_matching_keys(
        self, repository_instance: SshKeysRepository, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        other_user = await create_test_user(fixture)
        await create_test_user_sshkey(
            fixture, key="ssh-ed25519 first comment", user_id=user.id
        )
        other_key = await create_test_user_sshkey(
            fixture, key="ssh-ed25519 second comment", user_id=other_user.id
        )

        await repository_instance.delete_many(
            QuerySpec(where=SshKeyFilters.with_user_id(user.id))
        )

        assert await repository_instance.get_many(QuerySpec()) == [other_key]

    @pytest.mark.parametrize(
        "filter, expected_keys",
        [
            pytest.param(
                SshKeyFilters.and_filters([]),
                {"manual", "launchpad", "github"},
                id="empty-and",
            ),
            pytest.param(SshKeyFilters.or_filters([]), set(), id="empty-or"),
            pytest.param(
                SshKeyFilters.not_filter(SshKeyFilters.and_filters([])),
                set(),
                id="not-empty-and",
            ),
            pytest.param(
                SshKeyFilters.not_filter(SshKeyFilters.or_filters([])),
                {"manual", "launchpad", "github"},
                id="not-empty-or",
            ),
            pytest.param(
                SshKeyFilters.and_filters(
                    [
                        SshKeyFilters.or_filters([]),
                        SshKeyFilters.with_protocol(None),
                    ]
                ),
                set(),
                id="nested-empty-or",
            ),
            pytest.param(
                SshKeyFilters.or_filters(
                    [
                        SshKeyFilters.and_filters([]),
                        SshKeyFilters.with_protocol(SshKeysProtocolType.LP),
                    ]
                ),
                {"manual", "launchpad", "github"},
                id="nested-empty-and",
            ),
            pytest.param(
                FieldFilter(SshKey, "protocol", Operator.IN, ()),
                set(),
                id="empty-membership",
            ),
            pytest.param(
                FieldFilter(SshKey, "protocol", Operator.IN, (None,)),
                {"manual"},
                id="null-membership",
            ),
            pytest.param(
                FieldFilter(SshKey, "protocol", Operator.IN, (None, "lp")),
                {"manual", "launchpad"},
                id="nullable-membership",
            ),
            pytest.param(
                FieldFilter(SshKey, "protocol", Operator.IN, ("lp", "gh")),
                {"launchpad", "github"},
                id="nonnull-membership",
            ),
            pytest.param(
                SshKeyFilters.not_filter(
                    SshKeyFilters.with_protocol(SshKeysProtocolType.LP)
                ),
                {"manual", "github"},
                id="negated-equality",
            ),
            pytest.param(
                SshKeyFilters.not_filter(SshKeyFilters.with_protocol(None)),
                {"launchpad", "github"},
                id="negated-null-equality",
            ),
            pytest.param(
                SshKeyFilters.not_filter(
                    FieldFilter(SshKey, "protocol", Operator.IN, ("lp",))
                ),
                {"manual", "github"},
                id="negated-membership",
            ),
            pytest.param(
                SshKeyFilters.not_filter(
                    FieldFilter(SshKey, "protocol", Operator.IN, (None, "lp"))
                ),
                {"github"},
                id="negated-nullable-membership",
            ),
            pytest.param(
                SshKeyFilters.not_filter(
                    SshKeyFilters.not_filter(
                        SshKeyFilters.with_protocol(SshKeysProtocolType.LP)
                    )
                ),
                {"launchpad"},
                id="double-negation",
            ),
            pytest.param(
                SshKeyFilters.not_filter(
                    SshKeyFilters.or_filters(
                        [
                            SshKeyFilters.with_protocol(
                                SshKeysProtocolType.LP
                            ),
                            SshKeyFilters.with_auth_id(None),
                        ]
                    )
                ),
                {"github"},
                id="negated-disjunction",
            ),
            pytest.param(
                SshKeyFilters.not_filter(
                    SshKeyFilters.and_filters(
                        [
                            SshKeyFilters.with_protocol(
                                SshKeysProtocolType.LP
                            ),
                            SshKeyFilters.with_auth_id("alice"),
                        ]
                    )
                ),
                {"manual", "github"},
                id="negated-conjunction",
            ),
            pytest.param(
                SshKeyFilters.or_filters(
                    [
                        SshKeyFilters.with_protocol(SshKeysProtocolType.LP),
                        SshKeyFilters.not_filter(
                            SshKeyFilters.with_auth_id("bob")
                        ),
                    ]
                ),
                {"manual", "launchpad"},
                id="nested-negation",
            ),
        ],
    )
    async def test_get_many_filter_semantics(
        self,
        repository_instance: SshKeysRepository,
        filter_keys: dict[str, SshKey],
        filter: Filter,
        expected_keys: set[str],
    ) -> None:
        keys = await repository_instance.get_many(QuerySpec(where=filter))

        assert {key.id for key in keys} == {
            filter_keys[name].id for name in expected_keys
        }

    @pytest.mark.parametrize(
        "filter, expected_deleted",
        [
            pytest.param(SshKeyFilters.or_filters([]), set(), id="empty-or"),
            pytest.param(
                SshKeyFilters.not_filter(
                    SshKeyFilters.with_protocol(SshKeysProtocolType.LP)
                ),
                {"manual", "github"},
                id="nullable-negation",
            ),
        ],
    )
    async def test_delete_many_filter_semantics(
        self,
        repository_instance: SshKeysRepository,
        filter_keys: dict[str, SshKey],
        filter: Filter,
        expected_deleted: set[str],
    ) -> None:
        deleted = await repository_instance.delete_many(
            QuerySpec(where=filter)
        )
        remaining = await repository_instance.get_many(QuerySpec())

        assert {key.id for key in deleted} == {
            filter_keys[name].id for name in expected_deleted
        }
        assert {key.id for key in remaining} == {
            key.id
            for name, key in filter_keys.items()
            if name not in expected_deleted
        }

    async def test_delete_many_rejects_filter_of_another_model(
        self,
        repository_instance: SshKeysRepository,
        filter_keys: dict[str, SshKey],
    ) -> None:
        with pytest.raises(UnsupportedFilterError):
            await repository_instance.delete_many(
                QuerySpec(where=FieldFilter(Event, "id", Operator.EQ, 1))
            )

        remaining = await repository_instance.get_many(QuerySpec())
        assert {key.id for key in remaining} == {
            key.id for key in filter_keys.values()
        }
