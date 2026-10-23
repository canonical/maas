# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.sshkeys import SshKeysProtocolType
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.sshkeys import SshKeysRepository
from maasservicelayer.filters.sshkeys import SshKeyFilters
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.sshkeys import SshKey
from tests.fixtures.factories.user import (
    create_test_user,
    create_test_user_sshkey,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestSshKeysRepository(RepositoryCommonTests[SshKey]):
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
