# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import call, Mock

from fastapi.encoders import jsonable_encoder
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
from maascommon.workflows.bootresource import (
    SYNC_SELECTION_WORKFLOW_NAME,
    SyncSelectionParam,
)
from maasservicelayer.builders.bootsourceselections import (
    BootSourceSelectionBuilder,
)
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionClauseFactory,
    BootSourceSelectionStatusClauseFactory,
)
from maasservicelayer.exceptions.catalog import AlreadyExistsException
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
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.temporal import TemporalService
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
        return [
            Endpoint(method="POST", path=self.BASE_PATH),
            Endpoint(method="DELETE", path=self.BASE_PATH),
        ]

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

    async def test_bulk_create_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.create_many.return_value = [
            TEST_BOOTSOURCESELECTION
        ]
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get.return_value = False

        bulk_create_request = [
            {
                "os": TEST_BOOTSOURCESELECTION.os,
                "release": TEST_BOOTSOURCESELECTION.release,
                "arch": TEST_BOOTSOURCESELECTION.arch,
                "boot_source_id": TEST_BOOTSOURCESELECTION.boot_source_id,
            }
        ]

        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(bulk_create_request)
        )
        boot_source_selections_response = ImageListResponse(**response.json())
        assert len(boot_source_selections_response.items) == 1
        assert boot_source_selections_response.total == 1

        services_mock.boot_source_selections.create_many.assert_awaited_once_with(
            [
                BootSourceSelectionBuilder(
                    os=TEST_BOOTSOURCESELECTION.os,
                    release=TEST_BOOTSOURCESELECTION.release,
                    arch=TEST_BOOTSOURCESELECTION.arch,
                    boot_source_id=TEST_BOOTSOURCESELECTION.boot_source_id,
                )
            ]
        )

    async def test_bulk_create_409(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.create_many.side_effect = (
            AlreadyExistsException()
        )

        bulk_create_request = [
            {
                "os": TEST_BOOTSOURCESELECTION.os,
                "release": TEST_BOOTSOURCESELECTION.release,
                "arch": TEST_BOOTSOURCESELECTION.arch,
                "boot_source_id": TEST_BOOTSOURCESELECTION.boot_source_id,
            }
        ]

        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(bulk_create_request)
        )
        assert response.status_code == 409

    @pytest.mark.parametrize(
        "bulk_create_request",
        [
            [],  # empty list
            [  # non-unique values
                {
                    "os": "os",
                    "release": "release",
                    "arch": "arch",
                    "boot_source_id": "id",
                },
                {
                    "os": "os",
                    "release": "release",
                    "arch": "arch",
                    "boot_source_id": "id",
                },
            ],
        ],
    )
    async def test_bulk_create_422(
        self,
        bulk_create_request: list,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(bulk_create_request)
        )
        assert response.status_code == 422
        services_mock.boot_source_selections.create_many.assert_not_awaited()

    @pytest.mark.parametrize("auto_sync_enabled", [True, False])
    async def test_bulk_create_starts_image_sync_if_auto_sync_enabled(
        self,
        auto_sync_enabled: bool,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        s1 = TEST_BOOTSOURCESELECTION.copy()
        s2 = TEST_BOOTSOURCESELECTION.copy()
        s2.id = 2
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.create_many.return_value = [
            s1,
            s2,
        ]
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get.return_value = auto_sync_enabled
        services_mock.temporal = Mock(TemporalService)
        services_mock.temporal.register_workflow_call.return_value = None

        bulk_create_request = [
            {
                "os": TEST_BOOTSOURCESELECTION.os,
                "release": TEST_BOOTSOURCESELECTION.release,
                "arch": TEST_BOOTSOURCESELECTION.arch,
                "boot_source_id": TEST_BOOTSOURCESELECTION.boot_source_id,
            }
        ]
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(bulk_create_request)
        )
        assert response.status_code == 200
        if auto_sync_enabled:
            services_mock.temporal.register_workflow_call.assert_has_calls(
                [
                    call(
                        workflow_name=SYNC_SELECTION_WORKFLOW_NAME,
                        workflow_id=f"sync-selection:{s1.id}",
                        parameter=SyncSelectionParam(selection_id=s1.id),
                        wait=False,
                    ),
                    call(
                        workflow_name=SYNC_SELECTION_WORKFLOW_NAME,
                        workflow_id=f"sync-selection:{s2.id}",
                        parameter=SyncSelectionParam(selection_id=s2.id),
                        wait=False,
                    ),
                ]
            )
        else:
            services_mock.temporal.register_workflow_call.assert_not_called()

    async def test_bulk_delete(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.delete_many.return_value = None
        # httpx.delete doesn't support json
        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}?id=1&id=2"
        )
        assert response.status_code == 204
        services_mock.boot_source_selections.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootSourceSelectionClauseFactory.with_ids([1, 2])
            )
        )


class TestBootSourceSelectionStatusesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/selections/statuses"

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
    BASE_PATH = f"{V3_API_PREFIX}/selections/statistics"

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
