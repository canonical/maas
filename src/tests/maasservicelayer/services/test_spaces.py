# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.spaces import (
    SpaceResourceBuilder,
    SpacesRepository,
)
from maasservicelayer.db.repositories.vlans import (
    VlanResourceBuilder,
    VlansClauseFactory,
)
from maasservicelayer.exceptions.catalog import PreconditionFailedException
from maasservicelayer.exceptions.constants import (
    ETAG_PRECONDITION_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.spaces import Space
from maasservicelayer.services.spaces import SpacesService
from maasservicelayer.services.vlans import VlansService
from maasservicelayer.utils.date import utcnow

TEST_SPACE = Space(
    id=1,
    name="test_space_name",
    description="test_space_description",
    created=utcnow(),
    updated=utcnow(),
)


@pytest.mark.asyncio
class TestSpacesService:
    async def test_list(self) -> None:
        vlans_service_mock = Mock(VlansService)
        spaces_repository_mock = Mock(SpacesRepository)
        spaces_repository_mock.list.return_value = ListResult[Space](
            items=[], next_token=None
        )
        spaces_service = SpacesService(
            context=Context(),
            vlans_service=vlans_service_mock,
            spaces_repository=spaces_repository_mock,
        )
        spaces_list = await spaces_service.list(token=None, size=1)
        spaces_repository_mock.list.assert_called_once_with(token=None, size=1)
        assert spaces_list.next_token is None
        assert spaces_list.items == []

    async def test_get_by_id(self) -> None:
        now = utcnow()
        expected_space = Space(
            id=0, name="test", description="descr", created=now, updated=now
        )
        vlans_service_mock = Mock(VlansService)
        spaces_repository_mock = Mock(SpacesRepository)
        spaces_repository_mock.get_by_id.return_value = expected_space
        spaces_service = SpacesService(
            context=Context(),
            vlans_service=vlans_service_mock,
            spaces_repository=spaces_repository_mock,
        )
        space = await spaces_service.get_by_id(id=1)
        spaces_repository_mock.get_by_id.assert_called_once_with(id=1)
        assert expected_space == space

    async def test_create(self) -> None:
        now = utcnow()
        created_space = Space(
            id=1,
            name="space",
            description="description",
            created=now,
            updated=now,
        )

        resource = (
            SpaceResourceBuilder()
            .with_name(created_space.name)
            .with_description(created_space.description)
            .with_created(created_space.created)
            .with_updated(created_space.updated)
            .build()
        )

        vlans_service_mock = Mock(VlansService)
        spaces_repository_mock = Mock(SpacesRepository)
        spaces_repository_mock.create.return_value = created_space
        spaces_service = SpacesService(
            context=Context(),
            vlans_service=vlans_service_mock,
            spaces_repository=spaces_repository_mock,
        )

        await spaces_service.create(resource=resource)

        spaces_repository_mock.create.assert_called_once_with(
            resource=resource
        )

    async def test_delete_by_id(
        self,
        mocker: MockerFixture,
    ) -> None:
        vlans_service_mock = Mock(VlansService)
        spaces_repository_mock = Mock(SpacesRepository)
        spaces_repository_mock.delete_by_id.return_value = None
        spaces_repository_mock.delete.return_value = None
        spaces_service = SpacesService(
            context=Context(),
            vlans_service=vlans_service_mock,
            spaces_repository=spaces_repository_mock,
        )

        mock_datetime = mocker.patch("maasservicelayer.utils.date.datetime")
        mock_datetime.now.return_value = TEST_SPACE.updated

        query = QuerySpec(
            where=VlansClauseFactory.with_space_id(TEST_SPACE.id)
        )
        resource = (
            VlanResourceBuilder()
            .with_space_id(None)
            .with_updated(TEST_SPACE.updated)
            .build()
        )

        await spaces_service.delete_by_id(id=TEST_SPACE.id)

        spaces_repository_mock.delete_by_id.assert_called_once_with(
            id=TEST_SPACE.id
        )
        spaces_repository_mock.get_by_id.assert_called_once_with(
            id=TEST_SPACE.id
        )
        vlans_service_mock.update.assert_called_once_with(
            query=query, resource=resource
        )

    async def test_delete_by_id_etag(
        self,
        mocker: MockerFixture,
    ) -> None:
        vlans_service_mock = Mock(VlansService)
        spaces_repository_mock = Mock(SpacesRepository)
        spaces_repository_mock.delete_by_id.return_value = None
        spaces_repository_mock.delete.return_value = None
        spaces_repository_mock.get_by_id.side_effect = [TEST_SPACE, None]
        spaces_service = SpacesService(
            context=Context(),
            vlans_service=vlans_service_mock,
            spaces_repository=spaces_repository_mock,
        )

        mocker.patch(
            "maasservicelayer.models.spaces.Space.etag",
            return_value="correct-etag",
        )
        mock_datetime = mocker.patch("maasservicelayer.utils.date.datetime")
        mock_datetime.now.return_value = TEST_SPACE.updated

        query = QuerySpec(
            where=VlansClauseFactory.with_space_id(TEST_SPACE.id)
        )
        resource = (
            VlanResourceBuilder()
            .with_space_id(None)
            .with_updated(TEST_SPACE.updated)
            .build()
        )

        await spaces_service.delete_by_id(
            id=TEST_SPACE.id, etag_if_match="correct-etag"
        )

        spaces_repository_mock.delete_by_id.assert_called_once_with(
            id=TEST_SPACE.id
        )
        vlans_service_mock.update.assert_called_once_with(
            query=query, resource=resource
        )

        assert (await spaces_service.get_by_id(TEST_SPACE.id)) is None

    async def test_delete_by_id_etag_not_match(
        self,
        mocker: MockerFixture,
    ) -> None:
        vlans_service_mock = Mock(VlansService)
        spaces_repository_mock = Mock(SpacesRepository)
        spaces_repository_mock.get_by_id.return_value = TEST_SPACE
        spaces_service = SpacesService(
            context=Context(),
            vlans_service=vlans_service_mock,
            spaces_repository=spaces_repository_mock,
        )

        mocker.patch(
            "maasservicelayer.models.spaces.Space.etag",
            return_value="correct-etag",
        )

        with pytest.raises(PreconditionFailedException) as excinfo:
            await spaces_service.delete_by_id(TEST_SPACE.id, "wrong-etag")
            assert (
                excinfo.value.details[0].type
                == ETAG_PRECONDITION_VIOLATION_TYPE
            )
            vlans_service_mock.update.assert_not_called()
