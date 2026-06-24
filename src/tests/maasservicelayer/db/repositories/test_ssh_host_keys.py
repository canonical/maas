# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.ssh_host_keys import TrustedSshHostKeyBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.ssh_host_keys import (
    TrustedSshHostKeyClauseFactory,
    TrustedSshHostKeyRepository,
)
from maasservicelayer.exceptions.catalog import AlreadyExistsException
from maasservicelayer.models.ssh_host_keys import TrustedSshHostKey
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


async def create_test_trusted_ssh_host_key_entry(
    fixture: Fixture,
    host: str = "192.168.1.1",
    key_type: str = "ssh-rsa",
    public_key: str = "AAAAB3NzaC1yc2EAAAADAQABAAABAQC0",
    label: str | None = "rack-1",
) -> dict[str, ...]:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()

    ssh_host_key = {
        "created": created_at,
        "updated": updated_at,
        "host": host,
        "key_type": key_type,
        "public_key": public_key,
        "label": label,
    }

    [created] = await fixture.create(
        "maasserver_trustedsshhostkey", ssh_host_key
    )
    return created


class TestTrustedSshHostKeyClauseFactory:
    def test_with_id_filters_on_id_column(self) -> None:
        clause = TrustedSshHostKeyClauseFactory.with_id(42)
        sql = str(clause.condition)
        assert "trustedsshhostkey.id" in sql

    def test_with_host_filters_on_host_column(self) -> None:
        clause = TrustedSshHostKeyClauseFactory.with_host("192.168.1.1")
        sql = str(clause.condition)
        assert "trustedsshhostkey.host" in sql

    def test_with_key_type_filters_on_key_type_column(self) -> None:
        clause = TrustedSshHostKeyClauseFactory.with_key_type("ssh-rsa")
        sql = str(clause.condition)
        assert "trustedsshhostkey.key_type" in sql

    def test_with_public_key_filters_on_public_key_column(self) -> None:
        clause = TrustedSshHostKeyClauseFactory.with_public_key(
            "AAAAB3NzaC1yc2E="
        )
        sql = str(clause.condition)
        assert "trustedsshhostkey.public_key" in sql


class TestTrustedSshHostKeysRepository(
    RepositoryCommonTests[TrustedSshHostKey]
):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> TrustedSshHostKeyRepository:
        return TrustedSshHostKeyRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[TrustedSshHostKey]:
        keys = []
        for i in range(num_objects):
            key = await create_test_trusted_ssh_host_key_entry(
                fixture,
                host=f"192.168.1.{i}",
                key_type="ssh-rsa",
                public_key=f"AAAAB3NzaC1yc2E_TEST_{i}",
                label=f"rack-{i}",
            )
            keys.append(TrustedSshHostKey(**key))
        return keys

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> TrustedSshHostKey:
        key = await create_test_trusted_ssh_host_key_entry(
            fixture,
            host="192.168.1.99",
            key_type="ssh-rsa",
            public_key="AAAAB3NzaC1yc2E_UNIQUE",
            label="test-key",
        )
        return TrustedSshHostKey(**key)

    @pytest.fixture
    async def instance_builder_model(
        self,
    ) -> type[TrustedSshHostKeyBuilder]:
        return TrustedSshHostKeyBuilder

    @pytest.fixture
    async def instance_builder(
        self, *args, **kwargs
    ) -> TrustedSshHostKeyBuilder:
        return TrustedSshHostKeyBuilder(
            host="192.168.1.100",
            key_type="ssh-rsa",
            public_key="AAAAB3NzaC1yc2E_NEW",
            label="new-key",
        )

    async def test_create_with_unique_constraint(
        self,
        repository_instance: TrustedSshHostKeyRepository,
        fixture: Fixture,
    ) -> None:
        builder = TrustedSshHostKeyBuilder(
            host="192.168.1.1",
            key_type="ssh-rsa",
            public_key="AAAAB3NzaC1yc2E_DUP",
        )
        await repository_instance.create(builder)
        with pytest.raises(AlreadyExistsException):
            await repository_instance.create(builder)
