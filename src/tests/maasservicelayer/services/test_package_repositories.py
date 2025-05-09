# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.events import EventTypeEnum
from maascommon.enums.package_repositories import (
    PACKAGE_REPO_MAIN_ARCHES,
    PACKAGE_REPO_PORTS_ARCHES,
)
from maasservicelayer.builders.package_repositories import (
    PackageRepositoryBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.package_repositories import (
    PackageRepositoriesRepository,
)
from maasservicelayer.exceptions.catalog import BadRequestException
from maasservicelayer.models.fields import PackageRepoUrl
from maasservicelayer.models.package_repositories import PackageRepository
from maasservicelayer.services.events import EventsService
from maasservicelayer.services.package_repositories import (
    PackageRepositoriesService,
)
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests

MAIN_PACKAGE_REPO = PackageRepository(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    name="main_archive",
    url=PackageRepoUrl("http://archive.ubuntu.com/ubuntu"),
    components=set(),
    arches=PACKAGE_REPO_MAIN_ARCHES,
    key="",
    default=True,
    enabled=True,
    disabled_pockets=set(),
    distributions=[],
    disabled_components=set(),
    disable_sources=True,
)

PORTS_PACKAGE_REPO = PackageRepository(
    id=2,
    created=utcnow(),
    updated=utcnow(),
    name="ports_archive",
    url=PackageRepoUrl("http://ports.ubuntu.com/ubuntu-ports"),
    components=set(),
    arches=PACKAGE_REPO_PORTS_ARCHES,
    key="",
    default=True,
    enabled=True,
    disabled_pockets=set(),
    distributions=[],
    disabled_components=set(),
    disable_sources=True,
)

TEST_PACKAGE_REPO = PackageRepository(
    id=3,
    created=utcnow(),
    updated=utcnow(),
    name="test-main",
    key="test-key",
    url=PackageRepoUrl("http://archive.ubuntu.com/ubuntu"),
    distributions=[],
    components=set(),
    arches=set(),
    disabled_pockets=set(),
    disabled_components=set(),
    disable_sources=False,
    default=False,
    enabled=True,
)


@pytest.mark.asyncio
class TestCommonPackageRepositoriesService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> PackageRepositoriesService:
        return PackageRepositoriesService(
            context=Context(),
            repository=Mock(PackageRepositoriesRepository),
            events_service=Mock(EventsService),
        )

    @pytest.fixture
    def test_instance(self) -> PackageRepository:
        return TEST_PACKAGE_REPO

    async def test_delete_many(self, service_instance, test_instance):
        with pytest.raises(NotImplementedError):
            await super().test_delete_many(service_instance, test_instance)

    async def test_update_many(self, service_instance, test_instance):
        with pytest.raises(NotImplementedError):
            await super().test_delete_many(service_instance, test_instance)


class TestPackageRepositoriesService:
    @pytest.fixture
    def repository_mock(self):
        return Mock(PackageRepositoriesRepository)

    @pytest.fixture
    def events_service_mock(self):
        return Mock(EventsService)

    @pytest.fixture
    def service(
        self, repository_mock, events_service_mock
    ) -> PackageRepositoriesService:
        return PackageRepositoriesService(
            context=Context(),
            repository=repository_mock,
            events_service=events_service_mock,
        )

    async def test_get_main_archive(
        self, repository_mock: Mock, service: PackageRepositoriesService
    ) -> None:
        repository_mock.get_main_archive.return_value = MAIN_PACKAGE_REPO
        await service.get_main_archive()
        repository_mock.get_main_archive.assert_called_once()

    async def test_get_ports_archive(
        self, repository_mock: Mock, service: PackageRepositoriesService
    ) -> None:
        repository_mock.get_ports_archive.return_value = PORTS_PACKAGE_REPO
        await service.get_ports_archive()
        repository_mock.get_ports_archive.assert_called_once()

    async def test_delete_default_archive(
        self, repository_mock: Mock, service: PackageRepositoriesService
    ) -> None:
        repository_mock.get_main_archive.return_value = MAIN_PACKAGE_REPO
        repository_mock.get_ports_archive.return_value = PORTS_PACKAGE_REPO
        repository_mock.get_by_id.side_effect = [
            MAIN_PACKAGE_REPO,
            PORTS_PACKAGE_REPO,
        ]
        with pytest.raises(BadRequestException) as e:
            await service.delete_by_id(MAIN_PACKAGE_REPO.id)
        assert e.value.details is not None
        assert (
            e.value.details[0].message
            == "Default package repositories cannot be deleted."
        )

        with pytest.raises(BadRequestException) as e:
            await service.delete_by_id(PORTS_PACKAGE_REPO.id)
        assert e.value.details is not None
        assert (
            e.value.details[0].message
            == "Default package repositories cannot be deleted."
        )

    async def test_update_arches_default_archive(
        self, repository_mock: Mock, service: PackageRepositoriesService
    ) -> None:
        repository_mock.get_main_archive.return_value = MAIN_PACKAGE_REPO
        repository_mock.get_ports_archive.return_value = PORTS_PACKAGE_REPO
        builder = PackageRepositoryBuilder(arches=set())
        with pytest.raises(BadRequestException) as e:
            await service.update_by_id(MAIN_PACKAGE_REPO.id, builder)
        assert e.value.details is not None
        assert (
            e.value.details[0].message
            == "Architectures for default package repositories cannot be updated."
        )

        with pytest.raises(BadRequestException) as e:
            await service.update_by_id(PORTS_PACKAGE_REPO.id, builder)

        assert e.value.details is not None
        assert (
            e.value.details[0].message
            == "Architectures for default package repositories cannot be updated."
        )

    async def test_create_creates_event(
        self,
        repository_mock: Mock,
        events_service_mock: Mock,
        service: PackageRepositoriesService,
    ) -> None:
        repository_mock.create.return_value = TEST_PACKAGE_REPO
        events_service_mock.record_event.return_value = None
        await service.create(builder=Mock(PackageRepository))
        events_service_mock.record_event.assert_called_once_with(
            event_type=EventTypeEnum.SETTINGS,
            event_description=f"Created package repository {TEST_PACKAGE_REPO.name}",
        )

    async def test_update_creates_event(
        self,
        repository_mock: Mock,
        events_service_mock: Mock,
        service: PackageRepositoriesService,
    ) -> None:
        repository_mock.get_by_id.return_value = TEST_PACKAGE_REPO
        repository_mock.update_by_id.return_value = TEST_PACKAGE_REPO
        events_service_mock.record_event.return_value = None
        builder = PackageRepositoryBuilder(name="foo")
        await service.update_by_id(id=1, builder=builder)
        events_service_mock.record_event.assert_called_once_with(
            event_type=EventTypeEnum.SETTINGS,
            event_description=f"Updated package repository {TEST_PACKAGE_REPO.name}",
        )

    async def test_delete_creates_event(
        self,
        repository_mock: Mock,
        events_service_mock: Mock,
        service: PackageRepositoriesService,
    ) -> None:
        repository_mock.delete_by_id.return_value = TEST_PACKAGE_REPO
        events_service_mock.record_event.return_value = None
        await service.delete_by_id(id=1)
        events_service_mock.record_event.assert_called_once_with(
            event_type=EventTypeEnum.SETTINGS,
            event_description=f"Deleted package repository {TEST_PACKAGE_REPO.name}",
        )
