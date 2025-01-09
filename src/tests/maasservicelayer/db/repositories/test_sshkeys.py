# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.base import ResourceBuilder
from maasservicelayer.db.repositories.sshkeys import (
    SshKeyClauseFactory,
    SshKeysRepository,
)
from maasservicelayer.models.sshkeys import SshKey
from tests.fixtures.factories.user import (
    create_test_user,
    create_test_user_sshkey,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestSshKeyClauseFactory:
    def test_with_user_id(self) -> None:
        clause = SshKeyClauseFactory.with_user_id(1)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_sshkey.user_id = 1"
        )


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
