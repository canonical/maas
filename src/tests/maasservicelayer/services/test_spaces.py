# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.spaces import (
    SpaceResourceBuilder,
    SpacesRepository,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.spaces import Space
from maasservicelayer.services.spaces import SpacesService
from maasservicelayer.utils.date import utcnow


@pytest.mark.asyncio
class TestSpacesService:
    async def test_list(self) -> None:
        spaces_repository_mock = Mock(SpacesRepository)
        spaces_repository_mock.list.return_value = ListResult[Space](
            items=[], next_token=None
        )
        spaces_service = SpacesService(
            context=Context(), spaces_repository=spaces_repository_mock
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
        spaces_repository_mock = Mock(SpacesRepository)
        spaces_repository_mock.get_by_id.return_value = expected_space
        spaces_service = SpacesService(
            context=Context(),
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

        spaces_repository_mock = Mock(SpacesRepository)
        spaces_repository_mock.create.return_value = created_space
        spaces_service = SpacesService(
            context=Context(),
            spaces_repository=spaces_repository_mock,
        )

        await spaces_service.create(resource=resource)

        spaces_repository_mock.create.assert_called_once_with(
            resource=resource
        )
