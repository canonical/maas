# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from base64 import b64decode, b64encode
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.filestorage import FileStorageBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.repositories.filestorage import FileStorageRepository
from maasservicelayer.filters.base import FieldFilter, Operator
from maasservicelayer.filters.filestorage import FileStorageFilters
from maasservicelayer.filters.query import OrderBy, QuerySpec
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.filestorage import FileStorage
from tests.fixtures.factories.filestorage import create_test_filestorage_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestFilestorageRepository(RepositoryCommonTests[FileStorage]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> FileStorageRepository:
        return FileStorageRepository(context=Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[FileStorage]:
        files = [
            await create_test_filestorage_entry(
                fixture,
                key=f"key-{i}",
                filename=f"filename-{i}",
                content=b64encode(f"content-{i}".encode()).decode(),
            )
            for i in range(num_objects)
        ]
        for file in files:
            file.content = b64decode(file.content)
        return files

    @pytest.fixture
    async def instance_builder(self, *args, **kwargs) -> ResourceBuilder:
        return FileStorageBuilder(
            filename="filename",
            content=b"content",
            key="key",
            owner_id=None,
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[ResourceBuilder]:
        return FileStorageBuilder

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> FileStorage:
        expected_file = await create_test_filestorage_entry(fixture)
        expected_file.content = b64decode(expected_file.content)
        return expected_file

    async def test_get_one_converts_content_str_to_bytes(
        self,
        repository_instance: FileStorageRepository,
        fixture: Fixture,
    ) -> None:
        content = b"expected-content-string"
        encoded_content = b64encode(content).decode()

        await create_test_filestorage_entry(
            fixture,
            content=encoded_content,
        )

        file = await repository_instance.get_one(query=QuerySpec())

        # Ensure returned object got content parsed from str to bytes
        assert type(file.content) is bytes
        assert file.content != encoded_content
        assert file.content == content

    @patch("maasservicelayer.db.repositories.filestorage.b64decode")
    async def test_get_one_doesnt_convert_content_if_none(
        self,
        b64decode_mock: MagicMock,
        repository_instance: FileStorageRepository,
    ) -> None:
        file = await repository_instance.get_one(query=QuerySpec())
        assert file is None
        b64decode_mock.assert_not_called()

    async def test_get_by_id_converts_content_str_to_bytes(
        self,
        repository_instance: FileStorageRepository,
        fixture: Fixture,
    ) -> None:
        id_to_use = 42
        content = b"expected-content-string"
        encoded_content = b64encode(content).decode()

        await create_test_filestorage_entry(
            fixture,
            id=id_to_use,
            content=encoded_content,
        )

        file = await repository_instance.get_by_id(id_to_use)

        assert type(file.content) is bytes
        assert file.content != encoded_content
        assert file.content == content

    @pytest.mark.parametrize("num_objects", [2])
    async def test_get_many_converts_content_str_to_bytes(
        self,
        repository_instance: FileStorageRepository,
        _setup_test_list: list[FileStorage],
        num_objects: int,
    ) -> None:
        files = await repository_instance.get_many(query=QuerySpec())

        for idx, file in enumerate(files):
            expected_content = f"content-{idx}".encode("utf-8")
            encoded_content = b64encode(expected_content).decode()

            assert type(file.content) is bytes
            assert file.content != encoded_content
            assert file.content == expected_content

    async def test_update_one(self, repository_instance, instance_builder):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one(
                repository_instance, instance_builder
            )

    @pytest.mark.parametrize("num_objects", [2])
    async def test_update_one_multiple_results(
        self,
        repository_instance,
        instance_builder_model,
        _setup_test_list,
        num_objects,
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one_multiple_results(
                repository_instance,
                instance_builder_model,
                _setup_test_list,
                num_objects,
            )

    @pytest.mark.parametrize("num_objects", [2])
    async def test_update_many(
        self,
        repository_instance,
        instance_builder_model,
        _setup_test_list,
        num_objects,
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_many(
                repository_instance,
                instance_builder_model,
                _setup_test_list,
                num_objects,
            )

    async def test_update_by_id(self, repository_instance, instance_builder):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id(
                repository_instance, instance_builder
            )

    async def test_create(
        self,
        repository_instance: BaseRepository,
        instance_builder: ResourceBuilder,
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_create(
                repository_instance,
                instance_builder,
            )

    async def test_create_duplicated(
        self,
        repository_instance: BaseRepository,
        instance_builder: ResourceBuilder,
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_create_duplicated(
                repository_instance,
                instance_builder,
            )

    async def test_create_many(
        self,
        repository_instance: BaseRepository,
        instance_builder: ResourceBuilder,
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_create_many(
                repository_instance,
                instance_builder,
            )

    async def test_create_many_duplicated(
        self,
        repository_instance: BaseRepository,
        instance_builder: ResourceBuilder,
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_create_many_duplicated(
                repository_instance,
                instance_builder,
            )

    async def test_create_or_update_adds_new_file(
        self,
        repository_instance: FileStorageRepository,
    ) -> None:
        filename = "test-file-name"
        content = b64encode(b"test-file-content")
        key = str(uuid4())
        owner_id = 1

        builder = FileStorageBuilder(
            filename=filename,
            content=content,
            key=key,
            owner_id=owner_id,
        )

        created_file = await repository_instance.create_or_update(
            builder=builder
        )

        assert created_file.filename == filename
        assert created_file.content == content
        assert created_file.key == key
        assert created_file.owner_id == owner_id

    async def test_create_or_update_overwrites_existing_file(
        self,
        repository_instance: FileStorageRepository,
        fixture: Fixture,
    ) -> None:
        filename = "test-file-name"
        content = b64encode(b"test-file-content")
        key = str(uuid4())
        owner_id = 1

        existing_file = await create_test_filestorage_entry(
            fixture,
            filename=filename,
            content=content.decode(),
            key=key,
            owner_id=owner_id,
        )

        new_content = b64encode(b"new-test-file-content")
        builder = FileStorageBuilder(
            filename=filename,
            content=new_content,
            key=str(uuid4()),
            owner_id=owner_id,
        )

        updated_file = await repository_instance.create_or_update(
            builder=builder
        )

        assert updated_file.id == existing_file.id
        assert updated_file.filename == existing_file.filename
        assert updated_file.content == new_content
        assert updated_file.key == existing_file.key
        assert updated_file.owner_id == existing_file.owner_id

    @pytest.mark.parametrize("content", [b"", b"\x00\xff\xfe", b"plain text"])
    @pytest.mark.parametrize("operator", [Operator.EQ, Operator.IN])
    async def test_domain_content_filter_round_trip(
        self, repository_instance, content, operator
    ):
        created = await repository_instance.create_or_update(
            FileStorageBuilder(
                filename="binary", content=content, key="binary", owner_id=None
            )
        )
        other = await repository_instance.create_or_update(
            FileStorageBuilder(
                filename="other", content=b"other", key="other", owner_id=None
            )
        )
        value = [content] if operator is Operator.IN else content
        query = QuerySpec(
            where=FieldFilter(FileStorage, "content", operator, value)
        )
        assert await repository_instance.get_one(query) == created
        page = await repository_instance.list(page=1, size=1, query=query)
        assert page.items == [created]
        assert page.total == 1
        assert await repository_instance.list_all(query) == [created]
        assert await repository_instance.delete_one(query) == created
        assert await repository_instance.get_one(query) is None
        assert await repository_instance.get_by_id(other.id) == other

    async def test_content_ordering_uses_decoded_bytes(
        self, repository_instance
    ):
        for index, content in enumerate([b"\xff", b"\x00", b"a"]):
            await repository_instance.create_or_update(
                FileStorageBuilder(
                    filename=f"binary-{index}",
                    content=content,
                    key=f"binary-{index}",
                    owner_id=None,
                )
            )
        files = await repository_instance.get_many(
            QuerySpec(order_by=(OrderBy(FileStorage, "content"),))
        )
        assert [file.content for file in files] == [b"\x00", b"a", b"\xff"]

    async def test_filename_prefix_is_case_insensitive(
        self, repository_instance
    ):
        created = await repository_instance.create_or_update(
            FileStorageBuilder(
                filename="MaAs-file", content=b"data", key="key", owner_id=None
            )
        )
        await repository_instance.create_or_update(
            FileStorageBuilder(
                filename="other", content=b"data", key="other", owner_id=None
            )
        )
        assert await repository_instance.get_many(
            QuerySpec(where=FileStorageFilters.with_filename_prefix("maas-"))
        ) == [created]

    async def test_key_filter_selects_matching_file(self, repository_instance):
        first = await repository_instance.create_or_update(
            FileStorageBuilder(
                filename="first", content=b"first", key="first", owner_id=None
            )
        )
        await repository_instance.create_or_update(
            FileStorageBuilder(
                filename="second",
                content=b"second",
                key="second",
                owner_id=None,
            )
        )
        assert (
            await repository_instance.get_one(
                QuerySpec(where=FileStorageFilters.with_key("first"))
            )
            == first
        )
