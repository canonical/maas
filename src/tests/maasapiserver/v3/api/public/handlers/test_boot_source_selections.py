# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from httpx import AsyncClient
import pytest

from maasapiserver.v3.api.public.models.responses.boot_images_common import (
    ImageListResponse,
    ImageStatisticListResponse,
    ImageStatisticResponse,
    ImageStatusListResponse,
    ImageStatusResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.boot_resources import ImageStatus, ImageUpdateStatus
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionStatusClauseFactory,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.bootsourceselections import (
    BootSourceSelection,
    BootSourceSelectionStatistic,
    BootSourceSelectionStatus,
)
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.bootsourceselections import (
    BootSourceSelectionsService,
    BootSourceSelectionStatusService,
)
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_BOOTSOURCESELECTION = BootSourceSelection(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    os="ubuntu",
    release="noble",
    arch="amd64",
    boot_source_id=12,
    legacyselection_id=1,
)


class TestBootSourceSelectionsApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/selections"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=self.BASE_PATH),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.list.return_value = ListResult[
            BootSourceSelection
        ](items=[TEST_BOOTSOURCESELECTION], total=1)

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?page=1&size=1"
        )
        assert response.status_code == 200
        boot_source_selections_response = ImageListResponse(**response.json())
        assert len(boot_source_selections_response.items) == 1
        assert boot_source_selections_response.total == 1
        assert boot_source_selections_response.next is None

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        selection_2 = TEST_BOOTSOURCESELECTION.copy()
        selection_2.id = 2

        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.list.return_value = ListResult[
            BootSourceSelection
        ](items=[TEST_BOOTSOURCESELECTION, selection_2], total=2)

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?page=1&size=1"
        )
        assert response.status_code == 200
        boot_source_selections_response = ImageListResponse(**response.json())
        assert len(boot_source_selections_response.items) == 2
        assert boot_source_selections_response.total == 2
        assert (
            boot_source_selections_response.next
            == f"{self.BASE_PATH}?page=2&size=1"
        )

        selection = boot_source_selections_response.items[0]
        assert selection.hal_links.self.href == (
            f"{self.BASE_PATH}/{TEST_BOOTSOURCESELECTION.id}"
        )

    async def test_list_empty(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.list.return_value = ListResult[
            BootSourceSelection
        ](items=[], total=0)

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?size=10"
        )
        assert response.status_code == 200
        boot_source_selections_response = ImageListResponse(**response.json())
        assert len(boot_source_selections_response.items) == 0
        assert boot_source_selections_response.total == 0
        assert boot_source_selections_response.next is None


class TestBootSourceSelectionStatusesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/selection_statuses"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=self.BASE_PATH),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

    async def test_get_selection_status_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_source_selection_status = Mock(
            BootSourceSelectionStatusService
        )
        services_mock.boot_source_selection_status.get_by_id.return_value = (
            BootSourceSelectionStatus(
                id=TEST_BOOTSOURCESELECTION.id,
                status=ImageStatus.DOWNLOADING,
                update_status=ImageUpdateStatus.NO_UPDATES_AVAILABLE,
                sync_percentage=50.0,
                selected=True,
            )
        )

        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/1")
        assert response.status_code == 200
        selection_status_response = ImageStatusResponse(**response.json())
        assert selection_status_response.id == TEST_BOOTSOURCESELECTION.id
        assert selection_status_response.status == ImageStatus.DOWNLOADING
        assert (
            selection_status_response.update_status
            == ImageUpdateStatus.NO_UPDATES_AVAILABLE
        )
        assert selection_status_response.sync_percentage == 50.0

    async def test_get_selection_status_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_source_selection_status = Mock(
            BootSourceSelectionStatusService
        )
        services_mock.boot_source_selection_status.get_by_id.return_value = (
            None
        )

        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/1")
        assert response.status_code == 404

    async def test_list_selection_status_one_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_source_selection_status = Mock(
            BootSourceSelectionStatusService
        )
        services_mock.boot_source_selection_status.list.return_value = (
            ListResult[BootSourceSelectionStatus](
                items=[
                    BootSourceSelectionStatus(
                        id=TEST_BOOTSOURCESELECTION.id,
                        status=ImageStatus.DOWNLOADING,
                        update_status=ImageUpdateStatus.NO_UPDATES_AVAILABLE,
                        sync_percentage=50.0,
                        selected=True,
                    )
                ],
                total=1,
            )
        )

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?page=1&size=1&id={TEST_BOOTSOURCESELECTION.id}"
        )
        assert response.status_code == 200
        list_response = ImageStatusListResponse(**response.json())

        assert len(list_response.items) == 1
        assert list_response.items[0].status == ImageStatus.DOWNLOADING
        assert (
            list_response.items[0].update_status
            == ImageUpdateStatus.NO_UPDATES_AVAILABLE
        )

    async def test_list_selection_status_another_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_source_selection_status = Mock(
            BootSourceSelectionStatusService
        )
        services_mock.boot_source_selection_status.list.return_value = (
            ListResult[BootSourceSelectionStatus](
                items=[
                    BootSourceSelectionStatus(
                        id=TEST_BOOTSOURCESELECTION.id,
                        status=ImageStatus.DOWNLOADING,
                        update_status=ImageUpdateStatus.NO_UPDATES_AVAILABLE,
                        sync_percentage=50.0,
                        selected=True,
                    )
                ],
                total=2,
            )
        )

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?page=1&size=1&id={TEST_BOOTSOURCESELECTION.id}&id=2"
        )
        assert response.status_code == 200
        list_response = ImageStatusListResponse(**response.json())

        assert len(list_response.items) == 1
        assert list_response.next is not None
        assert list_response.next == (
            f"{self.BASE_PATH}?page=2&size=1&id={TEST_BOOTSOURCESELECTION.id}&id=2"
        )

    async def test_list_selection_status_empty(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_source_selection_status = Mock(
            BootSourceSelectionStatusService
        )
        services_mock.boot_source_selection_status.list.return_value = (
            ListResult[BootSourceSelectionStatus](
                items=[],
                total=0,
            )
        )

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?page=1&size=1"
        )
        assert response.status_code == 200
        list_response = ImageStatusListResponse(**response.json())

        assert len(list_response.items) == 0
        assert list_response.next is None

    async def test_list_selection_status_filter_by_ids(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_source_selection_status = Mock(
            BootSourceSelectionStatusService
        )
        services_mock.boot_source_selection_status.list.return_value = (
            ListResult[BootSourceSelectionStatus](
                items=[
                    BootSourceSelectionStatus(
                        id=TEST_BOOTSOURCESELECTION.id,
                        status=ImageStatus.DOWNLOADING,
                        update_status=ImageUpdateStatus.NO_UPDATES_AVAILABLE,
                        sync_percentage=50.0,
                        selected=True,
                    )
                ],
                total=1,
            )
        )

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?page=1&size=1&id=1&id=2"
        )
        assert response.status_code == 200

        services_mock.boot_source_selection_status.list.assert_called_once_with(
            query=QuerySpec(
                where=BootSourceSelectionStatusClauseFactory.with_ids([1, 2])
            ),
            page=1,
            size=1,
        )

    async def test_list_selection_status_only_selected(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_source_selection_status = Mock(
            BootSourceSelectionStatusService
        )
        services_mock.boot_source_selection_status.list.return_value = (
            ListResult[BootSourceSelectionStatus](
                items=[
                    BootSourceSelectionStatus(
                        id=TEST_BOOTSOURCESELECTION.id,
                        status=ImageStatus.DOWNLOADING,
                        update_status=ImageUpdateStatus.NO_UPDATES_AVAILABLE,
                        sync_percentage=50.0,
                        selected=True,
                    )
                ],
                total=0,
            )
        )

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?page=1&size=1&selected=true"
        )
        assert response.status_code == 200

        services_mock.boot_source_selection_status.list.assert_called_once_with(
            query=QuerySpec(
                where=BootSourceSelectionStatusClauseFactory.with_selected(
                    True
                )
            ),
            page=1,
            size=1,
        )

    async def test_list_selection_status_filter_selected_only_and_id(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_source_selection_status = Mock(
            BootSourceSelectionStatusService
        )
        services_mock.boot_source_selection_status.list.return_value = (
            ListResult[BootSourceSelectionStatus](
                items=[
                    BootSourceSelectionStatus(
                        id=TEST_BOOTSOURCESELECTION.id,
                        status=ImageStatus.DOWNLOADING,
                        update_status=ImageUpdateStatus.NO_UPDATES_AVAILABLE,
                        sync_percentage=50.0,
                        selected=True,
                    )
                ],
                total=0,
            )
        )

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?page=1&size=1&selected=true&id=1"
        )
        assert response.status_code == 200

        services_mock.boot_source_selection_status.list.assert_called_once_with(
            query=QuerySpec(
                where=BootSourceSelectionStatusClauseFactory.and_clauses(
                    [
                        BootSourceSelectionStatusClauseFactory.with_selected(
                            True
                        ),
                        BootSourceSelectionStatusClauseFactory.with_ids([1]),
                    ]
                )
            ),
            page=1,
            size=1,
        )


class TestBootSourceSelectionStatisticsApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/selection_statistics"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=self.BASE_PATH),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

    async def test_get_selection_statistic_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.get_selection_statistic_by_id.return_value = BootSourceSelectionStatistic(
            id=TEST_BOOTSOURCESELECTION.id,
            last_updated=utcnow(),
            last_deployed=None,
            size=1024,
            node_count=2,
            deploy_to_memory=True,
        )

        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/1")
        assert response.status_code == 200
        selection_statistics_response = ImageStatisticResponse(
            **response.json()
        )
        assert selection_statistics_response.id == TEST_BOOTSOURCESELECTION.id
        assert selection_statistics_response.node_count == 2
        assert selection_statistics_response.deploy_to_memory is True
        assert selection_statistics_response.size == "1.0 kB"

    async def test_get_selection_statistic_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.get_selection_statistic_by_id.return_value = None

        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/1")
        assert response.status_code == 404

    async def test_list_selection_statistics_one_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.list_selections_statistics.return_value = ListResult[
            BootSourceSelectionStatus
        ](
            items=[
                BootSourceSelectionStatistic(
                    id=TEST_BOOTSOURCESELECTION.id,
                    last_updated=utcnow(),
                    last_deployed=None,
                    size=1024,
                    node_count=2,
                    deploy_to_memory=True,
                )
            ],
            total=1,
        )

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?page=1&size=1&id={TEST_BOOTSOURCESELECTION.id}"
        )
        assert response.status_code == 200
        list_response = ImageStatisticListResponse(**response.json())

        assert len(list_response.items) == 1
        assert list_response.total == 1

    async def test_list_selection_statistics_another_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.list_selections_statistics.return_value = ListResult[
            BootSourceSelectionStatus
        ](
            items=[
                BootSourceSelectionStatistic(
                    id=TEST_BOOTSOURCESELECTION.id,
                    last_updated=utcnow(),
                    last_deployed=None,
                    size=1024,
                    node_count=2,
                    deploy_to_memory=True,
                )
            ],
            total=2,
        )

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?page=1&size=1&id={TEST_BOOTSOURCESELECTION.id}&id=2"
        )
        assert response.status_code == 200
        list_response = ImageStatisticListResponse(**response.json())

        assert len(list_response.items) == 1
        assert list_response.next is not None
        assert list_response.next == (
            f"{self.BASE_PATH}?page=2&size=1&id={TEST_BOOTSOURCESELECTION.id}&id=2"
        )
